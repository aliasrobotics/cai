"""
CAI agents abstraction layer

CAI abstracts its cybersecurity behavior via agents and agentic patterns.

An Agent in an intelligent system that interacts with some environment.
More technically, and agent is anything that can be viewed as perceiving
its environment through sensors and acting upon that environment through
actuators (Russel & Norvig, AI: A Modern Approach). In cybersecurity,
an Agent interacts with systems and networks, using peripherals and
network interfaces as sensors, and executing network actions as
actuators.

An Agentic Pattern is a structured design paradigm in artificial
intelligence systems where autonomous or semi-autonomous agents operate
within a "defined interaction framework" to achieve a goal. These
patterns specify the organization, coordination, and communication
methods among agents, guiding decision-making, task execution,
and delegation.

An agentic pattern (`AP`) can be formally defined as a tuple:


\\[
AP = (A, H, D, C, E)
\\]

where:

- **\\(A\\) (Agents):** A set of autonomous entities, \\( A = \\{a_1, a_2, ..., a_n\\} \\), each with defined roles, capabilities, and internal states.
- **\\(H\\) (Handoffs):** A function \\( H: A \times T \to A \\) that governs how tasks \\( T \\) are transferred between agents based on predefined logic (e.g., rules, negotiation, bidding).
- **\\(D\\) (Decision Mechanism):** A decision function \\( D: S \to A \\) where \\( S \\) represents system states, and \\( D \\) determines which agent takes action at any given time.
- **\\(C\\) (Communication Protocol):** A messaging function \\( C: A \times A \to M \\), where \\( M \\) is a message space, defining how agents share information.
- **\\(E\\) (Execution Model):** A function \\( E: A \times I \to O \\) where \\( I \\) is the input space and \\( O \\) is the output space, defining how agents perform tasks.

| **Agentic Pattern** | **Description** |
|--------------------|------------------------|
| `Swarm` (Decentralized) | Agents share tasks and self-assign responsibilities without a central orchestrator. Handoffs occur dynamically. *An example of a peer-to-peer agentic pattern is the `CTF Agentic Pattern`, which involves a team of agents working together to solve a CTF challenge with dynamic handoffs.* |
| `Hierarchical` | A top-level agent (e.g., "PlannerAgent") assigns tasks via structured handoffs to specialized sub-agents. Alternatively, the structure of the agents is harcoded into the agentic pattern with pre-defined handoffs. |
| `Chain-of-Thought` (Sequential Workflow) | A structured pipeline where Agent A produces an output, hands it to Agent B for reuse or refinement, and so on. Handoffs follow a linear sequence. *An example of a chain-of-thought agentic pattern is the `ReasonerAgent`, which involves a Reasoning-type LLM that provides context to the main agent to solve a CTF challenge with a linear sequence.*[^1] |
| `Auction-Based` (Competitive Allocation) | Agents "bid" on tasks based on priority, capability, or cost. A decision agent evaluates bids and hands off tasks to the best-fit agent. |
| `Recursive` | A single agent continuously refines its own output, treating itself as both executor and evaluator, with handoffs (internal or external) to itself. *An example of a recursive agentic pattern is the `CodeAgent` (when used as a recursive agent), which continuously refines its own output by executing code and updating its own instructions.* |

[^1]: Arguably, the Chain-of-Thought agentic pattern is a special case of the Hierarchical agentic pattern.
"""

# Standard library imports
import os
import pkgutil
import importlib

from typing import Dict

# Local application imports
from cai.agents.flag_discriminator import (
    flag_discriminator,
    transfer_to_flag_discriminator
)
from cai.state.pydantic import state_agent
from cai.types import Agent


# Extend the search path for namespace packages (allows merging)
__path__ = pkgutil.extend_path(__path__, __name__)

# Get model from environment or use default
model = os.getenv('CAI_MODEL', "qwen2.5:14b")


PATTERNS = [
    "hierarchical",
    "swarm",
    "chain_of_thought",
    "auction_based",
    "recursive"
]


def get_available_agents() -> Dict[str, Agent]:  # pylint: disable=R0912  # noqa
    """
    Get a dictionary of all available agents compiled
    from the cai/agents folder.

    Returns:
        Dictionary mapping agent names to Agent instances
    """
    agents_to_display = {}

    # # First, add all agents from AVAILABLE_AGENTS
    # for name, agent in AVAILABLE_AGENTS.items():
    #     agents_to_display[name] = agent

    # Add multi-type agent if available
    try:
        if "state" not in agents_to_display:
            agents_to_display["state"] = transfer_to_state_agent()
    except (ImportError, AttributeError):
        pass

    # Try to import all agents from the agents folder
    for _, name, _ in pkgutil.iter_modules(__path__,
                                           __name__ + "."):
        try:
            module = importlib.import_module(name)
            # Look for Agent instances in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(
                        attr, Agent) and not attr_name.startswith("_"):
                    # agent_name = attr_name.replace("_agent", "")
                    agent_name = attr_name
                    if agent_name not in agents_to_display:
                        agents_to_display[agent_name] = attr
        except (ImportError, AttributeError):
            pass

    # Also check the patterns subdirectory
    patterns_path = os.path.join(os.path.dirname(__file__), "patterns")
    if os.path.exists(patterns_path) and os.path.isdir(patterns_path):  # pylint: disable=R1702  # noqa
        for _, name, _ in pkgutil.iter_modules([patterns_path],
                                               __name__ + ".patterns."):
            try:
                module = importlib.import_module(name)
                # Look for Agent instances in the patterns module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(
                            attr, Agent) and not attr_name.startswith("_"):
                        # agent_name = attr_name.replace("_agent", "")
                        agent_name = attr_name
                        if agent_name not in agents_to_display:
                            agents_to_display[agent_name] = attr
            except (ImportError, AttributeError):
                pass

    return agents_to_display


def get_agent_module(agent_name: str) -> str:
    """
    Get the module name where a given agent is defined.

    Args:
        agent_name: Name of the agent
        (with or without '_agent' suffix)

    Returns:
        The full module name where the agent
        is defined (e.g., 'cai.agents.basic')
    """
    # Try to import all agents from the agents folder
    for _, name, _ in pkgutil.iter_modules(__path__,
                                           __name__ + "."):
        try:
            module = importlib.import_module(name)
            # Look for Agent instances in the module
            for attr_name in dir(module):
                # Try both with and without _agent suffix
                if (attr_name == agent_name) and isinstance(
                        getattr(module, attr_name), Agent):
                    return name
        except (ImportError, AttributeError):
            pass

    # Also check the patterns subdirectory
    patterns_path = os.path.join(os.path.dirname(__file__), "patterns")
    if os.path.exists(patterns_path) and os.path.isdir(patterns_path):
        for _, name, _ in pkgutil.iter_modules([patterns_path],
                                               __name__ + ".patterns."):
            try:
                module = importlib.import_module(name)
                # Look for Agent instances in the patterns module
                for attr_name in dir(module):
                    # Try both with and without _agent suffix
                    if (attr_name == agent_name) and isinstance(
                            getattr(module, attr_name), Agent):
                        return name
            except (ImportError, AttributeError):
                pass

    return "unknown"


def transfer_to_state_agent():
    """
    Transfer to the state agent
    """
    return state_agent


########################################################
# MAIN
########################################################
cai_agent = os.getenv('CAI_AGENT_TYPE', "one_tool_agent").lower()
# Get all available agents
available_agents = get_available_agents()

if cai_agent not in available_agents:
    # stop and raise error
    raise ValueError(f"Invalid CAI agent type: {cai_agent}")

# Set the initial agent based on the environment variable
cai_initial_agent = available_agents[cai_agent]

# Special handling for one_tool agent
#
# NOTE: maintained this for backwards compatibility
#
# NOTE 2: consider adding this if CTF_NAME defined
#
if cai_agent == "one_tool_agent":
    from cai.agents.one_tool import transfer_to_one_tool_agent  # noqa
    cai_initial_agent.functions.append(
        transfer_to_flag_discriminator
    )
    flag_discriminator.functions.append(transfer_to_one_tool_agent)  # noqa
