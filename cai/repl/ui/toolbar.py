"""
Toolbar module for the CAI REPL.
This module contains the toolbar-related functions for the CAI REPL.
"""

import datetime
import os
from prompt_toolkit.formatted_text import HTML

from cai.repl.utils.system import get_system_resources
from cai.repl.utils.ollama import get_ollama_status


def get_bottom_toolbar():
    """
    Return a toolbar with system information.
    This function is called by prompt_toolkit to get the bottom toolbar.
    """
    # Cache the toolbar data for 60 seconds to avoid excessive system calls
    if not hasattr(get_bottom_toolbar, "cache_time") or \
       not hasattr(get_bottom_toolbar, "cached_data") or \
       (datetime.datetime.now() - get_bottom_toolbar.cache_time).total_seconds() > 60:
        
        # Get system resources
        resources = get_system_resources()
        
        # Format CPU usage
        cpu_percent = resources['cpu']
        cpu_color = "green"
        if cpu_percent > 70:
            cpu_color = "yellow"
        if cpu_percent > 90:
            cpu_color = "red"
            
        # Format memory usage
        memory_percent = resources['memory']
        memory_color = "green"
        if memory_percent > 70:
            memory_color = "yellow"
        if memory_percent > 90:
            memory_color = "red"
            
        # Format disk usage
        disk_percent = resources['disk']
        disk_color = "green"
        if disk_percent > 70:
            disk_color = "yellow"
        if disk_percent > 90:
            disk_color = "red"
            
        # Check if HTB is active
        htb_active = os.environ.get("CAI_HTB", "false").lower() == "true"
        active_machine = ""
        if htb_active:
            active_machine = f"<b><style fg='cyan'>HTB:</style></b> {os.environ.get('CAI_HTB_MACHINE', 'Unknown')} | "
            
        # Check Ollama status
        ollama_available = get_ollama_status()
        if ollama_available:
            ollama_status = "<b><style fg='green'>Ollama: Available</style></b>"
        else:
            ollama_status = "<b><style fg='red'>Ollama: Unavailable</style></b>"
            
        # Build the toolbar string
        cached_data = (
            f'<b><style fg="yellow">CAI</style></b> | <style bg="green">Use ↑↓ for history</style> | '
            f'{active_machine}'
            f'<b><style fg="{cpu_color}">CPU:</style></b> {cpu_percent}% | '
            f'<b><style fg="{memory_color}">RAM:</style></b> {memory_percent}% | '
            f'<b><style fg="{disk_color}">Disk:</style></b> {disk_percent}% | '
            f'{ollama_status}'
        )
        
        # Cache the data
        get_bottom_toolbar.cache_time = datetime.datetime.now()
        get_bottom_toolbar.cached_data = cached_data
    else:
        # Use cached data
        cached_data = get_bottom_toolbar.cached_data
        
    return HTML(cached_data) 