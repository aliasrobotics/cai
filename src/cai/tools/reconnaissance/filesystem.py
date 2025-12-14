"""
Here are the CLI tools for executing commands.
"""

from cai.tools.common import run_command  # pylint: disable=E0401
from cai.sdk.agents import function_tool

@function_tool
def list_dir(path: str, args: str = "", ctf=None) -> str:
    """
    List the contents of a directory.
    
    Args:
        path: The directory path to list contents from
        args: Additional arguments to pass to the ls command

    Returns:
        str: The output of running the ls command
    """
    command = f'ls {args} "{path}"'
    return run_command(command, ctf=ctf)

@function_tool
def cat_file(file_path: str, args: str = "", ctf=None) -> str:
    """
    Display the contents of a file.

    Args:
        file_path: Path to the file to display contents of
        args: Additional arguments to pass to the cat command

    Returns:
        str: The output of running the cat command
    """
    command = f'cat {args} "{file_path}"'
    return run_command(command, ctf=ctf)


# FileSearchTool
# ListDirTool
# TextSearchTool
# FileAnalysisTool
# StringExtractionTool
# ReadFileTool
# FilePermissionsTool
# FileCompressionTool

@function_tool
def pwd_command(ctf=None) -> str:
    """
    Retrieve the current working directory.

    Returns:
        str: The absolute path of the current working directory
    """
    command = 'pwd'
    return run_command(command, ctf=ctf)

@function_tool
def find_file(file_path: str, args: str = "", ctf=None) -> str:
    """
    Find a file in the filesystem.
    
    Args:
        file_path: The search path or pattern to find files
        args: Additional arguments to pass to the find command

    Returns:
        str: The output of running the find command
    """
    command = f'find {args} "{file_path}"'
    return run_command(command, ctf=ctf)
