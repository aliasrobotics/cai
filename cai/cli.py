"""
This module provides a CLI interface for testing and
interacting with CAI agents.
"""
import os
from mako.template import Template  # pylint: disable=import-error
from cai.repl import run_demo_loop
from cai import Agent
# Codebase Tools
from cai.tools.llm_plugins.cli_utils import execute_cli_command  # pylint: disable=ungrouped-imports  # noqa: E501
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


def cli_agent_handoff():
    """
    CLI Security Tester, call this function
    empty CliAgent() to transfer to cli_agent
    """
    return cli_agent


def thought_agent_handoff():
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
    parallel_tool_calls=False
)


cli_agent = Agent(
    name="Boot2Root CTF Tester",
    instructions=cli_agent_system_prompt + env_context,
    functions=[
        execute_cli_command,
        thought_agent_handoff,
        # Code_Executor_Expert,
        web_request_framework,
        generate_php_webshell,
        upload_ftp_webshell
    ],
    parallel_tool_calls=False,
)

if __name__ == "__main__":
    os.environ["CAI_TRACING"] = "false"
    run_demo_loop(thought_agent, debug=2)
