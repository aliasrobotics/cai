"""
CTF Flag Discriminator Agent
"""
import os
from cai.types import Agent

model = os.getenv('CAI_MODEL', "qwen2.5:14b")
flag_discriminator = Agent(
    model="gpt-4o" if os.getenv('CAI_MODEL') == "o3-mini" else model,
    name="Flag discriminator",
    description="Agent focused on extracting the flag from the output",
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
