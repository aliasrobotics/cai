"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""
# Standard library imports
import json
import os
import sys
import subprocess  # nosec B404
import signal
from configparser import ConfigParser
from importlib.resources import files
from typing import Optional, List
from pathlib import Path
import datetime
import time
import asyncio
import threading

# Third party imports
from mako.template import Template  # pylint: disable=import-error
from prompt_toolkit import prompt, PromptSession  # pylint: disable=import-error
from prompt_toolkit.completion import (  # pylint: disable=import-error
    Completer, Completion
)
from prompt_toolkit.history import FileHistory  # pylint: disable=import-error
from prompt_toolkit.auto_suggest import (  # pylint: disable=import-error
    AutoSuggestFromHistory
)
from prompt_toolkit.key_binding import (  # pylint: disable=import-error
    KeyBindings
)
from prompt_toolkit.styles import Style  # pylint: disable=import-error
from prompt_toolkit.formatted_text import HTML  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.progress import (  # pylint: disable=import-error
    Progress, SpinnerColumn, TextColumn
)
from rich.text import Text  # pylint: disable=import-error
# Local imports
from cai import (
    is_caiextensions_report_available,
    is_caiextensions_platform_available
)
from cai.core import CAI  # pylint: disable=import-error
from cai.rag.vector_db import QdrantConnector
import requests
import psutil

if is_caiextensions_platform_available():
    from caiextensions.platform.base import (  # pylint: disable=ungrouped-imports,line-too-long,import-error # noqa: E501
        platform_manager
    )

# Global variables
client = None  # pylint: disable=invalid-name
console = Console()

# Command descriptions for better help and autocompletion
COMMAND_DESCRIPTIONS = {
    "/memory": "Manage memory collections for episodic and semantic memory",
    "/help": "Display help information about commands and features",
    "/graph": "Visualize the agent interaction graph",
    "/exit": "Exit the CAI REPL",
    "/shell": "Execute shell commands in the current environment",
    "/env": "Display environment variables and their values",
    "/platform": "Interact with platform-specific features",
    "/kill": "Terminate active processes or sessions",
    "/model": "View or change the current LLM model",
    "/turns": "View or change the maximum number of turns"
}

# Subcommand descriptions for better help and autocompletion
SUBCOMMAND_DESCRIPTIONS = {
    "/memory list": "List all available memory collections",
    "/memory load": "Load a specific memory collection",
    "/memory delete": "Delete a specific memory collection",
    "/memory create": "Create a new memory collection",
    "/help memory": "Show help for memory commands",
    "/help agents": "Show help for agent-related features",
    "/help graph": "Show help for graph visualization",
    "/help platform": "Show help for platform-specific features",
    "/help shell": "Show help for shell command execution",
    "/help env": "Show help for environment variables",
    "/help aliases": "Show all command aliases",
    "/help model": "Show help for model selection",
    "/help turns": "Show help for managing turns"
}

# Command aliases for convenience
COMMAND_ALIASES = {
    "/h": "/help",      # Display help information
    "/q": "/exit",      # Exit the application
    "/quit": "/exit",   # Exit the application
    "/k": "/kill",      # Terminate active sessions
    "/e": "/env",       # Show environment variables
    "/g": "/graph",     # Display graph
    "/m": "/memory",    # Access memory
    "/p": "/platform",  # Interact with platform/s
    # shell commands
    "/s": "/shell",     # Execute shell commands
    "$": "/shell",      # Execute shell commands  # NOTE: research why this doesn't work
    # model and turns commands
    "/mod": "/model",   # Change the model
    "/t": "/turns",     # Change max turns
}


def get_platform_commands():
    """Get commands for all registered platforms."""
    if not is_caiextensions_platform_available():
        return ["No platform extensions installed"]
    platforms = platform_manager.list_platforms()
    return [
        "list",  # Para listar plataformas disponibles
        *[f"{platform} {cmd}"
          for platform in platforms
          for cmd in platform_manager.get_platform(platform).get_commands()]
    ]


COMMANDS = {
    "/memory": [
        "list",
        "load",
        "delete",
        "create"
    ],
    "/help": [
        "memory",
        "agents",
        "graph",
        "platform",
        "shell",
        "env",
        "aliases",
        "model",
        "turns"
    ],
    "/graph": [],
    "/exit": [],
    "/shell": [],
    "/env": [],
    "/platform":
        get_platform_commands(),
    "/kill": [],
    "/model": [],
    "/turns": []
}


def handle_memory_list():
    """Handle /memory list command"""
    try:
        db = QdrantConnector()
        collections = db.client.get_collections()

        print("\nAvailable Memory Collections:")
        print("-----------------------------")

        for collection in collections.collections:
            name = collection.name
            info = db.client.get_collection(name)
            points_count = db.client.count(collection_name=name).count

            print(f"\nCollection: {color(name, fg='green', bold=True)}")
            print(f"Vectors: {points_count}")
            print(f"Vector Size: {info.config.params.vectors.size}")
            print(f"Distance: {info.config.params.vectors.distance}")

        print("\n")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error listing collections: {e}")
        return False


def handle_memory_delete(collection_name):
    """Handle /memory delete command"""
    try:
        db = QdrantConnector()
        db.client.delete_collection(collection_name=collection_name)
        print(
            f"\nDeleted collection: {
                color(
                    collection_name,
                    fg='red',
                    bold=True)}\n")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error deleting collection: {e}")
        return False


def handle_memory_load(collection_name):
    """Handle /memory load command"""
    try:
        os.environ['CAI_MEMORY_COLLECTION'] = collection_name
        if collection_name != "_all_":
            os.environ['CAI_MEMORY'] = "episodic"
        elif collection_name == "_all_":
            os.environ['CAI_MEMORY'] = "semantic"
        print(
            f"\nMemory collection set to: {
                color(
                    collection_name,
                    fg='green',
                    bold=True)}\n")
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error setting memory collection: {e}")
        return False


def handle_memory_create(collection_name, distance="Cosine"):
    """Handle /memory create command"""
    try:
        db = QdrantConnector()
        success = db.create_collection(
            collection_name=collection_name,
            distance=distance)

        if success:
            print(
                f"\nCreated collection: {
                    color(
                        collection_name,
                        fg='green',
                        bold=True)}\n")
            return True
        else:
            print(f"Error creating collection: {collection_name}")
            return False
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error creating collection: {e}")
        return False


def handle_help_memory():
    """Show help for memory commands with rich formatting."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    # Create a styled header
    header = Text("Memory Command Help", style="bold yellow")
    console.print(Panel(header, border_style="yellow"))

    # Usage table
    usage_table = Table(
        title="Usage",
        show_header=True,
        header_style="bold white")
    usage_table.add_column("Command", style="yellow")
    usage_table.add_column("Description", style="white")

    usage_table.add_row(
        "/memory list",
        "Display all available memory collections")
    usage_table.add_row(
        "/memory load <collection>",
        "Set the active memory collection")
    usage_table.add_row(
        "/memory delete <collection>",
        "Delete a memory collection")
    usage_table.add_row(
        "/memory create <collection>",
        "Create a new memory collection")
    usage_table.add_row("/m", "Alias for /memory")

    console.print(usage_table)

    # Examples table
    examples_table = Table(
        title="Examples",
        show_header=True,
        header_style="bold cyan")
    examples_table.add_column("Example", style="cyan")
    examples_table.add_column("Description", style="white")

    examples_table.add_row("/memory list", "List all available collections")
    examples_table.add_row(
        "/memory load _all_",
        "Load the semantic memory collection")
    examples_table.add_row(
        "/memory load my_ctf",
        "Load the episodic memory for 'my_ctf'")
    examples_table.add_row(
        "/memory create new_collection",
        "Create a new collection named 'new_collection'")
    examples_table.add_row(
        "/memory delete old_collection",
        "Delete the collection named 'old_collection'")

    console.print(examples_table)

    # Collection types table
    types_table = Table(
        title="Collection Types",
        show_header=True,
        header_style="bold green")
    types_table.add_column("Type", style="green")
    types_table.add_column("Description", style="white")

    types_table.add_row("_all_", "Semantic memory across all CTFs")
    types_table.add_row("<CTF_NAME>", "Episodic memory for a specific CTF")
    types_table.add_row("<custom_name>", "Custom memory collection")

    console.print(types_table)

    # Notes panel
    notes = Panel(
        Text.from_markup(
            "• Memory collections are stored in the Qdrant vector database\n"
            "• The active collection is stored in the CAI_MEMORY_COLLECTION environment variable\n"
            "• Episodic memory is used for specific CTFs or tasks\n"
            "• Semantic memory (_all_) is used across all CTFs\n"
            "• Memory is used to provide context to the agent"
        ),
        title="Notes",
        border_style="yellow"
    )
    console.print(notes)

    return True


def handle_help():
    """Handle /help command with improved formatting and details."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    # Create a styled header
    header = Text("CAI Command Reference", style="bold cyan")
    console.print(Panel(header, border_style="cyan"))

    # Memory Commands Table
    memory_table = Table(
        title="Memory Commands",
        show_header=True,
        header_style="bold yellow")
    memory_table.add_column("Command", style="yellow")
    memory_table.add_column("Alias", style="green")
    memory_table.add_column("Description", style="white")

    memory_table.add_row(
        "/memory list",
        "/m list",
        "List all memory collections")
    memory_table.add_row(
        "/memory load <collection>",
        "/m load <collection>",
        "Load a memory collection")
    memory_table.add_row(
        "/memory delete <collection>",
        "/m delete <collection>",
        "Delete a memory collection")
    memory_table.add_row(
        "/memory create <collection>",
        "/m create <collection>",
        "Create a new memory collection")

    # Collection types info
    collection_info = Text()
    collection_info.append("\nCollection Types:\n", style="bold")
    collection_info.append("• CTF_NAME", style="yellow")
    collection_info.append(
        " - Episodic memory for a specific CTF (e.g. ", style="white")
    collection_info.append("baby_first", style="bold white")
    collection_info.append(")\n", style="white")
    collection_info.append("• _all_", style="yellow")
    collection_info.append(" - Semantic memory across all CTFs", style="white")

    console.print(memory_table)
    console.print(collection_info)

    # Graph Commands Table
    graph_table = Table(
        title="Graph Commands",
        show_header=True,
        header_style="bold blue")
    graph_table.add_column("Command", style="blue")
    graph_table.add_column("Alias", style="green")
    graph_table.add_column("Description", style="white")

    graph_table.add_row(
        "/graph",
        "/g",
        "Show the graph of the current memory collection")
    console.print(graph_table)

    # Shell Commands Table
    shell_table = Table(
        title="Shell Commands",
        show_header=True,
        header_style="bold green")
    shell_table.add_column("Command", style="green")
    shell_table.add_column("Alias", style="green")
    shell_table.add_column("Description", style="white")

    shell_table.add_row(
        "/shell <command>",
        "/s <command>",
        "Execute a shell command (can be interrupted with CTRL+C)")
    console.print(shell_table)

    # Environment Commands Table
    env_table = Table(
        title="Environment Commands",
        show_header=True,
        header_style="bold cyan")
    env_table.add_column("Command", style="cyan")
    env_table.add_column("Alias", style="green")
    env_table.add_column("Description", style="white")

    env_table.add_row(
        "/env",
        "/e",
        "Display environment variables (CAI_* and CTF_*)")
    console.print(env_table)

    # Model Commands Table
    model_table = Table(
        title="Model Commands",
        show_header=True,
        header_style="bold magenta")
    model_table.add_column("Command", style="magenta")
    model_table.add_column("Alias", style="green")
    model_table.add_column("Description", style="white")

    model_table.add_row(
        "/model",
        "/mod",
        "Display current model and list available models")
    model_table.add_row(
        "/model <model_name>",
        "/mod <model_name>",
        "Change the model to <model_name>")
    console.print(model_table)

    # Turns Commands Table
    turns_table = Table(
        title="Turns Commands",
        show_header=True,
        header_style="bold magenta")
    turns_table.add_column("Command", style="magenta")
    turns_table.add_column("Alias", style="green")
    turns_table.add_column("Description", style="white")

    turns_table.add_row(
        "/turns",
        "/t",
        "Display current maximum number of turns")
    turns_table.add_row(
        "/turns <number>",
        "/t <number>",
        "Change the maximum number of turns")
    turns_table.add_row("/turns inf", "/t inf", "Set unlimited turns")
    console.print(turns_table)

    # Exit Commands Table
    exit_table = Table(
        title="Exit Commands",
        show_header=True,
        header_style="bold red")
    exit_table.add_column("Command", style="red")
    exit_table.add_column("Alias", style="green")
    exit_table.add_column("Description", style="white")

    exit_table.add_row("/exit", "/q", "Exit CAI")
    exit_table.add_row("", "/quit", "Exit CAI (alias)")
    console.print(exit_table)

    # Help Commands Table
    help_table = Table(
        title="Help Commands",
        show_header=True,
        header_style="bold grey70")
    help_table.add_column("Command", style="grey70")
    help_table.add_column("Alias", style="green")
    help_table.add_column("Description", style="white")

    help_table.add_row("/help", "/h", "Display this help information")
    help_table.add_row(
        "/help aliases",
        "/h aliases",
        "Show all command aliases")
    help_table.add_row(
        "/help model",
        "/h model",
        "Show detailed help for model selection")
    help_table.add_row(
        "/help turns",
        "/h turns",
        "Show detailed help for managing turns")
    console.print(help_table)

    # Platform Commands Table (if available)
    if is_caiextensions_platform_available():
        platform_table = Table(
            title="Platform Commands",
            show_header=True,
            header_style="bold grey70")
        platform_table.add_column("Command", style="grey70")
        platform_table.add_column("Alias", style="green")
        platform_table.add_column("Description", style="white")

        platform_table.add_row(
            "/platform", "/p", "Show all available platforms")
        platform_table.add_row(
            "/platform list",
            "/p list",
            "List available platforms")

        # Add platform-specific commands if available
        platforms = platform_manager.list_platforms(
        ) if is_caiextensions_platform_available() else []
        for platform in platforms:
            platform_cmds = platform_manager.get_platform(
                platform).get_commands()
            for cmd in platform_cmds:
                platform_table.add_row(f"/platform {platform} {cmd}", f"/p {platform} {cmd}",
                                       f"Execute '{cmd}' command on {platform} platform")

        console.print(platform_table)

    # Tips section
    tips = Panel(
        Text.from_markup(
            "[bold cyan]Tips:[/bold cyan]\n"
            "• Use [bold]Tab[/bold] for command completion\n"
            "• Use [bold]↑/↓[/bold] to navigate command history\n"
            "• Use [bold]Ctrl+L[/bold] to clear the screen\n"
            "• Most commands have shorter aliases (e.g. [bold]/h[/bold] instead of [bold]/help[/bold])"
        ),
        title="Helpful Tips",
        border_style="cyan"
    )
    console.print(tips)

    return True


def handle_help_aliases():
    """Show all command aliases in a well-formatted table."""
    from rich.table import Table
    from rich.panel import Panel

    # Create a styled header
    console.print(
        Panel(
            "Command Aliases Reference",
            border_style="magenta",
            title="Aliases"))

    # Create a table for aliases
    alias_table = Table(show_header=True, header_style="bold magenta")
    alias_table.add_column("Alias", style="green")
    alias_table.add_column("Command", style="yellow")
    alias_table.add_column("Description", style="white")

    # Add rows for each alias
    for alias, command in sorted(COMMAND_ALIASES.items()):
        description = COMMAND_DESCRIPTIONS.get(command, "")
        alias_table.add_row(alias, command, description)

    console.print(alias_table)

    # Add a tip about using aliases
    console.print(
        "\n[cyan]Tip:[/cyan] Aliases can be used anywhere the full command would be used.")
    console.print(
        "[cyan]Example:[/cyan] [green]/m list[/green] instead of [yellow]/memory list[/yellow]")

    return True


def handle_graph_show():
    """Handle /graph show command"""
    if not client or not client._graph:  # pylint: disable=protected-access
        print("No conversation graph available.")
        return True

    try:
        print("\nConversation Graph:")
        print("------------------")
        print(client._graph.ascii())  # pylint: disable=protected-access
        print()
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error displaying graph: {e}")
        return False


def handle_platform_command(
        command: str, args: Optional[List[str]] = None) -> bool:
    """Handle platform specific commands."""
    if not args:
        # Mostrar plataformas disponibles
        platforms = platform_manager.list_platforms()
        console.print(Panel(
            "\n".join(f"[green]{p}[/green]" for p in platforms),
            title="Available Platforms",
            border_style="blue"
        ))
        return True

    platform_name = args[0].lower()
    platform = platform_manager.get_platform(platform_name)

    if not platform:
        console.print(f"[red]Unknown platform: {platform_name}[/red]")
        return False

    if len(args) == 1:
        # Mostrar ayuda de la plataforma
        console.print(Panel(
            platform.get_help(),
            title=f"{platform_name.upper()} Help",
            border_style="blue"
        ))
        return True

    # Pasar el comando a la plataforma (sin el nombre de la plataforma)
    platform.handle_command(args[1:])
    return True


def handle_shell_command(command_args: List[str]) -> bool:
    """Execute a shell command that can be interrupted with CTRL+C.

    Args:
        command_args: The shell command and its arguments

    Returns:
        bool: True if the command was executed successfully
    """
    if not command_args:
        console.print("[red]Error: No command specified[/red]")
        return False

    shell_command = " ".join(command_args)
    console.print(f"[blue]Executing:[/blue] {shell_command}")

    # Save original signal handler
    original_sigint_handler = signal.getsignal(signal.SIGINT)

    try:
        # Set temporary handler for SIGINT that only affects shell command
        def shell_sigint_handler(sig, frame):
            # Just allow KeyboardInterrupt to propagate
            signal.signal(signal.SIGINT, original_sigint_handler)
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, shell_sigint_handler)

        # Check if this is a command that should run asynchronously
        async_commands = [
            'nc',
            'netcat',
            'ncat',
            'telnet',
            'ssh',
            'python -m http.server']
        is_async = any(cmd in shell_command for cmd in async_commands)

        if is_async:
            # For async commands, use os.system to allow terminal interaction
            console.print(
                "[yellow]Running in async mode (Ctrl+C to return to REPL)[/yellow]")
            os.system(shell_command)  # nosec B605
            console.print("[green]Async command completed or detached[/green]")
            return True
        else:
            # For regular commands, use the standard approach
            process = subprocess.Popen(  # nosec B602
                shell_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Show output in real time
            for line in iter(process.stdout.readline, ''):
                print(line, end='')

            # Wait for process to finish
            process.wait()

            if process.returncode == 0:
                console.print("[green]Command completed successfully[/green]")
            else:
                console.print(
                    f"[yellow]Command exited with code {process.returncode}"
                    f"[/yellow]")

            return True
    except KeyboardInterrupt:
        # Handle CTRL+C only for this command
        try:
            if not is_async:
                process.terminate()
            console.print("\n[yellow]Command interrupted by user[/yellow]")
        except Exception:  # nosec B110
            pass
        return True
    except Exception as e:
        console.print(f"[red]Error executing command: {str(e)}[/red]")
        return False
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_sigint_handler)


def handle_kill_command(args: List[str]) -> bool:
    """Kill a background process by PID.

    Args:
        args: List containing the PID to kill

    Returns:
        bool: True if the process was killed successfully
    """
    if not args:
        console.print("[red]Error: No PID specified[/red]")
        return False

    try:
        pid = int(args[0])
        import os
        import signal

        # Try to kill the process group
        try:
            os.killpg(pid, signal.SIGTERM)
            console.print(f"[green]Process group {pid} terminated[/green]")
        except BaseException:
            # If killing the process group fails, try killing just the process
            os.kill(pid, signal.SIGTERM)
            console.print(f"[green]Process {pid} terminated[/green]")

        return True
    except ValueError:
        console.print("[red]Error: Invalid PID format[/red]")
        return False
    except ProcessLookupError:
        console.print(f"[yellow]No process with PID {args[0]} found[/yellow]")
        return False
    except Exception as e:
        console.print(f"[red]Error killing process: {str(e)}[/red]")
        return False


def handle_env_command() -> bool:
    """Display environment variables starting with CAI or CTF.

    Returns:
        bool: True if the command was executed successfully
    """
    # Get all environment variables
    env_vars = {
        k: v for k, v in os.environ.items() if k.startswith(
            ('CAI_', 'CTF_'))}

    if not env_vars:
        console.print(
            "[yellow]No CAI_ or CTF_ environment variables found[/yellow]")
        return True

    # Create a table to display the variables
    from rich.table import Table
    table = Table(
        title="Environment Variables",
        show_header=True,
        header_style="bold magenta")
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="green")

    # Add rows to the table with masked values for sensitive data
    for key, value in sorted(env_vars.items()):
        # Mask sensitive values (API keys, tokens, etc.)
        if any(sensitive in key.lower()
               for sensitive in ['key', 'token', 'secret', 'password']):
            # Show first half of the value, mask the rest
            half_length = len(value) // 2
            masked_value = value[:half_length] + \
                '*' * (len(value) - half_length)
            table.add_row(key, masked_value)
        else:
            table.add_row(key, value)

    console.print(table)
    return True


def handle_model_command(args: List[str]) -> bool:
    """Change the model used by CAI.

    Args:
        args: List containing the model name to use or a number to select from the list

    Returns:
        bool: True if the model was changed successfully
    """
    global client  # pylint: disable=global-statement
    from rich.table import Table
    from rich.panel import Panel
    import requests
    
    # Define model categories and their models for easy reference
    MODEL_CATEGORIES = {
        "Claude 3.7": [
            {"name": "claude-3-7-sonnet-20250219", "description": "Best model for complex reasoning and creative tasks"}
        ],
        "Claude 3.5": [
            {"name": "claude-3-5-sonnet-20240620", "description": "Excellent balance of performance and efficiency"},
            {"name": "claude-3-5-sonnet-20241022", "description": "Latest Claude 3.5 model with improved capabilities"}
        ],
        "Claude 3": [
            {"name": "claude-3-opus-20240229", "description": "Powerful Claude 3 model for complex tasks"},
            {"name": "claude-3-sonnet-20240229", "description": "Balanced performance and speed"},
            {"name": "claude-3-haiku-20240307", "description": "Fast and efficient model"}
        ],
        "OpenAI O-series": [
            {"name": "o1", "description": "Excellent for mathematical reasoning and problem-solving"},
            {"name": "o1-mini", "description": "Smaller O1 model with good math capabilities"},
            {"name": "o3-mini", "description": "Latest mini model in the O-series"}
        ],
        "OpenAI GPT-4": [
            {"name": "gpt-4o", "description": "Latest GPT-4 model with improved capabilities"},
            {"name": "gpt-4-turbo", "description": "Fast and powerful GPT-4 model"}
        ],
        "OpenAI GPT-4.5": [
            {"name": "gpt-4.5-preview", "description": "Latest non reasoning openai model with improved capabilities"},
        ],
        "OpenAI GPT-3.5": [
            {"name": "gpt-3.5-turbo", "description": "Fast and cost-effective model"}
        ],
        "DeepSeek": [
            {"name": "deepseek-v3", "description": "DeepSeek's latest general-purpose model"},
            {"name": "deepseek-r1", "description": "DeepSeek's specialized reasoning model"}
        ]
    }
    
    # Fetch model pricing data from LiteLLM GitHub repository
    model_pricing_data = {}
    try:
        response = requests.get(
            "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
            timeout=2
        )
        if response.status_code == 200:
            model_pricing_data = response.json()
            
            # Add DeepSeek models with their pricing if not already in the data
            if "deepseek/deepseek-v3" in model_pricing_data and "deepseek-v3" not in model_pricing_data:
                model_pricing_data["deepseek-v3"] = model_pricing_data["deepseek/deepseek-v3"]
            if "deepseek/deepseek-r1" in model_pricing_data and "deepseek-r1" not in model_pricing_data:
                model_pricing_data["deepseek-r1"] = model_pricing_data["deepseek/deepseek-r1"]
    except Exception:  # pylint: disable=broad-except
        console.print("[yellow]Warning: Could not fetch model pricing data[/yellow]")
    
    # Create a flat list of all models for numeric selection
    ALL_MODELS = []
    for category, models in MODEL_CATEGORIES.items():
        for model in models:
            # Get pricing info if available
            pricing_info = model_pricing_data.get(model["name"], {})
            input_cost = pricing_info.get("input_cost_per_token", None)
            output_cost = pricing_info.get("output_cost_per_token", None)
            
            # Convert to dollars per million tokens if values exist
            input_cost_per_million = input_cost * 1000000 if input_cost is not None else None
            output_cost_per_million = output_cost * 1000000 if output_cost is not None else None
            
            ALL_MODELS.append({
                "name": model["name"],
                "provider": "Anthropic" if "claude" in model["name"] else 
                           "DeepSeek" if "deepseek" in model["name"] else "OpenAI",
                "category": category,
                "description": model["description"],
                "input_cost": input_cost_per_million,
                "output_cost": output_cost_per_million
            })
    
    if not args:
        # Display current model
        model_info = os.getenv("CAI_MODEL", "Unknown")
        console.print(Panel(f"Current model: [bold green]{model_info}[/bold green]", 
                           border_style="green", title="Active Model"))
        
        # Show available models in a table
        model_table = Table(title="Available Models", show_header=True, header_style="bold yellow")
        model_table.add_column("#", style="bold white", justify="right")
        model_table.add_column("Model", style="cyan")
        model_table.add_column("Provider", style="magenta")
        model_table.add_column("Category", style="blue")
        model_table.add_column("Input Cost ($/M)", style="green", justify="right")
        model_table.add_column("Output Cost ($/M)", style="red", justify="right")
        model_table.add_column("Description", style="white")
        
        # Add all predefined models with numbers
        for i, model in enumerate(ALL_MODELS, 1):
            # Format pricing info as dollars per million tokens
            input_cost_str = f"${model['input_cost']:.2f}" if model['input_cost'] is not None else "Unknown"
            output_cost_str = f"${model['output_cost']:.2f}" if model['output_cost'] is not None else "Unknown"
            
            model_table.add_row(
                str(i),
                model["name"],
                model["provider"],
                model["category"],
                input_cost_str,
                output_cost_str,
                model["description"]
            )
        
        # Ollama models (if available)
        try:
            # Get Ollama models with a short timeout to prevent hanging
            api_base = get_ollama_api_base()
            response = requests.get(f"{api_base.replace('/v1', '')}/api/tags", timeout=1)
            
            if response.status_code == 200:
                data = response.json()
                ollama_models = []
                
                if 'models' in data:
                    ollama_models = data['models']
                else:
                    # Fallback for older Ollama versions
                    ollama_models = data.get('items', [])
                
                # Add Ollama models to the table with continuing numbers
                start_index = len(ALL_MODELS) + 1
                for i, model in enumerate(ollama_models, start_index):
                    model_name = model.get('name', '')
                    model_size = model.get('size', 0)
                    # Convert size to human-readable format
                    size_str = ""
                    if model_size:
                        if model_size < 1024*1024*1024:
                            size_str = f"{model_size/(1024*1024):.1f} MB"
                        else:
                            size_str = f"{model_size/(1024*1024*1024):.1f} GB"
                    
                    # Ollama models are free to use locally
                    model_table.add_row(
                        str(i),
                        model_name, 
                        "Ollama", 
                        "Local",
                        "Free",
                        "Free",
                        f"Local model{f' ({size_str})' if size_str else ''}"
                    )
                    
                    # Add to ALL_MODELS for numeric selection
                    ALL_MODELS.append({
                        "name": model_name,
                        "provider": "Ollama",
                        "category": "Local",
                        "description": f"Local model{f' ({size_str})' if size_str else ''}",
                        "input_cost": 0.0,
                        "output_cost": 0.0
                    })
        except Exception:  # pylint: disable=broad-except
            # Add a note about Ollama if we couldn't fetch models
            start_index = len(ALL_MODELS) + 1
            model_table.add_row(str(start_index), "llama3", "Ollama", "Local", "Free", "Free", "Local Llama 3 model (if installed)")
            model_table.add_row(str(start_index+1), "mistral", "Ollama", "Local", "Free", "Free", "Local Mistral model (if installed)")
            model_table.add_row(str(start_index+2), "...", "Ollama", "Local", "Free", "Free", "Other local models (if installed)")
        
        console.print(model_table)
        
        # Usage instructions
        console.print("\n[cyan]Usage:[/cyan]")
        console.print("  [bold]/model <model_name>[/bold] - Select by name (e.g. [bold]/model claude-3-7-sonnet-20250219[/bold])")
        console.print("  [bold]/model <number>[/bold]     - Select by number (e.g. [bold]/model 1[/bold] for first model in list)")
        return True
    
    model_arg = args[0]
    
    # Check if the argument is a number for model selection
    if model_arg.isdigit():
        model_index = int(model_arg) - 1  # Convert to 0-based index
        if 0 <= model_index < len(ALL_MODELS):
            model_name = ALL_MODELS[model_index]["name"]
        else:
            # Si el número está fuera de rango, usamos el número directamente como nombre del modelo
            model_name = model_arg
    else:
        model_name = model_arg
    
    # Set the model in environment variable
    os.environ["CAI_MODEL"] = model_name
    
    console.print(Panel(
        f"Model changed to: [bold green]{model_name}[/bold green]\n"
        "[yellow]Note: This will take effect on the next agent interaction[/yellow]",
        border_style="green", 
        title="Model Changed"
    ))
    return True


def handle_turns_command(args: List[str]) -> bool:
    """Change the maximum number of turns for CAI.

    Args:
        args: List containing the number of turns

    Returns:
        bool: True if the max turns was changed successfully
    """
    global client  # pylint: disable=global-statement
    from rich.panel import Panel
    
    if not args:
        # Display current max turns
        max_turns_info = os.getenv("CAI_MAX_TURNS", "inf")
        console.print(Panel(
            f"Current maximum turns: [bold green]{
                max_turns_info}[/bold green]",
            border_style="green",
            title="Max Turns Setting"
        ))

        # Usage instructions
        console.print(
            "\n[cyan]Usage:[/cyan] [bold]/turns <number_of_turns>[/bold]")
        console.print("[cyan]Examples:[/cyan]")
        console.print("  [bold]/turns 10[/bold]    - Limit to 10 turns")
        console.print("  [bold]/turns inf[/bold]   - Unlimited turns")
        return True
    
    try:
        turns = args[0]
        # Check if it's a number or 'inf'
        if turns.lower() == 'inf':
            max_turns_value = float('inf')
            turns = 'inf'
        else:
            max_turns_value = float(turns)
            
        # Set the max turns in environment variable
        os.environ["CAI_MAX_TURNS"] = turns
        
        console.print(Panel(
            f"Maximum turns changed to: [bold green]{turns}[/bold green]\n"
            "[yellow]Note: This will take effect on the next run[/yellow]",
            border_style="green",
            title="Max Turns Changed"
        ))
        return True
    except ValueError:
        console.print(Panel(
            "Error: Max turns must be a number or 'inf'",
            border_style="red",
            title="Invalid Input"
        ))
        return False


def handle_help_model():
    """Show help for model command with rich formatting."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    # Create a styled header
    header = Text("Model Command Help", style="bold magenta")
    console.print(Panel(header, border_style="magenta"))

    # Usage table
    usage_table = Table(
        title="Usage",
        show_header=True,
        header_style="bold white")
    usage_table.add_column("Command", style="magenta")
    usage_table.add_column("Description", style="white")

    usage_table.add_row(
        "/model",
        "Display current model and list available models")
    usage_table.add_row(
        "/model <model_name>",
        "Change the model to <model_name>")
    usage_table.add_row(
        "/model <number>",
        "Change the model using its number from the list")
    usage_table.add_row("/mod", "Alias for /model")

    console.print(usage_table)

    # Examples table
    examples_table = Table(
        title="Examples",
        show_header=True,
        header_style="bold cyan")
    examples_table.add_column("Example", style="cyan")
    examples_table.add_column("Description", style="white")

    examples_table.add_row(
        "/model 1",
        "Switch to the first model in the list (Claude 3.7 Sonnet)")
    examples_table.add_row(
        "/model claude-3-7-sonnet-20250219",
        "Switch to Claude 3.7 Sonnet model")
    examples_table.add_row(
        "/model o1",
        "Switch to OpenAI's O1 model (good for math)")
    examples_table.add_row("/model gpt-4o", "Switch to OpenAI's GPT-4o model")

    console.print(examples_table)

    # Model categories table
    categories_table = Table(
        title="Model Categories",
        show_header=True,
        header_style="bold green")
    categories_table.add_column("Category", style="green")
    categories_table.add_column("Description", style="white")

    categories_table.add_row(
        "Claude 3.7",
        "Best models for complex reasoning and creative tasks")
    categories_table.add_row(
        "Claude 3.5",
        "Excellent balance of performance and efficiency")
    categories_table.add_row(
        "Claude 3",
        "Range of models from powerful (Opus) to fast (Haiku)")
    categories_table.add_row(
        "OpenAI O-series",
        "Specialized models with strong mathematical capabilities")
    categories_table.add_row("OpenAI GPT-4", "Powerful general-purpose models")
    categories_table.add_row(
        "Ollama",
        "Local models running on your machine or Docker container")

    console.print(categories_table)

    # Notes panel
    notes = Panel(
        Text.from_markup(
            "• The model change takes effect on the next agent interaction\n"
            "• The model is stored in the CAI_MODEL environment variable\n"
            "• Some models may require specific API keys to be set\n"
            "• OpenAI models require OPENAI_API_KEY to be set\n"
            "• Anthropic models require ANTHROPIC_API_KEY to be set\n"
            "• Ollama models require Ollama to be running locally\n"
            "• Ollama is configured to run on host.docker.internal:8000"
        ),
        title="Notes",
        border_style="yellow"
    )
    console.print(notes)

    return True


def handle_help_turns():
    """Show help for turns command with rich formatting."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    # Create a styled header
    header = Text("Turns Command Help", style="bold magenta")
    console.print(Panel(header, border_style="magenta"))

    # Usage table
    usage_table = Table(
        title="Usage",
        show_header=True,
        header_style="bold white")
    usage_table.add_column("Command", style="magenta")
    usage_table.add_column("Description", style="white")

    usage_table.add_row("/turns", "Display current maximum number of turns")
    usage_table.add_row(
        "/turns <number>",
        "Change the maximum number of turns to <number>")
    usage_table.add_row("/turns inf", "Set unlimited turns")
    usage_table.add_row("/t", "Alias for /turns")

    console.print(usage_table)

    # Examples table
    examples_table = Table(
        title="Examples",
        show_header=True,
        header_style="bold cyan")
    examples_table.add_column("Example", style="cyan")
    examples_table.add_column("Description", style="white")

    examples_table.add_row("/turns 5", "Limit to 5 turns")
    examples_table.add_row("/turns 10", "Limit to 10 turns")
    examples_table.add_row("/turns inf", "Set unlimited turns")
    examples_table.add_row("/t 3", "Limit to 3 turns (using alias)")

    console.print(examples_table)

    # Notes panel
    notes = Panel(
        Text.from_markup(
            "• The turns setting takes effect on the next run\n"
            "• The setting is stored in the CAI_MAX_TURNS environment variable\n"
            "• Setting a lower number of turns can help control costs\n"
            "• 'inf' represents infinity (unlimited turns)"
        ),
        title="Notes",
        border_style="yellow"
    )
    console.print(notes)

    return True


def handle_command(command, args=None):  # pylint: disable=too-many-branches,too-many-locals,too-many-statements,line-too-long # noqa: E501
    """Handle CLI commands"""
    # Handle command aliases
    if command in COMMAND_ALIASES:
        command = COMMAND_ALIASES[command]

    # Special handling for shell command
    if command == "/shell":
        if not args:
            console.print("[red]Error: No command specified[/red]")
            return False
        return handle_shell_command(args)

    # Handle kill command
    if command == "/kill":
        return handle_kill_command(args)

    if command.startswith("/htb"):
        def is_platform_enabled(platform_name: str) -> bool:
            """Check if a platform is enabled as an extension."""
            try:
                if platform_name == "htb":
                    # Import only when needed
                    return True
                # Add more platforms here as needed
            except ImportError:
                return False
            return False
        if not is_platform_enabled("htb"):
            console.print(
                "[red]HTB extension not installed or properly configured"
                "[/red]")
            return False
        try:
            # Import HTB modules only when needed
            from caiextensions.platforms.htb.cli import (
                handle_htb_command
            )
            from caiextensions.platforms.htb.api import HTBClient

            token = os.getenv("HTB_TOKEN")
            if not token:
                console.print(
                    "[red]No HTB token found. Please set HTB_TOKEN "
                    "environment variable.[/red]")
                return False

            # Extract all parts after /htb as arguments
            full_command = command.split() + (args if args else [])
            htb_args = full_command[1:]  # Remove '/htb'

            htb_client = HTBClient(
                token=token, debug=os.getenv(
                    'CAI_HTB_DEBUG', 'false').lower() == 'true')
            handle_htb_command(htb_client, htb_args)
            return True
        except ImportError:
            console.print(
                "[red]HTB extension not installed or properly configured"
                "[/red]")
            return False

    # Handle memory commands
    if command == "/memory":
        if not args:
            # Display memory help if no subcommand
            console.print(
                "[yellow]Memory command requires a subcommand: list, load, delete, or create[/yellow]")
            return False

        subcommand = args[0]
        if subcommand == "list":
            return handle_memory_list()
        elif subcommand == "load":
            if len(args) < 2:
                console.print("[red]Error: Collection name required[/red]")
            return False
            return handle_memory_load(args[1])
        elif subcommand == "delete":
            if len(args) < 2:
                console.print("[red]Error: Collection name required[/red]")
                return False
            return handle_memory_delete(args[1])
        elif subcommand == "create":
            if len(args) < 2:
                console.print("[red]Error: Collection name required[/red]")
                return False
            return handle_memory_create(args[1])
        else:
            console.print(
                f"[red]Unknown memory subcommand: {subcommand}[/red]")
            return False

    # Handle other commands
    if command.startswith("/graph"):
        return handle_graph_show()
    if command.startswith("/help memory"):
        return handle_help_memory()
    if command.startswith("/help aliases"):
        return handle_help_aliases()
    if command.startswith("/help model"):
        return handle_help_model()
    if command.startswith("/help turns"):
        return handle_help_turns()
    if command.startswith("/help"):
        return handle_help()
    if command.startswith("/exit"):
        sys.exit(0)
    if command.startswith("/env"):
        return handle_env_command()
    if command.startswith("/platform"):
        # Extract all parts after /platform as arguments
        full_command = command.split() + (args if args else [])
        platform_args = full_command[1:]  # Remove '/platform'
        return handle_platform_command(command, platform_args)
    if command.startswith("/model"):
        return handle_model_command(args)
    if command.startswith("/turns"):
        return handle_turns_command(args)
    return False


class FuzzyCommandCompleter(Completer):
    """Command completer with fuzzy matching for the REPL.

    This advanced completer provides intelligent suggestions for commands,
    subcommands, and arguments based on what the user is typing.
    It supports fuzzy matching to find commands even with typos.
    """

    def __init__(self):
        """Initialize the command completer with cached model information."""
        super().__init__()
        self.cached_models = []
        self.cached_model_numbers = {}  # Map of numbers to model names
        self.last_model_fetch = datetime.datetime.now() - datetime.timedelta(minutes=10)
        self.fetch_ollama_models()

    def fetch_ollama_models(self):
        """Fetch available models from Ollama if it's running."""
        # Only fetch every 60 seconds to avoid excessive API calls
        now = datetime.datetime.now()
        if (now - self.last_model_fetch).total_seconds() < 60:
            return

        self.last_model_fetch = now
        ollama_models = []
        
        try:
            # Get the Ollama API base URL
            api_base = get_ollama_api_base()
            
            # Make a request to the Ollama API to get available models with a short timeout
            response = requests.get(f"{api_base.replace('/v1', '')}/api/tags", timeout=1)
            
            if response.status_code == 200:
                data = response.json()
                if 'models' in data:
                    ollama_models = data['models']
                else:
                    # Fallback for older Ollama versions
                    ollama_models = data.get('items', [])
        except Exception:  # pylint: disable=broad-except
            # Silently fail if Ollama is not available
            pass
        
        # Standard models always available
        standard_models = [
            # Claude 3.7 models
            "claude-3-7-sonnet-20250219",
            
            # Claude 3.5 models
            "claude-3-5-sonnet-20240620",
            "claude-3-5-20241122",
            
            # Claude 3 models
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307",
            
            # OpenAI O-series models
            "o1",
            "o1-mini",
            "o3-mini",
            
            # OpenAI GPT models
            "gpt-4o", 
            "gpt-4-turbo", 
            "gpt-3.5-turbo"
        ]
        
        # Combine standard models with Ollama models
        self.cached_models = standard_models + ollama_models
        
        # Create number mappings for models (1-based indexing)
        self.cached_model_numbers = {}
        for i, model in enumerate(self.cached_models, 1):
            self.cached_model_numbers[str(i)] = model

    def get_completions(self, document, complete_event):
        """Get completions for the current document with fuzzy matching support."""
        text = document.text_before_cursor.strip()
        words = text.split()

        # Refresh Ollama models periodically
        self.fetch_ollama_models()

        if not text:
            # Show all main commands with descriptions
            for cmd, description in sorted(COMMAND_DESCRIPTIONS.items()):
                yield Completion(
                    cmd,
                                 start_position=0,
                    display=f"{cmd:<15} {description}",
                    style="fg:ansicyan bold"
                )
            return

        if text.startswith('/'):
            current_word = words[-1]

            # Main command completion (first word)
            if len(words) == 1:
                # Complete main commands with fuzzy matching
                for cmd, description in sorted(COMMAND_DESCRIPTIONS.items()):
                    # Exact prefix match
                    if cmd.startswith(current_word):
                        yield Completion(
                            cmd,
                                         start_position=-len(current_word),
                            display=f"{cmd:<15} {description}",
                            style="fg:ansicyan bold"
                        )
                    # Fuzzy match (contains the substring)
                    elif current_word in cmd and not cmd.startswith(current_word):
                        yield Completion(
                            cmd,
                            start_position=-len(current_word),
                            display=f"{cmd:<15} {description}",
                            style="fg:ansicyan"
                        )

                # Complete aliases with descriptions
                for alias, cmd in sorted(COMMAND_ALIASES.items()):
                    cmd_description = COMMAND_DESCRIPTIONS.get(cmd, "")
                    if alias.startswith(current_word):
                        yield Completion(
                            alias,
                                         start_position=-len(current_word),
                            display=f"{alias:<15} {cmd} - {cmd_description}",
                            style="fg:ansigreen bold"
                        )
                    elif current_word in alias and not alias.startswith(current_word):
                        yield Completion(
                            alias,
                            start_position=-len(current_word),
                            display=f"{alias:<15} {cmd} - {cmd_description}",
                            style="fg:ansigreen"
                        )

            # Subcommand completion (second word)
            elif len(words) == 2:
                cmd = words[0]
                # If using an alias, get the real command
                if cmd in COMMAND_ALIASES:
                    cmd = COMMAND_ALIASES[cmd]

                if cmd in COMMANDS:
                    for subcmd in sorted(COMMANDS[cmd]):
                        # Get description for this subcommand if available
                        subcmd_description = SUBCOMMAND_DESCRIPTIONS.get(
                            f"{cmd} {subcmd}", "")

                        # Exact prefix match
                        if subcmd.startswith(current_word):
                            yield Completion(
                                subcmd,
                                             start_position=-len(current_word),
                                display=f"{subcmd:<15} {subcmd_description}",
                                style="fg:ansiyellow bold"
                            )
                        # Fuzzy match
                        elif current_word in subcmd and not subcmd.startswith(current_word):
                            yield Completion(
                                subcmd,
                                start_position=-len(current_word),
                                display=f"{subcmd:<15} {subcmd_description}",
                                style="fg:ansiyellow"
                            )

                # Special handling for model command
                if cmd in ["/model", "/mod"]:
                    # First try to complete model numbers
                    for num, model_name in self.cached_model_numbers.items():
                        if num.startswith(current_word):
                            yield Completion(
                                num,
                                start_position=-len(current_word),
                                display=f"{num:<3} {model_name}",
                                style="fg:ansiwhite bold"
                            )

                    # Then try to complete model names
                    for model in self.cached_models:
                        if model.startswith(current_word):
                            yield Completion(
                                model,
                                start_position=-len(current_word),
                                style="fg:ansimagenta bold"
                            )
                        elif current_word.lower() in model.lower() and not model.startswith(current_word):
                            yield Completion(
                                model,
                                start_position=-len(current_word),
                                style="fg:ansimagenta"
                            )


def run_demo_loop(
    starting_agent,
    context_variables=None,
    stream=False,
    debug=False,
    max_turns=float('inf'),
    ctf=None,
    state_agent=None
) -> None:
    """
    Run the demo loop for CAI.

    Args:
        starting_agent: The agent to start with
        context_variables: Optional context variables
        stream: Whether to stream responses
        debug: Debug level
        max_turns: Maximum number of turns
        ctf: Optional CTF instance to use
        state_agent: Optional state agent to use
    """
    global client  # pylint: disable=global-statement
    # Initialize CAI with CTF and state agent if provided
    client = CAI(
        ctf=ctf if os.getenv(
            'CTF_INSIDE',
            "true").lower() == "true" else None,
        state_agent=state_agent)

    # Get version from setup.cfg
    version = "unknown"
    try:
        config = ConfigParser()
        config.read('setup.cfg')
        version = config.get('metadata', 'version')
    except Exception:  # pylint: disable=broad-except
        version = 'unknown'

    print(f"""
                CCCCCCCCCCCCC      ++++++++   ++++++++      IIIIIIIIII
             CCC::::::::::::C  ++++++++++       ++++++++++  I::::::::I
           CC:::::::::::::::C ++++++++++         ++++++++++ I::::::::I
          C:::::CCCCCCCC::::C +++++++++    ++     +++++++++ II::::::II
         C:::::C       CCCCCC +++++++     +++++     +++++++   I::::I
        C:::::C                +++++     +++++++     +++++    I::::I
        C:::::C                ++++                   ++++    I::::I
        C:::::C                 ++                     ++     I::::I
        C:::::C                  +   +++++++++++++++   +      I::::I
        C:::::C                    +++++++++++++++++++        I::::I
        C:::::C                     +++++++++++++++++         I::::I
         C:::::C       CCCCCC        +++++++++++++++          I::::I
          C:::::CCCCCCCC::::C         +++++++++++++         II::::::II
           CC:::::::::::::::C           +++++++++           I::::::::I
             CCC::::::::::::C             +++++             I::::::::I
                CCCCCCCCCCCCC               ++              IIIIIIIIII

                              Cybersecurity AI (CAI) v{version}
""")

    messages = []
    messages_init = []
    if ctf:
        # Get challenge
        challenge_key = os.getenv('CTF_CHALLENGE')
        challenges = list(ctf.get_challenges().keys())
        challenge = challenge_key if challenge_key in challenges else (
            challenges[0] if len(challenges) > 0 else None)

        if challenge:
            print(color("Testing challenge: ", fg="white", bg="blue")
                  + color(f"'{challenge}'", fg="white", bg="blue"))

        # Get initial messages aligned with CTF
        messages += [{
            "role": "user",
            "content": Template(  # nosec B702
                filename="cai/prompts/core/user_master_template.md").render(
                    ctf=ctf,
                    challenge=challenge,
                    ip=ctf.get_ip() if ctf else None
            )
        }]

        messages_init = messages
    agent = starting_agent

    # Setup history file
    history_dir = Path.home() / ".cai"
    history_dir.mkdir(exist_ok=True)
    history_file = history_dir / "history.txt"

    # Setup session log file
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_log = history_dir / f"session_{session_id}.log"

    # Log start of session
    with open(session_log, "w", encoding="utf-8") as f:
        f.write(
            f"CAI Session started at {
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Version: {version}\n")
        if ctf:
            f.write(f"CTF: {ctf.__class__.__name__}\n")
            if challenge:
                f.write(f"Challenge: {challenge}\n")
        f.write("\n")

    # Function to log interactions
    def log_interaction(role, content):
        with open(session_log, "a", encoding="utf-8") as f:
            f.write(
                f"\n[{
                    datetime.datetime.now().strftime('%H:%M:%S')}] {
                    role.upper()}:\n")
            f.write(f"{content}\n")

    # Create key bindings
    kb = KeyBindings()

    @kb.add('c-l')
    def clear_screen(event):
        """Clear the screen."""
        os.system('cls' if os.name == 'nt' else 'clear')  # nosec B605
        event.app.renderer.clear()

    # Setup prompt style
    cli_style = Style.from_dict({
        'prompt': '#ff0066 bold',
        '': '#ffcc00',
        'bottom-toolbar': 'bg:#222222 #aaaaaa',
    })

    # # Setup command completer
    command_completer = FuzzyCommandCompleter()

    # Function to display bottom toolbar
    def get_bottom_toolbar():
        """Return bottom toolbar HTML content with enhanced information."""
        # Cache all data for 60 seconds to improve performance
        if not hasattr(get_bottom_toolbar, "cache_time") or \
           not hasattr(get_bottom_toolbar, "cached_data") or \
           (datetime.datetime.now() - get_bottom_toolbar.cache_time).total_seconds() > 60:
            
            # Initialize cached data dictionary
            cached_data = {}
            
            # Get HTB machine info
            active_machine = ""
            if is_caiextensions_platform_available():
                try:
                    from caiextensions.platform.htb.api import HTBClient
                    token = os.getenv("HTB_TOKEN")
                    if token:
                        htb_client = HTBClient(token=token)
                        machine = htb_client.get_active_machine()
                        if machine:
                            active_machine = (
                                f" | <b><style fg='cyan'>HTB:</style></b> {
                                    machine.get('name', 'Unknown')} "
                                f"({machine.get('ip', 'Unknown')})"
                            )
                except Exception:  # pylint: disable=broad-except # nosec B110
                    pass
            cached_data['active_machine'] = active_machine
            
            # Get local IP addresses
            try:
                # Run 'ip a' command to get network interfaces
                output = subprocess.check_output(['ip', 'a'], text=True)
                
                local_ips = []
                vpn_ip = None
                
                # Parse the output to extract IP addresses
                for line in output.splitlines():
                    # Look for inet lines that contain IP addresses
                    if 'inet ' in line and not 'inet6' in line:
                        # Extract the IP address
                        ip_match = line.strip().split('inet ')[1].split('/')[0]
                        if ip_match != '127.0.0.1':  # Skip localhost
                            local_ips.append(ip_match)
                            
                            # Check if this is a tun/tap interface (VPN)
                            if 'tun' in line or 'tap' in line:
                                vpn_ip = ip_match
                
                # Format IP display, prioritizing VPN IP if available
                if vpn_ip:
                    local_ip = f"{vpn_ip} (VPN)"
                else:
                    local_ip = ", ".join(local_ips[:2])  # Show at most 2 IPs
                    if len(local_ips) > 2:
                        local_ip += "..."
                        
                if not local_ips:
                    local_ip = "Unknown"
            except Exception:  # pylint: disable=broad-except
                local_ip = "Unknown"
            cached_data['local_ip'] = local_ip
            
            # Get OS information
            import platform
            cached_data['os_info'] = platform.system()
            
            # Get model information from environment variable
            cached_data['model_info'] = os.getenv("CAI_MODEL", "Unknown")
            
            # Get system resource information
            import psutil
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)

                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                memory_used = f"{memory.used / (1024 * 1024 * 1024):.1f}GB"
                memory_total = f"{memory.total / (1024 * 1024 * 1024):.1f}GB"

                # Disk usage
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent

                # Format system resources with HTML formatting
                system_resources = (
                    f"<b><style fg='green'>CPU:</style></b> {cpu_percent}% | "
                    f"<b><style fg='green'>RAM:</style></b> {
                        memory_percent}% ({memory_used}/{memory_total}) | "
                    f"<b><style fg='green'>Disk:</style></b> {disk_percent}%"
                )
            except Exception:  # pylint: disable=broad-except
                system_resources = "System resources unavailable"
            cached_data['system_resources'] = system_resources

            # Check if Ollama is available
            ollama_status = "<b><style fg='red'>Unavailable</style></b>"
            try:
                api_base = get_ollama_api_base()
                response = requests.get(f"{api_base.replace('/v1', '')}/api/tags", timeout=0.5)
                if response.status_code == 200:
                    data = response.json()
                    model_count = 0
                    if 'models' in data:
                        model_count = len(data['models'])
                    else:
                        # Fallback for older Ollama versions
                        model_count = len(data.get('items', []))
                    ollama_status = f"<b><style fg='green'>Available</style></b> ({model_count} models)"
            except Exception:  # pylint: disable=broad-except
                pass
            cached_data['ollama_status'] = ollama_status
            
            # Cache all the data
            get_bottom_toolbar.cache_time = datetime.datetime.now()
            get_bottom_toolbar.cached_data = cached_data
        else:
            # Use cached data
            cached_data = get_bottom_toolbar.cached_data
        
        # Get current time (always fresh)
        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        # Format the toolbar with HTML formatting for prompt_toolkit using cached data
        return HTML(
            f'<b><style fg="yellow">CAI</style></b> | <style bg="green">Use ↑↓ for history</style>'
            f' | <style fg="yellow">Time: {current_time}</style>'
            f' | <style fg="cyan">IP:</style> {cached_data["local_ip"]} | <style fg="cyan">OS:</style> {cached_data["os_info"]}'
            f' | <style fg="magenta">Model:</style> {cached_data["model_info"]}'
            f' | <style fg="cyan">Ollama:</style> {cached_data["ollama_status"]}'
            f' | {cached_data["system_resources"]}'
            f'{cached_data["active_machine"]}'
        )

    # Show welcome message with tips
    console.print(Panel(
        "[cyan]Welcome to CAI REPL![/cyan]\n\n"
        "[green]• Use arrow keys ↑↓ to navigate command history[/green]\n"
        "[green]• Press Tab for command completion[/green]\n"
        "[green]• Type /help for available commands[/green]\n"
        "[green]• Type /help aliases for command shortcuts[/green]\n"
        "[green]• Press Ctrl+L to clear the screen[/green]\n"
        "[green]• Press Ctrl+C to exit[/green]",
        title="Quick Tips",
        border_style="blue"
    ))

    while True:
        try:
            if ctf and len(messages) == 1:
                pass
            else:
                user_input = prompt(
                    [('class:prompt', 'CAI> ')],
                    completer=command_completer,
                    style=cli_style,
                    history=FileHistory(str(history_file)),
                    auto_suggest=AutoSuggestFromHistory(),
                    key_bindings=kb,
                    bottom_toolbar=get_bottom_toolbar,
                    complete_in_thread=True,
                    complete_while_typing=False,  # Better performance
                    mouse_support=False  # Better performance
                )

                # Log user input
                log_interaction("user", user_input)

                # Handle commands
                if user_input.startswith('/') or user_input.startswith('$'):
                    parts = user_input.strip().split()
                    command = parts[0]
                    args = parts[1:] if len(parts) > 1 else None

                    # Handle the command
                    if handle_command(command, args):
                        # # Ensure global handler is active after any command
                        # signal.signal(signal.SIGINT, signal_handler)
                        continue

                    # If we get here, command wasn't handled correctly
                    console.print(f"[red]Unknown command: {command}[/red]")
                    continue

                # If not a command, add as message to agent
                messages.append({"role": "user", "content": user_input})

            # Show a spinner while waiting for the response
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:

                task = progress.add_task(   # noqa: F841
                    description="Thinking",
                    total=None)

            response = client.run(
                agent=agent,
                messages=messages,
                context_variables=context_variables or {},
                stream=stream,
                debug=debug,
                max_turns=float(os.getenv('CAI_MAX_TURNS', str(max_turns))),
                model_override=os.getenv('CAI_MODEL', None),
            )

            messages = response.messages

            # Log assistant response
            if messages and len(messages) > 0:
                last_message = messages[-1]
                if last_message.get(
                        "role") == "assistant" and last_message.get("content"):
                    log_interaction("assistant", last_message["content"])

            if response.agent:
                agent = response.agent
        except KeyboardInterrupt:
            if is_caiextensions_report_available and os.getenv("CAI_REPORT"):
                # Show a spinner while generating the report
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(
                        description="Generating report...", total=None)

                    from caiextensions.report.common import create_report
                    report_type = os.environ.get("CAI_REPORT", "ctf").lower()

                    if report_type == "pentesting":
                        from caiextensions.report.pentesting.pentesting_agent import reporter_agent
                        template = str(
                            files('caiextensions.report.pentesting') / 'template.md')
                    elif report_type == "nis2":
                        from caiextensions.report.nis2.nis2_report_agent import reporter_agent
                        template = str(
                            files('caiextensions.report.nis2') / 'template.md')
                    else:
                        from caiextensions.report.ctf.ctf_reporter_agent import reporter_agent
                        template = str(
                            files('caiextensions.report.ctf') / 'template.md')

                    client = CAI(
                        state_agent=state_agent,
                        force_until_flag=False)
                response_report = client.run(
                    agent=reporter_agent,
                    messages=[{
                        "role": "user",
                        "content": "Do a report from " +
                        "\n".join(
                                msg['content'] for msg in response.messages
                                if msg.get('content') is not None
                        )
                    }],
                    debug=float(os.environ.get('CAI_DEBUG', '2')),
                    max_turns=float(
                        os.environ.get(
                            'CAI_MAX_TURNS', 'inf')),
                )

                if messages_init:
                    response.messages.insert(0, messages_init[0])
                report_data = json.loads(
                    response_report.messages[0]['content'])
                report_data["history"] = json.dumps(
                    response.messages, indent=4)
                report_path = create_report(report_data, template)

                console.print(
                    f"[green]Report generated successfully: {report_path}"
                    f"[/green]")

            # Log end of session
            with open(session_log, "a", encoding="utf-8") as f:
                f.write(
                    f"\nSession ended at {
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    f"\n")

            break


def get_ollama_api_base():
    """Get the Ollama API base URL.

    Returns:
        str: The Ollama API base URL, defaulting to host.docker.internal:8000
    """
    # Default to host.docker.internal:8000 for Docker environments
    return os.getenv("OLLAMA_API_BASE", "http://host.docker.internal:8000/v1")
