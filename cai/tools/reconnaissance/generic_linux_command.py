"""
This is used to create a generic linux command.
"""
from cai.tools.common import run_command  # pylint: disable=import-error


def generic_linux_command(command: str = "", args: str = "", ctf=None) -> str:
    """
    A simple tool to do a linux command.

    Args:
        command: The name of the command
        args: Additional arguments to pass to the command

    Returns:
        str: The output of running the linux command
    """
    command = f'{command} {args}'
    return run_command(command, ctf=ctf)
