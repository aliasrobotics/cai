

def pwd_command(path: str, args: str = "") -> str:
    """
    Retrieve the current working directory.

    Returns:
        str: The absolute path of the current working directory
    """
    global ctf
    command = f'pwd'
    return run_ctf(ctf, command)

def strings_command(args: str, file_path: str) -> str:
    """
    Extract printable strings from a binary file.

    Args:
        args: Additional arguments to pass to the strings command
        file_path: Path to the binary file to extract strings from

    Returns:
        str: The output of running the strings command
    """
    global ctf
    command = f'strings {file_path} '
    return run_ctf(ctf, command)


def nmap_command(ip_address: str, args: str = "") -> str:
    """
    Scan a network host for open ports and services.

    Args:
        ip_address: The IP address or hostname of the target to scan
        args: Additional arguments to pass to the nmap command

    Returns:
        str: The output of running the nmap command
    """
    global ctf
    command = f'nmap {ip_address} {args}'
    return run_ctf(ctf, command)


def netcat_command(ip_address: str, port: str, args: str = "") -> str:
    """
    Connect to a network host via a specific port.
    """
    global ctf
    command = f'nc {ip_address} {port} {args}'
    return run_ctf(ctf, command)

def decode64(input_data: str, args: str = "") -> str:
    """
    Decode a base64-encoded string.

    Args:
        input_data: The base64-encoded string to decode
        args: Additional arguments (not used in this function)

    Returns:
        str: The decoded string
    """
    import base64
    try:
        decoded_bytes = base64.b64decode(input_data)
        decoded_str = decoded_bytes.decode('utf-8')
        return decoded_str
    except Exception as e:
        print(color(f"Error decoding base64 data: {e}", fg="red"))
        return f"Error decoding base64 data: {str(e)}"


