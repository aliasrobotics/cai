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
        with open("state.txt", "a") as f:
            f.write("\n" + findings + "\n")
        return f"Successfully wrote findings to state.txt:\n{findings}"
    except Exception as e:
        return f"Error writing to state.txt: {str(e)}"
        
def read_key_findings() -> str:
    """
    Read key findings from the state.txt file to retrieve important CTF details.
    Retrieves critical information like:
    - Discovered credentials
    - Found vulnerabilities
    - Privilege escalation vectors 
    - Important system access details
    - Other key findings needed for progression

    Returns:
        String containing all findings from state.txt, or error message if file not found
    """
    try:
        with open("state.txt", "r") as f:
            findings = f.read()
        return findings if findings else "No findings recorded yet in state.txt"
    except FileNotFoundError:
        return "state.txt file not found. No findings have been recorded."
    except Exception as e:
        return f"Error reading state.txt: {str(e)}"
