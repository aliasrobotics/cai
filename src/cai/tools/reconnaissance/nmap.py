"""
Here are the nmap tools.
"""

import shlex
from cai.tools.common import run_command  # pylint: disable=E0401
from cai.sdk.agents import function_tool


@function_tool
def nmap(args: str, target: str, ctf=None) -> str:
    """
    A simple nmap tool to scan a specified target.

    Args:
        args: Additional arguments to pass to the nmap command
        target: The target host or IP address to scan

    Returns:
        str: The output of running the nmap command
    """
    command = f"nmap {args} {shlex.quote(target)}"
    return run_command(command, ctf=ctf, stream=True)


# --- Auto-register with ToolRegistry ---
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402
TOOL_REGISTRY.register("nmap", nmap, categories=['recon', 'network'])
