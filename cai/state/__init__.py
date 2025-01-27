"""
This module provides a state class that can be used to represent
the state of a cybersecurity system.
"""

from pydantic import BaseModel  # pylint: disable=import-error


class State(BaseModel):  # pylint: disable=too-few-public-methods
    """
    The state is a representation of the system being tested.

    The state should capture the response of any
    cybersecurity action/operation, in a way that the resulting data
    (which represents the state itself) can be used to
    understand the current state of the system being tested as
    well as to interpret it in human-readable output formats.

    NOTE: The state is both produced and consumed by the LLM.

    Implementations of the state should inherit from this class.
    """
