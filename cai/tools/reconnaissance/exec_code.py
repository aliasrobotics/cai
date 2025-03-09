"""
Tool for executing code via LLM tool calls.
"""
from cai.tools.common import run_command  # pylint: disable=import-error

def execute_code(code: str = "", language: str = "python",
                filename: str = "exploit", ctf=None) -> str:
    """
    Create a file code store it and execute it

    This tool allows for executing code provided in different
    programming languages. It creates a permanent file with the provided code
    and executes it using the appropriate interpreter. You can exec this
    code as many times as you want using `generic_linux_command` tool.

    Priorize: Python and Perl

    Args:
        code: The code snippet to execute
        language: Programming language to use (default: python)
        filename: Base name for the file without extension (default: exploit)
        ctf: CTF environment object for execution context

    Returns:
        Command output or error message from execution
    """
    
    if not code:
        return "No code provided to execute"

    # Map file extensions
    extensions = {
        "python": "py",
        "php": "php",
        "bash": "sh",
        "ruby": "rb",
        "perl": "pl"
    }
    ext = extensions.get(language.lower(), "txt")
    full_filename = f"{filename}.{ext}"

    create_cmd = f"cat << 'EOF' > {full_filename}\n{code}\nEOF"
    result = run_command(create_cmd, ctf=ctf)
    if "error" in result.lower():
        return f"Failed to create code file: {result}"

    if language.lower() == "python":
        exec_cmd = f"python3 {full_filename}"
    elif language.lower() == "php":
        exec_cmd = f"php {full_filename}"
    elif language.lower() in ["bash", "sh"]:
        exec_cmd = f"bash {full_filename}"
    elif language.lower() == "ruby":
        exec_cmd = f"ruby {full_filename}"
    elif language.lower() == "perl":
        exec_cmd = f"perl {full_filename}"
    else:
        return f"Unsupported language: {language}"

    output = run_command(exec_cmd, ctf=ctf)

    return output




