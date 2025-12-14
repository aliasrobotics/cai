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

@function_tool
def text_search(pattern: str, file_path: str, args: str = "", ctf=None) -> str:
    """
    Search for a text pattern within a file or files.
    
    Args:
        pattern: The text pattern to search for
        file_path: Path to file or directory to search in
        args: Additional arguments to pass to grep command

    Returns:
        str: The output of running the grep command
    """
    command = f'grep {args} "{pattern}" "{file_path}"'
    return run_command(command, ctf=ctf)

@function_tool
def file_analysis(file_path: str, args: str = "", ctf=None) -> str:
    """
    Analyze file properties and content.
    
    Args:
        file_path: Path to the file to analyze
        args: Additional arguments to pass to file command

    Returns:
        str: The output of running file analysis commands
    """
    # Get basic file information
    info_command = f'file {args} "{file_path}"'
    info_result = run_command(info_command, ctf=ctf)
    
    # Get file size and permissions
    stat_command = f'stat -c "%A %h %U %G %s %y %n" "{file_path}"'
    stat_result = run_command(stat_command, ctf=ctf)
    
    return f"File Information:\n{info_result}\n\nFile Statistics:\n{stat_result}"

@function_tool
def file_permissions(file_path: str, args: str = "", ctf=None) -> str:
    """
    Check and display file permissions.
    
    Args:
        file_path: Path to the file or directory to check permissions for
        args: Additional arguments to pass to ls command

    Returns:
        str: The output of running permission checking commands
    """
    command = f'ls -la {args} "{file_path}"'
    return run_command(command, ctf=ctf)

@function_tool
def string_extraction(file_path: str, args: str = "", ctf=None) -> str:
    """
    Extract printable strings from a file.
    
    Args:
        file_path: Path to the file to extract strings from
        args: Additional arguments to pass to the strings command

    Returns:
        str: The output of running the strings command
    """
    command = f'strings {args} "{file_path}"'
    return run_command(command, ctf=ctf)

# FileSearchTool
# ListDirTool
# TextSearchTool
# FileAnalysisTool
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
