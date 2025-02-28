"""
Graph command for CAI REPL.
This module provides commands for visualizing the agent interaction graph.
"""
from typing import List, Optional
from rich.console import Console

from cai.repl.commands.base import Command, register_command

console = Console()


class GraphCommand(Command):
    """Command for visualizing the agent interaction graph."""

    def __init__(self):
        """Initialize the graph command."""
        super().__init__(
            name="/graph",
            description="Visualize the agent interaction graph",
            aliases=["/g"]
        )

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the graph command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_graph_show()

    def handle_graph_show(self) -> bool:
        """Handle /graph show command"""
        # Import here to avoid circular imports
        from cai.repl.repl import client

        if not client or not client._graph:  # pylint: disable=protected-access
            console.print("[yellow]No conversation graph available.[/yellow]")
            return True

        try:
            console.print("\n[bold]Conversation Graph:[/bold]")
            console.print("------------------")
            console.print(
                client._graph.ascii())  # pylint: disable=protected-access
            console.print()
            return True
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[red]Error displaying graph: {e}[/red]")
            return False


# Register the command
register_command(GraphCommand())
