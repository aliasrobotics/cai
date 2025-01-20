"""
This module provides a REPL interface for testing and
interacting with CAI agents.
"""

import json
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


def run_demo_loop(  # pylint: disable=too-many-locals,too-many-nested-blocks
    starting_agent,
    context_variables=None,
    stream=False,
    debug=False,
    max_turns=10000
) -> None:
    """
    Run the demo loop for CAI.
    """
    client = CAI()
    print("Starting CAI CLI 🐝")

    messages = []
    agent = starting_agent
    while True:
        user_input = input("\033[90mUser\033[0m: ")
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
                content = msg.get("content", "")

                if msg.get("tool_calls"):
                    for tool_call in msg["tool_calls"]:
                        tool_result = next(
                            (m for m in response.messages
                             if m.get("tool_call_id") == tool_call["id"]),
                            None
                        )
                        if tool_result:
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
