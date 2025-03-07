"""
Longterm Memory agent module for processing historical messages through memory management.

Usage:
    JSONL_FILE_PATH="jsonl_path" CAI_MEMORY="episodic" CAI_MEMORY_COLLECTION="CTF_NAME|Target_Name" CAI_MODEL="qwen2.5:14b" python3 tools/2_jsonl_to_memory.py

Examples:
    ## episodic memory
        # Process historical messages from a JSONL file and store them in episodic memory
        JSONL_FILE_PATH="tests/agents/kiddoctf.jsonl" CAI_MEMORY_COLLECTION="kiddoctf" CAI_MEMORY="episodic" CAI_MODEL="gpt-4o" python3 tools/2_jsonl_to_memory.py
        # Solve same CTF enabling episodic memory
        CTF_NAME="kiddoctf" CTF_CHALLENGE="02 linux ii" CAI_MEMORY="episodic" CAI_MODEL="gpt-4o" CTF_INSIDE="True" CAI_MEMORY_COLLECTION="kiddoctf" python3 cai/cli.py
    
    ## semantic memory
        # Process historical messages from a JSONL file and store them in semantic memory
        JSONL_FILE_PATH="tests/agents/kiddoctf.jsonl" CAI_MEMORY="semantic" CAI_MODEL="gpt-4o" python3 tools/2_jsonl_to_memory.py
        
        # Solve same CTF enabling semantic memory
        CTF_NAME="kiddoctf" CTF_CHALLENGE="02 linux ii" CAI_MEMORY="semantic" CAI_MODEL="gpt-4o" CTF_INSIDE="True" python3 cai/cli.py


Environment Variables:
    CAI_MEMORY_COLLECTION: Name of the collection in Qdrant in CTFs
     is equal to the CTF_NAME (required, e.g. "bob", "172.16.0.14")
    JSONL_FILE_PATH: Path to JSONL file containing historical messages
    CAI_MEMORY: Memory type to use, either "episodic" or "semantic" (all not supported in this case)
    CAI_MEMORY_INTERVAL: Number of messages to process per inference
"""

import os
from cai.core import CAI
from cai.agents.memory import episodic_builder, semantic_builder
from cai.datarecorder import load_history_from_jsonl

def memory_loop(messages_file: str, max_iterations: int = 10) -> None:
    """
    Process historical messages through memory management by 
    chunking them into batches and storing them in either 
    episodic or semantic memory via a memory processor agent.

    The function loads messages from a JSONL file, 
    filters out system/user messages, and processes 
    the remaining assistant/tool messages in chunks. 
    For each chunk, it runs a memory agent that either:
    - Stores chronological records in episodic memory collections
    - Creates semantic embeddings for cross-exercise knowledge transfer

    Args:
        messages_file: Path to JSONL file containing historical messages to process
        max_iterations: Maximum number of messages to process per memory agent inference.
                       Messages are chunked into batches of this size to avoid 
                       overwhelming the agent. Defaults to 10.

    Environment Variables Used:
        CAI_MEMORY: Type of memory to use - must be either "episodic" or "semantic"
        CAI_MEMORY_COLLECTION: Name of collection to store memories in (e.g. CTF name)

    Returns:
        None. Messages are processed and stored in the configured memory store.
    """

    messages = load_history_from_jsonl(messages_file)
    if not messages:
        print("No messages found to memorize from")
        return
        
    filtered_messages = [m for m in messages if m["role"] not in ["system", "user"]]
    if not filtered_messages:
        print("No assistant or tool messages found to memorize from")
        return

    memory_type = os.getenv("CAI_MEMORY", "episodic")
    if memory_type == "episodic":
        memory_agent = episodic_builder
    elif memory_type == "semantic":
        memory_agent = semantic_builder
    else:
        print(f"Invalid memory type: {memory_type}. Must be either 'episodic' or 'semantic'")
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