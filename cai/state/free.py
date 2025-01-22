"""
This module provides a Pydantic model for
representing network state in cybersecurity contexts.
"""

from cai.types import Agent

state_agent = Agent(
    name="Plain Free-form Text NetworkState Agent",
    instructions="""
    I am a network state building agent that analyzes chat history to
    construct network state in Plain Free-form Text that represents
    the current state of the network.""",
)
