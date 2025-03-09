"""
SSH Pass tool for executing remote commands via SSH using password authentication.

Example of generalization: to execute a local command we use a bash wrapper
in `generic_linux_command` and in `execute_cli_command` -> `cai.tools.misc.cli_utils`
Using these wrappers, commands like `ssh` or `netcat` usually get trapped
by the LLM, so prompt engineering is used to execute the command locally
and return the result. Another solution is to implement interactive CLIs, for now this command
covers all SSH use cases. A much more logical and simpler implementation than
`hackingbuddyGPT` `https://github.com/ipa-lab/hackingBuddyGPT`
It handles privilege escalation very well and is autonomous regarding SSH password input,
something that hasn't been seen in other cybersecurity frameworks yet (Feb 2025)
"""  # noqa: E501

from cai.tools.misc.cli_utils import execute_cli_command  # pylint: disable=E0401 # noqa: E501

def run_ssh_command_with_credentials(
        host: str,
        username: str,
        password: str,
        command: str,
        port: int = 22) -> str:
    """
    Execute a command on a remote host via SSH using password authentication.

    Args:
        host: Remote host address
        username: SSH username
        password: SSH password
        command: Command to execute on remote host
        port: SSH port (default: 22)

    Returns:
        str: Output from the remote command execution
    """
    # Escape special characters in password and command to prevent shell injection
    escaped_password = password.replace("'", "'\\''")
    escaped_command = command.replace("'", "'\\''")
    
    ssh_command = (
        f"sshpass -p '{escaped_password}' "
        f"ssh -o StrictHostKeyChecking=no "
        f"{username}@{host} -p {port} "
        f"'{escaped_command}'"
    )
    return execute_cli_command(ssh_command)
