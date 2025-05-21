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
        midi.show('text') # Show the text representation of the MIDI data
        # midi.show()

    def get_notes(self):
        # Extract notes from the MIDI data into an array with total file offset + note
        if self.midi_data is None:
            raise ValueError("MIDI data not loaded.")

        part = self.midi_data.parts[0]
        notes = [(n.getOffsetInHierarchy(part), n)
                 for n in part.recurse().notes]
        notes.sort(key=lambda t: t[0])
        return notes

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

    def get_number_of_measures(self):
        # Get the number of measures in the MIDI file
        if self.midi_data is None:
            raise ValueError("MIDI data not loaded.")
        return len(self.midi_data.parts[0].getElementsByClass(m21.stream.Measure))

    def get_time_signature(self):
        # Extract the time signature from the MIDI data
        if self.midi_data is None:
            raise ValueError("MIDI data not loaded.")
        return self.midi_data.parts[0].measures(0,1)[0].timeSignature


    def get_chord_progression(self, chords):
        # Get the key of the MIDI file
        key = self.get_key()
        roman_numerals = []

        for _, chord in chords:
            # Convert the chord to a Roman numeral in the given key
            roman = m21.roman.romanNumeralFromChord(chord, key)
            roman_numerals.append(roman)
        return roman_numerals


    def convert_to_chords(self, window_size = 1):   # window size is in measures
        notes = self.get_notes()
        time_signature = self.get_time_signature()

        chords = []

        for i in range(0, self.get_number_of_measures(), window_size):
            lower_offset = i * time_signature.numerator
            upper_offset = lower_offset + (window_size * time_signature.numerator)
            window = []

            for note in notes:
                if(lower_offset <= note[0] < upper_offset):
                    if isinstance(note[1], m21.note.Note):
                        window.append(note[1])
                    elif isinstance(note[1], m21.chord.Chord):
                        chords.append(note)

            if(len(window) != 0):
                chord = self.get_nearest_chord_by_melody(window)
                chords.append((lower_offset, chord))

        chords.sort(key=lambda chord: chord[0])  # Sort by offset

        return chords

    # Find the nearest chord to the given note
    def get_nearest_chord_by_melody(self, notes):
        pitches = [note.pitch for note in notes]
        chord = m21.chord.Chord(pitches)
        return chord

    def get_key(self):
        # Extract the key signature from the MIDI
        # returns a music21 key.Key object
        key = (self.midi_data.flatten().keySignature).asKey()
        return key

    def save_midi(self, output_file: str):
        if self.midi_data is None:
            raise ValueError("Nothing to save; load or generate MIDI first.")
        self.midi_data.write("midi", fp=output_file)
        print(f"Saved MIDI to {output_file}")
