"""
Module for the CAI REPL toolbar functionality.
"""
import datetime
import os
import socket
import platform
import threading
import time
from functools import lru_cache
import requests  # pylint: disable=import-error
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error

# Variable to track when to refresh the toolbar
toolbar_last_refresh = [datetime.datetime.now()]

# Cache for toolbar data
toolbar_cache = {
    'html': "",
    'last_update': datetime.datetime.now(),
    'refresh_interval': 60  # Refresh every 60 seconds
}

# Cache for system information that rarely changes
system_info = {
    'ip_address': None,
    'os_name': None,
    'os_version': None
}


@lru_cache(maxsize=1)
def get_system_info():
    """Get system information that rarely changes (cached)."""
    if not system_info['ip_address']:
        try:
            # Get local IP addresses
            hostname = socket.gethostname()
            system_info['ip_address'] = socket.gethostbyname(hostname)
            
            # Get OS information
            system_info['os_name'] = platform.system()
            system_info['os_version'] = platform.release()
        except Exception:  # pylint: disable=broad-except
            system_info['ip_address'] = "unknown"
            system_info['os_name'] = "unknown"
            system_info['os_version'] = "unknown"
    
    return system_info


def update_toolbar_in_background():
    """Update the toolbar cache in a background thread."""
    try:
        # Get system info (cached)
        sys_info = get_system_info()
        ip_address = sys_info['ip_address']
        os_name = sys_info['os_name']
        os_version = sys_info['os_version']

        # Get Ollama information
        ollama_status = "unavailable"
        try:
            # Get Ollama models with a short timeout to prevent hanging
            api_base = os.getenv(
                "OLLAMA_API_BASE",
                "http://host.docker.internal:8000/v1")
            response = requests.get(
                f"{api_base.replace('/v1', '')}/api/tags", timeout=0.5)

            if response.status_code == 200:
                data = response.json()
                if 'models' in data:
                    ollama_models = len(data['models'])
                else:
                    # Fallback for older Ollama versions
                    ollama_models = len(data.get('items', []))
                ollama_status = f"{ollama_models} models"
        except Exception:  # pylint: disable=broad-except
            # Silently fail if Ollama is not available
            ollama_status = "unavailable"

        # Get current time for the toolbar refresh indicator
        current_time = datetime.datetime.now().strftime("%H:%M")

        # Add timezone information to show it's local time
        timezone_name = datetime.datetime.now().astimezone().tzname()
        current_time_with_tz = f"{current_time} {timezone_name}"

        # Update the cache
        toolbar_cache['html'] = HTML(
            f"<ansired><b>IP:</b></ansired> <ansigreen>{
                ip_address}</ansigreen> | "
            f"<ansiyellow><b>OS:</b></ansiyellow> <ansiblue>{
                os_name} {os_version}</ansiblue> | "
            f"<ansicyan><b>Ollama:</b></ansicyan> <ansimagenta>{
                ollama_status}</ansimagenta> | "
            f"<ansiyellow><b>Model:</b></ansiyellow> <ansigreen>{
                os.getenv('CAI_MODEL', 'default')}</ansigreen> | "
            f"<ansicyan><b>Max Turns:</b></ansicyan> <ansiblue>{
                os.getenv('CAI_MAX_TURNS', 'inf')}</ansiblue> | "
            f"<ansigray>{current_time_with_tz}</ansigray>"
        )
        toolbar_cache['last_update'] = datetime.datetime.now()
    except Exception:  # pylint: disable=broad-except
        # If there's an error, set a simple toolbar
        toolbar_cache['html'] = HTML(
            f"<ansigray>{datetime.datetime.now().strftime('%H:%M')}</ansigray>"
        )


def get_bottom_toolbar():
    """Get the bottom toolbar with system information (cached)."""
    # If the toolbar is empty, initialize it
    if not toolbar_cache['html']:
        # Create a simple initial toolbar while the full one loads
        current_time = datetime.datetime.now().strftime("%H:%M")
        timezone_name = datetime.datetime.now().astimezone().tzname()
        toolbar_cache['html'] = HTML(
            f"<ansigray>Loading system information... {current_time} {timezone_name}</ansigray>"
        )
        # Start background update
        threading.Thread(
            target=update_toolbar_in_background,
            daemon=True
        ).start()
    
    # Return the cached toolbar HTML
    return toolbar_cache['html']


def get_toolbar_with_refresh():
    """Get toolbar with refresh control (once per minute)."""
    now = datetime.datetime.now()
    seconds_elapsed = (now - toolbar_cache['last_update']).total_seconds()
    
    # Check if we need to refresh the toolbar
    if seconds_elapsed >= toolbar_cache['refresh_interval']:
        # Start a background thread to update the toolbar
        threading.Thread(
            target=update_toolbar_in_background,
            daemon=True
        ).start()
    
    # Always return the cached version immediately
    return get_bottom_toolbar()


# Initialize the toolbar on module import
threading.Thread(
    target=update_toolbar_in_background,
    daemon=True
).start()
