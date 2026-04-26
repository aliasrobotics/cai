"""Reporter Agent - Creates professional security assessment reports"""
import os
from dotenv import load_dotenv
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel  # pylint: disable=import-error
from openai import AsyncOpenAI
from cai.util import load_prompt_template  # Add this import

from cai.tools.reconnaissance.generic_linux_command import (  # pylint: disable=import-error # noqa: E501
    generic_linux_command
)

from cai.tools.reconnaissance.exec_code import (  # pylint: disable=import-error # noqa: E501
    execute_code
)

load_dotenv()
# Prompts
reporting_agent_system_prompt = load_prompt_template("prompts/system_reporting_agent.md")

# Define functions list
functions = [
    generic_linux_command,
    execute_code,
]


# Create an instance of the reporting agent
reporting_agent = Agent(
    name="reporting agent",
    instructions=reporting_agent_system_prompt,
    description="""Agent that generates reports in html.""",
    tools=functions,
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "alias1"),
        openai_client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder")),
    )
)
