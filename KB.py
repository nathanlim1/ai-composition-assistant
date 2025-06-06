from typing import List, Dict
from MidiHandler import MidiHandler


class KnowledgeBase:
    def __init__(self):
        self.rules: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.dynamic_context: dict[str, str] = {}
        self.generated_rules: str = ""
        self.load_static_rules()

    def load_static_rules(self):
        """
        Load static theory and compositional rules into the knowledge base.
        """
        self.rules = {
            "continuity": {
                "honor_established_key": {
                    "desc": (
                        "Remain in the current key for at least four full measures "
                        "after it is stated, unless a prepared modulation or tonicization "
                        "has been foreshadowed."
                    ),
                    "severity": "hard",
                    "suggestion": "If modulation is desired, insert a secondary-dominant or pivot-chord first.",
                },
                "follow_active_progression": {
                    "desc": (
                        "The next harmony should fit the functional trajectory implied by the "
                        "preceding 2-4 chords (e.g., ii–V wants I or vi; V/V wants V)."
                    ),
                    "severity": "hard",
                    "suggestion": "Use circle-of-fifths or deceptive options that listeners expect.",
                },
                "reuse_recent_rhythmic_cell": {
                    "desc": "At least one rhythmic figure from the previous 2 bars should return or vary.",
                    "severity": "soft",
                    "suggestion": "Alter only the final note value or apply syncopation to keep it fresh.",
                },
            },

            "chord_progression": {
                "respect_phrase_cadence_points": {
                    "desc": (
                        "End of a 4- or 8-bar phrase must cadence (PAC, IAC, HC, or DC) "
                        "consistent with established style."
                    ),
                    "severity": "hard",
                    "suggestion": "Plan harmonic rhythm so the cadence chord lands on a strong beat.",
                },
            },

            "voice_leading": {
                "resolve_sevenths_and_leading_tones": {
                    "desc": "Chordal sevenths resolve down; leading tones resolve up (or down in inner voices).",
                    "severity": "hard",
                    "suggestion": "Check every V⁷→I, ii⁷→V, etc., for proper resolution.",
                },
                "no_doubled_leading_tone": {
                    "desc": "Never double the leading tone in minor or major keys.",
                    "severity": "hard",
                    "suggestion": "Double scale degrees 3 or 5 instead.",
                },
            },

            "phrase_structure": {
                "consistent_phrase_length": {
                    "desc": "Maintain the established phrase length (usually 4 or 8 measures) unless intentionally varied.",
                    "severity": "soft",
                    "suggestion": "If you extend or truncate a phrase, balance it in the next phrase (period construction).",
                },
                "cadence_alignment": {
                    "desc": "Cadences should coincide with strong metric accents (typically beat 1).",
                    "severity": "hard",
                    "suggestion": "Shift preceding material earlier or later to land the cadence correctly.",
                },
            },

            "motivic": {
                "develop_primary_motif": {
                    "desc": (
                        "Every 2–4 measures, reference or vary the primary melodic/rhythmic motif "
                        "introduced earlier (inversion, retrograde, augmentation, diminution, etc.)."
                    ),
                    "severity": "soft",
                    "suggestion": "Transform interval shapes or durations but keep the contour recognizable.",
                },
                "avoid_unrelated_material": {
                    "desc": "Do not introduce wholly new motives unless beginning a clearly defined new section.",
                    "severity": "soft",
                    "suggestion": "If new material is needed, derive it from fragments of existing motives.",
                },
            },

            "melodic": {
                "avoid_extreme_registers": {
                    "desc": "Keep melodic lines inside the piano’s playable range (A0–C8).",
                    "severity": "hard",
                    "suggestion": "Transpose extreme notes or rethink voicing.",
                },
            },

            "rhythmic": {
                "avoid_constant_note_values": {
                    "desc": "Monotonous repeated note values flatten interest.",
                    "severity": "soft",
                    "suggestion": "Mix longer and shorter durations or introduce syncopation.",
                },
            },
        }



    def build_algorithmic_dynamic(self, midi_handler: MidiHandler):
        """
        Algorithmically builds dynamic rules for the KB based on the MIDI file.
        """
        key = midi_handler.get_readable_key()
        self.dynamic_context["key"] = str(key)

        time_signature = midi_handler.get_human_readable_time_signature()
        self.dynamic_context["time_signature"] = time_signature
        
        notes_by_part = midi_handler.get_notes_by_part()
        if(len(notes_by_part) == 2):
            treble_chords = midi_handler.get_chord_progression(notes_by_part[0])
            bass_chords = midi_handler.get_chord_progression(notes_by_part[1])
            self.dynamic_context["treble_chord_progression"] = midi_handler.get_human_readable_chord_progression(treble_chords)
            self.dynamic_context["bass_chord_progression"] = midi_handler.get_human_readable_chord_progression(bass_chords)
        else:
            chords = midi_handler.get_chord_progression(midi_handler.get_notes())
            self.dynamic_context["chord_progression"] = midi_handler.get_human_readable_chord_progression(chords)

    def summary_llm_friendly(self) -> str:
        """
        Returns all rules in a format that is most LLM-friendly: clear, concise, grouped by category, with each rule as a short, direct statement. Ignores severity and suggestion fields. Includes generated rules as a separate section if present.
        """
        lines: list[str] = [
            f"**Key:** {self.dynamic_context.get('key', 'Unknown')}\n",
            f"**Time Signature:** {self.dynamic_context.get('time_signature', 'Unknown')}\n"
        ]
        
        # Output either chord progression or treble+bass chord progression
        if "chord_progression" in self.dynamic_context:
            lines.append(f"**Chord Progression:** {self.dynamic_context.get('chord_progression', 'Unknown')}\n")
        elif "treble_chord_progression" in self.dynamic_context and "bass_chord_progression" in self.dynamic_context:
            lines.append(f"**Treble Chord Progression:** {self.dynamic_context.get('treble_chord_progression', 'Unknown')}\n")
            lines.append(f"**Bass Chord Progression:** {self.dynamic_context.get('bass_chord_progression', 'Unknown')}\n")

        # Generated rules (from LLM analysis)
        lines.append(f"**Generated Rules:** {self.generated_rules}\n")

        # Static rules
        for cat, rules in self.rules.items():
            lines.append(f"### {cat.replace('_', ' ').title()} Rules")
            for rid, meta in rules.items():
                lines.append(f"- {meta['desc']}")

        return "\n".join(lines)

kb = KnowledgeBase()
print(kb.summary_llm_friendly())

