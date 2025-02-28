"""
Commands module for CAI REPL.
This module exports all commands available in the CAI REPL.
"""
from cai.repl.commands.completer import FuzzyCommandCompleter
from typing import Dict, List, Optional

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
from cai.repl.commands import (
    memory,
    help,
    graph,
    exit,
    shell,
    env,
    platform,
    kill,
    model,
    turns
)

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
