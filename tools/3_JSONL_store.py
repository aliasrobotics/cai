"""
Longterm Memory module for directly adding historical messages to vector database.

Usage:
    JSONL_FILE_PATH="logs/test_20250209_191542.jsonl" CTF_NAME="testctf" python3 tools/3_JSONL_store.py

Environment Variables:
    CTF_NAME: Name of the collection in Qdrant (required, e.g. "testctf")
    JSONL_FILE_PATH: Path to JSONL file containing historical messages
"""

import os
import json
from typing import List, Dict
from cai.datarecorder import get_longest_messages


def storage_run(messages_file: str) -> None:
    """
    Process historical messages and save them as a JSON file in a designated folder.

    The resulting JSON file, containing only the assistant and tool messages
    (i.e. excluding those with role 'system' and 'user'), can later be used
    as input for get_chat_comp@core.py.

    Args:
        messages_file: Path to JSONL file containing historical messages.
    """
    ctf_name = os.getenv("CTF_NAME")
    if not ctf_name:
        print("CTF_NAME environment variable not set")
        return

    messages = get_longest_messages(messages_file)
    if not messages:
        print("No messages found to memorize from")
        return

    # Remove messages with role 'system' and 'user'
    filtered_messages = [m for m in messages if m.get("role") not in [
        "system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to memorize from")
        return

    # Create output folder for saving the JSON file
    output_dir = "best_runs"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{ctf_name}_messages.json")

    # Save the filtered messages into a JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(filtered_messages, f, ensure_ascii=False, indent=2)

    print(f"Filtered messages saved to {output_file}")


def get_json_messages(messages_file: str) -> List[Dict]:
    """
    Process historical messages and return them as a list of message objects
    for appending to the history in get_chat_completion.

    This function filters out 'system' and 'user' messages, returning only the
    assistant and tool messages.

    Args:
        messages_file: Path to JSONL file containing historical messages.

    Returns:
        list: A list of message objects, each with keys 'role' and 'content'.
              If no valid messages are found, returns an empty list.
    """
    messages = get_longest_messages(messages_file)
    if not messages:
        print("No messages found to memorize from")
        return []

    filtered_messages = [m for m in messages if m.get("role") not in [
        "system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to memorize from")
        return []

    return filtered_messages

jsonl_file = os.getenv("JSONL_FILE_PATH")
if not jsonl_file:
    print("JSONL_FILE_PATH environment variable not set. Please set it to the path of your messages file.")
    print("Example: export JSONL_FILE_PATH=path/to/messages.jsonl")
    exit(1)

storage_run(messages_file=jsonl_file)
