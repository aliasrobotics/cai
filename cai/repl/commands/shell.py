"""
Shell command for CAI REPL.
This module provides commands for executing shell commands.
"""
import os
import signal
import subprocess  # nosec B404
from typing import (
    Dict,
    List,
    Optional
)
from rich.console import Console  # pylint: disable=import-error

from cai.repl.commands.base import Command, register_command

console = Console()


class ShellCommand(Command):
    """Command for executing shell commands."""

    def __init__(self):
        """Initialize the shell command."""
        super().__init__(
            name="/shell",
            description="Execute shell commands in the current environment",
            aliases=["/s", "$"]
        )

    def handle(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the shell command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            console.print("[red]Error: No command specified[/red]")
            return False

        return self.handle_shell_command(args)
    def handle_shell_command(self, command_args: List[str], messages: Optional[List[Dict]] = None) -> bool:
        """Execute a shell command, potentially changing directory first.

        Args:
            command_args: The shell command and its arguments
            messages: Optional list of conversation messages

        Returns:
            bool: True if the command was executed successfully
        """
        if not command_args:
            console.print("[red]Error: No command specified[/red]")
            return False

        original_command = " ".join(command_args)
        shell_command_to_execute = original_command
        
        # Get workspace path from environment variable
        workspace_name = os.getenv("CAI_WORKSPACE", "")
        effective_cwd = None

        # Check if workspace is set
        if workspace_name:
            # Construct the workspace path
            base_dir = os.getenv("CAI_WORKSPACE_DIR", "workspaces")
            workspace_path = os.path.join(base_dir, workspace_name)
            
            # Check if the workspace path exists
            if os.path.isdir(workspace_path):
                effective_cwd = workspace_path
            else:
                # Fallback to current directory
                console.print(f"[yellow]Warning: Workspace '{workspace_name}' not found at {workspace_path}.[/yellow]")
                effective_cwd = os.getcwd()
            
            # For os.system when using async commands, prepend cd
            if effective_cwd != os.getcwd():
                shell_command_to_execute = f"cd {effective_cwd!r} && {original_command}"
                console.print(f"[dim]Running in workspace: {effective_cwd}[/dim]")
            else:
                console.print(f"[dim]Running in current directory: {effective_cwd}[/dim]")
        else:
            effective_cwd = os.getcwd()
            console.print(f"[dim]Running in current directory: {effective_cwd}[/dim]")

        console.print(f"[blue]Executing:[/blue] {original_command}")

        # Save original signal handler
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        try:
            # Set temporary handler for SIGINT that only affects shell command
            def shell_sigint_handler(sig, frame):  # pylint: disable=unused-argument
                # Just allow KeyboardInterrupt to propagate
                signal.signal(signal.SIGINT, original_sigint_handler)
                raise KeyboardInterrupt

            signal.signal(signal.SIGINT, shell_sigint_handler)

            # Determine if the *original* command suggests async execution
            async_commands = [
                'nc', 'netcat', 'ncat', 'telnet', 'ssh',
                'python -m http.server'
            ]
            is_async = any(cmd in original_command for cmd in async_commands)

            if is_async:
                # For async commands, use os.system. It respects the shell's cd
                console.print(
                    "[yellow]Running in async mode "
                    "(Ctrl+C to return to REPL)[/yellow]"
                )
                # os.system runs in a subshell, inheriting the environment
                # The shell handles the `cd ... && ...` part correctly.
                os.system(shell_command_to_execute)  # nosec B605
                console.print(
                    "[green]Async command completed or detached[/green]"
                )
                return True

            # For regular commands, use subprocess.Popen
            # Pass the potentially modified command (with cd)
            # Use cwd parameter for Popen for reliability
            process = subprocess.Popen(  # nosec B602 # pylint: disable=consider-using-with # noqa: E501
                original_command, # Execute original command directly
                shell=True,       # Shell handles cd if present in command_to_execute
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                cwd=effective_cwd # Set the current working directory explicitly
            )

            # Show output in real time
            for line in iter(process.stdout.readline, ''):
                print(line, end='')

            # Wait for process to finish
            process.wait()

            if process.returncode == 0:
                console.print(
                    "[green]Command completed successfully[/green]")
            else:
                console.print(
                    f"[yellow]Command exited with code {
                        process.returncode}"
                    f"[/yellow]")
            return True

        except KeyboardInterrupt:
            # Handle CTRL+C only for this command
            try:
                if not is_async:
                    process.terminate()
                console.print("\n[yellow]Command interrupted by user[/yellow]")
            except Exception:  # pylint: disable=broad-except # nosec
                pass
            return True
        except Exception as e:  # pylint: disable=broad-except
            console.print(f"[red]Error executing command: {str(e)}[/red]")
            return False
        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, original_sigint_handler)

# Register the command
register_command(ShellCommand())
