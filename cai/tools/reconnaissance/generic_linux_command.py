"""
This is used to create a generic linux command.
"""
from cai.tools.common import run_command, list_shell_sessions, get_session_output, terminate_session  # pylint: disable=import-error


def generic_linux_command(
        command: str = "",
        args: str = "",
        ctf=None,  # type: ignore
        async_mode: bool = False,
        session_id: str = None) -> str:  # pylint: disable=too-many-arguments
    """
    Execute a Linux command with support for both synchronous and 
    asynchronous operation.

    This function provides a flexible interface to run Linux commands, 
    with special handling for long-running network commands and 
    session management. It can execute commands directly or
    within an existing session context.

    Args:
        command (str, optional): The Linux command to execute. 
            Defaults to "".
        args (str, optional): Command line arguments to pass to the command. 
            Defaults to "".
        ctf (object, optional): CTF environment object for specialized execution contexts.
            Defaults to None.
        async_mode (bool, optional): Force asynchronous execution mode. Some network commands
            (nc, ssh, telnet, etc.) automatically run asynchronously. 
            Defaults to False.
        session_id (str, optional): ID of an existing session to execute the command in.
            If provided, the command runs in that session's context. 
            Defaults to None.

    Returns:
        str: For synchronous commands, returns the command output.
            For asynchronous commands, returns a status message with session information.
            For session management commands, returns session status or listing information.

    Note:
        Special 'session' commands are available:
        - 'session list': Shows all active sessions
        - 'session output <id>': Gets output from a specific session
        - 'session kill <id>': Terminates a specific session
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
