"""
Here are the CLI tools for executing commands, they should usually return
with run_command, but you can be creative
"""

from .common import run_command


def list_dir(path: str, args: str, ctf=None) -> str:
    """
    List the contents of a directory.
    by def .
    Args:
        path: The directory path to list contents from
        args: Additional arguments to pass to the ls command

    Returns:
        str: The output of running the ls command
    """
    command = f'ls {path} {args}'
    return run_command(command, ctf=ctf)


def cat_file(args: str, file_path: str, ctf=None) -> str:
    """
    Display the contents of a file.

    Args:
        args: Additional arguments to pass to the cat command
        file_path: Path to the file to display contents of

    Returns:
        str: The output of running the cat command
    """
    command = f'cat {args} {file_path} '
    return run_command(command, ctf=ctf)
