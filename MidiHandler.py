import music21 as m21

class MidiHandler:
    def __init__(self, midi_file):
        self.midi_file = midi_file
        self.midi_data = None
        self.load_midi()

    def load_midi(self):
        # Load the MIDI file and parse it
        pass

    def get_notes(self):
        # Extract notes from the MIDI data
        pass

    def save_midi(self, output_file):
        # Save the modified MIDI data to a new file
        pass