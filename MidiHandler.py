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
        print(midi.show())

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
    
    def get_key(self):
        # Extract the key signature from the MIDI data
        key = self.midi_data.analyze('key')
        return key

    def save_midi(self, output_file: str):
        if self.midi_data is None:
            raise ValueError("Nothing to save; load or generate MIDI first.")
        self.midi_data.write("midi", fp=output_file)
        print(f"Saved MIDI to {output_file}")
        