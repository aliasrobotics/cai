"""
This module contains the graph class for the CAI library.

This is a graph that stores the Agent and its history
at each step and allows reflecting on both, the reasoning
and the execution approach.
"""
# Standard library imports
import json
import logging
from typing import List  # pylint: disable=import-error

# Third party imports
from litellm.types.utils import Message  # pylint: disable=import-error
import networkx as nx  # pylint: disable=import-error
from pydantic import BaseModel  # pylint: disable=import-error
import requests  # pylint: disable=import-error
import urllib3  # pylint: disable=import-error

# Local imports
from cai.state.pydantic import state_agent
from .types import (
    Agent,
    ChatCompletionMessageToolCall
)


class Node(BaseModel):  # pylint: disable=too-few-public-methods
    """
    Represents a node in the graph.
    """
    name: str = "Node"
    agent: Agent = None
    turn: int = 0
    message: Message = None
    history: List = []
    strout: str = None

    def __hash__(self):
        # Convert history list to tuple for hashing
        history_tuple = tuple(str(h) for h in self.history)
        return hash((self.name, self.agent.name, self.turn, history_tuple))

    def __str__(self):
        """
        Format node label to be concise and
        readable within 80 chars width
        """
        if not self.strout:
            return self.name

        # NOTE: Review this part and consider using a more
        # efficient way to parse the strout and to format it
        # nicely
        try:  # pylint: disable=too-many-nested-blocks,too-many-branches,too-many-statements # noqa: E501
            # Parse JSON content after first double newline
            content = json.loads(self.strout.split('\n\n', 1)[1])

            # Special handling for network state
            if isinstance(content, dict) and 'network' in content:
                lines = [self.name, "\n"]
                for node in content['network']:
                    # Build endpoint summary line
                    summary = []
                    if 'ip' in node:
                        summary.append(f"{node['ip']}")
                    if node.get('ports'):
                        summary.append(f"{len(node['ports'])} ports")
                    if node.get('exploits'):
                        exploits = [e['name'] for e in node['exploits']]
                        summary.append(f"exploits: {', '.join(exploits)}")
                    if node.get('users'):
                        summary.append(f"users: {', '.join(node['users'])}")

                    # Add endpoint summary
                    lines.append(" - " + " | ".join(summary))

                    # Add files indented if present
                    if node.get('files'):
                        for file in node['files'][:10]:  # Limit to 10 files
                            if len(file) > 60:
                                file = file[:57] + "..."
                            lines.append("   ├─ " + file)
                        if len(node['files']) > 10:
                            lines.append("   └─ ...")

                    lines.append("\n")

                return "\n".join(lines)

            # For non-network state, format normally
            return f"{self.name}\n\n{json.dumps(content, indent=2)[:300]}"

        except (json.JSONDecodeError, IndexError):
            # Fallback for non-JSON content
            return f"{self.name}\n\n{self.strout}"


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
        self.previous_node = None

        # state, NOTE: each agent is stateless, and so is the default CAI
        # instance
        self.state = state_agent
        # self.state.model = "gpt-4o"  # NOTE: override the default model
        # self.state.model = "qwen2.5:72b"
        self._cai = None

    @property
    def cai(self):
        """Lazily initialize CAI instance"""
        if self._cai is None:
            from .core import CAI  # pylint: disable=import-outside-toplevel # noqa: E501
            self._cai = CAI(state_agent=self.state)
        return self._cai

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
        #
        # return node.name  # NOTE: avoid re-naming the node

    def calculate_node_strout(self, history, node_name):
        """
        Calculates the strout for the given node
        """
        # calculate node's state
        completion = self.cai.get_chat_completion(
            agent=self.state,  # force to use the state agent
            history=history[1:],
            context_variables={},
            model_override=None,
            stream=False,
            debug=False
        )
        message = completion.choices[0].message

        # Parse the JSON content and format it nicely
        try:
            content_json = json.loads(message.content)
            formatted_json = json.dumps(content_json, indent=2)
            strout = f"{node_name}\n\n{formatted_json}"
        except json.JSONDecodeError:
            # Fallback if content is not valid JSON
            strout = f"{node_name}\n\n{message.content}"
            print("ERROR:")
            print(strout)
        return strout

    def add_to_graph(
            self,
            node: object,
            action: List[ChatCompletionMessageToolCall] | None = None
    ) -> None:
        """Add a node to the graph and connect it to previous node.

        This method adds the given node to the graph and creates an edge from
        the previous node if one exists. It generates a unique name for the
        node, updates its name attribute, adds it to the name-operation mapping
        and the graph itself. If a previous node exists, it creates an edge
        between them.

        Args:
            node: Node object to add. Must have a settable 'name' attribute.
            action: Optional list of ChatCompletionMessageToolCall objects for
                labeling the edge from previous node. If None, edge has no
                label.

        Returns:
            None
        """
        unique_name = self.get_unique_name(node)
        node.name = unique_name

        # calculate strout via state agent inference
        # node.strout = self.calculate_node_strout(node.history, node.name)

        # map and add the node to the graph
        self._name_op_map[str(node)] = node
        self.add_node(node)

        # edge
        action_label = None
        if action:
            # Convert list of tool calls to readable format
            action_labels = []
            for tool_call in action:
                args_dict = json.loads(tool_call.function.arguments)
                args_str = ", ".join(f"{k}={v}" for k, v in args_dict.items())
                action_labels.append(f"{tool_call.function.name}({args_str})")
            action_label = "\n".join(action_labels)

        if self.previous_node:
            self.add_edge(self.previous_node, node, label=action_label)

        # update previous node
        self.previous_node = node

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
        # Disable warnings for unverified HTTPS requests
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        dot = self.to_pydot()

        # Configure the graph attributes for better formatting
        dot.set_rankdir('TB')  # Top to bottom layout
        dot.set_nodesep(0.75)  # Increased node separation
        dot.set_ranksep(0.75)  # Increased rank separation

        # Configure node attributes
        for node in dot.get_nodes():
            node.set_shape('box')
            node.set_fontname('monospace')
            node.set_margin('0.3,0.2')  # Increased margins
            # Left-align text in nodes
            label = node.get_label()
            if label:
                # Strip quotes that may be present
                label = label.strip('"')
                # Add left alignment and padding
                node.set_label(f'"{{\\l{label}\\l}}"')

        # Configure edge attributes
        for edge in dot.get_edges():
            edge.set_arrowsize('0.5')
            # Left-align edge labels
            label = edge.get_label()
            edge.set_label(label)

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
