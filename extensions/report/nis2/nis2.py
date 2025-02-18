"""
    This module provides functions for conducting a NIS2 compliance analysis
    and conducts a comprehensive analysis for NIS2 compliance.
    Example of execution:
        CAI_TRACING=False CAI_STATE=true python3 cai/nis2/nis2.py

"""
import os
import json
from cai.types import Agent   # pylint: disable=import-error
from cai.core import CAI  # pylint: disable=import-error
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command  # noqa: E501 # pylint: disable=import-error
from extensions.report.nis2.nis2_report_agent import reporter_agent # pylint: disable=import-error  
from extensions.report.nis2.support_agents.risk_agent import risk_agent  # pylint: disable=import-error # noqa: E501
from extensions.report.nis2.support_agents.check_agent import transfer_to_check_agent  # pylint: disable=import-error # noqa: E501
# pylint: disable=C0103
from extensions.report.common import create_report  # pylint: disable=import-error # noqa: E501


def load_history_from_jsonl(file_path):
    """
    Load conversation history from a JSONL file and
    return it as a list of messages.

    Args:
        file_path (str): The path to the JSONL file.

    Returns:
        list: A list of messages extracted from the JSONL file.
    """
    history = []
    with open(file_path, encoding='utf-8') as file:
        for line in file:
            entry = json.loads(line)
            messages = entry.get("messages", [])
            for message in messages:
                role = message.get("role")
                content = message.get("content")
                if role and content:
                    history.append({"role": role, "content": content})
    return history


def get_user_input(prompt: str) -> str:
    """
    Prompt the user for input and return a formatted response.

    Args:
        prompt (str): The message displayed to the user when asking for input.

    Returns:
        str: A formatted string indicating the user's response,
             either "[x]" for 'yes' or "[ ]" for 'no'.
    """
    while True:
        user_input = input(prompt).strip().lower()
        if user_input == 'y':
            return "[x]"
        if user_input == 'n':
            return "[ ]"
        print("Invalid input. Please enter 'y' or 'n'.")


def risk_assessment(risk_str: str):
    """
    This function prompts the user for a file path containing
    pentesting history. If the file exists, it loads the
    conversation history and prepares a message for the risk
    analysis agent. The agent then conducts a risk analysis and
    returns the results along with the pentesting history.

    Args:
        risk_str: A prompt message asking the user for the file path
                        containing the pentesting history.
    Returns:
        tuple: A tuple containing:
            - str: The content of the risk assessment message
            - list: The history of pentesting messages loaded
                    from the specified file.
    """
    user_input = input(risk_str)
    #user_input = "logs/test_alias.jsonl"
    # Check if the file path exists
    if not os.path.isfile(user_input):
        print("The file does not exist. Skipping risk analysis...")
        return None, None

    # Conducts a risk analysis with the pentesting history loaded.
    history_pentesting = load_history_from_jsonl(user_input)
    messages = [{
        "role": "user",
        "content": """
                            Do a risk analysis of the pentest that we
                            did for a company, we obtained this: """
        + "\n".join(str(item)
                    for item in history_pentesting)
    }]
    # Get model from environment or use defQault
    model = os.getenv('CTF_MODEL', "qwen2.5:14b")
    state_agent = None
    stateful = os.getenv('CAI_STATE', "false").lower() == "true"
    if stateful:
        from cai.state.pydantic import state_agent  # pylint: disable=import-error,import-outside-toplevel # noqa: E501
        state_agent.model = model  # set model
    client = CAI(state_agent=state_agent)
    risk = client.run(
        agent=risk_agent,
        messages=messages,
        debug=float(os.getenv('CAI_DEBUG', '2')),
        max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
        brief=os.getenv('CAI_BRIEF', 'false').lower() == 'true')

    return risk.messages[0].get('content'), history_pentesting


def verify_security_measures():
    """
    Verifies the security measures for a specified organization by analyzing
    various aspects of cybersecurity compliance.

    Returns:
        Response: The response from the CAI agent after running the
                  security measures verification.
    """
    nis2_agent = Agent(
        name="NIS2 agent",
        instructions="""
       You are in charge of verifying the following security measures:

        Data Encryption
        - Check that sensitive information is encrypted
          both when stored and when transmitted.
        - Look for encryption standards like AES-256 or TLS 1.2/1.3.
        - Ensure no sensitive data is being sent in plaintext.

        Multi-Factor Authentication (MFA)
        - Confirm that MFA is required for accessing critical systems
        - Check logs to verify that MFA is being used
          (such as one-time passwords, biometrics, or security keys).

        Secure Communication: Ensure that voice, video, and text
        communications are encrypted.
        - Look for secure protocols like TLS, SRTP, or ZRTP.
        - Make sure no unencrypted communication is happening over the network.

        Use tools like TShark or Wireshark to check encryption
        and report any security issues immediately.
        IMPORTANT: Don't stop iterating until you check all, and transfer to
        check agent for reporting the findings.

        """,
        model=os.getenv('CTF_MODEL', "qwen2.5:14b"),
        functions=[
            generic_linux_command, transfer_to_check_agent
        ],
        parallel_tool_calls=False,
    )

    messages = [{
        "role": "user",
        "content": """Do the analysis for aliasrobotics.com,
            first find the IP, don't stop iterating until you
            check all the security measures
            and call check_agent when you have finished
            """
    }]

    # Get model from environment or use default
    model = os.getenv('CTF_MODEL', "qwen2.5:14b")
    state_agent = None
    stateful = os.getenv('CAI_STATE', "false").lower() == "true"
    if stateful:
        from cai.state.pydantic import state_agent  # pylint: disable=import-error,import-outside-toplevel # noqa: E501
        state_agent.model = model  # set model
    client = CAI(state_agent=state_agent)
    response = client.run(
        agent=nis2_agent,
        messages=messages,
        debug=float(os.getenv('CAI_DEBUG', '2')),
        max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
        brief=os.getenv('CAI_BRIEF', 'false').lower() == 'true')

    return response


if __name__ == "__main__":
    print("\n --------------------------------------------------")
    print("STARTING THE NIS2 ANALYSIS WITH CAI")

    # Client risk analysis
    risk_client, history_pentesting_client = risk_assessment(
        "Please enter the path to the JSONL of the pentesting: ")
    if risk_client is None:  # No pentesting file available,
        # so the following requirements cannot be fulfilled
        A2_risk_assessments = "[ ]"
        A3_critical_assess = "[ ]"
        B3_simulations = "[ ]"
        E1_vulnerability_testing = "[ ]"
        F1_regular_audits = "[ ]"
        F2_kpis_effectiveness = "[x]"
        F3_risk_reports = "[ ]"
    else:
        A2_risk_assessments = "[x]"
        A3_critical_assess = "[x]"
        B3_simulations = "[x]"
        E1_vulnerability_testing = "[x]"
        F1_regular_audits = "[x]"
        F2_kpis_effectiveness = "[x]"
        F3_risk_reports = "[x]"
        risk_client = json.loads(risk_client)

    # Nis2 alnysis for other security configurations
    nis2_check_agent = False
    response_nis2 = verify_security_measures()
    history_nis2_response = response_nis2.messages

    # Obtain the response from the Check Agent
    if any("Check Agent" in message.get('sender', '')
           for message in history_nis2_response):
        agent_response = next(
            (message for message in history_nis2_response if message.get(
                'sender') == "Check Agent"),
            None)
        if agent_response:
            agent_content = agent_response.get('content', 'No content found')
            # Check if the content is a dictionary
            if isinstance(agent_content, dict):
                H1_data_encryption = agent_content.get(
                    "H1_data_encryption", "[ ]")
                J1_mfa_usage = agent_content.get("J1_mfa_usage", "[ ]")
                J2_communications_protection = agent_content.get(
                    "J2_communications_protection", "[ ]")
                nis2_check_agent = True
            # If the content is a string (potentially JSON), parse it
            elif isinstance(agent_content, str):
                try:
                    # If it's a JSON string, parse it into a dictionary
                    parsed_content = json.loads(agent_content)
                    H1_data_encryption = parsed_content.get(
                        "H1_data_encryption", "[ ]")
                    J1_mfa_usage = parsed_content.get("J1_mfa_usage", "[ ]")
                    J2_communications_protection = parsed_content.get(
                        "J2_communications_protection", "[ ]")
                    nis2_check_agent = True
                except json.JSONDecodeError:
                    print("Error: The content is not valid JSON.")

    # If not response for Check Agent set defaults
    if not nis2_check_agent:
        H1_data_encryption = "[ ]"
        J1_mfa_usage = "[ ]"
        J2_communications_protection = "[ ]"

    print("FINALIZED THE NIS2 ANALYSIS WITH CAI")
    print("\n --------------------------------------------------")

    # Store responses
    compliance_assessment_check = {

        "A2_risk_assessments": A2_risk_assessments,
        "A3_critical_assess": A3_critical_assess,
        "B3_simulations": B3_simulations,
        "E1_vulnerability_testing": E1_vulnerability_testing,
        "F1_regular_audits": F1_regular_audits,
        "F2_kpis_effectiveness": F2_kpis_effectiveness,
        "F3_risk_reports": F3_risk_reports,
        "H1_data_encryption": H1_data_encryption,
        "J1_mfa_usage": J1_mfa_usage,
        "J2_communications_protection": J2_communications_protection,
    }

    messages = [{
        "role": "user",
        "content": f"""Elaborate a report knowing this data:
        risk: {risk_client},
        compliance_assessment: {compliance_assessment_check}
        """
    }]
    print(messages)
    # Get model from environment or use default
    model = os.getenv('CTF_MODEL', "qwen2.5:14b")
    state_agent = None
    stateful = os.getenv('CAI_STATE', "false").lower() == "true"
    if stateful:
        from cai.state.pydantic import state_agent  # pylint: disable=import-error,import-outside-toplevel # noqa: E501
        state_agent.model = model  # set model
    client = CAI(state_agent=state_agent)
    response_nis2_report = client.run(
        agent=reporter_agent,
        messages=messages,
        debug=float(os.getenv('CAI_DEBUG', '2')),
        max_turns=float(os.getenv('CAI_MAX_TURNS', 'inf')),
        brief=os.getenv('CAI_BRIEF', 'false').lower() == 'true')

    print(response_nis2_report)
    report_data = json.loads(response_nis2_report.messages[0]['content'])
    report_data["history"] = json.dumps(history_nis2_response, indent=4)
    report_data["history_pentesting"] = json.dumps(
        history_pentesting_client, indent=4)
    print("Saving NIS2 report")
    create_report(report_data, "extensions/report/nis2/template.md")
    print("The compliance assessment has been completed and the report has"
          "been generated in the /reports folder.")
