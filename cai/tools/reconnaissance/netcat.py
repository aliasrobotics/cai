"""
 Here are the tools for netcat command
"""
from cai.tools.common import run_command   # pylint: disable=import-error


def netcat(host: str, port: int, data: str = '',
           args: str = '', ctf=None) -> str:
    """
    A simple netcat tool to connect to a specified host and port.
    Args:
        args: Additional arguments to pass to the netcat command
        host: The target host to connect to
        port: The target port to connect to
        data: Data to send to the host (optional)

    Returns:
        str: The output of running the netcat command
         or error message if connection fails
    """
    try:
        if not isinstance(port, int):
            return "Error: Port must be an integer"
        if port < 1 or port > 65535:
            return "Error: Port must be between 1 and 65535"

        if data:
            command = f'echo "{data}" | nc -w 3 {host} {port} {args}; exit'
        else:
            command = f'echo "" | nc -w 3 {host} {port} {args}; exit'

        result = run_command(command, ctf=ctf)

        return result
    except Exception as e:  # pylint: disable=broad-except
        return f"Error executing netcat command: {str(e)}"
