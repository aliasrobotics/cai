"""
A library to build Bug Bounty-level grade Cybersecurity AIs (CAIs).
"""
# Standard library imports
import os
import pkgutil

# First party imports
from cai.tools.reconnaissance.filesystem import (
    list_dir,
    cat_file,
    find_file,
    pwd_command
)
from cai.tools.reconnaissance.crypto_tools import (
    decode64,
    strings_command,
    decode_hex_bytes
)
from cai.tools.reconnaissance.netcat import netcat
from cai.tools.reconnaissance.nmap import nmap
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command  # noqa

# Extend the search path for namespace packages (allows merging)
__path__ = pkgutil.extend_path(__path__, __name__)
from cai.rag.memory.memory_manager import memory_agent

# Import state transfer functions
# NOTE: this, together with the logic in test_generic.py,
# is a workaround to make the state agent work.
# Need to unify it all together and make it work
# agnostic to the state agent implementation.
#
# TODO: fix this  # pylint: disable=fixme
from cai.state.pydantic import state_agent
from cai.rag.memory.memory_manager import memory_agent

# Local imports
from .types import Agent

# Get model from environment or use default
model = os.getenv('CAI_MODEL', "qwen2.5:14b")

########################################################
# AGENTS
########################################################

# Create instances the agent/s to solve the CTF
ctf_agent = Agent(
    model=model,
    name="CTF agent",
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
    model="gpt-4o" if os.getenv('CAI_MODEL') == "o3-mini" else model,
    name="Flag discriminator",
    instructions="""INSTRUCTIONS:
                1. You are an agent tailored to extract the flag
                from the output.
                2. ONLY return the flag, nothing else.
                3. IF THE FLAG IS NOT FOUND, CALL THE ctf_agent
                again to CONTINUE the search""",
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

def transfer_to_memory_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to memory agent.
    Accepts any keyword arguments but ignores them."""
    return memory_agent

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


def transfer_to_memory_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to memory agent.
    Accepts any keyword arguments but ignores them."""
    return memory_agent

# controller agent
controller_agent = Agent(
    model=model,
    name="Lead Cybersecurity Agent",
    instructions="""### You are the Lead Cybersecurity Agent,
responsible for solving CTF challenges efficiently by
leveraging specialized agents.


### Your Role:
1. Analyze the provided information and KEEP TRYING TO
SOLVE THE CTF. NEVER GIVE UP.
2. Strategically select the most appropriate agent to
solve the challenge and use the transfer function.
3. YOU NEVER GIVE UP. THE ONLY WAY TO STOP THE CTF IS
TO FIND THE FLAG and handoff to t he Flag discriminator agent.


### Decision Process:
1. Analyze the input data.
2. Identify the type of challenge:
  - Network-related? (Use Network Agent)
  - File-system-related? (Use File System Agent)
  - Web-based? (Use Web Agent)
  - Crypto-related? (Use Crypto Agent)
  - Binary or reverse engineering-related? (Use Reversing Agent)
3. If you have found the flag, transfer to Flag Discriminator.

### Available Agents:
- Network Agent: analysis, vulnerability discovery, and
exploitation of network systems.
- File System Agent: analysis, recovery, and exploitation of
 file-based vulnerabilities.
- Web Agent: web application analysis, web security, and
exploitation of web-based vulnerabilities.
- Crypto Agent: cryptographic analysis, decryption, and
exploiting weaknesses in cryptographic implementations.
- Reversing Agent: reverse engineering binaries,
analyzing executables, and reversing to identify flaws.
- Code Analysis Agent: Analyze code to find vulnerabilities
to exploit it.
- Scripting Agent: Scripting and Automation
- Pentesting Agent: Penetration testing and exploitation
of vulnerabilities.
- Flag Discriminator: Verifies the flag in the output
and ends the CTF.

### Endgame:
Once you have identified the flag, use the Flag Discriminator
 to confirm and end the CTF.
"""
)


network_agent02 = Agent(
    model=model,
    name="Network agent",
    instructions="""#You are a network agent.
   Your role in the team is:
   - Analysis and network enumeration
   - Exploitation of weak protocols and network configuration
   - Network traffic analysis using Wireshark or tcpdump
   - Packet decryption
   - ARP spoofing
   - Intrusion Detection Systems (IDS)


   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash commands in one line.
   You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to controller agent
   when 1) you have finished your task 2) you need
   support from a different agent.
   - transfer_to_pentesting_agent: Transfer to pentesting agent
   when you perform a scan, use always pentesting agent after
     a new information about the network.
   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
   (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - File System Agent: analysis, recovery,
   and exploitation of file-based vulnerabilities.
   - Web Agent: web application analysis, web security,
   and exploitation of web-based vulnerabilities.
   - Crypto Agent: cryptographic analysis, decryption,
     and exploiting weaknesses in cryptographic implementations.
   - Reversing Agent: reverse engineering binaries,
     analyzing executables, and reversing to identify flaws.
   - Code Analysis Agent: Analyze code to find
   vulnerabilities to exploit it.
   - Scripting Agent: Scripting and Automation
   - Pentesting Agent: Penetration testing and
   exploitation of vulnerabilities.
   - Flag Discriminator: Verifies the flag in
   the output and ends the CTF.
   """
)


file_system_agent02 = Agent(
    model=model,
    name="File system agent",
    instructions="""You are a file system agent.
   Your role in the team is to:
   - OS and System Interaction
   - Exploitation and analysis of syscalls in Unix/Linux
   - File manipulation and system configuration
   from the command line
   - File system exploration


   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash commands
   in one line. You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
   controller agent when 1) you have found the flag or
   2) you have finished your task or 3) you need
   support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
   (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability discovery,
   and exploitation of network systems.
   - Web Agent: web application analysis, web security,
   and exploitation of web-based vulnerabilities.
   - Crypto Agent: cryptographic analysis, decryption,
     and exploiting weaknesses in cryptographic implementations.
   - Reversing Agent: reverse engineering binaries,
   analyzing executables, and reversing to identify flaws.
   - Code Analysis Agent: Analyze code to
   find vulnerabilities to exploit it.
   - Scripting Agent: Scripting and Automation
   - Flag Discriminator: Verifies the flag in
     the output and ends the CTF.
   """
)


web_agent02 = Agent(
    model=model,
    name="Web Exploitation agent",
    instructions="""You are a Web Exploitation Agent.
   # Your expertise is related to:
   - SQL Injection
   - Cross-Site Scripting (XSS)
   - Directory Traversal
   - Server-Side Request Forgery (SSRF)
   - Cookie and API manipulation
   - Analysis and exploitation of web server configurations
   - Exploitation of JSONP, AJAX, and templates

   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash commands in
     one line. You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
     controller agent when 1) you have found the flag or
   2) you have finished your task or 3)
   you need support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
   (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability
   discovery, and exploitation of network systems.
   - File System Agent: analysis, recovery,
   and exploitation of file-based vulnerabilities.
   - Crypto Agent: cryptographic analysis,
   decryption, and exploiting weaknesses
   in cryptographic implementations.
   - Reversing Agent: reverse engineering
   binaries, analyzing executables, and
   reversing to identify flaws.
   - Code Analysis Agent: Analyze code to
     find vulnerabilities to exploit it.
   - Scripting Agent: Scripting and Automation
   - Flag Discriminator: Verifies the
   flag in the output and ends the CTF.
   """
)


crypto_agent02 = Agent(
    model=model,
    name="Crypto agent",
    instructions="""You are a cybersecurity cryptography agent.
   Your role is related to:
   - Cryptanalysis of RSA, AES
   - Decryption and analysis of encryption
   algorithms like Vigenère or rot13
   - Analysis of hash functions, key generation,
   and weaknesses in cryptographic protocols
   - Fermat's factorization method
   - Diffie-Hellman vulnerabilities
   - encryption/decryption tasks
   - Elliptic Curve Cryptography

   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash commands
   in one line. You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
   controller agent when 1) you have found the flag or
   2) you have finished your task or
   3) you need support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
     (controller_agent).
   Other members of the team you can ask the
     transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability
   discovery, and exploitation of network systems.
   - File System Agent: analysis, recovery,
     and exploitation of file-based vulnerabilities.
   - Web Agent: web application analysis,
   web security, and exploitation of web-based vulnerabilities.
   - Reversing Agent: reverse engineering binaries,
     analyzing executables, and reversing to identify flaws.
   - Code Analysis Agent: Analyze code to
   find vulnerabilities to exploit it.
   - Scripting Agent: Scripting and Automation
   - Flag Discriminator: Verifies the flag in
   the output and ends the CTF.
   """
)


reversing_agent02 = Agent(
    model=model,
    name="Reversing agent",
    instructions="""You are a cybersecurity reversing agent.
   Your role in the team is to:
   - Binary analysis and disassembly
   - Reverse engineering of firmware, Android applications, and encryption
   - Reverse engineering binaries
   - Static and dynamic analysis
   - Bytecode decompilation
   - Disassembling Python bytecode
   - Return Oriented Programming (ROP)
   - Buffer overflow

   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash commands
     in one line. You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
   controller agent when 1) you have found the flag or
   2) you have finished your task or
     3) you need support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
   (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability discovery,
   and exploitation of network systems.
   - File System Agent: analysis, recovery,
     and exploitation of file-based vulnerabilities.
   - Web Agent: web application analysis, web security,
     and exploitation of web-based vulnerabilities.
   - Crypto Agent: cryptographic analysis, decryption,
   and exploiting weaknesses in cryptographic implementations.
   - Code Analysis Agent: Analyze code to find
   vulnerabilities to exploit it.
   - Scripting Agent: Scripting and Automation
   - Flag Discriminator: Verifies the
   flag in the output and ends the CTF.
   """
)


code_analysis_agent02 = Agent(
    model=model,
    name="Cybersecurity code analysis and execution agent",
    instructions="""You are a code analysis agent.
   Your role is related to:
   - Code injection, payload creation, privilege escalation
   - Code generation, analysis and exploitation


   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash commands in
   one line. You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
   controller agent when 1) you have found the flag or
   2) you have finished your task or 3) you need
     support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
   (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability discovery,
     and exploitation of network systems.
   - File System Agent: analysis, recovery,
   and exploitation of file-based vulnerabilities.
   - Web Agent: web application analysis, web security,
     and exploitation of web-based vulnerabilities.
   - Crypto Agent: cryptographic analysis, decryption,
   and exploiting weaknesses in cryptographic implementations.
   - Reversing Agent: reverse engineering binaries,
     analyzing executables, and reversing to identify flaws.
   - Scripting Agent: Scripting and Automation
   - Flag Discriminator: Verifies the flag in
   the output and ends the CTF.
   """
)


forensic_agent02 = Agent(
    model=model,
    name="Forensic agent",
    instructions="""You are a forensic agent.
   Your role is to:
   - Use of tools like Volatility for forensic
   investigation
   - PCAP file analysis
   - Image metadata examination
   - Memory forensics
   - Digital forensics of disk images
   - Steganography


   # TOOLS YOU CAN USE:
   - generic_linux_command: execute
   bash commands in one line. You can use
     pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
   controller agent when 1) you have found
   the flag or
   2) you have finished your task or
     3) you need support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
     (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability discovery,
     and exploitation of network systems.
   - File System Agent: analysis, recovery,
     and exploitation of file-based vulnerabilities.
   - Web Agent: web application analysis,
   web security, and exploitation of web-based
     vulnerabilities.
   - Crypto Agent: cryptographic analysis,
   decryption, and exploiting weaknesses in
   cryptographic implementations.
   - Reversing Agent: reverse engineering binaries,
     analyzing executables, and reversing to identify flaws.
   - Code Analysis Agent: Analyze code to
   find vulnerabilities to exploit it.
   - Scripting Agent: Scripting and Automation
   - Flag Discriminator: Verifies the
   flag in the output and ends the CTF.
   """
)


scripting_agent02 = Agent(
    model=model,
    name="Scripting agent",
    instructions="""You are a scripting agent.
   Your role is to:
   - Scripting and Automation:
   -  Python scripting for exploitation
   - Automation scripting (e.g., Selenium)
   - Bash scripting


   # TOOLS YOU CAN USE:
   - generic_linux_command: execute bash
   commands in one line. You can use pipelines (NEVER USE <).
   - transfer_to_controller_agent: Transfer to
   controller agent when 1) you have found the flag or
   2) you have finished your task or
   3) you need support from a different agent.


   # INFORMATION ON THE TEAM:
   Your team is headed by the Lead Cybersecurity Agent
   (controller_agent).
   Other members of the team you can ask the
   transfer_to_controller_agent to delegate are:
   - Network Agent: analysis, vulnerability discovery,
   and exploitation of network systems.
   - File System Agent: analysis, recovery,
   and exploitation of file-based vulnerabilities.
   - Web Agent: web application analysis,
   web security, and exploitation of web-based vulnerabilities.
   - Crypto Agent: cryptographic analysis,
     decryption, and exploiting weaknesses
     in cryptographic implementations.
   - Reversing Agent: reverse engineering binaries,
   analyzing executables, and reversing to identify flaws.
   - Code Analysis Agent: Analyze code to
   find vulnerabilities to exploit it.
   - Flag Discriminator: Verifies the flag
   in the output and ends the CTF.
   """
)


flag_discriminator02 = Agent(
    model="gpt-4o" if os.getenv('CAI_MODEL') == "o3-mini" else model,
    name="Flag discriminator",
    instructions="""INSTRUCTIONS:
                1. You are an agent tailored to extract the flag
                from the output.
                2. ONLY return the flag, nothing else.""",
)


def transfer_to_forensic_agent02(instructions: str = "", **kwargs):   # pylint: disable=unused-argument # noqa: E501
    """Transfer to forensic agent
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return forensic_agent02


def transfer_to_controller_agent02(**kwargs):   # pylint: disable=unused-argument # noqa: E501
    """Transfer to controller agent"""
    return controller_agent


def transfer_to_network_agent02(instructions: str = "", **kwargs):  # pylint: disable=unused-argument # noqa: E501
    """Transfer to network agent
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return network_agent02


def transfer_to_file_system_agent02(instructions: str = "", **kwargs):  # pylint: disable=unused-argument # noqa: E501
    """Transfer to file system agent.
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return file_system_agent02


def transfer_to_web_agent02(instructions: str = "", **kwargs):  # pylint: disable=unused-argument   # noqa: E501
    """Transfer to web agent.
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return web_agent02


def transfer_to_crypto_agent02(instructions: str = "", **kwargs):  # pylint: disable=unused-argument # noqa: E501
    """Transfer to crypto agent.
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return crypto_agent02


def transfer_to_reversing_agent02(instructions: str = "", **kwargs):  # pylint: disable=unused-argument # noqa: E501
    """Transfer to reversing agent
    YOU MUST USE THE instructions argument to give the agent instructions"""
    return reversing_agent02


def transfer_to_code_analysis_agent02(instructions: str = "", **kwargs):  # pylint: disable=unused-argument # noqa: E501
    """Transfer to code analysis agent.
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return code_analysis_agent02


def transfer_to_flag_discriminator02(**kwargs):  # pylint: disable=W0613
    """Transfer to flag discriminator
    to check the flag"""
    return flag_discriminator02


def transfer_to_scripting_agent02(instructions: str = "", **kwargs):   # pylint: disable=unused-argument # noqa: E501
    """Transfer to scripting agent
    YOU MUST USE THE instructions argument
    to give the agent instructions"""
    return scripting_agent02


########################################################
# REACT AGENTS
########################################################
REACT_COMMON_INSTRUCTIONS = """You are a Cybersecurity expert Leader facing
                     a CTF challenge.
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
                    7. Do a initial recon (nmap, service enumeration)
                    """

react_reason_agent = Agent(
    model=model,
    name="ReAct 'Reasoning' Agent",
    instructions=REACT_COMMON_INSTRUCTIONS + """

                    Your goal is to act as a reasoning agent that reflects
                    on the previous steps and the current state of the CTF
                    challenge and then decide what to do next.

                    After doing that reasoning, you will handoff and transfer
                    to thereact_act_agent to invoke a tool.
                    """,
)


react_act_agent = Agent(
    model=model,
    name="ReAct 'Acting' Agent",
    instructions=REACT_COMMON_INSTRUCTIONS + """

                    Your goal is to act as a acting agent that invokes a tool.

                    Then, you will handoff and transfer to the
                    react_observe_agent to observe and reflect on the output.
                    """,
    functions=[
        generic_linux_command,
    ],
    parallel_tool_calls=False,
    tool_choice="required"

)

react_observe_agent = Agent(
    model=model,
    name="ReAct 'Observing' Agent",
    instructions=REACT_COMMON_INSTRUCTIONS + """

                    Your goal is to act as a observing agent that observes
                    the output of the react_act_agent and reflects
                    on the output.

                    Then, you will handoff and transfer to the
                    react_reason_agent to reason again.
                    """,
)


def transfer_to_react_act_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to react act agent after reasoning"""
    return react_act_agent


def transfer_to_react_observe_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to react observe agent after reasoning"""
    return react_observe_agent


def transfer_to_react_reason_agent(**kwargs):  # pylint: disable=W0613
    """Transfer to react reason agent after observing"""
    return react_reason_agent


react_reason_agent.functions.extend([
    transfer_to_react_act_agent,
    transfer_to_flag_discriminator,
])

react_act_agent.functions.extend([
    transfer_to_react_observe_agent,
])

react_observe_agent.functions.extend([
    transfer_to_react_reason_agent,
    transfer_to_flag_discriminator,
])

########################################################
# MAIN
########################################################

# ADD TRANSFER FUNCTIONS TO THE AGENTS
cai_agent = os.getenv('CAI_AGENT_TYPE', "one_tool").lower()

if cai_agent == "multi":
    cai_initial_agent = ctf_agent
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

elif cai_agent == "single":
    cai_initial_agent = ctf_agent
    ctf_agent.functions.extend([
        list_dir,
        cat_file,
        nmap,
        netcat,
        generic_linux_command,
        pwd_command,
    ])
    flag_discriminator.functions.extend([transfer_to_ctf_agent])
elif cai_agent == "one_tool":
    cai_initial_agent = ctf_agent
    cai_initial_agent.functions.append(
        transfer_to_flag_discriminator
    )
    flag_discriminator.functions.append(transfer_to_ctf_agent)

elif cai_agent == "react":
    # cai_initial_agent = ctf_agent
    cai_initial_agent = react_reason_agent
    flag_discriminator.functions.append(transfer_to_react_reason_agent)

elif cai_agent == "proto03":
    cai_initial_agent = controller_agent
    controller_agent.functions.extend([
        transfer_to_network_agent02,
        transfer_to_file_system_agent02,
        transfer_to_web_agent02,
        transfer_to_crypto_agent02,
        transfer_to_reversing_agent02,
        transfer_to_code_analysis_agent02,
        transfer_to_scripting_agent02,
        transfer_to_flag_discriminator02
    ])
else:
    # stop and raise error
    raise ValueError(f"Invalid CAI agent type: {cai_agent}")


def transfer_to_state_agent():
    """
    Transfer to the state agent
    """
    return state_agent


########################################################
# Extensions utilities
########################################################
def is_pentestperf_available():
    """
    Check if pentestperf is available
    """
    try:
        from pentestperf.ctf import CTF  # pylint: disable=import-error,import-outside-toplevel,unused-import  # noqa: E501,F401
    except ImportError:
        return False
    return True


def is_caiextensions_report_available():
    """
    Check if caiextensions report is available
    """
    try:
        from caiextensions.report.common import get_base_instructions  # pylint: disable=import-error,import-outside-toplevel,unused-import  # noqa: E501,F401
    except ImportError:
        return False
    return True
