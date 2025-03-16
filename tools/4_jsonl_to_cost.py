"""
Calculate the cost of LLM usage from a JSONL history file.

This script processes a JSONL file containing conversation history and displays
the total cost based on token usage and the stored cost information.

Usage:
    JSONL_FILE_PATH="path/to/file.jsonl" python3 tools/4_jsonl_to_cost.py

Environment Variables:
    JSONL_FILE_PATH: Path to the JSONL file containing conversation history (required)

Output:
    Displays the total cost breakdown including input tokens, output tokens,
    and total cost in USD as stored in the JSONL file
"""
import os
import sys
from cai.datarecorder import get_token_stats
from cai import util


def main():
    """
    Main function to display the cost of LLM usage from a JSONL file.
    
    Reads environment variables for the JSONL file path,
    loads the conversation history, and displays the results.
    
    Raises:
        ValueError: If required environment variables are not set.
    """
    # Get environment variables
    jsonl_file_path = os.environ.get("JSONL_FILE_PATH")
    
    # Validate environment variables
    if not jsonl_file_path:
        raise ValueError("JSONL_FILE_PATH environment variable is required")
    
    # Get token stats from JSONL file
    try:
        file_model, total_input_tokens, total_output_tokens, total_cost = get_token_stats(
            jsonl_file_path)
    except Exception as e:
        print(f"Error loading JSONL file: {e}")
        sys.exit(1)
    
    # Display results using cli_print_tool_call
    util.cli_print_tool_call(
        tool_name="Cost Calculator",
        tool_args={
            "file": jsonl_file_path,
            "model": file_model
        },
        tool_output={
            "input_tokens": f"{total_input_tokens:,}",
            "output_tokens": f"{total_output_tokens:,}", 
            "total_tokens": f"{total_input_tokens + total_output_tokens:,}",
            "total_cost": f"${total_cost:.6f}",
            "stored_in_jsonl": "True"
        },
        interaction_input_tokens=total_input_tokens,
        interaction_output_tokens=total_output_tokens,
        interaction_reasoning_tokens=0,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_reasoning_tokens=0,
        model=file_model,
        debug=2,
        interaction_cost=0.0,
        total_cost=total_cost
    )


if __name__ == "__main__":
    main()
