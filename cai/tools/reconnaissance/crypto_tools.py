"""
 Here are crypto tools
"""
import base64
# # URLDecodeTool
# # HexDumpTool
# # Base64DecodeTool
# # ROT13DecodeTool
# # BinaryAnalysisTool


# def strings_command(file_path: str, ctf=None) -> str:
#     """
#     Extract printable strings from a binary file.

#     Args:
#         args: Additional arguments to pass to the strings command
#         file_path: Path to the binary file to extract strings from

#     Returns:
#         str: The output of running the strings command
#     """
#     command = f'strings {file_path} '
#     return run_command(ctf, command)


def decode64(input_data: str) -> str:
    """
    Decode a base64-encoded string.

    Args:
        input_data: The base64-encoded string to decode
        args: Additional arguments (not used in this function)

    Returns:
        str: The decoded string
    """

    try:
        decoded_bytes = base64.b64decode(input_data)
        decoded_str = decoded_bytes.decode('utf-8')
        return decoded_str
    except UnicodeDecodeError as e:
        print(f"Error decoding bytes to string: {e}")
        return f"Error decoding bytes to string: {str(e)}"
