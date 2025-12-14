"""
Here are the curl tools.
"""
from cai.tools.common import run_command  # pylint: disable=import-error
from cai.sdk.agents import function_tool

@function_tool
def curl(args: str = "", target: str = "", ctf=None) -> str:
    """
    A simple curl tool to make HTTP requests to a specified target.
    
    This is a convenience wrapper that executes 'curl' through the main 
    generic_linux_command interface, which provides comprehensive security filtering.

    Args:
        args: Additional arguments to pass to the curl command
        target: The target URL to request
        ctf: CTF context (if applicable)

    Returns:
        str: The output of running the curl command
        
    Note:
        All commands are processed through generic_linux_command which applies 
        comprehensive security protections including Unicode homograph detection,
        command substitution blocking, and dangerous pattern filtering.
    """
    # Simple validation to prevent empty targets
    if not target.strip():
        return "Error: Target URL cannot be empty"
    
    # Pass directly to the main command execution system for full security handling
    command = f'curl {args} "{target}"'
    return run_command(command, ctf=ctf)
