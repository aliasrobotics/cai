"""
Ollama utility functions for the CAI module.
This module contains Ollama-related utility functions for the CAI module.
"""

import os


def get_ollama_api_base():
    """Get the Ollama API base URL.

    Returns:
        str: The Ollama API base URL, defaulting to host.docker.internal:8000
    """
    # Default to host.docker.internal:8000 for Docker environments
    return os.getenv("OLLAMA_API_BASE", "http://host.docker.internal:8000/v1") 