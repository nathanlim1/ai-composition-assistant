from typing import List, Dict
from MidiHandler import MidiHandler


class KnowledgeBase:
    def __init__(self):
        self.rules: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.dynamic_context: dict[str, str] = {}
        self.generated_rules: Dict[str, Dict[str, Dict[str, str]]] = {}
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
                "avoid_unplayable_intervals": {
                    "desc": "Avoid writing intervals that exceed a 9th in one hand unless arpeggiated.",
                    "severity": "hard",
                    "suggestion": "Distribute wide intervals between hands or arpeggiate.",
                },
                "no_hand_overlap": {
                    "desc": "Avoid overlapping left and right hand note ranges unless intentional.",
                    "severity": "hard",
                    "suggestion": "Keep hands in separate registers to maintain clarity.",
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
                "avoid_extreme_registers": {
                    "desc": "Avoid writing melodic lines that fall outside the standard piano range (A0–C8).",
                    "severity": "hard",
                    "suggestion": "Transpose extreme notes into a playable range.",
                },
                "stay_within_piano_range": {
                    "desc": "All notes must stay within the standard piano range (A0 to C8).",
                    "severity": "hard",
                    "suggestion": "Transpose or omit notes that fall outside the playable piano range.",
                },
            },
            "rhythmic": {
                "avoid_constant_note_values": {
                    "desc": "Using the same note value repeatedly can make the rhythm monotonous.",
                    "severity": "soft",
                    "suggestion": "Vary note durations to create more rhythmic interest.",
                },
                "syncopation_should_resolve": {
                    "desc": "Syncopated figures should resolve onto strong beats within the meter.",
                    "severity": "soft",
                    "suggestion": "Follow syncopation with a strong downbeat to ground the rhythm.",
                },
            },
            "pianistic": {
                "balance_between_hands": {
                    "desc": "Ensure musical material is balanced between hands to avoid awkward textures.",
                    "severity": "soft",
                    "suggestion": "Distribute activity more evenly or alternate between hands.",
                },
                "use_pedal_clearly": {
                    "desc": "Avoid overlapping harmonies that cause pedal-induced blurring.",
                    "severity": "soft",
                    "suggestion": "Lift pedal between harmonically distant chords.",
                },
            },          
            "performance": {
                "avoid_excessive_velocity_contrast": {
                    "desc": "Avoid unnatural contrasts in note velocity that break musical phrasing.",
                    "severity": "soft",
                    "suggestion": "Apply dynamic shaping more smoothly across phrases.",
                },
                "use_articulation_consistently": {
                    "desc": "Articulation like staccato or legato should be used consistently within a phrase.",
                    "severity": "soft",
                    "suggestion": "Review articulation patterns to ensure clarity and consistency.",
                },
            },                                
        }


    def build_algorithmic_dynamic(self, midi_handler: MidiHandler):
        """
        Algorithmically builds dynamic rules for the KB based on the MIDI file.
        """
        key = midi_handler.get_readable_key()
        self.dynamic_context["key"] = str(key)
        # TODO: motifs, time signature, etc, then LLM analysis
        time_signature = midi_handler.get_human_readable_time_signature()
        self.dynamic_context["time_signature"] = time_signature

        chord_progression = midi_handler.get_human_readable_chord_progression()
        self.dynamic_context["chord_progression"] = chord_progression

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

