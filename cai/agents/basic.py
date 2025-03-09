"""
Collection of basic agents
"""

import os
from cai.util import Agent  # pylint: disable=import-error
from cai.tools.reconnaissance.netcat import netcat  # pylint: disable=import-error # noqa: E501
from cai.tools.reconnaissance.nmap import nmap  # pylint: disable=import-error # noqa: E501

# First party imports
from cai.tools.reconnaissance.filesystem import (
    list_dir,
    cat_file,
    find_file,
    pwd_command
)
from cai.tools.reconnaissance.generic_linux_command import (
    generic_linux_command
)
from cai.tools.reconnaissance.crypto_tools import (
    decode64,
    strings_command,
    decode_hex_bytes
)
model = os.getenv('CAI_MODEL', "qwen2.5:14b")


ctf_agent = Agent(
    model=model,
    name="CTF agent",
    description="""Agent focused on CTF challenges.
                   Expert in cybersecurity and exploitation.
                   Specializes in executing Linux commands efficiently.""",
    instructions="""You are a Cybersecurity expert Leader facing a CTF
                    challenge.
                    INSTRUCTIONS:
                    1. Execute the generic_linux_command tool without any
                    explanation.
                    2. Be efficient and strategic when executing commands.
                    3. Never assume the flag format - it could be any string
                    4. NEVER GIVE UP. KEEP EXECUTING TOOLS UNTIL YOU FIND
                    THE FLAG.
                    5. IF YOU ENCOUNTER A PROBLEM, IT IS HIGHLY LIKELY
                    THAT YOU ARE ASSUMING WRONG FILENAMES, PORTS,
                    IP ADDRESSES, ETC. PAY ATTENTION TO YOUR HALLUCINATIONS.
                    6. YOU MUST USE THE flag_discriminator to check the flag
                    when you have it in DECODED 64-bit format
                    7. Do a initial recon (nmap, service enumeration)""",
    functions=[
        generic_linux_command,
    ],
    parallel_tool_calls=False
)


def transfer_to_ctf_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to ctf agent.
    Accepts any keyword arguments but ignores them."""
    return ctf_agent


network_agent = Agent(
    model=model,
    name="Network Specialist",
    description="""Agent specialized in network reconnaissance.
                   Expert in using nmap and netcat for service discovery.
                   Focuses on identifying network vulnerabilities.""",
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


def transfer_to_network_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to network agent.
    Accepts any keyword arguments but ignores them."""
    return network_agent


crypto_agent = Agent(
    model=model,
    name="Cryptography Expert",
    description="""Agent specialized in cryptographic analysis.
                   Expert in decoding and analyzing encrypted data.
                   Focuses on breaking cryptographic challenges in CTFs.""",
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


def transfer_to_crypto_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to crypto agent.
    Accepts any keyword arguments but ignores them."""
    return crypto_agent


listing_agent = Agent(
    model=model,
    name="File Explorer",
    description="""Agent specialized in filesystem navigation and exploration.
                   Expert in finding and analyzing files and directories.
                   Focuses on discovering hidden files and sensitive data.""",
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


def transfer_to_listing_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to listing agent.
    Accepts any keyword arguments but ignores them."""
    return listing_agent
