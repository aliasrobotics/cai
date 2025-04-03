"""
Agent "command" for CAI CLI abstraction

Provides commands for managing and switching between agents.
"""

# Standard library imports
import inspect
import os
import sys

from typing import Dict, List, Optional

# Third-party imports
from rich.console import Console  # pylint: disable=import-error
from rich.markdown import Markdown  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error
from rich import box  # pylint: disable=import-error

# Local imports
from cai.agents import get_available_agents, get_agent_module
from cai.repl.commands.base import Command, register_command
from cai.types import Agent
from cai.util import visualize_agent_graph

console = Console()


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

    def handle(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the agent command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            return self.handle_list(args, messages)

        subcommand = args[0]
        if subcommand in self._subcommands:
            handler = getattr(self, f"handle_{subcommand}", None)
            if handler:
                return handler(args[1:] if len(args) > 1 else None, messages)

        # If not a subcommand, try to select an agent by name
        return self.handle_select(args, messages)

    def handle_list(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=unused-argument # noqa: E501
        """Handle /agent list command.

        Args:
            args: Optional list of command arguments (not used)
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully
        """
        table = Table(title="Available Agents")
        table.add_column("#", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Module", style="magenta")
        table.add_column("Description", style="green")
        table.add_column("Pattern", style="blue")
        table.add_column("Model", style="yellow")

        # Scan all agents from the agents folder
        agents_to_display = get_available_agents()

        # Display all agents
        for i, (name, agent) in enumerate(agents_to_display.items(), 1):
            description = agent.description
            if not description and hasattr(agent, 'instructions'):
                if callable(agent.instructions):
                    description = agent.instructions(context_variables={})
                else:
                    description = agent.instructions
            # Clean up description - remove newlines and strip spaces
            if isinstance(description, str):
                description = " ".join(description.split())
                if len(description) > 50:
                    description = description[:47] + "..."

            # Get the module name for the agent
            module_name = get_agent_module(name)

            # Get the pattern if it exists
            pattern = getattr(agent, 'pattern', '')
            if pattern:
                pattern = pattern.capitalize()

            # Handle model display based on agent type
            model_display = self._get_model_display(name, agent)
            table.add_row(
                str(i),
                name,
                module_name,
                description,
                pattern,
                model_display
            )

        console.print(table)
        return True

    def handle_select(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:  # pylint: disable=too-many-branches,line-too-long # noqa: E501
        """Handle /agent select command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            console.print("[red]Error: No agent specified[/red]")
            console.print("Usage: /agent select <name|number>")
            return False

        agent_id = args[0]

        # Get the list of available agents
        agents_to_display = get_available_agents()

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
                
                # Display agent summary information in a Rich table
                self._display_agent_summary(agent_name, agent)
                
                visualize_agent_graph(agent)
                return True
            console.print("[red]Error: CAI client not initialized[/red]")
            return False
        console.print("[red]Error: REPL module not initialized[/red]")
        return False

    def _display_agent_summary(self, agent_name: str, agent: Agent) -> None:
        """Display a compact summary of the selected agent in a Rich table.
        
        Args:
            agent_name: Name of the agent
            agent: Agent instance
        """
        table = Table(
            title=f"Agent: {agent_name}",
            box=box.SIMPLE_HEAD,
            show_header=True,
            padding=(0, 1),
            collapse_padding=True,
            title_style="bold cyan",
            header_style="bold"
        )
        
        table.add_column("Property", style="cyan", width=10)
        table.add_column("Value", style="green", max_width=70, overflow="fold")
        
        # Add agent name
        table.add_row("Name", agent_name)
        
        # Add description
        description = agent.description
        if not description and hasattr(agent, 'instructions'):
            if callable(agent.instructions):
                try:
                    description = agent.instructions(context_variables={})
                except:  # pylint: disable=bare-except
                    description = agent.instructions
            else:
                description = agent.instructions
                
        # Clean up description - remove newlines and strip spaces
        if isinstance(description, str):
            description = " ".join(description.split())
            if len(description) > 80:
                description = description[:77] + "..."
        table.add_row("Description", description or "No description available")
        
        # Add system prompt (more compact)
        system_prompt = ""
        if hasattr(agent, 'system_prompt'):
            system_prompt = agent.system_prompt
        elif hasattr(agent, 'instructions'):
            if callable(agent.instructions):
                try:
                    system_prompt = agent.instructions(context_variables={})
                except:  # pylint: disable=bare-except
                    system_prompt = agent.instructions
            else:
                system_prompt = agent.instructions
        
        if isinstance(system_prompt, str):
            # Remove excess whitespace and format more compactly
            system_prompt = " ".join([line.strip() for line in 
                                    system_prompt.split("\n") if line.strip()])
            # Even shorter preview for compactness
            if len(system_prompt) > 600:
                system_prompt = system_prompt[:597] + "..."
        else:
            system_prompt = "No system prompt available"
        
        table.add_row("System", system_prompt)
        
        console.print(table)

    def handle_info(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Handle /agent info command.

        Args:
            args: Optional list of command arguments
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            console.print("[red]Error: No agent specified[/red]")
            console.print("Usage: /agent info <name|number>")
            return False

        agent_id = args[0]

        # Get the list of available agents
        agents_to_display = get_available_agents()

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


# Register the command
register_command(AgentCommand())
