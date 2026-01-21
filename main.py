import argparse
import sys
from src.compositionAgent import compiled_graph, GraphState
from langgraph.errors import GraphRecursionError


def main():
    """Main function to run the AI composition assistant."""
    parser = argparse.ArgumentParser(description="AI Composition Assistant")
    parser.add_argument("--input", "-i", default="test_input/bach_minuet_in_g_116.mid",
                       help="Input MIDI file path")
    parser.add_argument("--output", "-o", default="our_generated_output/extended_piece.mid", 
                       help="Output MIDI file path")
    parser.add_argument("--measures", "-m", type=float, default=8.0,
                       help="Additional measures to extend")
    parser.add_argument("--prompt", "-p", default="Extend the excerpt in a similar style.",
                       help="User prompt for composition guidance")
    parser.add_argument("--recursion-limit", "-r", type=int, default=50,
                       help="Maximum recursion limit for the graph")
    parser.add_argument("--max-review-iterations", type=int, default=3,
                       help="Maximum number of review iterations to prevent infinite loops")
    
    args = parser.parse_args()
    
    # Initialize the state for the composition graph
    init_state: GraphState = {
        "midi_path": args.input,
        "user_prompt": args.prompt,
        "add_measures": args.measures,
        "target_measures": 0,
        "kb": None,
        "midi_handler": None,
        "messages": [],
        "output_midi": args.output,
        "remaining_steps": 30,
        "reviewer_satisfied": False,
        "review_iterations": 0,
        "max_review_iterations": args.max_review_iterations,
        "in_review_mode": False,
    }
    
    print(f"Starting composition with:")
    print(f"  Input MIDI: {args.input}")
    print(f"  Output MIDI: {args.output}")
    print(f"  Additional measures: {args.measures}")
    print(f"  Prompt: {args.prompt}")
    print()
    
    try:
        # Run the composition graph
        final = compiled_graph.invoke(init_state, {"recursion_limit": args.recursion_limit})
        
        # Save the composed MIDI
        final["midi_handler"].save_midi(final["output_midi"])
        print(f"Successfully saved composed MIDI -> {final['output_midi']}")
        
    except GraphRecursionError:
        print("Graph recursion error: The composition process exceeded the recursion limit.")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during composition: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
