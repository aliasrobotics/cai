"""
Count the number of iterations between agents in a JSONL file.

This script processes a JSONL file containing conversation history and counts
the number of iterations for each agent involved in the conversation.

Usage:
    JSONL_FILE_PATH="path/to/file.jsonl" python3 tools/6_interactions_counter.py

Environment Variables:
    JSONL_FILE_PATH: Path to the JSONL file containing conversation history (required)

Output:
    Displays the number of iterations for each agent in the conversation.
"""
import json
import os
from typing import List, Dict
from cai.datarecorder import load_history_from_jsonl  # pylint: disable=import-error # noqa: E501

def count_agent_iterations(jsonl_file_path: str) -> Dict[str, int]:
    """Count the number of iterations between agents in a JSONL file.

    Args:
        jsonl_file_path: Path to the JSONL file containing conversation history.

    Returns:
        A dictionary with agent names as keys and their respective iteration counts as values.
    """
    agent_iterations = {}
    history = load_history_from_jsonl(jsonl_file_path)
    
    for message in history:
        role = message.get("role", "")
        sender = message.get("sender", role)

        if role in ["user", "assistant", "tool", "state"]:
            if sender not in agent_iterations:
                agent_iterations[sender] = 0
            agent_iterations[sender] += 1

    return agent_iterations

def main():
    jsonl_file_path = os.environ.get("JSONL_FILE_PATH")
    
    if not jsonl_file_path:
        print("Error: JSONL_FILE_PATH environment variable is required")
        return

    iterations = count_agent_iterations(jsonl_file_path)
    print(f"SUMMARY ITERATIONS")
    for agent, count in iterations.items():
        print(f"{agent}: {count} iterations")
    total_interactions = sum(count for agent, count in iterations.items() if agent not in ["user", "tool"])
   
    print(f"TOTAL AGENT ITERATIONS: {total_interactions}")

if __name__ == "__main__":
    main()
