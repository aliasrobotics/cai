"""
Basic agents Boot2Root CTF Tester and Thought Agent

"""
import os
from mako.template import Template  # pylint: disable=import-error
from cai.types import Agent
from cai.agents.mail import dns_smtp_agent
from cai.tools.command_and_control.sshpass import (
    run_ssh_command_with_credentials
)
from cai.tools.misc.reasoning import thought
from cai.tools.reconnaissance.generic_linux_command import (
    generic_linux_command
)


def transfer_to_dns_agent():
    """
    Use THIS always for DNS scans and domain reconnaissance
    """
    return dns_smtp_agent


# Prompts
cli_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_cli_pentest_expert.md"
).render()

thought_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_thought_router.md"
).render()

exploit_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_exploit_expert.md"
).render()

web_bounty_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_web_bounty_agent.md"
).render()


def cli_agent_handoff(ctf=None):  # pylint: disable=unused-argument
    """
    CLI Security Tester, call this function
    empty CliAgent() to transfer to cli_agent
    """
    return cli_agent


def thought_agent_handoff(ctf=None):  # pylint: disable=unused-argument
    """
    Thought Agent, call this function empty
    Thought_Agent() to transfer to thought_agent
    """
    return thought_agent


# Thought Process Agent for analysis and planning
thought_agent = Agent(
    name="ThoughAgent",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    instructions=thought_agent_system_prompt,
    functions=[thought, cli_agent_handoff],
    parallel_tool_calls=False
)


# Update the system prompt to include information about shell sessions
cli_agent_system_prompt += """

## Shell Session Management
You can create and manage interactive shell sessions for commands like netcat, SSH, etc.

- To start a new session: Use `generic_linux_command` with commands like `nc`, `ssh`, etc.
- To list active sessions: `generic_linux_command("session", "list")`
- To get output from a session: `generic_linux_command("session", "output <session_id>")`
- To send input to a session: `generic_linux_command("<command>", "<args>", session_id="<session_id>")`
- To terminate a session: `generic_linux_command("session", "kill <session_id>")`

Example workflow:
1. Start netcat: `generic_linux_command("nc", "-lvnp 4444")` → Returns session ID
2. Check output: `generic_linux_command("session", "output <session_id>")`
3. Send data: `generic_linux_command("echo hello", session_id="<session_id>")`
4. Kill when done: `generic_linux_command("session", "kill <session_id>")`
"""

cli_agent = Agent(
    name="Boot2Root CTF Tester",
    instructions=cli_agent_system_prompt,
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    functions=[
        # execute_cli_command,  # does not support ctf context
        generic_linux_command,
        run_ssh_command_with_credentials,
        # thought_agent_handoff,
        # Code_Executor_Expert,
    ],
    parallel_tool_calls=False,
)

cli_agent.functions.append(transfer_to_dns_agent)
dns_smtp_agent.functions.append(cli_agent_handoff)
