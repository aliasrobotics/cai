"""
Memory Manager module for handling RAG operations through an agent interface.

Usage:
    # Import and use memory agent
    from cai.rag.memory.memory_manager import memory_agent
    active_agent = transfer_to_memory_agent()

    # Run offline LONG TERM MEMORY
    JSONL_FILE_PATH="logs/test_20250209_191542.jsonl" \\
    CTF_NAME="testctf" CAI_MODEL="qwen2.5:14b" \\
    python3 cai/agents/longterm_memory.py

Environment Variables:
    CTF_NAME: Name of the collection in Qdrant (required)
    CTF_RAG_MEMORY: Enable RAG memory functionality
    CAI_MODEL: Model to use for embeddings (default: qwen2.5:14b)
    ONLINE_MEMORY: Enable online memory mode
    CTF_RAG_MEMORY_INTERVAL: Interval for memory long_term_memory
    JSONL_FILE_PATH: Path to JSONL file for historical messages
"""

import os
from cai.types import Agent
from cai.tools.llm_plugins.rag import add_to_memory_v2
from cai.rag.vector_db import get_previous_memory

# Get model from environment or use default
model = os.getenv('CAI_MODEL', "qwen2.5:14b")


def get_previous_steps(query: str) -> str:
    """
    Get the previous memory from the vector database.
    """
    return get_previous_memory(query=query)


memory_agent = Agent(
    model=model,
    name="Memory Manager",
    instructions=f"""INSTRUCTIONS:
        1. You are a specialized agent for resume CTF and managing the RAG
        2. Adding new information to the persistent memory
        3. When adding information, ensure it is relevant and formatted
        4. Always verify the success of memory operations
        5. Include all information from previous tool execution
        6. Be verbose with useful context and very detailed
        7. Include all ports, services and network information

        Consider the current CTF pentesting process step.
        Overwrite step if you find a better solution.
        Do not overwrite if not more conclusive than existing.

        Add only facts, not next steps or assumptions.
        Add evidential information from previous CTF steps.
        For conflicts, determine if memory update needed.

        {get_previous_steps("")}
        """,
    tool_choice="required",
    temperature=0,
    functions=[add_to_memory_v2],
    parallel_tool_calls=True
)
