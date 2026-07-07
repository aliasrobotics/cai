"""
Here are the curl tools.
"""

import shlex
from cai.tools.common import run_command  # pylint: disable=import-error
from cai.sdk.agents import function_tool


@function_tool
def curl(args: str = "", target: str = "", ctf=None) -> str:
    """
    A simple curl tool to make HTTP requests to a specified target.

    Args:
        args: Additional arguments to pass to the curl command
        target: The target URL to request

    Returns:
        str: The output of running the curl command
    """
    command = f"curl {args} {shlex.quote(target)}"
    return run_command(command, ctf=ctf)


# --- Auto-register with ToolRegistry ---
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402
TOOL_REGISTRY.register("curl", curl, categories=['recon', 'web'])
