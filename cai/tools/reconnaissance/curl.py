"""
Here are the curl tools.
"""
from cai.tools.common import run_command  # pylint: disable=import-error


def curl(args: str = "", target: str = "", ctf=None) -> str:
    """
    A simple curl tool to make HTTP requests to a specified target.

    Args:
        args: Additional arguments to pass to the curl command
        target: The target URL to request

    Returns:
        str: The output of running the curl command
    """
    command = f'curl {args} {target}'
    return run_command(command, ctf=ctf)
