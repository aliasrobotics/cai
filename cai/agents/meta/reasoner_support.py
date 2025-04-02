"""
This module provides a Reasoner Agent for autonomous pentesting.

The Reasoner Agent is designed to enhance the reasoning capabilities
of the main agent by providing structured analysis without making tool calls.
"""

import os
from typing import Optional, Callable, Union
from cai.util import load_prompt_template  # Add this import
from cai.types import Agent


def create_reasoner_agent(
    name: str = "Reasoner",
    model: Optional[str] = None,
    instructions: Optional[Union[str, Callable[[], str]]] = None
) -> Agent:
    """
    Create a Reasoner Agent for autonomous pentesting.

    This agent is designed to provide in-depth reasoning and analysis
    without making tool calls. It helps the main agent by offering
    structured thinking about pentesting strategies and approaches.

    Args:
        name: The name of the reasoner agent.
        model: The model to use for the reasoner agent. If None,
               uses the CAI_SUPPORT_MODEL environment variable or
               falls back to the default model.
        instructions: Custom instructions for the reasoner agent.
                     If None, uses default reasoning instructions.

    Returns:
        Agent: A configured Reasoner Agent instance.
    """
    # Use environment variable for model if not specified
    if model is None:
        model = os.getenv("CAI_SUPPORT_MODEL", "o3-mini")

    # Default instructions for the reasoner agent
    default_instructions = load_prompt_template(
        "cai/prompts/system_reasoner_supporter.md")

    # Use provided instructions or default
    agent_instructions = (
        instructions if instructions is not None
        else default_instructions
    )

    # Check if the model supports reasoning_effort
    kwargs = {}
    if any(x in model for x in ["o1", "o3"]):
        kwargs["reasoning_effort"] = "high"

    # Create and return the reasoner agent
    return Agent(
        name=name,
        model=model,
        instructions=agent_instructions,
        **kwargs
    )


reasoner_agent = create_reasoner_agent()


def transfer_to_reasoner(**kwargs) -> str:  # pylint: disable=unused-argument
    """
    Transfer the conversation to the reasoner agent.
    """
    return reasoner_agent
