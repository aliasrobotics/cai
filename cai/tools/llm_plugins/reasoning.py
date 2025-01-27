"""
Reasoning tools module for tracking thoughts, findings and analysis
Provides utilities for recording and retrieving key information discovered
during CTF progression.
"""


def thought(breakdowns: str = "", reflection: str = "",  # pylint: disable=too-many-arguments  # noqa: E501
            action: str = "", next_step: str = "", key_clues: str = "",
            ctf=None) -> str:  # pylint: disable=unused-argument  # noqa: E501
    """
    Tool used to express detailed thoughts and analysis during boot2root CTF.

    Args:
        breakdowns: Detailed breakdown of current situation/findings
        reflection: Reflections on progress and insights gained
        action: Current or planned actions
        next_step: Next steps to take
        key_clues: Important clues or hints discovered
        ctf: CTF object to use for context
    Returns:
        str: Formatted string containing the provided thoughts and analysis
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


def write_key_findings(findings: str) -> str:
    """
    Write key findings to a state.txt file to track important CTF details.
    Only records critical information like:
    - Discovered credentials
    - Found vulnerabilities
    - Privilege escalation vectors
    - Important system access details
    - Other key findings needed for progression

    Args:
        findings: String containing the key findings to append to state.txt

    Returns:
        String confirming the findings were written
    """
    try:
        with open("state.txt", "a", encoding="utf-8") as f:
            f.write("\n" + findings + "\n")
        return f"Successfully wrote findings to state.txt:\n{findings}"
    except OSError as e:
        return f"Error writing to state.txt: {str(e)}"


def read_key_findings() -> str:
    """
    Read key findings from the state.txt file to retrieve important data
    Retrieves critical information like:
    - Discovered credentials
    - Found vulnerabilities
    - Privilege escalation vectors
    - Important system access details
    - Other key findings needed for progression

    Returns:
        String containing all findings from state.txt, or error message
        if file not found
    """
    try:
        with open("state.txt", encoding="utf-8") as f:
            findings = f.read()
        return findings or "Not finding"
    except FileNotFoundError:
        return "state.txt file not found. No findings have been recorded."
    except OSError as e:
        return f"Error reading state.txt: {str(e)}"
