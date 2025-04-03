"""
Exit command for CAI REPL.
This module provides the command to exit the REPL.
"""
import sys
from typing import Dict, List, Optional

from cai.repl.commands.base import Command, register_command


class ExitCommand(Command):
    """Command for exiting the REPL."""

    def __init__(self):
        """Initialize the exit command."""
        super().__init__(
            name="/exit",
            description="Exit the CAI REPL",
            aliases=["/q", "/quit"]
        )

    def handle(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the exit command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        sys.exit(0)


# Register the command
register_command(ExitCommand())
