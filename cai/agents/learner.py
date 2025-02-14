"""
Learner agent module for processing historical messages through memory management.

OFFLINE LEARNER:

CTF_NAME="testctf" CTF_MODEL="qwen2.5:14b" python3 cai/agents/learner.py 

CTF_NAME equals to the name of collection in qdrant ESSENTIAL, use testctf for check working

"""

import os
from typing import List, Dict
from cai.types import Agent
from cai.core import CAI
from cai.rag.memory.memory_manager import memory_agent
from cai.datarecorder import get_longest_messages

def run_learner(messages_file: str, max_iterations: int = 3) -> None:
    """
    Run the learner agent to process historical messages through memory management.
    
    Args:
        messages_file: Path to JSONL file containing historical messages
        max_iterations: Maximum number of message chunks to process per inference
    """

    messages = get_longest_messages(messages_file)
    if not messages:
        print("No messages found to learn from")
        return
        
    filtered_messages = [m for m in messages if m["role"] not in ["system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to learn from")
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
        
    print("Completed learning from historical messages")

run_learner(messages_file="logs/test_20250209_191542.jsonl")