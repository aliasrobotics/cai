"""
Longterm Memory agent module for processing historical messages through memory management.

OFFLINE LONG TERM MEMORY:

JSONL_FILE_PATH="logs/test_20250209_191542.jsonl" CTF_NAME="testctf" CTF_MODEL="qwen2.5:14b" python3 tools/2_JSONL_to_vectordb.py

Environment Variables:
    CTF_NAME: Name of the collection in Qdrant (required, e.g. "testctf")
    JSONL_FILE_PATH: Path to JSONL file containing historical messages
"""

import os
from typing import List, Dict
from cai.types import Agent
from cai.core import CAI
from cai.rag.memory.memory_manager import memory_agent
from cai.datarecorder import get_longest_messages

def JSONL_to_VectorDB(messages_file: str, max_iterations: int = 3) -> None:
    """
    Run the memory processor agent to process historical messages through memory management.
    
    Args:
        messages_file: Path to JSONL file containing historical messages
        max_iterations: Maximum number of message chunks to process per inference
    """

    messages = get_longest_messages(messages_file)
    if not messages:
        print("No messages found to memorize from")
        return
        
    filtered_messages = [m for m in messages if m["role"] not in ["system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to memorize from")
        return
        
    client = CAI(
        state_agent=None,
        force_until_flag=False,
        ctf_inside=False
    )
    
    for i in range(0, len(filtered_messages), max_iterations):
        chunk = filtered_messages[i:i + max_iterations]
        
        context = {
            "role": "user", 
            "content": "previous steps:\n" + 
                      "\n".join([str(m) for m in chunk])
        }
        
        response = client.run(
            agent=memory_agent,
            messages=[context],
            debug=2,
            max_turns=1,
            brief=False
        )
        
        print(f"Processed messages {i} to {i + len(chunk)}")
        
    print("Completed memorizeing from historical messages")

jsonl_file = os.getenv("JSONL_FILE_PATH")
if not jsonl_file:
    print("JSONL_FILE_PATH environment variable not set. Please set it to the path of your messages file.")
    print("Example: export JSONL_FILE_PATH=path/to/messages.jsonl")
    exit(1)
JSONL_to_VectorDB(messages_file=jsonl_file)