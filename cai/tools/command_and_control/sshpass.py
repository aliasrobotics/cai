"""
SSH Pass tool for executing remote commands via SSH using password authentication.

Example of generalization: to execute a local command we use a bash wrapper
in `generic_linux_command` and in `execute_cli_command` -> `cai.tools.llm_plugins.cli_utils`
Using these wrappers, commands like `ssh` or `netcat` usually get trapped
by the LLM, so prompt engineering is used to execute the command locally
and return the result. Another solution is to implement interactive CLIs, for now this command
covers all SSH use cases. A much more logical and simpler implementation than
`hackingbuddyGPT` -> `https://github.com/ipa-lab/hackingBuddyGPT/blob/main/src/hackingBuddyGPT/capabilities/ssh_run_command.py`
|
> `https://github.com/ipa-lab/hackingBuddyGPT/blob/main/src/hackingBuddyGPT/capabilities/ssh_test_credential.py`

It handles privilege escalation very well and is autonomous regarding SSH password input, something that hasn't 
been seen in other cybersecurity frameworks yet (Feb 2025)
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
