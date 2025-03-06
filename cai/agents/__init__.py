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
| `Peer-to-Peer` (Decentralized) | Agents share tasks and self-assign responsibilities without a central orchestrator. Handoffs occur dynamically. *An example of a peer-to-peer agentic pattern is the `CTF Agentic Pattern`, which involves a team of agents working together to solve a CTF challenge with dynamic handoffs.* |
| `Hierarchical` | A top-level agent (e.g., "PlannerAgent") assigns tasks via structured handoffs to specialized sub-agents. Alternatively, the structure of the agents is harcoded into the agentic pattern with pre-defined handoffs. |
| `Chain-of-Thought` (Sequential Workflow) | A structured pipeline where Agent A produces an output, hands it to Agent B for reuse or refinement, and so on. Handoffs follow a linear sequence. *An example of a chain-of-thought agentic pattern is the `ReasonerAgent`, which involves a Reasoning-type LLM that provides context to the main agent to solve a CTF challenge with a linear sequence.* |
| `Auction-Based` (Competitive Allocation) | Agents "bid" on tasks based on priority, capability, or cost. A decision agent evaluates bids and hands off tasks to the best-fit agent. |
| `Recursive` | A single agent continuously refines its own output, treating itself as both executor and evaluator, with handoffs (internal or external) to itself. *An example of a recursive agentic pattern is the `CodeAgent` (when used as a recursive agent), which continuously refines its own output by executing code and updating its own instructions.*  |
"""

# Standard library imports
import os
import pkgutil

# Local application imports
from cai.agents.flag_discriminator import (
    flag_discriminator,
    transfer_to_flag_discriminator
)
from cai.state.pydantic import state_agent


# Extend the search path for namespace packages (allows merging)
__path__ = pkgutil.extend_path(__path__, __name__)

# Get model from environment or use default
model = os.getenv('CAI_MODEL', "qwen2.5:14b")


# Dictionary of available agents
AGENTS = {
    "one_tool": ctf_agent_one_tool,
    "code": codeagent,
    "state": state_agent
}

PATTERNS = {
    "swarm": swarm_pattern,
    "hierarchical": hierarchical_pattern,
    "peer_to_peer": peer_to_peer_pattern,
    "chain_of_thought": chain_of_thought_pattern,
    "auction_based": auction_based_pattern,
    "recursive_self_improvement": recursive_self_improvement_pattern
}

########################################################
# MAIN
########################################################
cai_agent = os.getenv('CAI_AGENT_TYPE', "one_tool").lower()

if cai_agent == "one_tool":
    from cai.agents.one_tool import ctf_agent_one_tool, transfer_to_ctf_agent_one_tool  # noqa
    cai_initial_agent = ctf_agent_one_tool  # noqa
    cai_initial_agent.functions.append(
        transfer_to_flag_discriminator
    )
    flag_discriminator.functions.append(transfer_to_ctf_agent_one_tool)
elif cai_agent == "codeagent":
    from cai.agents.codeagent import codeagent
    cai_initial_agent = codeagent
elif cai_agent == "boot2root":
    from cai.agents.cli_basic import boot2root_agent
    cai_initial_agent = boot2root_agent
else:
    # stop and raise error
    raise ValueError(f"Invalid CAI agent type: {cai_agent}")


def transfer_to_state_agent():
    """
    Transfer to the state agent
    """
    return state_agent
