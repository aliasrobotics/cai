"""
Environment command for CAI REPL.
This module provides commands for displaying environment variables.
"""
import os
from typing import (
    List,
    Optional
)
from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error

from cai.repl.commands.base import Command, register_command

console = Console()


class EnvCommand(Command):
    """Command for displaying environment variables."""

    def __init__(self):
        """Initialize the env command."""
        super().__init__(
            name="/env",
            description="Display environment variables and their values",
            aliases=["/e"]
        )

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the env command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_env_command()

    def handle_env_command(self) -> bool:
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


# Register the command
register_command(EnvCommand())
