"""
Module for executing Python code and capturing its output.
"""

import io
import sys
from typing import Dict


def execute_python_code(code: str, context: Dict = None) -> str:
    """
    Execute Python code and return the output.

    Args:
        code (str): Python code to execute
        context (Dict, optional): Additional context for execution

    Returns:
        str: Output from code execution
    """
    try:
        local_vars = {}
        if context:
            local_vars.update(context)

        # Capture output using StringIO
        stdout = io.StringIO()
        sys.stdout = stdout

        # Execute code once with captured output
        # nosec B102 # pylint: disable=exec-used
        exec(code, globals(), local_vars)  # nosec 102

        # Restore stdout
        sys.stdout = sys.__stdout__
        output = stdout.getvalue()

        # Return captured output or last expression value
        return output if output else str(
            local_vars.get('__builtins__', {}).get('_', None))

    except Exception as e:  # pylint: disable=broad-except
        return f"Error executing code: {str(e)}"
