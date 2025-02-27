"""
System utilities for the CAI REPL.
This module contains system-related utility functions for the CAI REPL.
"""

import os
import psutil
from cai.rag.vector_db import QdrantConnector


def get_system_resources():
    """Get system resource information."""
    try:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Get memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        return {
            'cpu': cpu_percent,
            'memory': memory_percent,
            'disk': disk_percent
        }
    except Exception:  # pylint: disable=broad-except
        return {
            'cpu': 0,
            'memory': 0,
            'disk': 0
        }


def get_memory_collections():
    """Get available memory collections."""
    try:
        db = QdrantConnector()
        collections = db.client.get_collections()
        return [collection.name for collection in collections.collections]
    except Exception:  # pylint: disable=broad-except
        return [] 