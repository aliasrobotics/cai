"""Red Team Base Agent"""
import os
from dotenv import load_dotenv
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel
from openai import AsyncOpenAI
from cai.util import load_prompt_template, create_system_prompt_renderer
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

from cai.tools.reconnaissance.shodan import (  # pylint: disable=import-error # noqa: E501
    shodan_search,
    shodan_host_info
)

from cai.agents.guardrails import get_security_guardrails

load_dotenv()
# Prompts
bug_bounter_system_prompt = load_prompt_template("prompts/system_bug_bounter.md")
# Define tools list based on available API keys
tools = [
    generic_linux_command,
    execute_code,
    shodan_search,
    shodan_host_info
]

if os.getenv('GOOGLE_SEARCH_API_KEY') and os.getenv('GOOGLE_SEARCH_CX'):
    tools.append(make_google_search)

# Get security guardrails
input_guardrails, output_guardrails = get_security_guardrails()

bug_bounter_agent = Agent(
    name="Bug Bounter",
    instructions=create_system_prompt_renderer(bug_bounter_system_prompt),
    description="""Agent that specializes in bug bounty hunting and vulnerability discovery.
                   Expert in web security, API testing, and responsible disclosure.""",
    tools=tools,
    input_guardrails=input_guardrails,
    output_guardrails=output_guardrails,
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "alias0"),
        openai_client=AsyncOpenAI(),
    )
   
)