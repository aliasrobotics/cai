"""Blue Team Base Agent
SSH_PASS
SSH_HOST
SSH_USER
"""
import os
from cai.types import Agent  # pylint: disable=import-error
from cai.util import load_prompt_template  # Add this import
from cai.tools.command_and_control.sshpass import (  # pylint: disable=import-error # noqa: E501
    run_ssh_command_with_credentials
)

from cai.tools.reconnaissance.generic_linux_command import (  # pylint: disable=import-error # noqa: E501
    generic_linux_command
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)
from cai.tools.web.search_web import (  # pylint: disable=import-error # noqa: E501
    make_web_search_with_explanation,
)
# Prompts
blueteam_agent_system_prompt = load_prompt_template("prompts/system_blue_team_agent.md")
# Define functions list based on available API keys
functions = [
    generic_linux_command,
    run_ssh_command_with_credentials,
    execute_code,
]

if os.getenv('PERPLEXITY_API_KEY'):
    functions.append(make_web_search_with_explanation)

blueteam_agent = Agent(
    name="Blue Team Agent",
    instructions=blueteam_agent_system_prompt,
    description="""Agent that specializes in system defense and security monitoring.
                   Expert in cybersecurity protection and incident response.""",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    functions=functions,
    parallel_tool_calls=False,
)

def transfer_to_blue_teamer():
    return blueteam_agent