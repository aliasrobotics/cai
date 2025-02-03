"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""

import json
import os
from wasabi import color  # pylint: disable=import-error
from cai import CAI  # pylint: disable=import-error


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


def run_demo_loop(  # pylint: disable=too-many-locals,too-many-nested-blocks,too-many-arguments,too-many-branches  # noqa: E501
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
    client = CAI(ctf=ctf, state_agent=state_agent)
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
        print(response.messages)
        formatted_messages = []
        for msg in response.messages:
            if msg.get("content") or msg.get("tool_calls"):
                content = msg.get("content", "")

                if msg.get("tool_calls"):
                    for tool_call in msg["tool_calls"]:
                        tool_result = next(
                            (m for m in response.messages
                             if m.get("tool_call_id") == tool_call["id"]),
                            None
                        )
                        if tool_result and tool_result.get('content'):
                            if content:
                                content += "\n"
                            content += f"{tool_result['content']}"

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
