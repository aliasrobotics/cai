"""
SSH Pass tool for executing remote commands via SSH using password authentication.
"""

from cai.tools.llm_plugins.cli_utils import execute_cli_command


def run_ssh_command_with_credentials(
        host: str, username: str, password: str, command: str) -> str:
    """
    Execute a command on a remote host via SSH using password authentication.

    Args:
        host: Remote host address
        username: SSH username
        password: SSH password
        command: Command to execute on remote host

    Returns:
        str: Output from the remote command execution
    """
    ssh_command = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no {
        username}@{host} '{command}'"
    return execute_cli_command(ssh_command)
