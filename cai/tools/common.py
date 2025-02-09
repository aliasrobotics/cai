"""
Basic utilities for executing tools
inside or outside of virtual containers.
"""

import subprocess  # nosec B404
from wasabi import color  # pylint: disable=import-error


def _run_ctf(ctf, command, stdout=False):
    try:
        # Ensure the command is executed in a shell that supports command
        # chaining
        output = ctf.get_shell(command)
        # exploit_logger.log_ok()

        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output  # output if output else result.stder
    except Exception as e:  # pylint: disable=broad-except
        print(color(f"Error executing CTF command: {e}", fg="red"))
        # exploit_logger.log_error(str(e))
        return f"Error executing CTF command: {str(e)}"


def _run_local(command, stdout=False):
    try:
        # nosec B602 - shell=True is required for command chaining
        result = subprocess.run(
            command,
            shell=True,  # nosec B602
            capture_output=True,
            text=True,
            check=False,
            timeout=100)
        output = result.stdout if result.stdout else result.stderr
        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output
    except subprocess.TimeoutExpired as e:
        error_output = e.stdout.decode() if e.stdout else str(e)
        if stdout:
            print("\033[32m" + error_output + "\033[0m")
        return error_output
    except Exception as e:  # pylint: disable=broad-except
        error_msg = f"Error executing local command: {e}"
        print(color(error_msg, fg="red"))
        return error_msg


def run_command(command, ctf=None, stdout=False):
    """
    Run command either in CTF container or
    on the local attacker machine
    """
    if ctf:
        return _run_ctf(ctf, command, stdout)
    return _run_local(command, stdout)
