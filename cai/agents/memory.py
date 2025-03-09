"""
Memory agent for CAI.

Leverages Retrieval Augmented Generation (RAG) to
store long-term memory experiences across security
exercises and re-utilizes such experiences as input
in other security exercises. Memories are stored in
a vector database and retrieved using a RAG pipeline.

The implementation follows established research in
Retrieval Augmented Generation (RAG) and episodic
memory systems, utilizing two complementary mechanisms:

1. Episodic Memory Store (episodic): Maintains chronological
   records of past interactions and their summaries,
   organized by distinct security exercises (CTFs)
   or targets within a document-oriented collection
   structure

2. Semantic Memory Store (semantic): Enables cross-exercise
   knowledge transfer through similarity-based
   retrieval across the full corpus of historical
   experiences, leveraging dense vector embeddings
   and approximate nearest neighbor search

The system supports two distinct learning approaches:

1. Offline Learning: Processes historical data from JSONL files
   in batch mode (@2_jsonl_to_memory.py), enabling efficient
   bulk ingestion of past experiences and their transformation
   into vector embeddings without real-time constraints and
   interference with the current CTF pentesting process.
   This allows for comprehensive analysis and optimization
   of the memory corpus.

2. Online Learning: Incrementally updates memory during live
   interactions (@core.py), incorporating new experiences
   in real-time at defined intervals (rag_interval). This
   enables continuous adaptation and immediate integration
   of new knowledge while maintaining system responsiveness.

Memory Architecture Diagrams
----------------------------

Episodic Memory (Per Security Target_n "Collection"):
+----------------+     +-------------------+    +------------------+     +----------------+  # noqa: E501  # pylint: disable=line-too-long
|   Raw Events   |     |       LLM        |     |     Vector       |     |   Collection   |  # noqa: E501  # pylint: disable=line-too-long
|  from Target   | --> | Summarization    | --> |   Embeddings     | --> |   "Target_1"   |  # noqa: E501  # pylint: disable=line-too-long
|                |     |                  |     |                  |     |                |  # noqa: E501  # pylint: disable=line-too-long
| [Event 1]      |     | Condenses and    |     | Converts text    |     | Summary 1      |  # noqa: E501  # pylint: disable=line-too-long
| [Event 2]      |     | extracts key     |     | into dense       |     | Summary 2      |  # noqa: E501  # pylint: disable=line-too-long
| [Event 3]      |     | information      |     | vectors          |     | Summary 3      |  # noqa: E501  # pylint: disable=line-too-long
+----------------+     +------------------+     +------------------+     +----------------+  # noqa: E501  # pylint: disable=line-too-long

Semantic Memory (Single Global Collection "_all_"):
+---------------+    +--------------+    +------------------+
| Target_1 Data |--->|              |    |"_all_" collection|
+---------------+    |              |    |                  |
                     |    Vector    |    | [Vector 1] CTF_A |
+---------------+    |  Embeddings  |--->| [Vector 2] CTF_B |
| Target_2 Data |--->|              |    | [Vector 3] CTF_A |
+---------------+    |              |    | [Vector 4] CTF_C |
                     |              |    |        ...       |
+---------------+    |              |    |                  |
| Target_N Data |--->|              |    |                  |
+---------------+    +--------------+    +------------------+


Environment Variables enabling the episodic memory store
--------------------------------------------------------

   CAI_MEMORY: Enables the use of memory functionality in CAI
    can adopt values:
    - episodic: for episodic memory store
    - semantic: for semantic memory store
    - all: for all memory stores
   CAI_MEMORY_COLLECTION: Name of the collection in Qdrant
    (required if CAI_MEMORY=episodic)
   CAI_MEMORY_ONLINE: Enables online learning (incremental updates)
   CAI_MEMORY_OFFLINE: Trigger offline learning (@2_jsonl_to_memory.py) when
    cai.client.run() finishes
"""

import os
from cai.types import Agent
from cai.tools.misc.rag import add_to_memory_semantic, add_to_memory_episodic
from cai.rag.vector_db import get_previous_memory

# Get model from environment or use default
model = os.getenv('CAI_MODEL', "qwen2.5:14b")


def get_previous_steps(query: str) -> str:
    """
    Get the previous memory from the vector database.
    """
    results = get_previous_memory(query=query)
    return results


ADD_MEMORY_PROMPT = f"""INSTRUCTIONS:
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
    """

QUERY_PROMPT = """INSTRUCTIONS:
    You are a specialized agent for CTF exercises and security assessments,
    managing the RAG system.

    Your role is to:
    1. Retrieve and analyze relevant historical information from memory
    2. Focus on security-critical details like:
        - Discovered vulnerabilities and exploits
        - Network topology and exposed services
        - Credentials and access patterns
        - System configurations and versions
        - Previous successful attack vectors
    3. Prioritize technical details that could be useful for exploitation
    4. Consider the full context of the security assessment
    5. Maintain operational security by handling sensitive data appropriately

    When processing queries:
    - Extract specific technical indicators
    - Identify relationships between different findings
    - Highlight potential security implications
    - Provide actionable intelligence for further exploitation

    Format responses to emphasize critical security information
    while maintaining clarity and precision.
    """

semantic_builder = Agent(
    model=model,
    name="Semantic_Builder",
    instructions=ADD_MEMORY_PROMPT,
    description="""Agent that stores semantic memories from security assessments
                   and CTF exercises in semantic format.""",
    tool_choice="required",
    temperature=0,
    functions=[add_to_memory_semantic],
    parallel_tool_calls=True
)


episodic_builder = Agent(
    model=model,
    name="Episodic_Builder",
    instructions=ADD_MEMORY_PROMPT,
    description="""Agent that stores episodic memories from security assessments
                   and CTF exercises in episodic format.""",
    tool_choice="required",
    temperature=0,
    functions=[add_to_memory_episodic],
    parallel_tool_calls=True
)

query_agent = Agent(
    model=model,
    name="Query_Agent",
    description="""Agent that queries the memory system to retrieve relevant 
                   historical information from previous security assessments
                   and CTF exercises.""",
    instructions=QUERY_PROMPT,
    tool_choice="required",
    temperature=0,
)
