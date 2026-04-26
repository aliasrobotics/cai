"""Replay Attack and Counteroffensive Agent
Specialized agent module focused on network replay attacks, packet manipulation, 
and counteroffensive techniques for security testing and incident response.
This agent specializes in:
- Network packet capture and analysis
- Traffic replay attacks against various protocols
- Authentication sequence and session token replay
- Traffic manipulation and injection
- Man-in-the-middle attack simulation
- TCP session hijacking
- Protocol exploitation techniques
- Anti-replay defense testing
Objectives:
- Identify and exploit replay vulnerabilities
- Test protocol implementation security
- Simulate advanced persistent threats
- Evaluate defensive controls against replay attacks
"""


import os
from openai import AsyncOpenAI
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel  # pylint: disable=import-error
from cai.util import load_prompt_template, create_system_prompt_renderer
from dotenv import load_dotenv
from cai.tools.command_and_control.sshpass import (  # pylint: disable=import-error # noqa: E501
    run_ssh_command_with_credentials
)

from cai.tools.reconnaissance.generic_linux_command import (  # pylint: disable=import-error # noqa: E501
    generic_linux_command
)
from cai.tools.web.search_web import (  # pylint: disable=import-error # noqa: E501
    make_web_search_with_explanation
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)

# Import network tools
from cai.tools.network.capture_traffic import (  # pylint: disable=import-error # noqa: E501
    capture_remote_traffic,
    remote_capture_session
)

# Prompts
replay_attack_agent_prompt = load_prompt_template("prompts/system_replay_attack_agent.md")

# Define tools list based on available tools
tools = [
    generic_linux_command,
    run_ssh_command_with_credentials,
    execute_code,
    capture_remote_traffic,
    remote_capture_session,
]

# Add conditional tools based on available API keys
if os.getenv('PERPLEXITY_API_KEY'):
    tools.append(make_web_search_with_explanation)


# Create the agent instance
replay_attack_agent = Agent(
    name="Replay Attack Agent",
    instructions=create_system_prompt_renderer(replay_attack_agent_prompt),
    description="""Agent that specializes in network replay attacks and counteroffensive techniques.
                   Expert in packet manipulation, traffic replay, and protocol exploitation.""",
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "alias1"),
        openai_client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder")),
    ),
    tools=tools,
)

