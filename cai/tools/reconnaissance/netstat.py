# NetworkConnectionstool in exploitFlow
"""
Netstat tool
"""
from cai.tools.common import run_command   # pylint: disable=import-error


def netstat(args: str = '', ctf=None) -> str:
    """
    netstat tool to list all listening ports and their associated programs.
    Args:
        args: Additional arguments to pass to the netstat command
    Returns:
        str: The output of running the netstat command
    """
    command = f'netstat -tuln {args}'
    return run_command(command, ctf=ctf)
