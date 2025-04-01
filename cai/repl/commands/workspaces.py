"""
Workspace command for CAI.
"""
# Standard library imports
import os
from typing import List, Optional

# Third party imports
from rich.console import Console  # pylint: disable=import-error

# Local imports
from cai.repl.commands.base import Command, register_command
from cai.repl.commands.config import get_env_var_value, set_env_var
from cai.repl import repl  # Import the repl module to access the global client
from cai.datarecorder import DataRecorder  # Import DataRecorder

console = Console()


class WorkspaceCommand(Command):
    """Command for managing the current workspace."""

    def __init__(self):
        """Initialize the workspace command."""
        super().__init__(
            name="/workspace",
            description=(
                "Set or display the current workspace name."
                " Affects log file naming."
            ),
            aliases=["/ws"]
        )

        # Add subcommands
        self.add_subcommand(
            "set",
            "Set the current workspace name",
            self.handle_set
        )
        self.add_subcommand(
            "get",
            "Display the current workspace name",
            self.handle_get
        )

    def handle_no_args(self) -> bool:
        """Handle the command when no arguments are provided."""
        return self.handle_get(None)

    def handle_get(self, _: Optional[List[str]] = None) -> bool:
        """Display the current workspace name."""
        current_workspace = get_env_var_value("CAI_WORKSPACE")
        if current_workspace and current_workspace != "Not set":
            console.print(f"Current workspace: [bold green]{current_workspace}[/]")
        else:
            console.print("No workspace is currently set.")
            console.print("Use [yellow]/workspace set <name>[/yellow] to set one.")
        return True

    def handle_set(self, args: Optional[List[str]] = None) -> bool:
        """Set the current workspace name and update the data recorder."""
        if not args or len(args) != 1:
            console.print(
                "[yellow]Usage: /workspace set <workspace_name>[/yellow]"
            )
            return False

        workspace_name = args[0]
        # Allow alphanumeric, underscores, hyphens
        if not all(c.isalnum() or c in ['_', '-'] for c in workspace_name):
            console.print(
                "[red]Invalid workspace name. "
                "Use alphanumeric, underscores, or hyphens only.[/red]"
            )
            return False

        # Set the environment variable first
        if not set_env_var("CAI_WORKSPACE", workspace_name):
            console.print(
                "[red]Failed to set workspace environment variable.[/red]"
            )
            return False

        # Now, try to update the active DataRecorder instance
        new_filename = None
        try:
            # Check if the client and its recorder exist and are valid
            if (repl.client and
                    hasattr(repl.client, 'rec_training_data') and
                    isinstance(repl.client.rec_training_data, DataRecorder)):

                # Preserve the total cost from the old recorder
                old_total_cost = repl.client.rec_training_data.total_cost

                # Create a new recorder with the new workspace name
                # This will generate a new file path
                new_recorder = DataRecorder(workspace_name=workspace_name)

                # Restore the total cost to the new recorder
                new_recorder.total_cost = old_total_cost

                # Replace the old recorder instance in the client
                repl.client.rec_training_data = new_recorder
                new_filename = new_recorder.filename # Get the path of the new log file

                console.print(
                    f"Workspace set to: [bold green]{workspace_name}[/]\n"
                    "Data recorder instance updated.\n"
                    f"Logging will now use file: [cyan]{new_filename}[/]"
                )

            else:
                # Client or recorder not initialized yet, or recorder is None
                console.print(
                    f"Workspace environment variable set to: [bold green]{workspace_name}[/]\n"
                    "Log file prefixing will apply on next session start or "
                    "when logging is enabled."
                )

        except Exception as e:
            # Log the error for debugging, but inform the user gracefully
            # Consider adding more specific logging here if needed
            print(f"Error updating data recorder: {e}") # For debug
            console.print(
                f"[yellow]Workspace environment variable set to "
                f"'{workspace_name}', but failed to update the active "
                f"data recorder instance.[/yellow]"
            )
            # Fallback message if update fails
            console.print(
                "Log file prefixing will apply on the next session start "
                "or when logging is re-enabled."
            )
            # Return True because the env var was set, even if recorder failed
            return True

        return True # Env var set and recorder updated (or handled)


register_command(WorkspaceCommand()) 