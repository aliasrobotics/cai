"""
Common functionality shared between state agent implementations.
"""


def get_base_instructions(state, initial_history):
    """
    Get the base instructions template shared between state agents.

    Args:
        state: Previous network state
        initial_history: Initial chat history messages

    Returns:
        str: Base instruction template
    """
    return f"""
    The last state of the network is:
    ----------------------------
    {state}
    ----------------------------
    Build upon this state to construct the current state of the network.

    IMPORTANT: network state should be constructed coherent with the initial
    prompt and history. Take into account the initial messages to build
    the state:
    ----------------------------
    {"\n".join(f"- {msg['content']}" for msg in initial_history)}
    ----------------------------
    Carefully assess the flags and/or results encountered with regard the
    initial messages.
    """
