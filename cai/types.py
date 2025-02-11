"""
This module contains type definitions for the CAI library.
"""

from typing import List, Callable, Union, Optional
from openai.types.chat import ChatCompletionMessage  # noqa: F401, E501  # pylint: disable=import-error, unused-import
from openai.types.chat.chat_completion_message_tool_call import (  # noqa: F401, E501  # pylint: disable=import-error, unused-import
    ChatCompletionMessageToolCall,
    Function,
)

# Third-party imports
from pydantic import BaseModel  # pylint: disable=import-error
from cai.state import State

AgentFunction = Callable[[], Union[str, "Agent", dict, State]]


class Agent(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Represents an agent in the CAI.
    """

    name: str = "Agent"
    # model: str = "gpt-4o"
    model: str = "qwen2.5:14b"
    instructions: Union[str, Callable[[], str]] = "You are a helpful agent."
    functions: List[AgentFunction] = []
    tool_choice: str = None
    parallel_tool_calls: bool = True
    structured_output_class: Optional[type] = None
    reasoning_effort: Optional[str] = "low"  # "low", "medium", "high"


class Response(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Represents a response back to the user from the CAI.

    NOTE: This happens within the run() chain, after "Ending turn"
    in the CAI.
    """

    messages: List = []
    agent: Optional[Agent] = None
    context_variables: dict = {}
    time: float = 0.0
    report: Optional[str] = None


class Result(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Encapsulates the possible return values for an agent function.

    Attributes:
        value (str): The result value as a string.
        agent (Agent): The agent instance, if applicable.
        context_variables (dict): A dictionary of context variables.
    """

    value: str = ""
    agent: Optional[Agent] = None
    context_variables: dict = {}
