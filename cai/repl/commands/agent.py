"""
Agent command for CAI REPL.
This module provides commands for managing and switching between agents.
"""
# Standard library imports
import importlib
import os
import inspect
import pkgutil
from typing import (
    Dict,
    List,
    Optional
)
import sys
# Third-party imports
from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error
from rich.markdown import Markdown  # pylint: disable=import-error

# Local imports
from cai.types import Agent
from cai.repl.commands.base import Command, register_command
from cai import (
    state_agent,
    transfer_to_state_agent
)

# Import core agents that are guaranteed to be available
from cai.agents.one_tool import ctf_agent_one_tool
from cai.agents.codeagent import codeagent
import cai.agents

console = Console()

# Dictionary of available agents
AVAILABLE_AGENTS = {
    "one_tool": ctf_agent_one_tool,
    "code": codeagent,
    "state": state_agent
}

# Try to import additional agents if available
try:
    from cai.agents.flag_discriminator import flag_discriminator
    AVAILABLE_AGENTS["flag"] = flag_discriminator
except ImportError:
    pass

try:
    from cai.agents.basic import basic_agent
    AVAILABLE_AGENTS["basic"] = basic_agent
except ImportError:
    pass


class AgentCommand(Command):
    """Command for managing and switching between agents."""

    def __init__(self):
        """Initialize the agent command."""
        # Initialize with basic parameters
        super().__init__(
            name="/agent",
            description="Manage and switch between agents",
            aliases=["/a"]
        )

        # Add subcommands manually
        self._subcommands = {
            "list": "List available agents",
            "select": "Select an agent by name or number",
            "info": "Show information about an agent",
            "multi": "Enable multi-agent mode"
        }

    def _get_available_agents(self) -> Dict[str, Agent]:
        """Get a dictionary of all available agents.

        Returns:
            Dictionary mapping agent names to Agent instances
        """
        agents_to_display = {}

        # First, add all agents from AVAILABLE_AGENTS
        for name, agent in AVAILABLE_AGENTS.items():
            agents_to_display[name] = agent

        # Add multi-type agent if available
        try:
            if "state" not in agents_to_display:
                agents_to_display["state"] = transfer_to_state_agent()
        except (ImportError, AttributeError):
            pass

        # Try to import all agents from the agents folder
        for _, name, _ in pkgutil.iter_modules(cai.agents.__path__,
                                               cai.agents.__name__ + "."):
            try:
                module = importlib.import_module(name)
                # Look for Agent instances in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(
                            attr, Agent) and not attr_name.startswith("_"):
                        agent_name = attr_name.replace("_agent", "")
                        if agent_name not in agents_to_display:
                            agents_to_display[agent_name] = attr
            except (ImportError, AttributeError):
                pass

        return agents_to_display

    def _get_model_display(self, agent_name: str, agent: Agent) -> str:
        """Get the display string for an agent's model.

        Args:
            agent_name: Name of the agent
            agent: Agent instance

        Returns:
            String to display for the agent's model
        """
        # For code agent, always show the model
        if agent_name == "code":
            return agent.model

        # For other agents, check if CTF_MODEL is set
        ctf_model = os.getenv('CTF_MODEL')
        if ctf_model and agent.model == ctf_model:
            # Don't show default model for CTF_MODEL in table
            # but show "Default CTF Model" in info
            return ""

        # Show the model from environment variable if available
        env_var_name = f"CAI_{agent_name.upper()}_MODEL"
        model_env = os.getenv(env_var_name)
        if model_env:
            return model_env

        return agent.model

    def _get_model_display_for_info(
            self, agent_name: str, agent: Agent) -> str:
        """Get the display string for an agent's model in the info view.

        Args:
            agent_name: Name of the agent
            agent: Agent instance

        Returns:
            String to display for the agent's model in the info view
        """
        # For code agent, always show the model
        if agent_name == "code":
            return agent.model

        # For other agents, check if CTF_MODEL is set
        ctf_model = os.getenv('CTF_MODEL')
        if ctf_model and agent.model == ctf_model:
            # Show "Default CTF Model" in info
            return "Default CTF Model"

        # Show the model from environment variable if available
        env_var_name = f"CAI_{agent_name.upper()}_MODEL"
        model_env = os.getenv(env_var_name)
        if model_env:
            return model_env

        return agent.model

    def get_subcommands(self) -> List[str]:
        """Get list of subcommand names.

        Returns:
            List of subcommand names
        """
        return list(self._subcommands.keys())

    def get_subcommand_description(self, subcommand: str) -> str:
        """Get description for a subcommand.

        Args:
            subcommand: Name of the subcommand

        Returns:
            Description of the subcommand
        """
        return self._subcommands.get(subcommand, "")

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the agent command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            return self.handle_list(args)

        subcommand = args[0]
        if subcommand in self._subcommands:
            handler = getattr(self, f"handle_{subcommand}", None)
            if handler:
                return handler(args[1:] if len(args) > 1 else None)

        # If not a subcommand, try to select an agent by name
        return self.handle_select(args)

    def handle_list(self, args: Optional[List[str]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /agent list command.

        Args:
            args: Optional list of command arguments (not used)

        Returns:
            True if the command was handled successfully
        """
        table = Table(title="Available Agents")
        table.add_column("#", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Model", style="yellow")

        # Scan all agents from the agents folder
        agents_to_display = self._get_available_agents()

        # Display all agents
        for i, (name, agent) in enumerate(agents_to_display.items(), 1):
            description = agent.instructions
            if callable(description):
                description = description(context_variables={})

            # Truncate long descriptions
            if isinstance(description, str) and len(description) > 50:
                description = description[:47] + "..."

            # Handle model display based on agent type
            model_display = self._get_model_display(name, agent)

            table.add_row(
                str(i),
                name,
                description,
                model_display
            )

        console.print(table)
        return True

    def handle_select(self, args: Optional[List[str]] = None) -> bool:  # pylint: disable=too-many-branches,line-too-long # noqa: E501
        """Handle /agent select command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            console.print("[red]Error: No agent specified[/red]")
            console.print("Usage: /agent select <name|number>")
            return False

        agent_id = args[0]

        # Get the list of available agents
        agents_to_display = self._get_available_agents()

        # Check if agent_id is a number
        if agent_id.isdigit():
            index = int(agent_id)
            if 1 <= index <= len(agents_to_display):
                agent_name = list(agents_to_display.keys())[index - 1]
            else:
                console.print(
                    f"[red]Error: Invalid agent number: {agent_id}[/red]")
                return False
        else:
            # Treat as agent name
            agent_name = agent_id
            if agent_name not in agents_to_display:
                console.print(f"[red]Error: Unknown agent: {agent_name}[/red]")
                return False

        # Get the agent
        agent = agents_to_display[agent_name]

        # Set the agent as the current agent in the REPL
        # We need to avoid circular imports, so we'll use a different approach
        # to access the client and current_agent variables

        # Import the module dynamically to avoid circular imports
        if 'cai.repl.repl' in sys.modules:
            repl_module = sys.modules['cai.repl.repl']

            # Check if client is initialized
            if hasattr(repl_module, 'client') and repl_module.client:
                # Update the active_agent in the client
                repl_module.client.active_agent = agent

                # Update the global current_agent variable if it exists
                if hasattr(repl_module, 'current_agent'):
                    repl_module.current_agent = agent

                # Update the global agent variable if it exists
                if hasattr(repl_module, 'agent'):
                    repl_module.agent = agent

                # Also update the agent variable in the run_demo_loop
                # function's frame if possible
                try:
                    for frame_info in inspect.stack():
                        frame = frame_info.frame
                        if ('run_demo_loop' in frame.f_code.co_name and
                                'agent' in frame.f_locals):
                            frame.f_locals['agent'] = agent
                            break
                except Exception:  # pylint: disable=broad-except # nosec
                    # If this fails, we still have the global current_agent as
                    # a fallback
                    pass

                console.print(
                    f"[green]Switched to agent: {agent_name}[/green]")
                return True
            console.print("[red]Error: CAI client not initialized[/red]")
            return False
        console.print("[red]Error: REPL module not initialized[/red]")
        return False

    def handle_info(self, args: Optional[List[str]] = None) -> bool:
        """Handle /agent info command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            console.print("[red]Error: No agent specified[/red]")
            console.print("Usage: /agent info <name|number>")
            return False

        agent_id = args[0]

        # Get the list of available agents
        agents_to_display = self._get_available_agents()

        # Check if agent_id is a number
        if agent_id.isdigit():
            index = int(agent_id)
            if 1 <= index <= len(agents_to_display):
                agent_name = list(agents_to_display.keys())[index - 1]
            else:
                console.print(
                    f"[red]Error: Invalid agent number: {agent_id}[/red]")
                return False
        else:
            # Treat as agent name
            agent_name = agent_id
            if agent_name not in agents_to_display:
                console.print(f"[red]Error: Unknown agent: {agent_name}[/red]")
                return False

        # Get the agent
        agent = agents_to_display[agent_name]

        # Display agent information
        instructions = agent.instructions
        if callable(instructions):
            instructions = instructions()

        # Handle model display based on agent type
        model_display = self._get_model_display_for_info(agent_name, agent)

        # Create a markdown table for agent details
        markdown_content = f"""
# Agent: {agent_name}

| Property | Value |
|----------|-------|
| Name | {agent.name} |
| Model | {model_display} |
| Functions | {len(agent.functions)} |
| Parallel Tool Calls | {'Yes' if agent.parallel_tool_calls else 'No'} |

## Instructions

{instructions}
"""

        console.print(Markdown(markdown_content))
        return True

    def handle_multi(self, args: Optional[List[str]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /agent multi command to enable multi-agent mode.

        Args:
            args: Optional list of command arguments (not used)

        Returns:
            True if the command was handled successfully
        """
        # Check if CAI_MULTI_AGENT environment variable is set
        multi_agent = os.getenv('CAI_MULTI_AGENT', 'false').lower() == 'true'

        if not multi_agent:
            # Set the environment variable
            os.environ['CAI_MULTI_AGENT'] = 'true'
            console.print("[green]Multi-agent mode enabled[/green]")
            console.print(
                "[yellow]Note: This will take effect on restart[/yellow]")
        else:
            console.print(
                "[yellow]Multi-agent mode is already enabled[/yellow]")

        return True


# Register the command
register_command(AgentCommand())
