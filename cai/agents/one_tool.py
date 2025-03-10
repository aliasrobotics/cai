"""
CTF Agent with one tool
"""
import os
from cai.types import Agent
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command  # noqa
model = os.getenv('CAI_MODEL', "qwen2.5:14b")

one_tool_agent = Agent(
    model=model,
    name="CTF agent",
    description="""Agent focused on conquering security challenges using generic linux commands
                   Expert in cybersecurity and exploitation.""",
    instructions="""You are a Cybersecurity expert Leader facing a CTF
                    challenge.
                    INSTRUCTIONS:
                    1. Execute the generic_linux_command tool without any
                    explanation.
                    2. Never assume the flag format - it could be any string
                    3. YOU MUST USE THE flag_discriminator to check the flag
                    when you have it in DECODED 64-bit format

                    ## generic_linux_command usage
                    # 1. Regular command execution
                    # 2. Shell Session Management: create and manage
                    # interactive shell sessions for commands like netcat,
                    # SSH, telnet.

                    - To start a new session: Use `generic_linux_command` with
                      commands like `ssh`
                    - To list active sessions:
                      `generic_linux_command("session", "list")`
                    - To get output from a session:
                      `generic_linux_command("session", "output <session_id>")`
                    - To send input to a session:
                      `generic_linux_command("<command>", "<args>",
                      session_id="<session_id>")`
                    - To terminate a session:
                      `generic_linux_command("session", "kill <session_id>")`

                    """,
    functions=[
        generic_linux_command,
    ],
    parallel_tool_calls=False
)


def transfer_to_one_tool_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to ctf agent.
    Accepts any keyword arguments but ignores them."""
    return one_tool_agent
