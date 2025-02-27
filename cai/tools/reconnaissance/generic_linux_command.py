"""
This is used to create a generic linux command.
"""
from cai.tools.common import run_command, list_shell_sessions, get_session_output, terminate_session  # pylint: disable=import-error


def generic_linux_command(command: str = "", args: str = "", ctf=None,
                          async_mode: bool = False, session_id: str = None) -> str:
    """
    A simple tool to do a linux command.

    Args:
        command: The name of the command
        args: Additional arguments to pass to the command
        ctf: CTF environment object (if running in CTF)
        async_mode: Whether to run the command asynchronously
        session_id: ID of an existing session to send the command to

    Returns:
        str: The output of running the linux command or status message for async commands
    """
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

        return "Unknown session command. Available: list, output <id>, kill <id>"

    # Regular command execution
    full_command = f'{command} {args}'.strip()

    # Detect if this should be an async command
    if not async_mode and not session_id:
        async_commands = [
            'nc',
            'netcat',
            'ncat',
            'telnet',
            'ssh',
            'python -m http.server']
        async_mode = any(cmd in full_command for cmd in async_commands)

    return run_command(full_command, ctf=ctf,
                       async_mode=async_mode, session_id=session_id)
