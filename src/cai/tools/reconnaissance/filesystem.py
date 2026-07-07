"""
Here are the CLI tools for executing commands.
"""

import shlex
from cai.tools.common import run_command  # pylint: disable=E0401
from cai.sdk.agents import function_tool


@function_tool
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
    command = f"ls {shlex.quote(path)} {args}"
    return run_command(command, ctf=ctf)


@function_tool
def cat_file(file_path: str, args: str = "", ctf=None) -> str:
    """
    Display the contents of a file.

    Args:
        args: Additional arguments to pass to the cat command
        file_path: Path to the file to display contents of

    Returns:
        str: The output of running the cat command
    """
    command = f"cat {args} {shlex.quote(file_path)}"
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
    command = "pwd"
    return run_command(command, ctf=ctf)


@function_tool
def find_file(file_path: str, args: str = "", ctf=None) -> str:
    """
    Find a file in the filesystem.
    """
    command = f"find {shlex.quote(file_path)} {args}"
    return run_command(command, ctf=ctf)


# --- Auto-register with ToolRegistry ---
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402
TOOL_REGISTRY.register("list_dir", list_dir, categories=["recon", "misc"])
TOOL_REGISTRY.register("cat_file", cat_file, categories=["recon", "misc"])
TOOL_REGISTRY.register("pwd_command", pwd_command, categories=["recon", "misc"])
TOOL_REGISTRY.register("find_file", find_file, categories=["recon", "misc"])
