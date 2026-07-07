# FileDownloadTool in exploitFlow

"""
Wget tool
"""

import shlex
from cai.tools.common import run_command  # pylint: disable=import-error
from cai.sdk.agents import function_tool


@function_tool
def wget(url: str, args: str = "", ctf=None) -> str:
    """
    Wget tool to download files from the web.
    Args:
        url: The URL of the file to download
        args: Additional arguments to pass to the wget command

    Returns:
        str: The output of running the wget command
    """
    command = f"wget {args} {shlex.quote(url)}"
    return run_command(command, ctf=ctf)


# --- Auto-register with ToolRegistry ---
from cai.tool_registry import TOOL_REGISTRY  # noqa: E402
TOOL_REGISTRY.register("wget", wget, categories=['recon', 'web'])
