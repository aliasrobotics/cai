"""
Utility functions for the CAI REPL.
This module contains utility functions for the CAI REPL.
"""

from cai.repl.utils.ollama import (
    get_ollama_models,
    get_ollama_status
)
from cai.repl.utils.system import (
    get_system_resources,
    get_memory_collections
)

__all__ = [
    'get_ollama_models',
    'get_ollama_status',
    'get_system_resources',
    'get_memory_collections'
] 