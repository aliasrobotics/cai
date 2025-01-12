"""
CLI utilities module for executing shell commands and processing their output.
"""

from cai.tools.common import run_command


def execute_cli_command(command: str) -> str:
    """
    Execute a CLI command and return the output.

    Args:
        command (str): The command to execute. Should be concise and focused.
            Avoid overly verbose commands with unnecessary flags/options.

    Returns:
        str: Command output, formatted for clarity and readability.
            Long outputs will be truncated or filtered to highlight key information.
    """
    return run_command(command)
