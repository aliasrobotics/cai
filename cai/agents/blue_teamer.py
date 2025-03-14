"""Blue Team Base Agent
SSH_PASS
SSH_HOST
SSH_USER
"""
import os
from mako.template import Template  # pylint: disable=import-error
from cai.types import Agent  # pylint: disable=import-error
from cai.tools.command_and_control.sshpass import (  # pylint: disable=import-error # noqa: E501
    run_ssh_command_with_credentials
)

from cai.tools.reconnaissance.generic_linux_command import (  # pylint: disable=import-error # noqa: E501
    generic_linux_command
)
from cai.tools.web.search_web import (  # pylint: disable=import-error # noqa: E501
    search_web
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)

# Prompts
blueteam_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_blue_team_agent.md"
).render()
# Define functions list based on available API keys
functions = [
    generic_linux_command,
    run_ssh_command_with_credentials,
    execute_code,
]

# Add search_web function if PERPLEXITY_API_KEY environment variable is set
if os.getenv('PERPLEXITY_API_KEY'):
    functions.append(search_web)

blueteam_agent = Agent(
    name="Blue Team Agent",
    instructions=blueteam_agent_system_prompt,
    description="""Agent that specializes in system defense and security monitoring.
                   Expert in cybersecurity protection and incident response.""",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    functions=functions,
    parallel_tool_calls=False,
)
