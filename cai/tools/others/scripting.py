"""
This is used to create and execute a script in python
"""

import re
import sys
from io import StringIO
import ast


def scripting_tool(command: str = "", args: str = "") -> str:
    """Scripting tool for executing Python code directly in memory.
    IMPORTANT: Use with caution - executes Python code directly.
    IMPORTANT: Remember to import all the modules and libraries you need.

    Args:
        command: Python code, with or without markdown format. Can handle:
            - Raw Python code
            - Markdown formatted code (```python\ncode)
            - Code with leading/trailing whitespace
        args: Additional command line arguments
        ctf: CTF context object

    Returns:
        str: Output from the executed Python code

    Raises:
        ValueError: If the command is empty or invalid
        SecurityError: If potentially dangerous operations are detected
    """

    if not command or not isinstance(command, str):
        raise ValueError("Command must be a non-empty string")

    command = command.strip()

    markdown_patterns = [
        r"^```python\n(.*?)\n```",  # Standard markdown
        r"^```python(.+?)```",      # No newlines
        r"^```\n(.*?)\n```",        # No language specified
        r"^`{1,3}(.*?)`{1,3}"      # Single or triple backticks
    ]
    script = command
    for pattern in markdown_patterns:
        match = re.search(pattern, command, re.DOTALL)
        if match:
            script = match.group(1)
            break

    script = script.strip()
    if not script:
        raise ValueError("No valid Python code found in command")

    try:
        tree = ast.parse(script)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)
                          ):  # Check for potentially dangerous operations
                module = node.names[0].name.split('.')[0]
                if module in ['os', 'sys', 'subprocess', 'shutil']:
                    raise SecurityError(
                        f"Importing potentially dangerous module: {module}")
    except SyntaxError as e:
        return f"Python syntax error: {str(e)}"
    except SecurityError as e:
        return f"Security check failed: {str(e)}"

    # Capture stdout
    old_stdout = sys.stdout
    redirected_output = StringIO()
    sys.stdout = redirected_output

    try:
        local_vars = {}
        if args:
            local_vars['args'] = args

        exec(script, {'__builtins__': __builtins__}, local_vars)

        # Get the output
        output = redirected_output.getvalue()
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Error during execution: {str(e)}"
    finally:
        sys.stdout = old_stdout  # restore


class SecurityError(Exception):  # to be filled
    """
    TO-DO
    """

    pass
