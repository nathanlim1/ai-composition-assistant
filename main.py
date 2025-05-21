from MidiHandler import MidiHandler

def main():
    midi_handler = MidiHandler('test_input/simple1channel.mid')
    print("Key: ", midi_handler.get_key())
    print()
    print("Length in Measures: ", midi_handler.get_number_of_measures())
    print()
    print("Length in seconds: ", midi_handler.get_duration())
    print()
    print("Time Signature: ", midi_handler.get_time_signature())
    print()
    print("Notes: ", midi_handler.get_notes())
    print()

    chords = midi_handler.convert_to_chords()
    print("Underlying chords: ", chords)
    print()

    progression = midi_handler.get_chord_progression(chords)
    print("Chord Progression: ", progression)
    print()


if __name__ == "__main__":
    main()