#!/usr/bin/env python3
"""
Tool to convert JSONL files to a replay format that simulates the CLI output.
This allows reviewing conversations in a more readable format.

Usage:
    JSONL_FILE_PATH="path/to/file.jsonl" REPLAY_DELAY="0.5" python3 tools/5_jsonl_to_replay.py

Usage with asciinema rec, generating a .cast file and then converting it to a gif:
    asciinema rec --command="JSONL_FILE_PATH=\"/workspace/caiextensions-memory/caiextensions/memory/it/htb/challenges/insomnia/cai_20250307_114836.jsonl\" REPLAY_DELAY=\"0.5\" python3 tools/5_jsonl_to_replay.py" --overwrite
    agg /tmp/tmp6c4dxoac-ascii.cast demo.gif

Environment Variables:
    JSONL_FILE_PATH: Path to the JSONL file containing conversation history (required)
    REPLAY_DELAY: Time in seconds to wait between actions (default: 0.5)
"""

import json
import os
import sys
import time
from typing import Dict, List, Tuple
from cai.datarecorder import get_token_stats

# Add the parent directory to the path to import cai modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cai.util import (
    cli_print_agent_messages,
    cli_print_tool_call,
    cli_print_state,
    color
)
from cai.datarecorder import load_history_from_jsonl


def load_jsonl(file_path: str) -> List[Dict]:
    """Load a JSONL file and return its contents as a list of dictionaries."""
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Warning: Skipping invalid JSON line: {line[:50]}...")
    return data


def replay_conversation(messages: List[Dict], replay_delay: float = 0.5, usage: Tuple = None) -> None:
    """
    Replay a conversation from a list of messages, printing in real-time.
    
    Args:
        messages: List of message dictionaries
        replay_delay: Time in seconds to wait between actions
        usage: Tuple containing (model_name, total_input_tokens, total_output_tokens, 
               total_cost, active_time, idle_time)
    """
    turn_counter = 0
    interaction_counter = 0
    debug = 2  # Always set debug to 2
    
    if not messages:
        print(color("No valid messages found in the JSONL file", fg="yellow"))
        return
        
    print(color(f"Replaying conversation with {len(messages)} messages...", 
                fg="green"))
    
    # Extract the usage stats from the usage tuple
    # Handle both old format (4 elements) and new format (6 elements with timing)
    file_model = usage[0]
    total_input_tokens = usage[1]
    total_output_tokens = usage[2]
    total_cost = usage[3]
    
    # Check if timing information is available
    active_time = usage[4] if len(usage) > 4 else 0
    idle_time = usage[5] if len(usage) > 5 else 0
    
    # Display timing information if available
    if active_time > 0 or idle_time > 0:
        print(color(f"Active time: {active_time:.2f}s", fg="cyan"))
        print(color(f"Idle time: {idle_time:.2f}s", fg="cyan"))
    
    print(color(f"Total cost: ${total_cost:.6f}", fg="cyan"))

    for i, message in enumerate(messages):
        # Add delay between actions
        if i > 0:
            time.sleep(replay_delay)
            
        role = message.get("role", "")
        content = message.get("content", "")
        sender = message.get("sender", role)
        model = message.get("model", file_model)
        
        # Skip system messages
        if role == "system":
            continue
            
        # Handle user messages
        if role == "user":
            # Use cli_print_agent_messages for user messages
            print(color(f"CAI> ", fg="cyan") + f"{content}")

            turn_counter += 1
            interaction_counter = 0
            
        # Handle assistant messages
        elif role == "assistant":
            # Check if there are tool calls
            tool_calls = message.get("tool_calls", [])
            
            if tool_calls:
                # Print the assistant message with tool calls
                cli_print_agent_messages(
                    sender, 
                    content, 
                    interaction_counter, 
                    model, 
                    debug,
                    interaction_input_tokens=message.get("input_tokens", 0),
                    interaction_output_tokens=message.get("output_tokens", 0),
                    interaction_reasoning_tokens=message.get("reasoning_tokens", 0),
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_reasoning_tokens=message.get("total_reasoning_tokens", 0),
                    interaction_cost=message.get("interaction_cost", 0.0),
                    total_cost=total_cost
                )
                
                # Print each tool call
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    name = function.get("name", "")
                    arguments = function.get("arguments", "{}")
                    
                    cli_print_tool_call(
                        name, 
                        json.loads(arguments) if arguments else {},
                        content,  # tool_output
                        message.get("input_tokens", 0),  # interaction_input_tokens
                        message.get("output_tokens", 0),  # interaction_output_tokens
                        message.get("reasoning_tokens", 0),  # interaction_reasoning_tokens
                        total_input_tokens,  # total_input_tokens
                        total_output_tokens,  # total_output_tokens
                        message.get("total_reasoning_tokens", 0),  # total_reasoning_tokens
                        model,
                        debug,
                        interaction_cost=message.get("interaction_cost", 0.0),
                        total_cost=total_cost
                    )
            else:
                # Print regular assistant message
                cli_print_agent_messages(
                    sender, 
                    content, 
                    interaction_counter, 
                    model, 
                    debug,
                    interaction_input_tokens=message.get("input_tokens", 0),
                    interaction_output_tokens=message.get("output_tokens", 0),
                    interaction_reasoning_tokens=message.get("reasoning_tokens", 0),
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_reasoning_tokens=message.get("total_reasoning_tokens", 0),
                    interaction_cost=message.get("interaction_cost", 0.0),
                    total_cost=total_cost
                )
            interaction_counter += 1  # iterate the interaction counter
        
        # Handle tool messages
        elif role == "tool":
            tool_name = message.get("name", message.get("tool_call_id", "unknown"))
            cli_print_tool_call(
                tool_name,
                {},
                content,  # tool_output
                message.get("input_tokens", 0),
                message.get("output_tokens", 0),
                message.get("reasoning_tokens", 0),
                total_input_tokens,
                total_output_tokens,
                message.get("total_reasoning_tokens", 0),
                model,
                debug,
                interaction_cost=message.get("interaction_cost", 0.0),
                total_cost=total_cost
            )
            
        # Handle state messages
        elif role == "state" or sender == "State Agent":
            cli_print_state(
                sender,  # agent_name
                content,  # message
                interaction_counter,  # counter
                model,  # model
                debug,  # debug
                message.get("input_tokens", 0),  # interaction_input_tokens
                message.get("output_tokens", 0),  # interaction_output_tokens
                message.get("reasoning_tokens", 0),  # interaction_reasoning_tokens
                total_input_tokens,  # total_input_tokens
                total_output_tokens,  # total_output_tokens
                message.get("total_reasoning_tokens", 0),  # total_reasoning_tokens
                interaction_cost=message.get("interaction_cost", 0.0),
                total_cost=total_cost
            )
        
        # Handle any other message types
        else:
            cli_print_agent_messages(
                sender or role,
                content,
                interaction_counter,
                model,
                debug,
                interaction_input_tokens=message.get("input_tokens", 0),
                interaction_output_tokens=message.get("output_tokens", 0),
                interaction_reasoning_tokens=message.get("reasoning_tokens", 0),
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_reasoning_tokens=message.get("total_reasoning_tokens", 0),
                interaction_cost=message.get("interaction_cost", 0.0),
                total_cost=total_cost
            )
                    
        # Force flush stdout to ensure immediate printing
        sys.stdout.flush()


def main():
    """Main function to process JSONL files and generate replay output."""
    # Get environment variables
    jsonl_file_path = os.environ.get("JSONL_FILE_PATH")
    replay_delay = float(os.environ.get("REPLAY_DELAY", "0.5"))
    
    # Validate environment variables
    if not jsonl_file_path:
        print(color("Error: JSONL_FILE_PATH environment variable is required", 
                    fg="red"))
        sys.exit(1)
    
    print(color(f"Loading JSONL file: {jsonl_file_path}", fg="blue"))
    
    try:
        # Load the JSONL file using the proper function from datarecorder
        messages = load_history_from_jsonl(jsonl_file_path)
        print(color(f"Loaded {len(messages)} messages from JSONL file", fg="blue"))

        # Get token stats and cost from the JSONL file
        usage = get_token_stats(jsonl_file_path)
        
        # Display model and token information
        print(color(f"Model: {usage[0]}", fg="blue"))
        print(color(f"Total input tokens: {usage[1]:,}", fg="blue"))
        print(color(f"Total output tokens: {usage[2]:,}", fg="blue"))
        print(color(f"Total cost: ${usage[3]:.6f}", fg="blue"))
        
        # Display timing information if available (new format)
        if len(usage) > 4:
            print(color(f"Active time: {usage[4]:.2f}s", fg="blue"))
            print(color(f"Idle time: {usage[5]:.2f}s", fg="blue"))
                
        # Generate the replay with live printing
        replay_conversation(messages, replay_delay, usage)
        
        print(color("Replay completed successfully", fg="green"))
            
    except FileNotFoundError:
        print(color(f"Error: File {jsonl_file_path} not found", fg="red"))
        sys.exit(1)
    except json.JSONDecodeError:
        print(color(f"Error: Invalid JSON in {jsonl_file_path}", fg="red"))
        sys.exit(1)
    except Exception as e:
        print(color(f"Error: {str(e)}", fg="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()
