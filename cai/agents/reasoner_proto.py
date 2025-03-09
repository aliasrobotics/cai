"""
First prototype of a reasoner agent

using reasoner as a tool call

support meta agent may better @cai.agents.meta.reasoner_support
"""
from cai.tools.misc.reasoning import thought
from mako.template import Template  # pylint: disable=import-error
from cai.types import Agent  # pylint: disable=import-error
import os

thought_agent_system_prompt = Template(  # nosec B702
    filename="cai/prompts/system_thought_router.md"
).render()

# Thought Process Agent for analysis and planning
thought_agent = Agent(
    name="ThoughAgent",
    model=os.getenv('CAI_MODEL', "qwen2.5:14b"),
    description="""Agent focused on analyzing and planning the next steps
                   in a security assessment or CTF challenge.""",
    instructions=thought_agent_system_prompt,
    functions=[thought],
    parallel_tool_calls=False
)
