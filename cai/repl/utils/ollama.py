"""
Ollama utilities for the CAI REPL.
This module contains Ollama-related utility functions for the CAI REPL.
"""

import requests


def get_ollama_status():
    """Check if Ollama is available."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=1)
        return response.status_code == 200
    except Exception:  # pylint: disable=broad-except
        return False


def get_ollama_models():
    """Get available Ollama models."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=1)
        if response.status_code == 200:
            data = response.json()
            # Handle newer Ollama versions
            if "models" in data:
                ollama_models = data["models"]
            # Handle older Ollama versions
            else:
                ollama_models = data.get("items", [])
                
            return [
                {
                    "name": model["name"],
                    "description": f"Local Ollama model - {model.get('size', 'Unknown size')}",
                    "provider": "ollama"
                }
                for model in ollama_models
            ]
        return []
    except Exception:  # pylint: disable=broad-except
        return [] 