"""
Memory Manager module for handling RAG operations through an agent interface.

Usage:
    # Import and use memory agent
    from cai.rag.memory.memory_manager import memory_agent
    active_agent = transfer_to_memory_agent()

    # Run with online learning
    # Executes memory learning every 5 turns:
    CTF_NAME="hackableII" CTF_RAG_MEMORY="True" CTF_MODEL="o3-mini" \
    ONLINE_LEARNER="True" CTF_INSIDE="False" CTF_HINTS="False" python3 cai/cli.py

    # Run with custom learning interval
    # Executes memory learning every 3 turns:
    CTF_NAME="hackableII" CTF_RAG_MEMORY="True" CTF_MODEL="o3-mini" \
    CTF_RAG_MEMORY_INTERVAL="3" ONLINE_LEARNER="False" CTF_INSIDE="False" \
    CTF_HINTS="False" python3 cai/cli.py

    # Run offline learner
    JSONL_FILE_PATH="logs/test_20250209_191542.jsonl" CTF_NAME="testctf" CTF_MODEL="qwen2.5:14b" python3 cai/agents/learner.py

Environment Variables:
    CTF_NAME: Name of the collection in Qdrant (required)
    CTF_RAG_MEMORY: Enable RAG memory functionality
    CTF_MODEL: Model to use for embeddings (default: qwen2.5:14b)
    ONLINE_LEARNER: Enable online learning mode
    CTF_RAG_MEMORY_INTERVAL: Interval for memory learning (only works with ONLINE_LEARNER=False)
    JSONL_FILE_PATH: Path to JSONL file containing historical messages (only works in `learner.py`)
"""

import os
from cai.types import Agent
from cai.tools.llm_plugins.rag import query_memory, add_to_memory
from cai.util import get_previous_memory 

# Get model from environment or use default
model = os.getenv('CTF_MODEL', "qwen2.5:14b")

def get_previous_steps(query: str) -> str:
    """
    Get the previous memory from the vector database.
    """
    return get_previous_memory(query=query)

memory_agent = Agent(
    model=model,
    name="Memory Manager",
    instructions=f"""INSTRUCTIONS:
        1. You are a specialized agent for resume CTF and managing the RAG (Retrieval Augmented Generation) system
        2. Adding new information to the persistent memory
        3. When adding information, ensure it is relevant and properly formatted
        4. Always verify the success of memory operations
        5. Ensure that you include all the information from the previous tool execution, anything that can be useful for the context of the next execution, you have to be verbose in terms of useful context, you have to be very detailed
        6. Incluide all ports, services and all network information and network state
        
        Consider the current step of the CTF pentesting process being performed. Overwrite the step if you believe a better solution has been found for that step. Do not overwrite the step if it is not more conclusive than what already exists

        Add only facts, not next steps or assumptions, evidential information from previous CTF steps. If it conflicts with current memory, determine if memory update is necessary or not

        {get_previous_steps("")}
        """,
        tool_choice="required",
        temperature=0,
    functions=[
        add_to_memory
    ],
    parallel_tool_calls=True
)

