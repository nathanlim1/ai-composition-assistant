from typing import List, Dict
from MidiHandler import MidiHandler


class KnowledgeBase:
    def __init__(self):
        self.rules: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.dynamic_context: dict[str, str] = {}
        self.load_static_rules()

    def load_static_rules(self):
        """
        Load static theory and compositional rules into the knowledge base.
        """
        self.rules = {
            "chord_progression": {
                "resolve_dominant_to_tonic": {
                    "desc": "A V (dominant) chord should normally resolve to I (tonic) or vi in deceptive cadence.",
                    "severity": "hard",
                    "suggestion": "Try following a V chord with I (or vi for a deceptive resolution).",
                },
                "avoid_parallel_fifths_root_movement": {
                    "desc": "Avoid root progressions by parallel perfect fifths across consecutive chords.",
                    "severity": "soft",
                    "suggestion": "Insert passing or neighbor chords to break the fifths, or use inversion.",
                },
            },
            "harmonic": {
                "no_parallel_fifths": {
                    "desc": "No parallel perfect fifths between any pair of voices.",
                    "severity": "hard",
                    "suggestion": "Alter one voice by step to create contrary or oblique motion.",
                },
                "no_doubled_leading_tone": {
                    "desc": "Do not double the leading tone in minor keys.",
                    "severity": "hard",
                    "suggestion": "Use another scale degree for doubling (often 3 or 5).",
                },
            },
            "melodic": {
                "stay_within_tessitura": {
                    "desc": "Melody should generally stay within a reasonable tessitura (< an 11th).",
                    "severity": "soft",
                    "suggestion": "Bring extreme leaps back toward the center with stepwise motion.",
                },
                "no_augmented_seconds": {
                    "desc": "Avoid augmented 2nds in common‑practice melody unless stylistically justified.",
                    "severity": "soft",
                    "suggestion": "Use chromatic passing tones or re‑voice to form a minor 3rd instead.",
                },
            },
        }


    def build_algorithmic_dynamic(self, midi_handler: MidiHandler):
        """
        Algorithmically builds dynamic rules for the KB based on the MIDI file.
        """
        key = midi_handler.get_key()
        self.dynamic_context["key"] = str(key)
        # TODO: motifs, time signature, etc, then LLM analysis

    def summary_markdown(self) -> str:
        """
        Returns a summary of the rules in Markdown format for ease of use by an LLM.
        """
        lines: List[str] = [f"**Key:** {self.dynamic_context.get('key', 'Unknown')}"]
        for cat, rules in self.rules.items():
            lines.append(f"### {cat.replace('_', ' ').title()} Rules")
            for rid, meta in rules.items():
                lines.append(f"- **{rid.replace('_',' ')}** ({meta['severity']}): {meta['desc']}")
        return "\n".join(lines)

kb = KnowledgeBase()
print(kb.summary_markdown())

