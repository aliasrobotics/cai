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
| `Hierarchical` | A top-level agent (e.g., "PlannerAgent") assigns tasks via structured handoffs to specialized sub-agents. Alternatively, the structure of the agents is hardcoded into the agentic pattern with pre-defined handoffs. |
| `Chain-of-Thought` (Sequential Workflow) | A structured pipeline where Agent A produces an output, hands it to Agent B for reuse or refinement, and so on. Handoffs follow a linear sequence. *An example of a chain-of-thought agentic pattern is the `ReasonerAgent`, which involves a Reasoning-type LLM that provides context to the main agent to solve a CTF challenge with a linear sequence.*[^1] |
| `Auction-Based` (Competitive Allocation) | Agents "bid" on tasks based on priority, capability, or cost. A decision agent evaluates bids and hands off tasks to the best-fit agent. |
| `Recursive` | A single agent continuously refines its own output, treating itself as both executor and evaluator, with handoffs (internal or external) to itself. *An example of a recursive agentic pattern is the `CodeAgent` (when used as a recursive agent), which continuously refines its own output by executing code and updating its own instructions.* |

[^1]: Arguably, the Chain-of-Thought agentic pattern is a special case of the Hierarchical agentic pattern.
"""

# Standard library imports
import importlib
import os
import pkgutil
from typing import Dict

from dotenv import load_dotenv  # pylint: disable=import-error # noqa: E501

# Load .env file from current directory before importing agents
# This ensures that .env files in the user's working directory are loaded
# even when CAI is installed from PyPI
load_dotenv(override=True)  # override=True ensures env vars from .env take precedence

# Local application imports
from cai.agents.flag_discriminator import flag_discriminator, transfer_to_flag_discriminator
from cai.sdk.agents import Agent
from cai.sdk.agents.handoffs import handoff

# Extend the search path for namespace packages (allows merging)
__path__ = pkgutil.extend_path(__path__, __name__)

# Get model from environment or use default
model = os.environ.get("CAI_MODEL", "alias1")


PATTERNS = ["hierarchical", "swarm", "chain_of_thought", "auction_based", "recursive"]


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

    # Try to import all agents from the agents folder
    for _, name, _ in pkgutil.iter_modules(__path__, __name__ + "."):
        try:
            module = importlib.import_module(name)
            # Look for Agent instances in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, Agent) and not attr_name.startswith("_"):
                    # agent_name = attr_name.replace("_agent", "")
                    agent_name = attr_name
                    if agent_name not in agents_to_display:
                        agents_to_display[agent_name] = attr
        except (ImportError, AttributeError):
            pass

    # Also check the patterns subdirectory
    patterns_path = os.path.join(os.path.dirname(__file__), "patterns")
    if os.path.exists(patterns_path) and os.path.isdir(patterns_path):  # pylint: disable=R1702  # noqa
        for _, name, _ in pkgutil.iter_modules([patterns_path], __name__ + ".patterns."):
            try:
                module = importlib.import_module(name)
                # Look for Agent instances in the patterns module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, Agent) and not attr_name.startswith("_"):
                        # Only include agents that have a .pattern attribute (swarm patterns)
                        # Skip regular agents without pattern attribute
                        if not hasattr(attr, "pattern"):
                            continue
                        # agent_name = attr_name.replace("_agent", "")
                        agent_name = attr_name
                        if agent_name not in agents_to_display:
                            agents_to_display[agent_name] = attr
            except (ImportError, AttributeError) as e:
                # Extract module name from the full import path
                module_short_name = name.split('.')[-1]
                print(f"Error importing {module_short_name}: {e}")

    # Add all patterns (parallel, swarm, etc.) as pseudo-agents
    from cai.agents.patterns import PATTERNS
    for pattern_name, pattern_obj in PATTERNS.items():
        # Create a pseudo-agent object for the pattern
        class PatternAgent:
            def __init__(self, pattern):
                self.name = pattern.name
                self.description = pattern.description
                # Get the string value of the enum
                if hasattr(pattern.type, 'value'):
                    self.pattern_type = pattern.type.value
                else:
                    self.pattern_type = str(pattern.type)
                self._pattern = pattern
                # Add minimal attributes to avoid AttributeError
                self.instructions = f"Pattern: {pattern.description}"
                self.tools = []
                self.handoffs = []
                self.model = None
                self.output_type = None
        
        pseudo_agent = PatternAgent(pattern_obj)
        agents_to_display[pattern_name] = pseudo_agent

    return agents_to_display


def get_agent_module(agent_name: str) -> str:
    """
    Get the module name where a given agent is defined.

    Args:
        agent_name: Name of the agent
        (with or without '_agent' suffix)

    Returns:
        The full module name where the agent
        is defined (e.g., 'cai.sdk.agents.basic')
    """
    # Try to import all agents from the agents folder
    for _, name, _ in pkgutil.iter_modules(__path__, __name__ + "."):
        try:
            module = importlib.import_module(name)
            # Look for Agent instances in the module
            for attr_name in dir(module):
                # Try both with and without _agent suffix
                if (attr_name == agent_name) and isinstance(getattr(module, attr_name), Agent):
                    return name
        except (ImportError, AttributeError):
            pass

    # Also check the patterns subdirectory
    patterns_path = os.path.join(os.path.dirname(__file__), "patterns")
    if os.path.exists(patterns_path) and os.path.isdir(patterns_path):
        for _, name, _ in pkgutil.iter_modules([patterns_path], __name__ + ".patterns."):
            try:
                module = importlib.import_module(name)
                # Look for Agent instances in the patterns module
                for attr_name in dir(module):
                    # Try both with and without _agent suffix
                    if (attr_name == agent_name) and isinstance(getattr(module, attr_name), Agent):
                        return name
            except (ImportError, AttributeError):
                pass

    return "unknown"


def get_agent_by_name(agent_name: str, custom_name: str = None, model_override: str = None, agent_id: str = None) -> Agent:
    """
    Get a NEW agent instance by name using the dynamic factory system.

    Args:
        agent_name: Name of the agent to retrieve
        custom_name: Optional custom name for the agent instance (e.g., "Bug Bounter #1")
        model_override: Optional model to use instead of the default
        agent_id: Optional agent ID (e.g., "P1", "P2", "P3")

    Returns:
        NEW Agent instance corresponding to the given name

    Raises:
        ValueError: If the agent name is not found
    """
    # Import the generic factory system
    from cai.agents.factory import get_agent_factory

    try:
        # Use the generic factory system to get a factory for this agent
        factory = get_agent_factory(agent_name)
        # Create and return a new instance with optional model override and custom name
        agent = factory(model_override=model_override, custom_name=custom_name, agent_id=agent_id)
        return agent
    except ValueError:
        # If not found in factory, fall back to legacy method
        pass

    # Legacy fallback: get existing singleton instances
    available_agents = get_available_agents()
    agent_name_lower = agent_name.lower()

    # Check if the agent exists in available_agents
    if agent_name_lower not in available_agents:
        raise ValueError(
            f"Invalid agent type: {agent_name}. Available agents: {', '.join(available_agents.keys())}"
        )

    # Get the agent instance (singleton)
    agent = available_agents[agent_name_lower]

    # For singleton agents, try to create a copy with a fresh model instance
    if hasattr(agent, "model") and hasattr(agent.model, "__class__"):
        try:
            # Create a new model instance
            model_class = agent.model.__class__
            if model_class.__name__ == "OpenAIChatCompletionsModel":
                # Use custom name if provided, otherwise use agent's name
                instance_name = custom_name if custom_name else agent.name
                # Determine which model to use
                model_to_use = model_override if model_override else agent.model.model
                # Create new model with same config but new instance
                new_model = model_class(
                    model=model_to_use,
                    openai_client=agent.model._client,
                    agent_name=instance_name,
                    agent_id=agent_id,
                    agent_type=agent_name_lower,
                )
                # Clone the agent with the new model
                cloned_agent = agent.clone(model=new_model)
                # Update the agent's name if custom name provided
                if custom_name:
                    cloned_agent.name = custom_name
                    
                # Check if this agent has any MCP tools configured
                try:
                    from cai.repl.commands.mcp import get_mcp_tools_for_agent
                    
                    # Get MCP tools for this agent and add them
                    mcp_tools = get_mcp_tools_for_agent(agent_name_lower)
                    if mcp_tools:
                        # Ensure the agent has tools list
                        if not hasattr(cloned_agent, 'tools'):
                            cloned_agent.tools = []
                        
                        # Remove any existing tools with the same names to avoid duplicates
                        existing_tool_names = {t.name for t in mcp_tools}
                        cloned_agent.tools = [t for t in cloned_agent.tools if t.name not in existing_tool_names]
                        
                        # Add the MCP tools
                        cloned_agent.tools.extend(mcp_tools)
                except ImportError:
                    # MCP command not available, skip
                    pass
                    
                return cloned_agent
        except Exception:
            # If cloning fails, return the original
            pass

    # For singleton agents without cloning, still check for MCP tools
    try:
        from cai.repl.commands.mcp import get_mcp_tools_for_agent
        
        # Get MCP tools for this agent and add them
        mcp_tools = get_mcp_tools_for_agent(agent_name_lower)
        if mcp_tools:
            # Ensure the agent has tools list
            if not hasattr(agent, 'tools'):
                agent.tools = []
            
            # Remove any existing tools with the same names to avoid duplicates
            existing_tool_names = {t.name for t in mcp_tools}
            agent.tools = [t for t in agent.tools if t.name not in existing_tool_names]
            
            # Add the MCP tools
            agent.tools.extend(mcp_tools)
    except ImportError:
        # MCP command not available, skip
        pass
    
    return agent
