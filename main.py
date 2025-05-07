import MidiHandler

def main():
    midi_handler = MidiHandler.MidiHandler('test_input/simple1channel.mid')
    score = midi_handler.get_notes()
    print(score)
    print(midi_handler.get_key())

if __name__ == "__main__":
    main()