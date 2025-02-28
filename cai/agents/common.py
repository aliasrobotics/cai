"""Common functions for creating agents."""

import os
from cai.types import Agent
from cai.tools.reconnaissance.generic_linux_command import generic_linux_command

def create_ctf_agent(model: str = None, name: str = "CTF agent",
                    additional_functions=None) -> Agent:
    """Create a CTF agent with standard configuration.
    
    Args:
        model: The model to use. Defaults to environment variable CAI_MODEL
               or "qwen2.5:14b"
        name: The name of the agent. Defaults to "CTF agent"
        additional_functions: Additional functions to add to the agent
    
    Returns:
        Agent: The configured CTF agent
    """
    if model is None:
        model = os.getenv('CAI_MODEL', "qwen2.5:14b")
    
    functions = [generic_linux_command]
    if additional_functions:
        functions.extend(additional_functions)
    
    return Agent(
        model=model,
        name=name,
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
        functions=functions,
        parallel_tool_calls=False
    ) 