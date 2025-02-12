"""
This module provides a free-form text state agent for
representing network state in cybersecurity contexts.
"""

from cai.state.common import get_base_instructions, StateAgent


def instructions(context_variables):
    """
    Instructions for the free state agent
    """
    state = context_variables.get("state", "No previous state")
    initial_history = context_variables.get("initial_history", [])

    return f"""
    I am a network state building agent that analyzes chat history to
    construct network state in Plain Free-form Text that represents
    the current state of the network, capturing all details necessary
    for a cybersecurity exercise. Account for the following:
        - For the files, for each, include permissions and complete filepath

    {get_base_instructions(state, initial_history)}
    """


state_agent = StateAgent(
    name="Plain Free-form Text NetworkState Agent",
    instructions=instructions,
)
