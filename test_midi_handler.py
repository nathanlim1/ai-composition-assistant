from MidiHandler import MidiHandler

def main():
    midi_handler = MidiHandler('test_input/bach_minuet_in_g_116.mid')
    print("Key: ", midi_handler.get_readable_key())
    print()
    print("Length in Measures: ", midi_handler.get_number_of_measures())
    print()
    print("Length in seconds: ", midi_handler.get_duration())
    print()
    print("Time Signature: ", midi_handler.get_time_signature())
    print()
    print("Human-readable Time Signature: ", midi_handler.get_human_readable_time_signature())
    print()
    notes = midi_handler.get_notes()
    print("Notes: ", notes)
    print()
    print("Notes JSON: ", midi_handler.get_notes_json())
    print()

    notes_by_part = midi_handler.get_notes_by_part()
    print("Notes by part: ", notes_by_part)
    print()


    print("Extracting chords from all notes:")
    chords = midi_handler.convert_to_chords(notes)
    print("Underlying chords: ", chords)
    print()

    progression = midi_handler.get_chord_progression(chords)
    print("Chord Progression: ", progression)
    print()
    print()

    print("Extracting chords from notes by part:")
    for notes in notes_by_part:
        chords_by_part = midi_handler.convert_to_chords(notes)
        chord_progression = midi_handler.get_chord_progression(chords_by_part)
        hr_chord_progression = midi_handler.get_human_readable_chord_progression(chord_progression)
        print("Underlying chords by part: ", chords_by_part)
        print()
        print("Chord Progression by part: ", chord_progression)
        print()
        print("Human-readable Chord Progression: ", hr_chord_progression)
        print()




if __name__ == "__main__":
    main()