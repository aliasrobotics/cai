"""
Commands module for CAI REPL.
This module exports all commands available
in the CAI REPL.
"""
import os
from typing import (
    Dict,
    List,
    Optional
)

# Third-party imports
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error

# Local imports
from cai.repl.commands.completer import (
    FuzzyCommandCompleter
)

# Import base command structure
from cai.repl.commands.base import (
    Command,
    COMMANDS,
    COMMAND_ALIASES,
    register_command,
    get_command,
    handle_command
)

# Import all command modules
# These imports will register the commands with the registry
from cai.repl.commands import (  # pylint: disable=import-error,unused-import,line-too-long,redefined-builtin # noqa: E501,F401
    memory,
    help,
    graph,
    exit,
    shell,
    env,
    platform,
    kill,
    model,
    turns,
    agent,
    history,
    config,
    workspaces
)

# Import utility functions for token calculations
from cai.util import get_model_input_tokens

# Initialize console for rich formatting
console = Console()  # Define console globally


class FlushCommand(Command):
    """Command to flush the conversation history."""

    def handle_no_args(self, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the flush command when no args are provided.

        Args:
            messages: The conversation history messages

        Returns:
            True if the command was handled successfully
        """
        if messages:
            initial_length = len(messages)
            
            # Get token usage information before clearing
            token_info = ""
            context_usage = ""
            
            # Access client through a function to avoid circular imports
            # We can use globals() to get the client at runtime 
            client = self._get_client()
            
            if client and hasattr(client, 'interaction_input_tokens') and hasattr(client, 'total_input_tokens'):
                model = os.getenv('CAI_MODEL', 'gpt')
                input_tokens = client.interaction_input_tokens if hasattr(client, 'interaction_input_tokens') else 0
                total_tokens = client.total_input_tokens if hasattr(client, 'total_input_tokens') else 0
                max_tokens = get_model_input_tokens(model)
                context_pct = (input_tokens / max_tokens) * 100 if max_tokens > 0 else 0
                
                token_info = f"Current tokens: {input_tokens}, Total tokens: {total_tokens}"
                context_usage = f"Context usage: {context_pct:.1f}% of {max_tokens} tokens"
            
            # Clear the messages
            messages.clear()
            
            # Display information about the cleared messages
            content = [
                f"Conversation history cleared. Removed {initial_length} messages."
            ]
            
            if token_info:
                content.append(token_info)
            if context_usage:
                content.append(context_usage)
                
            console.print(Panel(
                "\n".join(content),
                title="[bold cyan]Context Flushed[/bold cyan]",
                border_style="blue",
                padding=(1, 2)
            ))
        else:
            console.print(Panel(
                "No conversation history to clear.",
                title="[bold cyan]Context Flushed[/bold cyan]",
                border_style="blue",
                padding=(1, 2)
            ))
        return True
    
    def _get_client(self):
        """Get the CAI client from the global namespace.
        
        This function avoids circular imports by accessing the client
        at runtime instead of import time.
        
        Returns:
            The global CAI client instance or None if not available
        """
        try:
            # Import here to avoid circular import
            from cai.repl.repl import client as global_client
            return global_client
        except (ImportError, AttributeError):
            return None


# Register the /flush command
register_command(FlushCommand(
    name="/flush",
    description="Clear the current conversation history.",
    aliases=["/clear"]
))


# Define helper functions


def get_command_descriptions() -> Dict[str, str]:
    """Get descriptions for all commands.

    Returns:
        A dictionary mapping command names to descriptions
    """
    return {cmd.name: cmd.description for cmd in COMMANDS.values()}


def get_subcommand_descriptions() -> Dict[str, str]:
    """Get descriptions for all subcommands.

    Returns:
        A dictionary mapping command paths to descriptions
    """
    descriptions = {}
    for cmd in COMMANDS.values():
        for subcmd in cmd.get_subcommands():
            key = f"{cmd.name} {subcmd}"
            descriptions[key] = cmd.get_subcommand_description(subcmd)
    return descriptions


def get_all_commands() -> Dict[str, List[str]]:
    """Get all commands and their subcommands.

    Returns:
        A dictionary mapping command names to lists of subcommand names
    """
    return {cmd.name: cmd.get_subcommands() for cmd in COMMANDS.values()}


# Import the command completer after defining the helper functions

# Export command registry
__all__ = [
    'Command',
    'COMMANDS',
    'COMMAND_ALIASES',
    'register_command',
    'get_command',
    'handle_command',
    'get_command_descriptions',
    'get_subcommand_descriptions',
    'get_all_commands',
    'FuzzyCommandCompleter'
]
