"""
Kill command for CAI REPL.
This module provides commands for terminating active processes or sessions.
"""
import os
import signal
from typing import (
    Dict,
    List,
    Optional
)
from rich.console import Console  # pylint: disable=import-error

from cai.repl.commands.base import Command, register_command

console = Console()


class KillCommand(Command):
    """Command for terminating active processes or sessions."""

    def __init__(self):
        """Initialize the kill command."""
        super().__init__(
            name="/kill",
            description="Terminate active processes or sessions",
            aliases=["/k"]
        )

    def handle(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the kill command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_kill_command(args)

    def handle_kill_command(self, args: List[str], messages: Optional[List[Dict]] = None) -> bool:
        """Kill a background process by PID.

        Args:
            args: List containing the PID to kill
            messages: Optional list of conversation messages

        Returns:
            bool: True if the process was killed successfully
        """
        if not args:
            console.print("[red]Error: No PID specified[/red]")
            return False

        try:
            pid = int(args[0])

            # Try to kill the process group
            try:
                os.killpg(pid, signal.SIGTERM)
                console.print(f"[green]Process group {pid} terminated[/green]")
            except BaseException:  # pylint: disable=broad-exception-caught
                # If killing the process group fails, try killing just the
                # process
                os.kill(pid, signal.SIGTERM)
                console.print(f"[green]Process {pid} terminated[/green]")

            return True
        except ValueError:
            console.print("[red]Error: Invalid PID format[/red]")
            return False
        except ProcessLookupError:
            console.print(
                f"[yellow]No process with PID {
                    args[0]} found[/yellow]")
            return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            console.print(f"[red]Error killing process: {str(e)}[/red]")
            return False


# Register the command
register_command(KillCommand())
