"""
This module defines the Check Agent for reviewing compliance assessments
related to NIS2 requirements. It utilizes Pydantic for data validation
and defines the structure of the output for the agent's responses.
"""
import os
from pydantic import BaseModel  # pylint: disable=import-error
from cai.types import Agent  # pylint: disable=import-error


class CheckCompliance(BaseModel):  # pylint: disable=too-few-public-methods # noqa: E501
    """Check some assessment of the report."""
    H1_data_encryption: str
    J1_mfa_usage: str
    J2_communications_protection: str


check_agent = Agent(
    name="Check Agent",
    model=os.getenv("CTF_MODEL", "qwen2.5:14b"),
    instructions="""
    You are in charge of reviewing the conversation. Return the variables
    filled with [x] if the condition is fulfilled
    or [ ] if not. The conditions are:

    H1. Data encryption is used for sensitive information to preserve data
       integrity, confidentiality, and authenticity.

    J1. Multi-factor authentication (MFA) is used for critical access.

    J2. Voice, video, and text communications are protected.
    """,
    structured_output_class=CheckCompliance
)


def transfer_to_check_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to check Agent.
    Accepts any keyword arguments but ignores them."""
    return check_agent
