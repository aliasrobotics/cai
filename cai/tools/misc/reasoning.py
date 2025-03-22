"""
Reasoning tools module for tracking thoughts, findings and analysis
Provides utilities for recording and retrieving key information discovered
during CTF progression.
"""

def think(thought: str) -> str:  # pylint: disable=unused-argument
    """
    Use the tool to think about something.
    
    It will not obtain new information or change the database, but just append
    the thought to the log. Use it when complex reasoning or some cache memory
    is needed.
    
    Args:
        thought: A thought to think about.
    Returns:
        str: The thought that was processed
    """
    return f"{thought}"


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
