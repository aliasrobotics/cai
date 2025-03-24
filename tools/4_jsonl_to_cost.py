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
from tokencost import (  # pylint: disable=import-error
    calculate_cost_by_tokens
    as
    cost_by_tokens_and_model
)


def calculate_conversation_cost(
    total_input_tokens: int,
    total_output_tokens: int,
    model: str
) -> dict:
    """
    Calculate the total cost of a conversation based on pre-calculated input and output tokens.

    Args:
        total_input_tokens (int): Number of input tokens
        total_output_tokens (int): Number of output tokens
        model (str): The model name used in the conversation

    Returns:
        dict: Dictionary containing input cost
              output cost, and total cost in USD

    Example:
        calculate_conversation_cost(1000, 2000, "gpt-4")
        {'input_cost': 0.03, 'output_cost': 0.12, 'total_cost': 0.15, 'input_tokens': 1000, 'output_tokens': 2000} # noqa: E501, # pylint: disable=line-too-long
    """
    try:
        input_cost = cost_by_tokens_and_model(
            total_input_tokens, model, "input")
        output_cost = cost_by_tokens_and_model(
            total_output_tokens, model, "output")
        total_cost = input_cost + output_cost
    except KeyError:
        # Local Model or not fetched models by token cost
        # Check https://github.com/AgentOps-AI/tokencost for more information
        return {
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens
        }
    return {
        "input_cost": float(input_cost),
        "output_cost": float(output_cost),
        "total_cost": float(total_cost),
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens
    }


def main():
    """
    Main function to calculate and display the cost of LLM usage from a JSONL file.
    
    Reads environment variables for the JSONL file path and model name,
    loads the conversation history, calculates the cost, and displays the results.
    
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
        token_stats = get_token_stats(jsonl_file_path)
        file_model = token_stats[0]
        total_input_tokens = token_stats[1]
        total_output_tokens = token_stats[2]
        total_cost = token_stats[3]
    except Exception as e:
        print(f"Error loading JSONL file: {e}")
        sys.exit(1)
    
    # If cost is not in JSONL, calculate it
    if total_cost == 0:
        cost_result = calculate_conversation_cost(
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            model=file_model
        )
        
        # Display results using cli_print_tool_call
        util.cli_print_tool_call(
            tool_name="Cost Calculator",
            tool_args={
                "file": jsonl_file_path,
                "model": file_model
            },
            tool_output={
                "input_tokens": f"{cost_result['input_tokens']:,}",
                "output_tokens": f"{cost_result['output_tokens']:,}", 
                "input_cost": f"${cost_result['input_cost']:.6f}",
                "output_cost": f"${cost_result['output_cost']:.6f}",
                "total_cost": f"${cost_result['total_cost']:.6f}"
            },
            interaction_input_tokens=total_input_tokens,
            interaction_output_tokens=total_output_tokens,
            interaction_reasoning_tokens=0,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_reasoning_tokens=0,
            model=file_model,
            debug=2
        )
    else:
        # Display results using cli_print_tool_call with stored cost
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
