"""
CTF Agent with one tool
"""
import os
from cai.types import Agent
from cai.agents.common import create_ctf_agent

model = os.getenv('CAI_MODEL', "qwen2.5:14b")

ctf_agent_one_tool = create_ctf_agent(model=model)


def transfer_to_ctf_agent_one_tool(**kwargs):  # pylint: disable=W0613
    """Transfer to ctf agent.
    Accepts any keyword arguments but ignores them."""
    return ctf_agent_one_tool
