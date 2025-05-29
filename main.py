from MidiHandler import MidiHandler
from KB import KnowledgeBase

def main():
    midi_handler = MidiHandler('test_input/complex1channel.mid')
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
    print("Notes: ", midi_handler.get_notes())
    print()
    print("Notes JSON: ", midi_handler.get_notes_json())
    print()

    chords = midi_handler.convert_to_chords()
    print("Underlying chords: ", chords)
    print()

    progression = midi_handler.get_chord_progression(chords)
    print("Chord Progression: ", progression)
    print()

    hr_progression = midi_handler.get_human_readable_chord_progression()
    print("Human-readable Chord Progression: ", hr_progression)
    print()



if __name__ == "__main__":
    main()