"""
This module provides a flexible JSON schema for
representing network state in cybersecurity contexts.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field  # pylint: disable=import-error
from cai.state import State


class Port(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents a network port and its properties"""
    port: int
    open: bool = True
    service: Optional[str] = None  # More flexible than strict 'name'
    version: Optional[str] = None
    # Simplified vulnerabilities
    vulns: List[str] = Field(default_factory=list)
    info: Dict[str, str] = Field(
        default_factory=dict)  # For additional details

    class Config:  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
        extra = "allow"  # Allows additional fields for flexibility


class Exploit(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents an exploit and its basic status"""
    name: str
    type: Optional[str] = None
    status: str = "pending"  # e.g., "success", "failed", "pending"
    info: Dict[str, str] = Field(
        default_factory=dict)  # For additional details

    class Config:  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
        extra = "allow"


class EndpointState(BaseModel):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """Represents the state of a single network endpoint"""
    ip: str
    ports: List[Port] = Field(default_factory=list)
    exploits: List[Exploit] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    users: List[str] = Field(default_factory=list)
    info: Dict[str, str] = Field(
        default_factory=dict)  # For additional details

    class Config:  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
        extra = "allow"


class NetworkState(State):  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
    """
    Represents the complete network state with multiple endpoints.
    Each key in the network dict is an IP address.
    """
    network: Dict[str, EndpointState] = Field(default_factory=dict)

    class Config:  # pylint: disable=too-few-public-methods, missing-class-docstring  # noqa: E501
        extra = "allow"
