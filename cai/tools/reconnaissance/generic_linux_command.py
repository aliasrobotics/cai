"""
This is used to create a generic linux command.
"""
import os
import subprocess  # nosec B404
from typing import Optional
from cai.constants import ASYNC_COMMANDS
from cai.tools.common import (
    run_command,
    list_shell_sessions,
    get_session_output,
    terminate_session
)  # pylint: disable=import-error,unused-import,line-too-long # noqa: E501


def generic_linux_command(
    command: str = "",
    args: str = "",
    ctf=None,
    session_id: Optional[str] = None
) -> str:
    """
    A simple tool to do a linux command.

    Args:
        command: The name of the command
        args: Additional arguments to pass to the command
        ctf: CTF environment object (if running in CTF)
        session_id: ID of an existing session to send the
            command to

    Returns:
        str: The output of running the linux command or
            status message for async commands
    """
    try:
        # Special commands for session management
        if command == "session":
            if args == "list":
                sessions = list_shell_sessions()
                if not sessions:
                    return "No active sessions"

                result = "Active sessions:\n"
                for session in sessions:
                    result += f"ID: {
                        session['session_id']} | Command: {
                        session['command']} | Last activity: {
                        session['last_activity']}\n"
                return result

            if args.startswith("output "):
                session_id = args.split(" ")[1]
                return get_session_output(session_id)

            if args.startswith("kill "):
                session_id = args.split(" ")[1]
                return terminate_session(session_id)

            return "Unknown session command." \
                "Available: list, output <id>, kill <id>"

        # Check if command is in async commands list
        if any(cmd in command for cmd in ASYNC_COMMANDS):
            # Run command in background
            if session_id:
                # Send input to existing session
                return run_command(
                    f"{command} {args}",
                    session_id=session_id,
                    ctf=ctf
                )
            else:
                # Start new session
                return run_command(
                    f"{command} {args}",
                    background=True,
                    ctf=ctf
                )
        else:
            # Run command normally
            return run_command(f"{command} {args}", ctf=ctf)

    except subprocess.CalledProcessError as e:
        return f"Error executing command: {str(e)}"
    except Exception as e:  # pylint: disable=broad-except
        return f"Error: {str(e)}"
