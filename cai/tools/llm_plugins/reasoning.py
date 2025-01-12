def thought(breakdowns: str = "", reflection: str = "",
            action: str = "", next_step: str = "", key_clues: str = "") -> str:
    """
    Tool used to express detailed thoughts and analysis during boot2root CTF.

    Args:

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
