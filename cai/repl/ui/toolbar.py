"""
Module for the CAI REPL toolbar functionality.
"""
import datetime
import os
import socket
import platform
import requests  # pylint: disable=import-error
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error

# Variable to track when to refresh the toolbar
toolbar_last_refresh = [datetime.datetime.now()]


def get_bottom_toolbar():
    """Get the bottom toolbar with system information."""
    try:
        # Get local IP addresses
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)

        # Get OS information
        os_name = platform.system()
        os_version = platform.release()

        # Get Ollama information
        ollama_status = "unavailable"
        try:
            # Get Ollama models with a short timeout to prevent hanging
            api_base = os.getenv(
                "OLLAMA_API_BASE",
                "http://host.docker.internal:8000/v1")
            response = requests.get(
                f"{api_base.replace('/v1', '')}/api/tags", timeout=1)

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
            # This is acceptable as Ollama is optional and we don't want to
            # disrupt the user experience if it's not running
            ollama_status = "unavailable"

        # Get current time for the toolbar refresh indicator
        current_time = datetime.datetime.now().strftime("%H:%M")

        return HTML(
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
            f"<ansigray>{current_time}</ansigray>"
        )
    except Exception:  # pylint: disable=broad-except
        return ""


def get_toolbar_with_refresh():
    """Get toolbar with refresh control (once per minute)."""
    now = datetime.datetime.now()
    seconds_elapsed = (now - toolbar_last_refresh[0]).total_seconds()
    if seconds_elapsed >= 60:  # Refresh every 60 seconds
        toolbar_last_refresh[0] = now
    return get_bottom_toolbar()
