"""
Module for the CAI REPL toolbar functionality.
"""
import datetime
import os
import socket
import platform
import requests
from prompt_toolkit.formatted_text import HTML
from cai.core import get_ollama_api_base

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
            ollama_api_base = get_ollama_api_base().replace("/v1", "")
            response = requests.get(f"{ollama_api_base}/api/tags", timeout=1)
            if response.status_code == 200:
                ollama_models = len(response.json().get("models", []))
                ollama_status = f"{ollama_models} models"
        except Exception:  # pylint: disable=broad-except
            pass

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
    if (now - toolbar_last_refresh[0]
        ).total_seconds() >= 60:  # Refresh every 60 seconds
        toolbar_last_refresh[0] = now
    return get_bottom_toolbar()
