"""Memory Analysis and Manipulation Agent"""
import os
from dotenv import load_dotenv
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel  # pylint: disable=import-error
from openai import AsyncOpenAI
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

load_dotenv()
# Prompts
memory_analysis_agent_system_prompt = load_prompt_template("prompts/memory_analysis_agent.md")

# Define functions list
functions = [
    generic_linux_command,
    run_ssh_command_with_credentials,
    execute_code,
]

# Add make_web_search_with_explanation function if PERPLEXITY_API_KEY environment variable is set
if os.getenv('PERPLEXITY_API_KEY'):
    functions.append(make_web_search_with_explanation)
    
# Create the agent
memory_analysis_agent = Agent(
    name="Memory Analysis Specialist",
    instructions=memory_analysis_agent_system_prompt,
    description="""Agent for runtime memory analysis and manipulation.
                   Specializes in process memory examination, monitoring, and modification
                   for security assessment, vulnerability discovery, and runtime behavior analysis.""",
    tools=functions,
    model=OpenAIChatCompletionsModel(
        model=os.getenv('CAI_MODEL', "alias1"),
        openai_client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder")),
    )
)
