"""
Shell command for CAI REPL.
This module provides commands for executing shell commands.
"""
import os
import signal
import subprocess  # nosec B404
from typing import (
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

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the shell command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            console.print("[red]Error: No command specified[/red]")
            return False

        return self.handle_shell_command(args)

    def handle_shell_command(self, command_args: List[str]) -> bool:
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
            def shell_sigint_handler(sig, frame):  # pylint: disable=unused-argument
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
                # For async commands, use os.system to allow terminal
                # interaction
                console.print(
                    "[yellow]Running in async mode "
                    "(Ctrl+C to return to REPL)[/yellow]")
                os.system(shell_command)  # nosec B605
                console.print(
                    "[green]Async command completed or detached[/green]")
                return True

            # For regular commands, use the standard approach
            process = subprocess.Popen(  # nosec B602 # pylint: disable=consider-using-with # noqa: E501
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
