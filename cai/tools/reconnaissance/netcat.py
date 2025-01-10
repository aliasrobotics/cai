from cai.tools.common import run_command
"""
Here are the netcat tools.
"""
def netcat(args: str, host: str, port: int, data: str = '', ctf=None) -> str:
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
