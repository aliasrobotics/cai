from wasabi import color
import subprocess
import os

def _run_ctf(ctf, command, stdout=True):
    try:
        # Ensure the command is executed in a shell that supports command chaining
        output = ctf.get_shell(command)
        # exploit_logger.log_ok()

        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output
    except Exception as e:
        print(color(f"Error executing CTF command: {e}", fg="red"))
        # exploit_logger.log_error(str(e))
        return f"Error executing CTF command: {str(e)}"

def _run_attacker_machine(command, stdout=True):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout
        if stdout:
            print("\033[32m" + output + "\033[0m")
        return output
    except Exception as e:
        print(color(f"Error executing local command: {e}", fg="red"))
        return f"Error executing local command: {str(e)}"

def run_command(command, ctf=None, stdout=True):
    """
    Run command either in CTF container or on local attacker machine based on CTF_IN_DOCKER flag
    """
    if os.getenv("CTF_IN_DOCKER").lower() == "true" and ctf:
        return _run_ctf(ctf, command, stdout)
    else:
        return _run_attacker_machine(command, stdout)
