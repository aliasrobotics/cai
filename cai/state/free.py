"""
This module provides a Pydantic model for
representing network state in cybersecurity contexts.
"""

from cai.types import Agent


def instructions(context_variables):
    """
    Instructions for the free state agent
    """
    state = context_variables.get("state", "No previous state")
    return f"""
    I am a network state building agent that analyzes chat history to
    construct network state in Plain Free-form Text that represents
    the current state of the network. Consider the following:
        - For the files, for each, include permissions and complete filepath

    The last state of the network is:
    ----------------------------
    {state}
    ----------------------------

    Build upon this state to construct the current state of the network.
    """


state_agent = Agent(
    name="Plain Free-form Text NetworkState Agent",
    instructions=instructions,
)
