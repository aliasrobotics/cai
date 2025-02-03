"""
This module provides a CLI interface for testing and
interacting with CAI agents.

Environment Variables:
    Optional:
        CTF_NAME: Name of the CTF challenge to
            run (e.g. "picoctf_static_flag")
        CTF_CHALLENGE: Specific challenge name
            within the CTF to test
        CTF_SUBNET: Network subnet for the CTF
            container (default: "192.168.2.0/24")
        CTF_IP: IP address for the CTF
            container (default: "192.168.2.100")
        CTF_MODEL: Model to use for agents
            (default: "qwen2.5:14b")
        CTF_INSIDE: Whether to conquer the CTF from
            within container (default: "true")

        CAI_DEBUG: Set debug output level (default: "1")
        CAI_BRIEF: Enable/disable brief output mode (default: "false")
        CAI_MAX_TURNS: Maximum number of turns for
            agent interactions (default: "inf")
        CAI_TRACING: Enable/disable OpenTelemetry tracing
            (default: "true")
        CAI_AGENT_TYPE: Specify agent type (default: "one_tool")
        CAI_STATE: Enable/disable stateful mode (default: "false")
"""
import os
from mako.template import Template  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error
import pentestperf as ptt  # pylint: disable=import-error
from cai.repl import run_demo_loop
from cai import Agent
# Codebase Tools
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command  # noqa: E501
from cai.tools.web.headers import web_request_framework
from cai.tools.llm_plugins.reasoning import thought
from cai.tools.web.webshell_suit import (
    generate_php_webshell,
    upload_webshell as upload_ftp_webshell
)

# Prompts
cli_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_cli_pentest_expert.md"
).render()

thought_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_thought_router.md"
).render()

env_context = Template(  # nosec B702
    filename="cai/prompts/ctx/env_context.md"
).render()

exploit_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_exploit_expert.md"
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
    instructions=thought_agent_system_prompt,
    functions=[thought, cli_agent_handoff],
    model=os.getenv('CTF_MODEL', "qwen2.5:14b"),
    parallel_tool_calls=False
)


cli_agent = Agent(
    name="Boot2Root CTF Tester",
    instructions=cli_agent_system_prompt + env_context,
    model=os.getenv('CTF_MODEL', "qwen2.5:14b"),
    functions=[
        # execute_cli_command,  # does not support ctf context
        generic_linux_command,
        # thought_agent_handoff,
        # Code_Executor_Expert,
        web_request_framework,
        generate_php_webshell,
        upload_ftp_webshell,  
    ],
    parallel_tool_calls=False,
)


def setup_ctf():
    """Setup CTF environment if CTF_NAME is provided"""
    ctf_name = os.getenv('CTF_NAME')
    if not ctf_name:
        return None

    print(color("Setting up CTF: ", fg="black", bg="yellow") +
          color(ctf_name, fg="black", bg="yellow"))

    ctf = ptt.ctf(
        ctf_name,
        subnet=os.getenv('CTF_SUBNET', "192.168.2.0/24"),
        container_name="ctf_target",
        ip_address=os.getenv('CTF_IP', "192.168.2.100"),
    )
    ctf.start_ctf()

    return ctf


def run_with_env():
    """Run CAI with environment configuration"""
    ctf = setup_ctf()

    try:
        # Configure state agent if enabled
        state_agent = None
        if os.getenv('CAI_STATE', "false").lower() == "true":
            from cai.state.pydantic import state_agent  # pylint: disable=import-outside-toplevel  # noqa: E501
            # from cai.state.free import state_agent  # pylint: disable=import-outside-toplevel  # noqa: E501
            state_agent.model = os.getenv('CTF_MODEL', "qwen2.5:14b")

        # Run interactive loop with CTF and state agent if available
        run_demo_loop(
            cli_agent,
            debug=float(os.getenv('CAI_DEBUG', 2)),  # pylint: disable=invalid-envvar-default  # noqa: E501
            max_turns=float(os.getenv('CAI_MAX_TURNS', '5')),  # pylint: disable=invalid-envvar-default  # noqa: E501
            ctf=ctf if os.getenv(
                'CTF_INSIDE',
                "true").lower() == "true" else None,
            state_agent=state_agent
        )

    finally:
        # Cleanup CTF if started
        if ctf:
            ctf.stop_ctf()


if __name__ == "__main__":
    run_with_env()
