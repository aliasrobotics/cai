"""
Module providing tools for structured reasoning and analysis during CTF challenges.

This module contains utilities that help AI agents express their thought process,
reflections, planned actions and track key findings during boot2root CTF challenges.
"""


def thought(breakdowns: str = "", reflection: str = "",
            action: str = "", next_step: str = "", key_clues: str = "") -> str:
    """
    Tool used to express detailed thoughts and analysis during boot2root CTF.

    Args:
        breakdowns (str): Detailed analysis and breakdown of the current situation
        reflection (str): Reflections on past actions and their outcomes
        action (str): Current action being taken or considered
        next_step (str): Planned next steps in the challenge
        key_clues (str): Important findings and clues discovered

    Returns:
        str: Formatted string containing the structured thoughts and analysis
    """
    output = []
    if breakdowns:
        output.append(f"Thought: {breakdowns}")
    if reflection:
        output.append(f"Reflection: {reflection}")
    if action:
        output.append(f"Action: {action}")
    if next_step:
        output.append(f"Next Step: {next_step}")
    if key_clues:
        output.append(f"Key Clues: {key_clues}")
    return "\n".join(output)
