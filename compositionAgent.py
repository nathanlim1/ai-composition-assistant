from __future__ import annotations
import os
from langgraph.graph.message import add_messages
from typing import Dict, List
from typing_extensions import Annotated, TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain_core.tools import tool
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import InjectedState, create_react_agent
from KB import KnowledgeBase
from MidiHandler import MidiHandler

load_dotenv()

# NOTE SPECS FOR LLM
class NoteInput(BaseModel):
    """Schema for a single music21 note."""

    pitch:    int   = Field(..., ge=0, le=127, description="MIDI pitch 0‑127 (Middle C = 60)")
    duration: float = Field(..., gt=0,          description="Note length in quarterLength (1.0 = quarter)")
    offset:   float = Field(..., ge=0,          description="absolute note start time in quarterLength (0.0 = piece start).")


# TOOL DEFINITIONS FOR LLM FUNCTION CALLING

@tool
def add_notes(
    notes: Annotated[
        List[NoteInput],
        Field(
            description=(
                "Ordered list of NoteInput objects to append. Each entry fully "
                "defines one note: **pitch** (0‑127), **duration** (quarterLength), "
                "and **offset** (absolute start time in quarterLength)."
            )
        ),
    ],
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Append one or more notes to the piece."""

    state["midi_handler"].add_notes([(n.pitch, n.duration, n.offset) for n in notes])
    return f"Added {len(notes)} notes."


@tool
def remove_notes(
    start_offset: Annotated[
        float,
        Field(gt=0, description="Inclusive lower bound of deletion window (in quarterLength)."),
    ],
    end_offset: Annotated[
        float,
        Field(gt=0, description="Exclusive upper bound of deletion window (in quarterLength)."),
    ],
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Erase every note with **offset** ∈ [start_offset, end_offset)."""

    return state["midi_handler"].remove_notes(start_offset, end_offset)


@tool
def replace_passage(
    start_offset: Annotated[
        float,
        Field(ge=0, description="Start of passage to replace (in quarterLength)."),
    ],
    end_offset: Annotated[
        float,
        Field(gt=0, description="End of passage to replace (in quarterLength, exclusive)."),
    ],
    notes: Annotated[
        List[NoteInput],
        Field(description="New material to insert. Offsets are **relative** to start_offset."),
    ],
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Atomically wipe a region and insert new notes."""

    return state["midi_handler"].replace_passage(start_offset, end_offset, [(n.pitch, n.duration) for n in notes])


MIDI_TOOLS = [add_notes, remove_notes, replace_passage]

# SETUP SHARED STATE SCHEMA
class GraphState(TypedDict):
    midi_path:       str
    user_prompt:     str
    target_duration: float

    kb:           KnowledgeBase | None
    midi_handler: MidiHandler   | None

    messages:     Annotated[list, add_messages]
    output_midi:  str

    remaining_steps: int  # max tool-call hops


# SETUP LLM INSTANCES
_MODEL = os.getenv("OPENAI_MODEL", "o4-mini")
composer_llm  = ChatOpenAI(model=_MODEL, temperature=1)
reviewer_llm  = ChatOpenAI(model=_MODEL, temperature=1)
handler_llm   = ChatOpenAI(model=_MODEL, temperature=1)

handler_agent = create_react_agent(model=handler_llm, tools=MIDI_TOOLS, state_schema=GraphState)

# SETUP GRAPH NODES

def dynamic_rule_builder(state: GraphState) -> Dict[str, object]:
    """Initialise MidiHandler + KB and emit the Handler system prompt."""

    mh = MidiHandler(state["midi_path"])
    kb = KnowledgeBase()
    kb.build_algorithmic_dynamic(mh)

    handler_system_msg = SystemMessage(
        f"""
        You are the **Handler** agent.

        Use the provided tools to carry out exactly the instructions that come
        from the Composer or Reviewer.

        **Numeric semantics (do not change):**
        • **offset**   — when the note plays relative to the start of the piece in *quarter note lengths* (0.0 = piece start).
        • **pitch**    — MIDI integer 0‑127 (Middle C = 60).
        • **duration** — duration of the note in quarter note lengths (4.0 = whole, 2.0 = half, 1.0 = quarter, 0.25 = sixteenth …).
        
        ALWAYS ADD NEW NOTES AT AN OFFSET EQUAL TO THE OFFSET OF THE LAST NOTE + THE DURATION OF THE LAST NOTE

        After every tool call sequence requested by the message, reply with a
        short natural‑language confirmation and **no additional tool calls**.
        """
    )

    return {"kb": kb, "midi_handler": mh, "messages": [handler_system_msg]}


def composer_planner(state: GraphState) -> Dict[str, object]:
    """Ask the Composer to propose ONE concrete musical edit and
    wipe message history before handing off to the Handler."""

    mh, kb = state["midi_handler"], state["kb"]
    # Preserve the Handler system prompt that was inserted in dynamic_rule_builder
    handler_sys_msg = state["messages"][0] if state["messages"] else None

    prompt = (
        """
        You are the **Composer** agent. Your goal is to continue composing a piece.

        Unless otherwise required, your additions should be measure by measure.
        
        For each measure, you u
        
        Be very specific about pitch and duration of the notes.

        **Numeric semantics (fixed):** pitch = MIDI 0-127 (Middle C = 60), duration =
        quarterLength, offset = absolute quarterLength.  **Do not specify
        offsets yourself**; the Handler will place the material.

        Keep your instruction ≤ 2 sentences, no tool syntax.

        Your edit will be sent to another AI agent who will use those instructions
        to add to the MIDI file.

        KNOWLEDGE BASE:
        {kb}
        """
    ).format(kb=kb.summary_markdown())

    suggestion: AIMessage = composer_llm.invoke(prompt)

    last20 = mh.get_notes()[-20:]
    content = f"LAST_20_NOTES:\n{last20}\n\n{suggestion.content}"

    # 1) wipe everything, 2) re-add system prompt, 3) deliver new instruction
    new_msgs = [
        RemoveMessage(id=REMOVE_ALL_MESSAGES),  # ← wipe
        handler_sys_msg,  # restore system prompt
        HumanMessage(content=content),  # composer’s fresh instruction
    ]

    return {"messages": new_msgs}


def reviewer_planner(state: GraphState) -> Dict[str, object]:
    """Have the Reviewer check for rule violations and propose one fix, if any."""

    mh, kb = state["midi_handler"], state["kb"]

    prompt = (
        """
        You are the **Reviewer** agent.

        Inspect the entire piece against the Knowledge Base.  If you find a
        violation, describe **ONE** short fix. Otherwise reply with an empty
        string.

        Numeric semantics are fixed (pitch = MIDI, duration = quarterLength,
        offset = quarterLength).

        KNOWLEDGE BASE:
        {kb}
        """
    ).format(kb=kb.summary_markdown())

    critique: AIMessage = reviewer_llm.invoke(prompt)

    last20 = mh.get_notes()[-20:]
    content = f"LAST_20_NOTES:\n{last20}\n\n{critique.content}"

    return {"messages": [HumanMessage(content=content)]}


# ROUTING FUNCTIONS

def after_handler(state: GraphState) -> str:
    if state["midi_handler"].get_duration() < state["target_duration"]:
        return "composer_planner"
    return "reviewer_planner"


def after_reviewer(state: GraphState) -> str:
    return END  # TODO: switch back to reviewer to loop against KB



# BUILD THE GRAPH

graph = StateGraph(GraphState)

graph.add_node("dynamic_rule_builder", dynamic_rule_builder)
graph.add_node("composer_planner",     composer_planner)
graph.add_node("handler_agent",        handler_agent)
graph.add_node("reviewer_planner",     reviewer_planner)

graph.add_edge(START,                   "dynamic_rule_builder")
graph.add_edge("dynamic_rule_builder",  "composer_planner")
graph.add_edge("composer_planner",      "handler_agent")

graph.add_conditional_edges(
    "handler_agent",
    after_handler,
    {"composer_planner": "composer_planner", "reviewer_planner": "reviewer_planner"},
)

graph.add_conditional_edges(
    "reviewer_planner",
    after_reviewer,
    {"handler_agent": "handler_agent", END: END},
)

compiled_graph = graph.compile()

# SAMPLE RUN
if __name__ == "__main__":
    MIDI_IN         = "test_input/simple1channel.mid"
    TARGET_SECONDS  = 25.0
    MIDI_OUT        = "extended_output4.mid"

    init_state: GraphState = {
        "midi_path": MIDI_IN,
        "user_prompt": "Extend the excerpt in a similar style.",
        "target_duration": TARGET_SECONDS,
        "kb": None,
        "midi_handler": None,
        "messages": [],
        "output_midi": MIDI_OUT,
        "remaining_steps": 30,
    }

    final = compiled_graph.invoke(init_state)
    final["midi_handler"].save_midi(final["output_midi"])
    print(f"Saved composed MIDI → {final['output_midi']}")
