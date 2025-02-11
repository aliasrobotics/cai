"""
Memory Manager module for handling RAG operations through an agent interface.
"""

import os
from cai.types import Agent
from cai.tools.llm_plugins.rag import query_memory, add_to_memory

# Get model from environment or use default
model = os.getenv('CTF_MODEL', "qwen2.5:14b")

memory_agent = Agent(
    model=model,
    name="Memory Manager",
    instructions="""INSTRUCTIONS:
        1. You are a specialized agent for managing the RAG (Retrieval Augmented Generation) system
        2. Your primary functions are:
           - Querying the vector database for relevant context
           - Adding new information to the persistent memory
        3. When querying, be precise with your search terms
        4. When adding information, ensure it is relevant and properly formatted
        5. Do not be verbose, focus on executing the memory operations efficiently
        6. Always verify the success of memory operations""",
    functions=[
        query_memory,
        add_to_memory
    ]
)

