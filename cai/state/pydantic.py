"""
This module provides a Pydantic model for
representing network state in cybersecurity contexts.
"""
from pydantic import BaseModel  # pylint: disable=import-error
from cai.state import State
from cai.types import Agent


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
    """Represents the state of a single network endpoint"""
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


state_agent = Agent(
    name="Pydantic NetworkState Agent",
    instructions="""
    I am a network state building agent that analyzes chat
    history to construct network state.

    I look for information about ports, services, exploits and
    build a structured state representation.
    """,
    structured_output_class=NetworkState
)
