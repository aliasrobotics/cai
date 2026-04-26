"""Use Case Agent"""
import os
from dotenv import load_dotenv
from cai.sdk.agents import Agent, OpenAIChatCompletionsModel
from openai import AsyncOpenAI
from cai.tools.reconnaissance.generic_linux_command import null_tool
from cai.util import load_prompt_template, create_system_prompt_renderer

load_dotenv()
model_name = os.getenv("CAI_MODEL", "alias1")

# Load prompt
use_case_agent_system_prompt = load_prompt_template("prompts/system_use_cases.md")

# # Define tools list
# tools = [
#     generic_linux_command,
#     list_dir,
#     cat_file,
#     edit_file,
#     replace_in_file,
#     read_file,
#     append_to_file,
#     create_file,
#     pwd_command,
#     find_file,
#     execute_code,
# ]
tools = [null_tool]
# Create the agent
use_case_agent = Agent(
    name="Use Case Agent",
    description="""Agent that creates high-quality cybersecurity case studies 
                   demonstrating how CAI tackles various security scenarios, 
                   CTF challenges, and cybersecurity exercises.""",
    instructions=create_system_prompt_renderer(use_case_agent_system_prompt),
    tools=tools,
    model=OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder")),
    ),
)

# Transfer function
def transfer_to_use_case_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to use case agent.
    Accepts any keyword arguments but ignores them."""
    return use_case_agent

