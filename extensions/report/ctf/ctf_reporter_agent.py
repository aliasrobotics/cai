"""
This module provides Pydantic models for generating reports in
Cybersecurity Capture The Flag (CTF) challenges.
"""
import os
from pydantic import BaseModel  # pylint: disable=import-error
from cai.types import Agent  # pylint: disable=import-error
from extensions.report.common import get_base_instructions  # pylint: disable=import-error # noqa: E501


class Tool(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """
    Sumary of each tool used
    """
    command_output: str  # Output of the command used
    command: str  # Complete command of the tool used


class Step(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """
    Summary of each step taken during the CTF challenge
    """
    identifier: str  # Unique identifier for the step (e.g., Step-001)
    description: str  # Detailed description of the actions performed
    reasoning: str  # Literal reasoning of LLM
    tools_used: list[Tool]  # Tools used fot this step


class CTFReport(BaseModel):  # pylint: disable=too-few-public-methods,
    """
    A Pydantic class representing a CTF Report Agent.
    This agent is responsible for generating reports based on CTF challenges.
    """
    final_flag: str  # Final flag found
    summary: str  # Summary of the CTF resolution process
    steps: list[Step]
    final_step: str  # Conclusion of the CTF challenge


def instructions(context_variables):  # pylint: disable=unused-argument  # noqa: E501
    """
    Instructions for the pydantic state agent
    """
    previous_reports = context_variables.get("previous_reports", [])

    return f"""
    You are a highly sophisticated and persuasive professional security report generator tasked with producing an exceptionally detailed report based on the CTF challenge results.
    Your mission is to create a document of technical excellence, comparable to a comprehensive whitepaper, where every observation, measurement, and recommendation is described with rigorous exactitude.

    Your report must be structured into the following sections:

    Table of Contents (with expandable subsections):
      • Final Flag
      • Summary
      • Steps Taken
      • Final Reasoning

    For each section, provide exhaustive, exact, and context-independent details:

    Final Flag:
      Clearly state the final flag obtained from the CTF challenge or if it is not found indicate this as "No flag found".

    Summary:
      Deliver a comprehensive overview summarizing the entire CTF resolution process.
      Summarize the key findings and overall outcomes of the CTF challenge with precision,
      including the success or failure of the challenge and the significance of the final flag.

    Steps Taken:
      Document EVERY STEP taken during the CTF challenge with rigorous precision.
      Ensuring that every tool used is documented for clarity and completeness.
      For each step, include:
          • A uniquely defined identifier (e.g., Step-001, Step-002, etc.).
          • A detailed description of the steps performed.
          • The tool or tools used for each step, and describe:
             - The command used for each step
             - The output of the command to provide a complete understanding of the actions taken.

    Final Step:
      Provide a detailed explanation of the reasoning behind the final step taken to find (or not find) the final flag in the CTF challenge.
      Explianing the situation where the CTF was stopped.

    {get_base_instructions(previous_reports)}
    """  # noqa: E501


reporter_agent = Agent(
    name="Report Agent",
    model=os.getenv("CAI_MODEL", "gpt-4o"),
    instructions=instructions,
    structured_output_class=CTFReport
)


def transfer_to_reporter_agent(**kwargs):  # pylint: disable=W0613
    """ Transfer to reporter agent.
    Accepts any keyword arguments but ignores them."""
    return reporter_agent
