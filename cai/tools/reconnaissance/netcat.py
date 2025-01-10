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
    """
    if data:
        command = f'echo "{data}" | nc -w 3 {host} {port} {args}'
    else:
        command = f'nc -w 3 {host} {port} {args}'
    return run_command(command, ctf=ctf)
