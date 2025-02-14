"""
This module contains the graph class for the CAI library.

This is a graph that stores the Agent and its history
at each step and allows reflecting on both, the reasoning
and the execution approach.
"""
# Standard library imports
import logging
from typing import List  # pylint: disable=import-error

# Third party imports
import networkx as nx  # pylint: disable=import-error
import requests  # pylint: disable=import-error
from litellm.types.utils import Message  # pylint: disable=import-error
from pydantic import BaseModel  # pylint: disable=import-error

# Local imports
from cai.types import Agent


class Node(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Represents a node in the graph.
    """
    name: str = "Node"
    agent: Agent = None
    turn: int = 0
    message: Message = None
    history: List = []

    def __hash__(self):
        # Convert history list to tuple for hashing
        history_tuple = tuple(str(h) for h in self.history)
        return hash((self.name, self.agent.name, self.turn, history_tuple))

    def __str__(self):
        return f"{self.name}"


class Graph(nx.DiGraph):
    """
    A graph storing every discrete step in the exploitation flow.

    Built using networkx:
    - source code https://github.com/networkx/networkx
    - algorithms https://networkx.org/documentation/stable/reference/algorithms/index.html  # noqa
    - tutorial https://networkx.org/documentation/stable/tutorial.html
    """

    def __init__(self):
        super().__init__()
        self._name_op_map = {}
        self._trainable_variables_collection = {}
        self.reward = 0  # Initialize reward attribute

    def get_name_op_map(self):
        """
        Returns the name-op map
        """
        return self._name_op_map

    def get_trainable_variables_collection(self):
        """
        Returns the trainable variables collection
        """
        return self._trainable_variables_collection

    def add_to_trainable_variables_collection(self, key, value):
        """
        Adds a key-value pair to the trainable variables collection
        """
        if key in self._trainable_variables_collection:
            logging.warning(
                "The key: %s exists in trainable_variables_collection",
                key
            )
        else:
            self._trainable_variables_collection[key] = value

    def get_unique_name(self, node):
        """
        Returns a unique name for the given node

        NOTE: it does not set the name of the node,
        it just returns a unique name
        """
        original_name = node.name
        unique_name = original_name
        index = 0
        while unique_name in self._name_op_map.keys():  # pylint: disable=consider-iterating-dictionary # noqa
            index += 1
            base_name = unique_name.split("_")[0]
            unique_name = f"{base_name}_{index}"
        return unique_name

    def add_to_graph(self, node):
        """
        Adds a node to the graph
        """
        unique_name = self.get_unique_name(node)
        node.name = unique_name
        self._name_op_map[node.name] = node
        self.add_node(node)

    def add_reward_graph(self, reward):
        """Adds a reward to the graph"""
        self.reward += reward

    def to_pydot(self):
        """
        Converts the graph to a pydot object
        """
        dot = nx.nx_pydot.to_pydot(self)
        return dot

    def to_dot(self, dotfile_path) -> None:
        """
        Exports the graph to a dot file

        NOTE: simple ASCII art visualizations can be
        made with https://dot-to-ascii.ggerganov.com/
        """
        nx.nx_pydot.write_dot(self, dotfile_path)

    def ascii(self) -> str:
        """
        Exports the graph to an ASCII art string

        NOTE: uses https://github.com/ggerganov/dot-to-ascii
        """
        dot = self.to_pydot()
        return requests.get(
            "https://dot-to-ascii.ggerganov.com/dot-to-ascii.php",
            params={
                "boxart": 1,  # 0 for not fancy
                "src": str(dot),
            },
            verify=False,  # nosec B501
            timeout=30  # nosec B113
        ).text


if "DEFAULT_GRAPH" not in globals():
    DEFAULT_GRAPH = None


def get_default_graph():
    """
    Returns the default graph instance, creating it if it doesn't exist.

    Returns:
        Graph: The default graph instance
    """
    global DEFAULT_GRAPH  # pylint: disable=global-statement
    if DEFAULT_GRAPH is None:
        DEFAULT_GRAPH = Graph()
    return DEFAULT_GRAPH


def reset_default_graph():
    """
    Resets the default graph to a new instance.

    Returns:
        Graph: A new default graph instance
    """
    global DEFAULT_GRAPH  # pylint: disable=global-statement
    DEFAULT_GRAPH = Graph()
    return DEFAULT_GRAPH
