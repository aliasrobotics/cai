"""
This module provides a flexible JSON schema for
representing network state in cybersecurity contexts.

Basic structure:
{
    "network": {
        "ip_address": {
            "ports": [
                {
                    "port": 80,
                    "open": true,
                    "service": "http",
                    "version": "2.4.41",
                    "vulns": ["CVE-2021-1234"]
                }
            ],
            "exploits": [
                {
                    "name": "exploit_name",
                    "type": "exploit_type",
                    "status": "success"
                }
            ],
            "files": ["/etc/passwd", "/home/user/.ssh/id_rsa"],
            "users": ["root", "admin"]
        }
    }
}
"""

import json
from typing import Dict, List, Optional, Union
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

    def add_endpoint(self, ip: str) -> None:
        """Add a new endpoint with default empty state"""
        if ip not in self.network:
            self.network[ip] = EndpointState()

    @classmethod
    def from_simple_dict(cls, data: Dict) -> "NetworkState":
        """
        Create NetworkState from a simple dictionary format.
        Handles both strict and flexible input formats.
        """
        if not isinstance(data, dict):
            raise ValueError("Input must be a dictionary")

        # Handle case where network key might be missing
        network_data = data.get("network", data)

        processed_network = {}
        for ip, endpoint_data in network_data.items():
            # Convert simple port lists/dicts to Port objects
            ports = []
            for port_data in endpoint_data.get("ports", []):
                if isinstance(port_data, int):
                    ports.append(Port(port=port_data))
                elif isinstance(port_data, dict):
                    ports.append(Port(**port_data))

            # Convert simple exploit lists/dicts to Exploit objects
            exploits = []
            for exploit_data in endpoint_data.get("exploits", []):
                if isinstance(exploit_data, str):
                    exploits.append(Exploit(name=exploit_data))
                elif isinstance(exploit_data, dict):
                    exploits.append(Exploit(**exploit_data))

            # Create EndpointState with processed data
            processed_network[ip] = EndpointState(
                ports=ports,
                exploits=exploits,
                files=endpoint_data.get("files", []),
                users=endpoint_data.get("users", []),
                info=endpoint_data.get("info", {})
            )

        return cls(network=processed_network)

    def to_dict(self) -> Dict:
        """Convert to a simplified dictionary format"""
        return self.model_dump()


def parse_network_state(data: Union[str, Dict]) -> NetworkState:
    """
    Helper function to parse network state from various input formats.
    Handles both JSON strings and dictionaries.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}") from e

    return NetworkState.from_simple_dict(data)
