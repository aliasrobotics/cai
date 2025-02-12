"""
RAG (Retrieval Augmented Generation) utilities module for querying and adding data to vector databases.
"""

from typing import List, Dict
from cai.rag.vector_db import QdrantConnector
import os

# CTF BASED MEMORY
collection_name = os.getenv("CTF_NAME", "default")
def query_memory(query: str, top_k: int = 3, **kwargs) -> str:
    """
    Query memory to retrieve relevant context. From Previous CTFs executions.

    Args:
        query (str): The search query to find relevant documents
        top_k (int): Number of top results to return (default: 3)

    Returns:
        str: Retrieved context from the vector database, formatted as a string
            with the most relevant matches
    """
    try:
        qdrant = QdrantConnector()
        
        # First try semantic search
        results = qdrant.search(
            collection_name=collection_name,
            query_text=query,
            limit=top_k,
        )
        
        # If no results, fall back to retrieving all documents
            
        if not results:
            return "No documents found in memory."
            
        return results
        
    except Exception:
        return results

def add_to_memory(texts: str, **kwargs) -> str:
    """
    This is a persistent memory to add relevant context to our persistent memory.
    Use this function to add relevant context 

    Args:
        texts: relevant data to add to memory

    Returns:
        str: Status message indicating success or failure
    """
    try:
        qdrant = QdrantConnector()
        try:
            qdrant.create_collection(collection_name)
        except Exception as e:
            pass
        
        success = qdrant.add_points(
            collection_name=collection_name,
            texts=[texts],
            metadata=[{"CTF":"True"}]
        )
        
        if success:
            return f"Successfully added document to collection {collection_name}"
        return "Failed to add documents to vector database"
        
    except Exception as e:
        return f"Error adding documents to vector database: {str(e)}"
