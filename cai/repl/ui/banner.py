"""
Module for displaying the CAI banner and welcome message.
"""
# Standard library imports
import os
import glob
import logging
from configparser import ConfigParser

# Third-party imports
import requests  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error


def get_version():
    """Get the CAI version from setup.cfg."""
    version = "unknown"
    try:
        config = ConfigParser()
        config.read('setup.cfg')
        version = config.get('metadata', 'version')
    except Exception:  # pylint: disable=broad-except
        logging.warning("Could not read version from setup.cfg")
    return version


def get_supported_models_count():
    """Get the count of supported models (with function calling)."""
    try:
        # Fetch model data from LiteLLM repository
        response = requests.get(
            "https://raw.githubusercontent.com/BerriAI/litellm/main/"
            "model_prices_and_context_window.json",
            timeout=2
        )

        if response.status_code == 200:
            model_data = response.json()

            # Count models with function calling support
            function_calling_models = sum(
                1 for model_info in model_data.values()
                if model_info.get("supports_function_calling", False)
            )

            # Try to get Ollama models count
            try:
                ollama_api_base = os.getenv(
                    "OLLAMA_API_BASE",
                    "http://host.docker.internal:8000/v1"
                )
                ollama_response = requests.get(
                    f"{ollama_api_base.replace('/v1', '')}/api/tags",
                    timeout=1
                )

                if ollama_response.status_code == 200:
                    ollama_data = ollama_response.json()
                    ollama_models = len(
                        ollama_data.get(
                            'models', ollama_data.get('items', [])
                        )
                    )
                    return function_calling_models + ollama_models
            except Exception:  # pylint: disable=broad-except
                logging.debug("Could not fetch Ollama models")
                # Continue without Ollama models

            return function_calling_models
    except Exception:  # pylint: disable=broad-except
        logging.warning("Could not fetch model data from LiteLLM")

    # Default count if we can't fetch the data
    return "many"


def count_tools():
    """Count the number of tools in the CAI framework."""
    try:
        # Count Python files in the tools directory
        tool_files = glob.glob("cai/tools/**/*.py", recursive=True)
        # Exclude __init__.py and other non-tool files
        tool_files = [
            f for f in tool_files
            if not f.endswith("__init__.py") and not f.endswith("__pycache__")
        ]
        return len(tool_files)
    except Exception:  # pylint: disable=broad-except
        logging.warning("Could not count tools")
        return "50+"


def count_agents():
    """Count the number of agents in the CAI framework."""
    try:
        # Count Python files in the agents directory
        agent_files = glob.glob("cai/agents/**/*.py", recursive=True)
        # Exclude __init__.py and other non-agent files
        agent_files = [
            f for f in agent_files
            if not f.endswith("__init__.py") and not f.endswith("__pycache__")
        ]
        return len(agent_files)
    except Exception:  # pylint: disable=broad-except
        logging.warning("Could not count agents")
        return "20+"


def count_ctf_memories():
    """Count the number of CTF memories in the CAI framework."""
    # This is a placeholder - adjust the actual counting logic based on your
    # framework structure
    return "100+"


def display_banner(console: Console):
    """
    Display a stylized CAI banner with Alias Robotics corporate colors.

    Args:
        console: Rich console for output
    """
    version = get_version()

    # Original banner with Alias Robotics colors (blue and white)
    # Use noqa to ignore line length for the ASCII art
    banner = f"""
[bold blue]                CCCCCCCCCCCCC      ++++++++   ++++++++      IIIIIIIIII
[bold blue]             CCC::::::::::::C  ++++++++++       ++++++++++  I::::::::I
[bold blue]           CC:::::::::::::::C ++++++++++         ++++++++++ I::::::::I
[bold blue]          C:::::CCCCCCCC::::C +++++++++    ++     +++++++++ II::::::II
[bold blue]         C:::::C       CCCCCC +++++++     +++++     +++++++   I::::I
[bold blue]        C:::::C                +++++     +++++++     +++++    I::::I
[bold blue]        C:::::C                ++++                   ++++    I::::I
[bold blue]        C:::::C                 ++                     ++     I::::I
[bold blue]        C:::::C                  +   +++++++++++++++   +      I::::I
[bold blue]        C:::::C                    +++++++++++++++++++        I::::I
[bold blue]        C:::::C                     +++++++++++++++++         I::::I
[bold blue]         C:::::C       CCCCCC        +++++++++++++++          I::::I
[bold blue]          C:::::CCCCCCCC::::C         +++++++++++++         II::::::II
[bold blue]           CC:::::::::::::::C           +++++++++           I::::::::I
[bold blue]             CCC::::::::::::C             +++++             I::::::::I
[bold blue]                CCCCCCCCCCCCC               ++              IIIIIIIIII

[bold blue]                              Cybersecurity AI (CAI), v{version}[/bold blue]
[white]                                  Bug bounty-ready AI[/white]
    """

    console.print(banner)

    # # Create a table showcasing CAI framework capabilities
    # #
    # # reconsider in the future if necessary
    # display_framework_capabilities(console)


def display_framework_capabilities(console: Console):
    """
    Display a table showcasing CAI framework capabilities in Metasploit style.

    Args:
        console: Rich console for output
    """
    # Create the main table
    table = Table(
        title="",
        box=None,
        show_header=False,
        show_edge=False,
        padding=(0, 2)
    )

    table.add_column("Category", style="bold cyan")
    table.add_column("Count", style="bold yellow")
    table.add_column("Description", style="white")

    # Add rows for different capabilities
    table.add_row(
        "AI Models",
        str(get_supported_models_count()),
        "Supported AI models including GPT-4, Claude, Llama"
    )

    # table.add_row(
    #     "Tools",
    #     str(count_tools()),
    #     "Cybersecurity tools for reconnaissance and scanning"
    # )

    table.add_row(
        "Agents",
        str(count_agents()),
        "Specialized AI agents for different cybersecurity tasks"
    )

    # Add the table to a panel for better visual separation
    capabilities_panel = Panel(
        table,
        title="[bold blue]CAI Features[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )

    console.print(capabilities_panel)


def display_welcome_tips(console: Console):
    """
    Display welcome message with tips for using the REPL.

    Args:
        console: Rich console for output
    """
    console.print(Panel(
        "[white]• Use arrow keys ↑↓ to navigate command history[/white]\n"
        "[white]• Press Tab for command completion[/white]\n"
        "[white]• Type /help for available commands[/white]\n"
        "[white]• Type /help aliases for command shortcuts[/white]\n"
        "[white]• Press Ctrl+L to clear the screen[/white]\n"
        "[white]• Press Esc+Enter to add a new line (multiline input)[/white]\n"
        "[white]• Press Ctrl+C to exit[/white]",
        title="Quick Tips",
        border_style="blue"
    ))
