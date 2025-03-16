"""Red Team Base Agent"""
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
    make_google_search
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)

# Prompts
bug_bounter_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_bug_bounter.md"
).render()
# Define functions list based on available API keys
functions = [
    generic_linux_command,
    execute_code,
]

if os.getenv('GOOGLE_SEARCH_API_KEY') and os.getenv('GOOGLE_SEARCH_CX'):
    functions.append(make_google_search)

bug_bounter_agent = Agent(
    name="Bug Bounter",
    instructions=bug_bounter_system_prompt,
    description="""Agent that specializes in bug bounty hunting and vulnerability discovery.
                   Expert in web security, API testing, and responsible disclosure.""",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    functions=functions,
    parallel_tool_calls=False,
)