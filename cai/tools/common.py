"""
Basic utilities for executing commands inside or outside of virtual
containers.
"""

import subprocess  # nosec B404
from wasabi import color  # pylint: disable=import-error


def _run_ctf(ctf, command, stdout=True):
    try:
        # Ensure the command is executed in a shell that supports command
        # chaining
        output = ctf.get_shell(command)
        # exploit_logger.log_ok()

        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output
    except Exception as e:  # pylint: disable=broad-except
        print(color(f"Error executing CTF command: {e}", fg="red"))
        # exploit_logger.log_error(str(e))
        return f"Error executing CTF command: {str(e)}"


def _run_attacker_machine(command, stdout=True):
    try:
        # nosec B602 - shell=True is required for command chaining
        result = subprocess.run(
            command,
            shell=True,  # nosec B602
            capture_output=True,
            text=True,
            check=True)
        output = result.stdout
        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output
    except Exception as e:  # pylint: disable=broad-except
        print(color(f"Error executing local command: {e}", fg="red"))
        return f"Error executing local command: {str(e)}"


def run_command(command, ctf=None, stdout=True):
    """
    Run command either in CTF container or
    on the local attacker machine
    """
    if ctf:
        return _run_ctf(ctf, command, stdout)
    return _run_attacker_machine(command, stdout)
