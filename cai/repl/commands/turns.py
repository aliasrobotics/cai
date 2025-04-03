"""
Turns command for CAI REPL.
This module provides commands for viewing and changing the maximum number
of turns.
"""
import os
from typing import (
    Dict,
    List,
    Optional
)
from rich.console import Console  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error

from cai.repl.commands.base import Command, register_command

console = Console()


class TurnsCommand(Command):
    """Command for viewing and changing the maximum number of turns."""

    def __init__(self):
        """Initialize the turns command."""
        super().__init__(
            name="/turns",
            description="View or change the maximum number of turns",
            aliases=["/t"]
        )

    def handle(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the turns command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_turns_command(args)

    def handle_turns_command(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Change the maximum number of turns for CAI.

        Args:
            args: List containing the number of turns
            messages: Optional list of conversation messages

        Returns:
            bool: True if the max turns was changed successfully
        """
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
                turns = 'inf'
            else:
                turns = int(turns)

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


# Register the command
register_command(TurnsCommand())
