from typing import List

import music21 as m21

class MidiHandler:
    def __init__(self, midi_file):
        self.midi_file = midi_file
        self.midi_data = None
        self.load_midi()

    def load_midi(self):
        # Load the MIDI file and parse it
        print("Loading MIDI file: ", self.midi_file)
        midi = m21.converter.parse(self.midi_file)
        self.midi_data = midi
        print(midi.show('text'))  # Show the text representation of the MIDI data
        # print(midi.show())

    def get_notes(self):
        # Extract notes from the MIDI data
        score = []
        part = self.midi_data[1]
        for measure in part:
            notes = []
            for note in measure.notes:
                notes.append(note)
            score.append(notes.copy())
        return score

    def add_notes(self, notes: List[tuple[int, float, float]]) -> str:
        """Append notes to the MIDI data."""
        if self.midi_data is None:
            raise ValueError("MIDI data not loaded.")

        part = self.midi_data.parts[0]
        for pitch, ql, offset in notes:
            note = m21.note.Note(pitch)
            note.quarterLength = ql
            note.offset = offset
            part.insert(offset, note)
        return f"Added {len(notes)} notes to the MIDI data."

    def remove_notes(self, start: float, end: float):
        """Delete notes whose offset is between start and end."""
        if self.midi_data is None:
            raise ValueError("MIDI data not loaded.")

        part = self.midi_data.parts[0]
        removed = 0
        for note in list(part.recurse().notes):
            if start <= note.offset < end:
                part.remove(note)
                removed += 1
        return f"Removed {removed} notes between {start} and {end} seconds."

    def edit_note(self, offset: float, pitch: int | None = None, ql: float | None = None) -> str:
        """Change the first note starting at offset."""
        part = self.midi_data.parts[0]
        for n in part.recurse().notes:
            if n.offset == offset:
                if pitch is not None:
                    n.pitch.midi = pitch
                if ql is not None:
                    n.quarterLength = ql
                return f"Edited note at {offset}: now pitch={n.pitch.midi}, ql={n.quarterLength}"
        return "No note found to edit."

    def replace_passage(self, start: float, end: float, notes: List[tuple[int, float]]) -> str:
        """High-level helper that wipes out a passage between [start,end] and inserts notes sequentially."""
        self.remove_notes(start, end)
        cur = start
        for pitch, ql in notes:
            self.add_notes([(pitch, ql, cur)])
            cur += ql
        return f"Replaced passage {start}‑{end} with {len(notes)} notes."


    def get_duration(self) -> float:
        """
        Return the real‑time duration of the currently‑loaded MIDI
        (in seconds), accounting for all tempo changes.
        """
        if self.midi_data is None:
            raise ValueError("MIDI data not loaded.")

        # self.midi_data is already a Stream
        smap = self.midi_data.secondsMap          # list of dicts

        if not smap:                              # empty score
            return 0.0

        last = max(smap,
                   key=lambda d: d['offsetSeconds'] + d['durationSeconds'])

        return last['offsetSeconds'] + last['durationSeconds']

    def get_key(self):
        # Extract the key signature from the MIDI data
        key = self.midi_data.analyze('key')
        return key

    def save_midi(self, output_file: str):
        if self.midi_data is None:
            raise ValueError("Nothing to save; load or generate MIDI first.")
        self.midi_data.write("midi", fp=output_file)
        print(f"Saved MIDI to {output_file}")
        