"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""
import time
import json
import os
from wasabi import color  # pylint: disable=import-error
from cai import CAI  # pylint: disable=import-error
from cai.util import create_report_from_messages


def process_and_print_streaming_response(response):  # pylint: disable=inconsistent-return-statements  # noqa: E501
    """
    Process and print streaming responses from CAI.
    """
    content = ""
    last_sender = ""

    for chunk in response:
        if "sender" in chunk:
            last_sender = chunk["sender"]

        if "content" in chunk and chunk["content"] is not None:
            if not content and last_sender:
                print(f"\033[94m{last_sender}:\033[0m", end=" ", flush=True)
                last_sender = ""
            print(chunk["content"], end="", flush=True)
            content += chunk["content"]

        if "tool_calls" in chunk and chunk["tool_calls"] is not None:
            for tool_call in chunk["tool_calls"]:
                f = tool_call["function"]
                name = f["name"]
                if not name:
                    continue
                print(f"\033[94m{last_sender}: \033[95m{name}\033[0m()")

        if "delim" in chunk and chunk["delim"] == "end" and content:
            print()  # End of response message
            content = ""

        if "response" in chunk:
            return chunk["response"]


def pretty_print_messages(messages) -> None:
    """
    Pretty print messages from CAI.
    """
    for message in messages:
        if message["role"] != "assistant":
            continue

        # print agent name in blue
        print(f"\033[94m{message['sender']}\033[0m:", end=" ")

        # print response, if any
        if message["content"]:
            print(message["content"])

        # print tool calls in purple, if any
        tool_calls = message.get("tool_calls") or []
        if len(tool_calls) > 1:
            print()
        for tool_call in tool_calls:
            f = tool_call["function"]
            name, args = f["name"], f["arguments"]
            arg_str = json.dumps(json.loads(args)).replace(":", "=")
            print(f"\033[95m{name}\033[0m({arg_str[1:-1]})")


def run_demo_loop(  # pylint: disable=too-many-locals,too-many-nested-blocks,too-many-arguments,too-many-branches,too-many-statements  # noqa: E501
    starting_agent,
    context_variables=None,
    stream=False,
    debug=False,
    max_turns=float('inf'),
    ctf=None,  # Add CTF parameter
    state_agent=None  # Add state agent parameter
) -> None:
    """
    Run the demo loop for CAI.

    Args:
        starting_agent: The agent to start with
        context_variables: Optional context variables
        stream: Whether to stream responses
        debug: Debug level
        max_turns: Maximum number of turns
        ctf: Optional CTF instance to use
        state_agent: Optional state agent to use
    """
    # Initialize CAI with CTF and state agent if provided
    client = CAI(
        ctf=ctf if os.getenv(
            'CTF_INSIDE',
            "true").lower() == "true" else None,
        state_agent=state_agent)
    print("""
 ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄
▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌
▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌ ▀▀▀▀█░█▀▀▀▀
▐░▌          ▐░▌       ▐░▌     ▐░▌
▐░▌          ▐░█▄▄▄▄▄▄▄█░▌     ▐░▌
▐░▌          ▐░░░░░░░░░░░▌     ▐░▌
▐░▌          ▐░█▀▀▀▀▀▀▀█░▌     ▐░▌
▐░▌          ▐░▌       ▐░▌     ▐░▌
▐░█▄▄▄▄▄▄▄▄▄ ▐░▌       ▐░▌ ▄▄▄▄█░█▄▄▄▄
▐░░░░░░░░░░░▌▐░▌       ▐░▌▐░░░░░░░░░░░▌
 ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀  ▀▀▀▀▀▀▀▀▀▀▀

    Cybersecurity AI, by Alias Robotics
""")

    messages = []
    all_reports = []
    if ctf:
        # Get challenge
        challenge_key = os.getenv('CTF_CHALLENGE')
        challenges = list(ctf.get_challenges().keys())
        challenge = challenge_key if challenge_key in challenges else (
            challenges[0] if len(challenges) > 0 else None)

        if challenge:
            print(color("Testing challenge: ", fg="white", bg="blue") +
                  color(f"'{challenge}'", fg="white", bg="blue"))

        # Get initial messages aligned with CTF
        inside = ""
        if os.getenv('CTF_INSIDE', "true").lower() == "true":
            inside = ("You are INSIDE the target machine in a docker container, "  # noqa: E501  # pylint: disable=line-too-long
                      "try not to do network commands unless it were necesary")
        else:
            inside = ("You are OUTSIDE the target machine which is a docker container, "  # noqa: E501  # pylint: disable=line-too-long
                      "you may use network commands as nmap for initial recon")
        messages += [{
            "role": "user",
            "content": "Instructions: " + ctf.get_instructions() +
            "\nChallenge: " + ctf.get_challenges()[challenge] +
            # "\nTechniques: " + ctf.get_techniques() +
            "\nTarget IP: " + ctf.get_ip() +
            "\n" + inside
        }]

    agent = starting_agent

    while True:

        # Skip input on first iteration if CTF is enabled
        if ctf and len(messages) == 1:
            pass
        else:
            user_input = input("\033[93mCAI\033[0m: ")
            messages.append({"role": "user", "content": user_input})

        response = client.run(
            agent=agent,
            messages=messages,
            context_variables=context_variables or {},
            stream=stream,
            debug=debug,
            max_turns=max_turns,
        )

        formatted_messages = []
        for msg in response.messages:
            if msg.get("content") or msg.get("tool_calls"):
                # Ensure the content is a string even if it's None
                content = msg.get("content") or ""
                if msg.get("tool_calls"):
                    for tool_call in msg["tool_calls"]:
                        tool_result = next(
                            (m for m in response.messages
                             if m.get("tool_call_id") == tool_call["id"]),
                            None
                        )
                        if tool_result:
                            # Safely retrieve tool_result content as a string
                            tool_content = tool_result.get("content") or ""
                            if tool_content:
                                if content:
                                    content += "\n"
                                content += tool_content
                formatted_msg = {
                    "role": "assistant",
                    "content": content,
                    "sender": msg.get("sender", agent.name)
                }
                formatted_messages.append(formatted_msg)
        if formatted_messages:
            messages.extend(formatted_messages)
        if response.agent:
            agent = response.agent
        if response.report:
            if all_reports:
                latest_report = all_reports[-1]
                latest_report.findings.extend(
                    response.report.findings
                )
                latest_report.vuln_critical += (
                    response.report.vuln_critical
                )
                latest_report.vuln_high += response.report.vuln_high
                latest_report.vuln_medium += response.report.vuln_medium
                latest_report.vuln_low += response.report.vuln_low
                if response.report.network_state:
                    if not latest_report.network_state:
                        latest_report.network_state = (
                            response.report.network_state
                        )
                    else:
                        existing_ips = {
                            ep.ip
                            for ep in latest_report.network_state.network
                        }
                        for endpoint in response.report.network_state.network:
                            if endpoint.ip not in existing_ips:
                                latest_report.network_state.network.append(
                                    endpoint
                                )
                            else:
                                existing = next(
                                    ep
                                    for ep in latest_report.network_state.network  # noqa: E501
                                    if ep.ip == endpoint.ip
                                )
                                existing.ports.extend([
                                    p
                                    for p in endpoint.ports
                                    if p.port not in [
                                        ep.port
                                        for ep in existing.ports
                                    ]
                                ])
                                existing.exploits.extend([
                                    e
                                    for e in endpoint.exploits
                                    if e.name not in [
                                        ex.name
                                        for ex in existing.exploits
                                    ]
                                ])
                                existing.files.extend([
                                    f
                                    for f in endpoint.files
                                    if f not in existing.files
                                ])
                                existing.users.extend([
                                    u
                                    for u in endpoint.users
                                    if u not in existing.users
                                ])
                latest_report.executive_summary += (
                    "\n" + response.report.executive_summary
                )
                latest_report.scope += "\n" + response.report.scope
                latest_report.methodology += (
                    "\n" + response.report.methodology
                )
                latest_report.tools.extend(response.report.tools)
                latest_report.risk_assessment += (
                    "\n" + response.report.risk_assessment
                )
                latest_report.remediation_recommendations += (
                    "\n" + response.report.remediation_recommendations
                )
                latest_report.conclusion += "\n" + response.report.conclusion
                latest_report.appendix += "\n" + response.report.appendix
            else:
                all_reports.append(response.report)

            merged_report = all_reports[0]
            for report in all_reports[1:]:
                merged_report.findings.extend(report.findings)
                merged_report.vuln_critical += report.vuln_critical
                merged_report.vuln_high += report.vuln_high
                merged_report.vuln_medium += report.vuln_medium
                merged_report.vuln_low += report.vuln_low
                if report.network_state:
                    if not merged_report.network_state:
                        merged_report.network_state = report.network_state
                    else:
                        existing_ips = {
                            ep.ip
                            for ep in merged_report.network_state.network
                        }
                        for endpoint in report.network_state.network:
                            if endpoint.ip not in existing_ips:
                                merged_report.network_state.network.append(
                                    endpoint
                                )
                            else:
                                existing = next(
                                    ep
                                    for ep in merged_report.network_state.network  # noqa: E501
                                    if ep.ip == endpoint.ip
                                )
                                existing.ports.extend([
                                    p
                                    for p in endpoint.ports
                                    if p.port not in [
                                        ep.port
                                        for ep in existing.ports
                                    ]
                                ])
                                existing.exploits.extend([
                                    e
                                    for e in endpoint.exploits
                                    if e.name not in [
                                        ex.name
                                        for ex in existing.exploits
                                    ]
                                ])
                                existing.files.extend([
                                    f
                                    for f in endpoint.files
                                    if f not in existing.files
                                ])
                                existing.users.extend([
                                    u
                                    for u in endpoint.users
                                    if u not in existing.users
                                ])
                merged_report.executive_summary += (
                    "\n" + report.executive_summary
                )
                merged_report.scope += "\n" + report.scope
                merged_report.methodology += "\n" + report.methodology
                merged_report.tools.extend(report.tools)
                merged_report.risk_assessment += (
                    "\n" + report.risk_assessment
                )
                merged_report.remediation_recommendations += (
                    "\n" + report.remediation_recommendations
                )
                merged_report.conclusion += "\n" + report.conclusion
                merged_report.appendix += "\n" + report.appendix

            report_json = merged_report.model_dump_json()
            print(report_json)

            hostname = merged_report.network_state.network[
                0].hostname if merged_report.network_state.network else "report"  # noqa: E501
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

            # Create filename with hostname and timestamp
            report_filename = f"{hostname}_{timestamp}.md"

            create_report_from_messages(report_json, report_filename)
