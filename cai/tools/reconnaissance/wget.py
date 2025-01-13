# FileDownloadTool in exploitFlow

"""
Wget tool
"""
from cai.tools.common import run_command   # pylint: disable=import-error


def wget(url: str, args: str = '', ctf=None) -> str:
    """
    Wget tool to download files from the web.
    Args:
        url: The URL of the file to download
        args: Additional arguments to pass to the wget command

    Returns:
        str: The output of running the wget command
    """
    command = f'wget {args} {url}'
    return run_command(command, ctf=ctf)
