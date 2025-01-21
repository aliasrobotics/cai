"""
Here are the CLI tools for executing commands.
"""

from cai.tools.common import run_command  # pylint: disable=E0401


def list_dir(path: str, args: str = "", ctf=None) -> str:
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


def cat_file(file_path: str, args: str = "", ctf=None) -> str:
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


# FileSearchTool
# ListDirTool
# TextSearchTool
# FileAnalysisTool
# StringExtractionTool
# ReadFileTool
# FilePermissionsTool
# FileCompressionTool


def pwd_command(ctf=None) -> str:
    """
    Retrieve the current working directory.

    Returns:
        str: The absolute path of the current working directory
    """
    command = 'pwd'
    return run_command(command, ctf=ctf)


def find_file(file_path: str, args: str = "", ctf=None) -> str:
    """
    Find a file in the filesystem.
    """
    command = f'find {file_path} {args}'
    return run_command(command, ctf=ctf)
