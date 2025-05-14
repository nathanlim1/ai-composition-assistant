from __future__ import annotations
import operator
import os
from typing import Dict, List
from typing_extensions import Annotated, TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import InjectedState, ToolNode
from KB import KnowledgeBase
from MidiHandler import MidiHandler

# load environment variables
load_dotenv()


class NoteInput(BaseModel):
    """Validated representation of a single note to be added to the score."""

    pitch: int = Field(..., ge=0, le=127, description="MIDI pitch number")
    duration: float = Field(..., gt=0, description="quarterLength duration")
    offset: float = Field(
        ..., ge=0, description="Offset (in quarterLength) from end of current score"
    )


class EditSpec(BaseModel):
    """Mutable attributes for an existing note (by flattened index)."""

    index: int = Field(..., ge=0, description="Index of note to edit in flattened list")
    pitch: int | None = Field(None, ge=0, le=127)
    duration: float | None = Field(None, gt=0)
    offset: float | None = Field(None, ge=0)


class StyleRules(BaseModel):
    """Structured style rules inferred by the rules‑LLM."""

    chord_progression_rules: Dict[str, Dict[str, str]] | None = Field(
        None,
        description="Rules for chord progressions (name → {desc, severity, suggestion})",
    )
    melodic_rules: Dict[str, Dict[str, str]] | None = Field(None, description="Rules for melody")
    harmonic_rules: Dict[str, Dict[str, str]] | None = Field(None, description="Rules for harmony")


# TOOL definitions for the LLMs to use

@tool
def add_notes(
    notes: List[NoteInput],
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Append notes to the current MIDI."""

    state["midi_handler"].add_notes([(n.pitch, n.duration, n.offset) for n in notes])
    return f"Added {len(notes)} notes."


@tool
def remove_notes(
    indices: List[int],
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Remove notes by flattened indices (0‑based)."""

    state["midi_handler"].remove_notes(indices)
    return f"Removed {len(indices)} notes."


@tool
def edit_note(
    spec: EditSpec,
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Edit attributes of a single note."""

    state["midi_handler"].edit_note(
        spec.index, pitch=spec.pitch, duration=spec.duration, offset=spec.offset
    )
    return "Note edited."


@tool
def replace_passage(
    start_offset: float,
    end_offset: float,
    notes: List[NoteInput],
    state: Annotated[Dict[str, object], InjectedState],
) -> str:
    """Replace passage between *start_offset* and *end_offset* with new notes."""

    state["midi_handler"].replace_passage(
        start_offset, end_offset, [(n.pitch, n.duration, n.offset) for n in notes]
    )
    return "Passage replaced."


COMPOSER_TOOLS = [add_notes, remove_notes, edit_note]
REVIEWER_TOOLS = COMPOSER_TOOLS + [replace_passage]


class GraphState(TypedDict):
    # Immutable inputs
    midi_path: str
    user_prompt: str
    target_duration: float

    # Internal, mutated in‑place
    kb: KnowledgeBase | None
    midi_handler: MidiHandler | None

    # Agent loop
    messages: Annotated[list, operator.add]
    done: bool

    # Output artifact
    output_midi: str



_MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

rules_llm = ChatOpenAI(model=_MODEL_NAME, temperature=0.0)
composer_llm = ChatOpenAI(model=_MODEL_NAME, temperature=0.7).bind_tools(COMPOSER_TOOLS)
reviewer_llm = ChatOpenAI(model=_MODEL_NAME, temperature=0.0).bind_tools(REVIEWER_TOOLS)

rules_parser = rules_llm.with_structured_output(StyleRules)

def dynamic_rule_builder(state: GraphState) -> Dict[str, object]:
    """Analyse MIDI & prompt, infer style rules, and initialise objects."""

    midi_handler = MidiHandler(state["midi_path"])
    kb = KnowledgeBase()

    # Extract static musical context (key, metre, etc.)
    kb.build_algorithmic_dynamic(midi_handler)

    # Infer additional stylistic rules using the LLM
    prompt = (
        "You are a music‑theory assistant. Given the STATIC rules below and "
        "the user's stylistic prompt, infer additional *stylistic* rules that "
        "should hold for any continuation of the piece. Return ONLY a JSON "
        "object that conforms to the provided schema.\n\n"
        f"STATIC + ALGO RULE SUMMARY:\n{kb.summary_markdown()}\n\n"
        f"USER STYLISTIC PROMPT:\n{state['user_prompt']}\n\n"
        f"NOTES:\n{midi_handler.get_notes()}\n\n"
        "Focus on key, characteristic rhythmic motives, allowable harmonic "
        "colour, and texture. Do not repeat rules already present."
    )

    style_rules: StyleRules = rules_parser.invoke(prompt)
    kb.generated_rules = style_rules

    return {
        "kb": kb,
        "midi_handler": midi_handler,
        "messages": [
            SystemMessage(
                content=(
                    "You are an expert MIDI composer. Extend the excerpt from the offset of the last note while "
                    "respecting ALL KB rules. Use tool calls to manipulate the "
                    "MIDI; respond with plain text ONLY when the score is complete."
                )
            ),
            HumanMessage(content="Please continue the excerpt."),
        ],
    }


def composer_agent(state: GraphState) -> Dict[str, object]:
    """Generate Composer output (plain text or tool calls)."""

    response = composer_llm.invoke(state["messages"])
    return {"messages": [response]}


def composer_router(state: GraphState):
    """Determine the next step in the Composer loop."""

    if state["done"]:
        return END

    # Hand over to reviewer once we've hit the target duration
    if state["midi_handler"].get_duration() >= state["target_duration"]:
        return "reviewer"

    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "composer_tools"

    return "composer_agent"


def reviewer(state: GraphState) -> Dict[str, object]:
    """Validate the completed piece and optionally apply fixes via tools."""

    prompt = (
        "You are a strict music‑theory reviewer. Analyse the ENTIRE MIDI "
        "(describe it abstractly) and the KB below. If you find violations or "
        "inconsistencies, fix them USING TOOL CALLS. If everything is OK, "
        "respond with NO tool calls.\n\n"
        f"KNOWLEDGE BASE:\n{state['kb'].summary_markdown()}"
    )

    result = reviewer_llm.invoke([SystemMessage(content=prompt)])
    return {"messages": [result]}


def reviewer_router(state: GraphState):
    """Decide whether the reviewer needs tool execution or we're finished."""

    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "reviewer_tools"
    return END

graph = StateGraph(GraphState)

# Nodes
graph.add_node("dynamic_rule_builder", dynamic_rule_builder)
graph.add_node("composer_agent", composer_agent)
graph.add_node("composer_tools", ToolNode(COMPOSER_TOOLS))
graph.add_node("reviewer", reviewer)
graph.add_node("reviewer_tools", ToolNode(REVIEWER_TOOLS))

# Edges
graph.add_edge(START, "dynamic_rule_builder")
graph.add_edge("dynamic_rule_builder", "composer_agent")

graph.add_conditional_edges(
    "composer_agent",
    composer_router,
    {
        "composer_tools": "composer_tools",
        "composer_agent": "composer_agent",
        "reviewer": "reviewer",
        END: END,
    },
)

graph.add_edge("composer_tools", "composer_agent")

graph.add_conditional_edges(
    "reviewer",
    reviewer_router,
    {
        "reviewer_tools": "reviewer_tools",
        END: END,
    },
)

graph.add_edge("reviewer_tools", "reviewer")

compiled_graph = graph.compile()


if __name__ == "__main__":
    initial_state: GraphState = {
        "midi_path": "test_input/simple1channel.mid",
        "user_prompt": (
            "Extend the excerpt in a similar style."
        ),
        "target_duration": 30.0,
        "kb": None,
        "midi_handler": None,
        "messages": [],
        "done": False,
        "output_midi": "extended_output.mid",
    }

    final_state = compiled_graph.invoke(initial_state)

    final_state["midi_handler"].save_midi(final_state["output_midi"])
    print(f"[FINAL] Saved composed MIDI → {final_state['output_midi']}")
