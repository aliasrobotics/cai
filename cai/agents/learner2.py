"""
Learner module for directly adding historical messages to vector database.

Usage:
    JSONL_FILE_PATH="logs/test_20250209_191542.jsonl" CTF_NAME="testctf" python3 cai/agents/learner2.py

Environment Variables:
    CTF_NAME: Name of the collection in Qdrant (required, e.g. "testctf") 
    JSONL_FILE_PATH: Path to JSONL file containing historical messages
"""

import os
from typing import List, Dict
from cai.datarecorder import get_longest_messages
from cai.rag.vector_db import QdrantConnector

def run_learner(messages_file: str) -> None:
    """
    Process historical messages and add directly to vector database.
    
    Args:
        messages_file: Path to JSONL file containing historical messages
    """
    ctf_name = os.getenv("CTF_NAME")
    col_name = "raw_jsonl" # Collection name for raw JSONL files
    if not ctf_name:
        print("CTF_NAME environment variable not set")
        return

    db = QdrantConnector()
    
    db.create_collection(col_name)

    messages = get_longest_messages(messages_file)
    if not messages:
        print("No messages found to learn from")
        return

    filtered_messages = [m for m in messages if m["role"] not in ["system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to learn from")
        return
    # Combine all messages into one point
    combined_text = "\n".join([m["content"] for m in filtered_messages])
    
    metadata = {
        "challenge": f"{ctf_name}.jsonl",
        "messages": filtered_messages
    }

    success = db.add_points(
        id=0, # Single point with id 0
        collection_name=col_name,
        texts=[combined_text],
        metadata=[metadata]
    )

    if success:
        print(f"Added combined messages to vector DB")
    else:
        print("Failed to add messages")

    print("Completed adding messages to vector DB")

jsonl_file = os.getenv("JSONL_FILE_PATH")
if not jsonl_file:
    print("JSONL_FILE_PATH environment variable not set. Please set it to the path of your messages file.")
    print("Example: export JSONL_FILE_PATH=path/to/messages.jsonl")
    exit(1)

run_learner(messages_file=jsonl_file)


