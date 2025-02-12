"""
This module provides a Pydantic model for
representing network state in cybersecurity contexts.
"""
from pydantic import BaseModel  # pylint: disable=import-error
from cai.state import State
from cai.state.common import get_base_instructions, StateAgent


class Port(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents a network port and its properties"""
    port: int
    open: bool
    service: str  # More flexible than strict 'name'
    version: str
    vulns: list[str]


class Exploit(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents an exploit and its basic status"""
    name: str
    exploit_type: str
    status: str  # e.g., "success", "failed", "pending"


class EndpointState(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """
    Represents the state of a single network endpoint
    """
    ip: str
    ports: list[Port]
    exploits: list[Exploit]
    files: list[str]
    users: list[str]


class NetworkState(State):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """
    Represents the complete network state with multiple endpoints.
    Each endpoint in the list contains its IP address.
    """
    network: list[EndpointState]


def instructions(context_variables):
    """
    Instructions for the pydantic state agent
    """
    state = context_variables.get("state", "No previous state")
    initial_history = context_variables.get("initial_history", [])

    return f"""
    I am a network state building agent that analyzes chat history to
    construct network state in JSON format. Consider the following:
        - Don't make up information, only use information provided
        by the chat history and/or previous state.
        - Don't discard port and/or service information, always
        reflect it in the state.
        - For the files, for each, include permissions and
        complete filepath, including the ip address if a remote
        path.
        - Do not repeat Endpoint entries with the same IP address

    {get_base_instructions(state, initial_history)}
    """


state_agent = StateAgent(
    name="Pydantic NetworkState Agent",
    instructions=instructions,
    structured_output_class=NetworkState
)
