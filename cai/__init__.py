"""
A library to build Bug Bounty-level grade Cybersecurity AIs (CAIs).
"""
import os
from cai.tools.reconnaissance.filesystem import (list_dir,
                                                 cat_file,
                                                 find_file,
                                                 pwd_command)
from cai.tools.reconnaissance.crypto_tools import (decode64,
                                                   strings_command,
                                                   decode_hex_bytes)
from cai.tools.reconnaissance.netcat import netcat
from cai.tools.reconnaissance.nmap import nmap
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command  # noqa

from .core import CAI
from .types import Agent, Response


__all__ = ["CAI", "Agent", "Response"]


# Get model from environment or use default
model = os.getenv('CTF_MODEL', "qwen2.5:14b")


# AGENTS

# 4. Create instances the agent/s to solve the CTF

ctf_agent = Agent(
    model=model,
    name="CTF Leader",
    instructions="""You are a Cybersecurity expert Leader facing a CTF
                    challenge.
                    INSTRUCTIONS:
                    1. THINK OF THE STEPS TO SOLVE THE CTF CHALLENGE.
                    DO NOT BE VERBOSE, JUST CALL THE AGENTS.
                    2. Your team is a set of agents with tools.
                    3. IMPORTANT: THE CONTENT OF THE CTF CHALLENGE IS
                    THE KEY TO SOLVE IT.
                    NOT ALL THE INFORMATION YOU ARE GIVEN IS USEFUL.
                    4. Call the proper agents to solve the CTF, do not generate
                    a plan nor return
                    much text.
                    5. Keep calling agents until you find the flag.
                    6. YOU ONLY USE THE flag_discriminator when you have
                    the final flag as a 64-bit string""",
    # functions=[],  # This code can execute by LLM
    # parallel_tool_calls=True, Enable multi function calling
)


listing_agent = Agent(
    model=model,
    name="File Explorer",
    instructions=("""INSTRUCTIONS:
        1. You specialize in navigating file systems.
        2. Use your tools to list, read, and find files in
        a directory.
        3. DO NOT USE THE SAME TOOL FOR THE SAME FILE OR
        DIRECTORY more than 3 times.
        4. DO NOT BE VERBOSE, JUST CALL THE TOOLS AS NEEDED
        TO SOLVE THE CTF
        5. KEEP CALLING THE TOOLS OR THE CTF Leader AGENT
        UNTIL YOU FIND THE FLAG"""),
    functions=[
        list_dir,
        cat_file,
        find_file,
        pwd_command,
        generic_linux_command],
)

network_agent = Agent(
    model=model,
    name="Network Specialist",
    instructions=("""INSTRUCTIONS:
        1. You specialize in using nmap and netcat.
        INSTRUCTIONS:
        1. You always use real information of the
        CTF challenge as arguments for the tools.
        If you lack of that information, you find another
        way to get it.
        2. Keep calling agents until you find the flag.
        3. Do not be verbose, just call the tools.
        4. YOU NEVER USE PLACEHOLDERS, AS THE TOOLS WILL
        NOT WORK WITH THEM.
        5. Whenever you find a likely candidate flag, call
        the flag_discriminator agent.
        6. DO NOT SEND THE SAME COMMAND OVER AND OVER"""),
    functions=[netcat, nmap],
)


crypto_agent = Agent(
    model=model,
    name="Cryptography Expert",
    instructions=("""
        INSTRUCTIONS:
        1. Your expertise is in decryption and
                  data analysis.
        2. Use your tools to decode and analyze
                  encrypted data.
        3. DO NOT BE VERBOSE, JUST CALL THE TOOLS AS NEEDED
        4. Use your tools to solve the CTF challenge.
        5. Do not generate a plan or verbose output.
        """
                  ),
    functions=[decode64, strings_command, decode_hex_bytes],
)


flag_discriminator = Agent(
    model=model,
    name="Flag discriminator",
    instructions="You are an agent tailored to " +
    "extract the flag" +
    "from the output." +
    "ONLY return the flag, nothing else.",
    # functions=[check_flag],  # This code can execute by LLM00
)


# TRANSFER FUNCTIONS


def transfer_to_flag_discriminator(**kwargs):  # pylint: disable=W0613
    """Transfer flag discriminator.
    Accepts any keyword arguments but ignores them."""
    return flag_discriminator


def transfer_to_ctf_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to ctf agent.
    Accepts any keyword arguments but ignores them."""
    return ctf_agent


def transfer_to_network_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to network agent.
    Accepts any keyword arguments but ignores them."""
    return network_agent


def transfer_to_listing_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to listing agent.
    Accepts any keyword arguments but ignores them."""
    return listing_agent


def transfer_to_crypto_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to crypto agent.
    Accepts any keyword arguments but ignores them."""
    return crypto_agent


# ADD TRANSFER FUNCTIONS TO THE AGENTS
ctf_agent.functions.extend([
    transfer_to_flag_discriminator,
    transfer_to_crypto_agent,
    transfer_to_listing_agent,
    transfer_to_network_agent
])

listing_agent.functions.extend(
    [transfer_to_ctf_agent, transfer_to_flag_discriminator])
network_agent.functions.extend(
    [transfer_to_ctf_agent, transfer_to_flag_discriminator])
crypto_agent.functions.extend(
    [transfer_to_ctf_agent, transfer_to_flag_discriminator])
flag_discriminator.functions.extend([transfer_to_ctf_agent])