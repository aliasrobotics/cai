"""Red Team Base Agent"""
import os
from cai.types import Agent  # pylint: disable=import-error
from cai.util import load_prompt_template  # Add this import
from cai.tools.command_and_control.sshpass import (  # pylint: disable=import-error # noqa: E501
    run_ssh_command_with_credentials
)

from cai.tools.reconnaissance.generic_linux_command import (  # pylint: disable=import-error # noqa: E501
    generic_linux_command
)
from cai.tools.web.search_web import (  # pylint: disable=import-error # noqa: E501
    make_web_search_with_explanation,
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)

# Prompts
redteam_agent_system_prompt = load_prompt_template("prompts/system_red_team_agent.md")
# Define functions list based on available API keys
functions = [
    generic_linux_command,
    run_ssh_command_with_credentials,
    execute_code,
]

# Add make_web_search_with_explanation function if PERPLEXITY_API_KEY environment variable is set
if os.getenv('PERPLEXITY_API_KEY'):
    functions.append(make_web_search_with_explanation)
    

redteam_agent = Agent(
    name="Red Team Agent",
    instructions=redteam_agent_system_prompt,
    description="""Agent that mimic pentester/red teamer in a security assessment.
                   Expert in cybersecurity and exploitation.""",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    functions=functions,
    parallel_tool_calls=False,
)