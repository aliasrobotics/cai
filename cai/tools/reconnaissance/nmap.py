"""
Here are the nmap tools.
"""

from cai.tools.common import run_command  # pylint: disable=E0401


def nmap(args: str, target: str, ctf=None) -> str:
    """
    A simple nmap tool to scan a specified target.

    Args:
        args: Additional arguments to pass to the nmap command
        target: The target host or IP address to scan

    Returns:
        str: The output of running the nmap command
    """
    command = f'nmap {args} {target}'
    return run_command(command, ctf=ctf)
