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
from langgraph.errors import GraphRecursionError
from KB import KnowledgeBase
from MidiHandler import MidiHandler

load_dotenv()

# NOTE SPECS FOR LLM
class NoteInput(BaseModel):
    """Schema for a single music21 note."""
    pitch: str = Field(..., description="Pitch as string (e.g., 'Bb4', 'C#5')")
    duration: float = Field(..., gt=0, description="Note length in quarterLength (1.0 = quarter)")
    offset: float = Field(..., ge=0, description="absolute note start time in quarterLength (0.0 = piece start).")


# TOOL DEFINITIONS FOR LLM FUNCTION CALLING

@tool
def add_notes(
    notes: Annotated[
        List[NoteInput],
        Field(
            description=(
                "Ordered list of NoteInput objects to append. Each entry fully "
                "defines one note: **pitch** (as string, e.g., 'Bb4'), **duration** (quarterLength), "
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

    return state["midi_handler"].replace_passage(start_offset, end_offset, [(n.pitch, n.duration, n.offset) for n in notes])


MIDI_TOOLS = [add_notes, remove_notes, replace_passage]

# SETUP SHARED STATE SCHEMA
class GraphState(TypedDict):
    midi_path:       str
    user_prompt:     str
    add_measures:    int
    target_measures: int

    kb:           KnowledgeBase | None
    midi_handler: MidiHandler   | None

    messages:     Annotated[list, add_messages]
    output_midi:  str

    remaining_steps: int  # max tool-call hops
    reviewer_satisfied: bool  # tracks if reviewer is satisfied with the composition
    review_iterations: int  # count of review iterations to prevent infinite loops
    max_review_iterations: int  # maximum allowed review iterations
    in_review_mode: bool  # explicitly tracks if we're in review mode vs composition mode


# SETUP LLM INSTANCES
_ADV_MODEL = os.getenv("OPENAI_MODEL", "o4-mini")
_BASIC_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

dynamic_rule_builder_llm = ChatOpenAI(model=_ADV_MODEL, temperature=1)
composer_llm  = ChatOpenAI(model=_ADV_MODEL, temperature=1)
reviewer_llm  = ChatOpenAI(model=_ADV_MODEL, temperature=1)
handler_llm   = ChatOpenAI(model=_ADV_MODEL, temperature=1)

handler_agent = create_react_agent(model=handler_llm, tools=MIDI_TOOLS, state_schema=GraphState)

# SETUP GRAPH NODES

def dynamic_rule_builder(state: GraphState) -> Dict[str, object]:
    """Initialise MidiHandler + KB and emit the Handler system prompt."""

    mh = MidiHandler(state["midi_path"])
    kb = KnowledgeBase()
    kb.build_algorithmic_dynamic(mh)

    notes_by_part = mh.get_notes_by_part()
    if(len(notes_by_part) == 2):
        treble_chords = mh.get_chord_progression(notes_by_part[0])
        bass_chords = mh.get_chord_progression(notes_by_part[1])
    else:
        chords = mh.get_chord_progression(mh.get_notes())

    # Get stylistic analysis from LLM
    analysis_prompt = f"""
    Analyze the following MIDI file and provide a list of stylistic rules and patterns:
    - Key: {mh.get_readable_key()}
    - Time Signature: {mh.get_time_signature()}
    - Number of Measures: {mh.get_number_of_measures()}
    - Notes: {mh.get_notes_json()}
    """
    if len(notes_by_part) == 2:
        analysis_prompt += f"""
        - Treble Chord Progression: {mh.get_human_readable_chord_progression(treble_chords)}
        - Bass Chord Progression: {mh.get_human_readable_chord_progression(bass_chords)}
        """
    else:
        analysis_prompt += f"""
        - Chord Progression: {mh.get_human_readable_chord_progression(chords)}
        """
    analysis_prompt += f"""
    - User Prompt: {state["user_prompt"]}
    
    Return a list of specific rules about:
    1. Chord progression patterns, including phrase length and cadences
    2. Note density and spacing in the melody (right hand)
    3. Note density and spacing in the harmony (left hand)
    4. Melodic patterns and intervals
    5. Rhythmic patterns (be very specific about how it should be continued and any variations)
    6. Anything that the user specifically asked for
    7. Any other notable stylistic elements that should be followed

    Be clear enough that a composer could follow the rules to continue the piece in the same style.
    """

    analysis_response = dynamic_rule_builder_llm.invoke(analysis_prompt)
    
    kb.generated_rules = analysis_response.content

    print("Generated Rules: ", kb.generated_rules)

    handler_system_msg = SystemMessage(
        f"""
        You are the **Handler** agent.

        Use the provided tools to carry out exactly the instructions that come
        from the Composer or Reviewer.

        **Numeric semantics (do not change):**
        • **offset**   — when the note plays relative to the start of the piece in *quarter note lengths* (0.0 = piece start).
        • **pitch**    — String representing pitch (e.g., 'Bb4', 'C#5').
        • **duration** — duration of the note in quarter note lengths (4.0 = whole, 2.0 = half, 1.0 = quarter, 0.25 = sixteenth …).

        After every tool call sequence requested by the message, reply with a
        short natural‑language confirmation and **no additional tool calls**.
        """
    )

    return {
        "kb": kb, 
        "midi_handler": mh, 
        "target_measures": state["add_measures"] + mh.get_number_of_measures(),
        "messages": [handler_system_msg]
        }


def composer_planner(state: GraphState) -> Dict[str, object]:
    """Ask the Composer to propose ONE concrete musical edit and
    wipe message history before handing off to the Handler."""

    mh, kb = state["midi_handler"], state["kb"]
    # Preserve the Handler system prompt that was inserted in dynamic_rule_builder
    handler_sys_msg = state["messages"][0] if state["messages"] else None

    # Get the last 8 measures as JSON
    last_measures_json = mh.get_notes_json(measure_nums=-12)

    prompt = (
        f"""
        You are the **Composer** agent. Your goal is to continue composing a piece.

        Unless otherwise required, your additions should be 1 measure at a time. Do not specify any specific measure 
        number. Simply explain what you want to add in.
        
        You should build off the existing piece in the continued style as the previous measures, continuing with similar
        key, rhythm, and harmonic progression.
        
        Be very specific about pitch (class and octave), placement, and duration of all the notes you want to be added.
        
        You do not need to specify anything about dynamics, articulations, or other performance details.

        Keep your instruction specific, but concise.

        Your instructions will be sent to another AI agent who will use those instructions
        to add to the MIDI file.

        KNOWLEDGE BASE:
        {kb.summary_llm_friendly()}

        The current piece (shortened to last 12 measures for brevity):
        {mh.get_notes_json(measure_nums=-12)}
        """
    )

    suggestion: AIMessage = composer_llm.invoke(prompt)

    print("Composer Edit Intention: ", suggestion.content)

    content = f"CONTEXT_NOTES_JSON:\n{last_measures_json}\n\n{suggestion.content}"

    # 1) wipe everything, 2) re-add system prompt, 3) deliver new instruction
    new_msgs = [
        RemoveMessage(id=REMOVE_ALL_MESSAGES),  # wipe
        handler_sys_msg,  # restore system prompt
        HumanMessage(content=content),  # composer's fresh instruction
    ]

    return {"messages": new_msgs}


def reviewer_planner(state: GraphState) -> Dict[str, object]:
    """Have the Reviewer check for rule violations and propose one fix, if any."""

    mh, kb = state["midi_handler"], state["kb"]
    
    # Increment review iteration count
    # Review iterations are expensive, since the entire piece is sent to the LLM
    current_iterations = state.get("review_iterations", 0)
    max_review_iterations = state.get("max_review_iterations", 5)
    
    # Check if we've exceeded max iterations
    if current_iterations >= max_review_iterations:
        print(f"Maximum review iterations ({max_review_iterations}) reached. Ending review process.")
        return {
            "reviewer_satisfied": True,
            "review_iterations": current_iterations + 1,
            "in_review_mode": False  # Exit review mode when max iterations reached
        }
    
    print(f"Review iteration {current_iterations + 1}/{max_review_iterations}")

    prompt = (
        f"""
        You are the **Reviewer** agent.

        Inspect the entire piece against the Knowledge Base.  If you find a
        violation, describe a replacement for the specific measure that is in violation.

        Be very specific about pitch (class and octave), placement, and duration of all the notes you want to be
        in the measure you are replacing.
        
        You do not need to specify anything about dynamics, articulations, or other performance details.

        Keep your instruction specific, but concise.

        Your instructions will be sent to another AI agent who will use those instructions
        to make changes to the MIDI file.

        **Do not make unnecessary changes. If no changes need to be made, respond the word "Verified".**

                **Numeric semantics (do not change):**
        • **offset**   — when the note plays relative to the start of the piece in *quarter note lengths* (0.0 = piece start).
        • **pitch**    — String representing pitch (e.g., 'Bb4', 'C#5').
        • **duration** — duration of the note in quarter note lengths (4.0 = whole, 2.0 = half, 1.0 = quarter, 0.25 = sixteenth …).


        KNOWLEDGE BASE:
        {kb.summary_llm_friendly()}

        The current piece, shortened to last {state["add_measures"]} measures for brevity:
        {mh.get_notes_json(measure_nums=-(state["add_measures"]))}
        """
    )  # Only provide the added measures to the reviewer

    critique: AIMessage = reviewer_llm.invoke(prompt)
    
    if critique.content.strip().lower() == "verified":
        print("Reviewer is satisfied with the composition.")
        return {
            "reviewer_satisfied": True,
            "review_iterations": current_iterations + 1,
            "in_review_mode": False  # Exit review mode when satisfied
        }
    
    print(f"Reviewer critique: '{critique.content.strip()}'")

    # Store the reviewer's response to determine next action
    reviewer_feedback = critique.content.strip()
    
    if reviewer_feedback:
        # Reviewer found issues, prepare message for handler
        all_notes_json = mh.get_notes_json()
        content = f"CONTEXT_NOTES_JSON:\n{all_notes_json}\n\n{reviewer_feedback}"
        return {
            "messages": [HumanMessage(content=content)],
            "reviewer_satisfied": False,
            "review_iterations": current_iterations + 1,
            "in_review_mode": True  # Set review mode when issues found
        }
    else:
        # Reviewer is satisfied (empty response)
        print("Reviewer is satisfied with the composition.")
        return {
            "reviewer_satisfied": True,
            "review_iterations": current_iterations + 1,
            "in_review_mode": False  # Exit review mode when satisfied
        }


# ROUTING FUNCTIONS

def after_handler(state: GraphState) -> str:
    """Route after handler: check if we're in review loop or composition loop."""
    
    # If we're in review mode, go back to reviewer for re-evaluation
    if state.get("in_review_mode", False):
        print("Handler completed reviewer's fix. Going back to reviewer for re-evaluation.")
        return "reviewer_planner"
    
    # Otherwise, we're in the normal composition flow
    cur_measures = state["midi_handler"].get_number_of_measures()
    print(f"Current duration: {state['midi_handler'].get_duration()}")
    print(f"Current measures: {cur_measures}, target measures: {state['target_measures']}")
    if cur_measures < state["target_measures"]:
        return "composer_planner"
    else:
        print("Target measures reached. Moving to review phase.")
        state["midi_handler"].save_midi(f"our_generated_output/last_output_pre_review.mid")
        return "reviewer_planner"


def after_reviewer(state: GraphState) -> str:
    """Route after reviewer: if satisfied, end; if not, go back to handler for fixes."""
    
    # Check if reviewer is satisfied
    if state.get("reviewer_satisfied", False):
        print("Reviewer approved the composition. Finishing.")
        return END
    else:
        print("Reviewer found issues. Sending to handler for fixes.")
        return "handler_agent"



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
