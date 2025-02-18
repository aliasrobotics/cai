"""
This module defines the Risk Agent for conducting risk assessments.
It utilizes Pydantic for data validation and defines the structure
of the output for the agent's responses.
"""
import os
from pydantic import BaseModel  # pylint: disable=import-error
from cai.types import Agent  # pylint: disable=import-error


class Hazard(BaseModel):  # pylint: disable=too-few-public-methods  # noqa: E501
    """Represents a hazard in the risk assessment."""
    name: str  # Name of the hazard
    harmed: str  # Who might be harmed
    current_measures: str  # What is already being done to control the risks
    actions: str  # Further actions needed to control the risks
    responsible: str  # Who needs to carry out the action
    deadline: str  # When is the action needed by


class RiskAssessment(BaseModel):  # pylint: disable=too-few-public-methods # noqa: E501
    """Represents a risk assessment report."""
    company_name: str  # Name of the company
    date_assessment: str  # Date the assessment was carried out
    hazards: list[Hazard]  # List of hazards identified in the assessment


def instructions(context_variables):  # pylint: disable=unused-argument  # noqa: E501
    """
    Instructions for the risk assessment agent
    """

    return """
    You are a risk analysis agent responsible for conducting a thorough risk analysis.
    Your analysis should be detailed and well-organized, addressing all critical elements of the risks identified.

    """  # noqa: E501


risk_agent = Agent(
    name="Risk Agent",
    model=os.getenv("CTF_MODEL", "qwen2.5:14b"),
    instructions=instructions,
    structured_output_class=RiskAssessment
)

def transfer_to_reporter_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to reporter agent.
    Accepts any keyword arguments but ignores them."""
    return risk_agent
