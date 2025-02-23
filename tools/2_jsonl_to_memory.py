"""
Longterm Memory agent module for processing historical messages through memory management.

Usage:
    JSONL_FILE_PATH="jsonl_path" CAI_MEMORY_COLLECTION="CTF_NAME|Target_Name" CAI_MODEL="qwen2.5:14b" python3 tools/2_jsonl_to_memory.py

Example:
    JSONL_FILE_PATH="tests/agents/kiddoctf.jsonl" CAI_MEMORY_COLLECTION="kiddoctf" CAI_MEMORY="Episodic" CAI_MODEL="qwen2.5:14b" python3 tools/2_jsonl_to_memory.py

Environment Variables:
    CAI_MEMORY_COLLECTION: Name of the collection in Qdrant in CTFs
     is equal to the CTF_NAME (required, e.g. "bob", "172.16.0.14")
    JSONL_FILE_PATH: Path to JSONL file containing historical messages
    CAI_MEMORY: Memory type to use, either "Episodic" or "Semantic" (all not supported in this case)
    CAI_MEMORY_INTERVAL: Number of messages to process per inference
"""

import os
from cai.core import CAI
from cai import episodic_builder, semantic_builder
from cai.datarecorder import load_history_from_jsonl

def memory_loop(messages_file: str, max_iterations: int = 10    ) -> None:
    """
    Run the memory processor agent to process historical messages through memory management.
    
    Args:
        messages_file: Path to JSONL file containing historical messages
        max_iterations: Maximum number of message chunks to process per inference
    """

    messages = load_history_from_jsonl(messages_file)
    if not messages:
        print("No messages found to memorize from")
        return
        
    filtered_messages = [m for m in messages if m["role"] not in ["system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to memorize from")
        return

    memory_type = os.getenv("CAI_MEMORY", "Episodic")
    if memory_type == "Episodic":
        memory_agent = episodic_builder
    elif memory_type == "Semantic":
        memory_agent = semantic_builder
    else:
        print(f"Invalid memory type: {memory_type}. Must be either 'Episodic' or 'Semantic'")
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
            "content": "OVERWRITE STEPS IF REPEATED AND WRONG DATA:\nprevious steps:\n" + 
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
memory_loop(messages_file=jsonl_file, max_iterations=os.getenv("CAI_MEMORY_INTERVAL", 10))