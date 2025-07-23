"""
Compact command for CAI REPL.
Compacts current conversation and manages model/prompt settings.
"""

from typing import List, Optional
import os
import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from cai.repl.commands.base import Command, register_command
from cai.sdk.agents.models.openai_chatcompletions import get_current_active_model
from cai.util import COST_TRACKER
from cai.repl.commands.model import (
    ModelCommand, 
    get_predefined_model_categories,
    get_all_predefined_models
)

console = Console()


class CompactCommand(Command):
    """Command for compacting conversations with optional model and prompt settings."""
    
    def __init__(self):
        """Initialize the compact command."""
        super().__init__(
            name="/compact",
            description="Compact current conversation into a memory summary",
            aliases=["/cmp"]
        )
        
        # Add subcommands
        self.add_subcommand("model", "Set model for compaction", self.handle_model)
        self.add_subcommand("prompt", "Set custom summarization prompt", self.handle_prompt)
        self.add_subcommand("status", "Show compaction settings", self.handle_status)
        
        # Default model for compaction (None means use current model)
        self.compact_model = None
        
        # Custom summarization prompt (None means use default)
        self.custom_prompt = None
        
        # Cache for model numbers
        self.cached_model_numbers = {}
        
    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the compact command."""
        # Parse arguments for --model and --prompt flags
        model_override = None
        prompt_override = None
        
        if args:
            i = 0
            while i < len(args):
                if args[i] == "--model" and i + 1 < len(args):
                    model_override = args[i + 1]
                    i += 2
                elif args[i] == "--prompt" and i + 1 < len(args):
                    # Collect all remaining args as prompt
                    prompt_override = " ".join(args[i + 1:])
                    break
                else:
                    # Check if it's a subcommand
                    subcommand = args[i].lower()
                    if subcommand in self.subcommands:
                        handler = self.subcommands[subcommand]["handler"]
                        return handler(args[i+1:] if len(args) > i+1 else [])
                    else:
                        console.print(f"[yellow]Unknown argument: {args[i]}[/yellow]")
                        console.print("[dim]Usage: /compact [--model <model>] [--prompt <prompt>][/dim]")
                        return True
        else:
            # No arguments provided - check if in parallel mode
            from cai.repl.commands.parallel import PARALLEL_CONFIGS
            
            if PARALLEL_CONFIGS:
                # In parallel mode - automatically compact all agents
                return self._perform_parallel_compaction()
            else:
                # Single agent mode - show help menu and ask
                self._show_help_menu()
                return self._ask_and_perform_compaction()
                    
        # If arguments provided, perform compaction with overrides
        return self._perform_compaction(model_override, prompt_override)
    
    def handle_model(self, args: Optional[List[str]] = None) -> bool:
        """Set model for compaction."""
        if not args:
            # Display current model
            console.print(
                Panel(
                    f"Current compact model: [bold green]{self.compact_model or 'Using current model'}[/bold green]",
                    border_style="green",
                    title="Compact Model Setting"
                )
            )
            
            # Get all predefined models using the shared function
            ALL_MODELS = get_all_predefined_models()
            
            # Show available models in a table
            model_table = Table(
                title="Available Models for Compaction",
                show_header=True,
                header_style="bold yellow")
            model_table.add_column("#", style="bold white", justify="right")
            model_table.add_column("Model", style="cyan")
            model_table.add_column("Provider", style="magenta")
            model_table.add_column("Category", style="blue")
            model_table.add_column("Input Cost ($/M)", style="green", justify="right")
            model_table.add_column("Output Cost ($/M)", style="red", justify="right")
            model_table.add_column("Description", style="white")
            
            # Add all predefined models
            for i, model in enumerate(ALL_MODELS, 1):
                # Format pricing info
                input_cost_str = (
                    f"${model['input_cost']:.2f}"
                    if model['input_cost'] is not None else "Unknown"
                )
                output_cost_str = (
                    f"${model['output_cost']:.2f}"
                    if model['output_cost'] is not None else "Unknown"
                )
                
                model_table.add_row(
                    str(i),
                    model["name"],
                    model["provider"],
                    model["category"],
                    input_cost_str,
                    output_cost_str,
                    model["description"]
                )
            
            console.print(model_table)
            
            # Usage instructions
            console.print("\n[cyan]Usage:[/cyan]")
            console.print("  [bold]/compact model <model_name>[/bold] - Set model by name")
            console.print("  [bold]/compact model <number>[/bold]     - Set model by number from table")
            console.print("  [bold]/compact model default[/bold]      - Use current agent model")
            
            # Update cached model numbers for selection
            self.cached_model_numbers = {
                str(i): model["name"] for i, model in enumerate(ALL_MODELS, 1)
            }
            
            return True
            
        model_arg = args[0]
        
        # Check if it's a number for model selection
        if model_arg.isdigit() and hasattr(self, 'cached_model_numbers'):
            if model_arg in self.cached_model_numbers:
                model_name = self.cached_model_numbers[model_arg]
            else:
                console.print(f"[red]Invalid model number: {model_arg}[/red]")
                return True
        else:
            model_name = model_arg
        
        if model_name.lower() == "default":
            self.compact_model = None
            console.print("[green]Will use current model for compaction[/green]")
        else:
            self.compact_model = model_name
            console.print(f"[green]Set compact model to: {model_name}[/green]")
            
        return True
    
    def handle_prompt(self, args: Optional[List[str]] = None) -> bool:
        """Set custom summarization prompt."""
        if not args:
            if self.custom_prompt:
                console.print("[cyan]Current custom prompt:[/cyan]")
                console.print(self.custom_prompt)
            else:
                console.print("[yellow]No custom prompt set. Using default prompt.[/yellow]")
            
            console.print("\nUsage: /compact prompt <prompt_text>")
            console.print("       /compact prompt reset    - Reset to default prompt")
            console.print("\nExample: /compact prompt Focus on security findings and vulnerabilities")
            return True
        
        if args[0].lower() == "reset":
            self.custom_prompt = None
            console.print("[green]Reset to default summarization prompt[/green]")
        else:
            # Join all args as the prompt
            self.custom_prompt = " ".join(args)
            console.print(f"[green]Set custom prompt: {self.custom_prompt}[/green]")
        
        return True
    
    def handle_status(self, args: Optional[List[str]] = None) -> bool:
        """Show compaction settings."""
        current_model = get_current_active_model()
        
        console.print("[bold cyan]Compaction Settings[/bold cyan]\n")
        
        # Show model info
        console.print(f"Compact Model: {self.compact_model or 'Using current model'}")
        if current_model:
            console.print(f"Current Model: {current_model.model}")
        
        # Show prompt info
        if self.custom_prompt:
            console.print(f"\nCustom Prompt: {self.custom_prompt}")
        else:
            console.print("\nCustom Prompt: Not set (using default)")
        
        # Show default prompt
        console.print("\n[dim]Default summarization prompt:[/dim]")
        console.print("[dim]You are a conversation summarizer. Your task is to create a concise summary that captures:[/dim]")
        console.print("[dim]1. The main objectives and goals discussed[/dim]")
        console.print("[dim]2. Key findings and important information discovered[/dim]")
        console.print("[dim]3. Critical tool outputs and results[/dim]")
        console.print("[dim]4. Current status and next steps[/dim]")
        console.print("[dim]5. Any flags, credentials, or important data found[/dim]")
        
        console.print("\n[yellow]Note: For memory management, use the /memory command[/yellow]")
        
        return True
    
    def _show_help_menu(self):
        """Show help menu for the compact command."""
        from rich.panel import Panel
        
        # Show current status
        current_model = get_current_active_model()
        model_info = self.compact_model or (current_model.model if current_model else "default")
        
        console.print(Panel(
            "[bold cyan]Compact Command - Memory Summarization[/bold cyan]\n\n"
            f"Current model: [green]{model_info}[/green]\n"
            f"Custom prompt: [green]{'Set' if self.custom_prompt else 'Using default'}[/green]",
            title="[bold yellow]💡 Compact Settings[/bold yellow]",
            border_style="cyan"
        ))
        
        console.print("\n[bold cyan]Available commands:[/bold cyan]")
        console.print("  [bold]/compact[/bold]                      - Summarize current conversation")
        console.print("  [bold]/compact model[/bold]                - Configure model for compaction") 
        console.print("  [bold]/compact prompt[/bold]               - Set custom summarization prompt")
        console.print("  [bold]/compact status[/bold]               - Show current settings")
        console.print("\n[bold cyan]Quick usage:[/bold cyan]")
        console.print("  [bold]/compact --model o3-mini[/bold]      - Compact with specific model")
        console.print("  [bold]/compact --prompt \"Focus on...\"[/bold] - Compact with custom prompt")
        console.print("\n[dim]Note: Compacted conversations are saved to /memory for later use[/dim]")
    
    def _ask_and_perform_compaction(self) -> bool:
        """Ask user if they want to compact and perform if confirmed."""
        from cai.sdk.agents.models.openai_chatcompletions import get_agent_message_history, get_all_agent_histories
        from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
        
        # Try to find an agent with messages
        agent_name = None
        current_agent = None
        
        # First check if there's an active agent
        current_agent = AGENT_MANAGER.get_active_agent()
        if current_agent:
            agent_name = getattr(current_agent, 'name', None)
        
        # If no active agent or no name, check all histories for one with messages
        if not agent_name:
            all_histories = get_all_agent_histories()
            for name, history in all_histories.items():
                if history and len(history) > 0:
                    agent_name = name
                    break
        
        # If still no agent, try to get from registered agents
        if not agent_name:
            registered = AGENT_MANAGER.get_registered_agents()
            if registered:
                # Get the first registered agent
                agent_name = list(registered.keys())[0]
        
        # If still no agent, try to get from environment
        if not agent_name:
            agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
            from cai.agents import get_available_agents
            agents = get_available_agents()
            if agent_type in agents:
                agent = agents[agent_type]
                agent_name = getattr(agent, "name", agent_type)
        
        # Get message count
        history = get_agent_message_history(agent_name) if agent_name else []
        msg_count = len(history)
        
        if msg_count == 0:
            console.print("\n[yellow]No conversation history to compact[/yellow]")
            return True
        
        # Ask for confirmation
        console.print(f"\n[cyan]¿Quieres resumir la conversación? ({msg_count} mensajes)[/cyan]")
        confirm = console.input("[cyan]Resumir conversación? (y/N): [/cyan]")
        
        if confirm.lower() == 'y':
            # Pass the detected agent name to _perform_compaction
            return self._perform_compaction(None, None, agent_name=agent_name)
        else:
            console.print("[dim]Compactación cancelada[/dim]")
            return True
    
    def _perform_parallel_compaction(self) -> bool:
        """Perform compaction for all parallel agents."""
        from cai.repl.commands.parallel import PARALLEL_CONFIGS
        from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
        from cai.sdk.agents.models.openai_chatcompletions import get_agent_message_history
        from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
        from cai.agents import get_available_agents
        from cai.agents.patterns import get_pattern
        
        if not PARALLEL_CONFIGS:
            console.print("[yellow]No parallel agents configured[/yellow]")
            return True
        
        console.print("[bold cyan]Compacting all parallel agents automatically...[/bold cyan]\n")
        
        success_count = 0
        total_count = 0
        
        # Process each parallel agent
        for idx, config in enumerate(PARALLEL_CONFIGS, 1):
            total_count += 1
            agent_id = config.id or f"P{idx}"
            
            # Get isolated history for this agent
            history = PARALLEL_ISOLATION.get_isolated_history(agent_id)
            if not history or len(history) == 0:
                # Also check AGENT_MANAGER for the history
                # Resolve the agent name from the config
                agent_name = None
                
                if config.agent_name.endswith("_pattern"):
                    # This is a pattern, get the entry agent name
                    pattern = get_pattern(config.agent_name)
                    if pattern and hasattr(pattern, 'entry_agent'):
                        agent_name = getattr(pattern.entry_agent, "name", None)
                else:
                    # Regular agent
                    available_agents = get_available_agents()
                    if config.agent_name in available_agents:
                        agent = available_agents[config.agent_name]
                        agent_name = getattr(agent, "name", config.agent_name)
                
                if agent_name:
                    # Try to get history from AGENT_MANAGER
                    history = get_agent_message_history(agent_name)
                
                if not history or len(history) == 0:
                    console.print(f"[yellow]{config.agent_name} [{agent_id}]: No messages to compact[/yellow]")
                    continue
            
            # Resolve the agent name for display
            display_name = config.agent_name
            if config.agent_name.endswith("_pattern"):
                pattern = get_pattern(config.agent_name)
                if pattern and hasattr(pattern, 'entry_agent'):
                    display_name = getattr(pattern.entry_agent, "name", config.agent_name)
            else:
                available_agents = get_available_agents()
                if config.agent_name in available_agents:
                    agent = available_agents[config.agent_name]
                    display_name = getattr(agent, "name", config.agent_name)
            
            console.print(f"[cyan]Compacting {display_name} [{agent_id}] ({len(history)} messages)...[/cyan]")
            
            # Create a temporary agent instance for this compaction
            # This is necessary because _perform_compaction expects an active agent
            from cai.agents import get_agent_by_name
            try:
                # Get the correct agent type name
                agent_type = config.agent_name
                
                # Create a temporary agent instance
                temp_agent = get_agent_by_name(agent_type, custom_name=display_name, agent_id=agent_id)
                
                # Set it as active temporarily
                old_active = AGENT_MANAGER.get_active_agent()
                old_active_name = AGENT_MANAGER._active_agent_name
                
                AGENT_MANAGER.set_active_agent(temp_agent, display_name)
                
                # Set the isolated history to the agent's model
                if hasattr(temp_agent, 'model') and hasattr(temp_agent.model, 'message_history'):
                    temp_agent.model.message_history.clear()
                    temp_agent.model.message_history.extend(history)
                
                # Perform compaction for this agent
                if self._perform_compaction(agent_name=display_name):
                    success_count += 1
                    console.print(f"[green]✓ {display_name} [{agent_id}] compacted successfully[/green]\n")
                    
                    # Clear the isolated history after successful compaction
                    PARALLEL_ISOLATION.replace_isolated_history(agent_id, [])
                else:
                    console.print(f"[red]✗ Failed to compact {display_name} [{agent_id}][/red]\n")
                
                # Restore the previous active agent
                if old_active:
                    AGENT_MANAGER.set_active_agent(old_active, old_active_name)
                else:
                    AGENT_MANAGER._active_agent = None
                    AGENT_MANAGER._active_agent_name = None
                    
            except Exception as e:
                console.print(f"[red]Error compacting {display_name}: {str(e)}[/red]\n")
                if os.getenv("CAI_DEBUG", "1") == "2":
                    import traceback
                    traceback.print_exc()
        
        # Summary
        console.print(f"\n[bold]Parallel compaction complete: {success_count}/{total_count} agents processed[/bold]")
        
        if success_count > 0:
            console.print("[dim]Use '/memory list' to see all saved memories[/dim]")
            console.print("[dim]All agent histories have been cleared after compaction[/dim]")
        
        return True
    
    def _perform_compaction(self, model_override: Optional[str] = None, prompt_override: Optional[str] = None, agent_name: Optional[str] = None, *args, **kwargs) -> bool:
        """Perform immediate compaction of the current conversation.
        
        Args:
            model_override: Optional model to use for this compaction
            prompt_override: Optional prompt to use for this compaction
            *args: Additional positional arguments (ignored)
            **kwargs: Additional keyword arguments (ignored)
            
        Returns:
            True if successful
        """
        from cai.repl.commands.memory import MEMORY_COMMAND_INSTANCE
        from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
        from cai.sdk.agents.models.openai_chatcompletions import (
            ACTIVE_MODEL_INSTANCES, 
            PERSISTENT_MESSAGE_HISTORIES,
            get_all_agent_histories
        )
        
        # If agent_name wasn't passed, try to detect it
        if not agent_name:
            # Get current agent
            current_agent = AGENT_MANAGER.get_active_agent()
            if current_agent:
                agent_name = getattr(current_agent, 'name', None)
            
            # If still no agent, check all histories for one with messages
            if not agent_name:
                all_histories = get_all_agent_histories()
                for name, history in all_histories.items():
                    if history and len(history) > 0:
                        agent_name = name
                        break
            
            # If still no agent, try to get from registered agents
            if not agent_name:
                registered = AGENT_MANAGER.get_registered_agents()
                if registered:
                    # Get the first registered agent
                    agent_name = list(registered.keys())[0]
            
            # If still no agent, try to get from environment
            if not agent_name:
                agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
                from cai.agents import get_available_agents
                agents = get_available_agents()
                if agent_type in agents:
                    agent = agents[agent_type]
                    agent_name = getattr(agent, "name", agent_type)
            
            if not agent_name:
                console.print("[red]Could not determine agent name[/red]")
                return False
        
        # Try to get the actual agent object if we don't have it
        current_agent = AGENT_MANAGER.get_active_agent()
        if not current_agent or getattr(current_agent, 'name', None) != agent_name:
            # The detected agent might not be the active one
            # Set it as active if possible
            from cai.agents import get_agent_by_name
            try:
                current_agent = get_agent_by_name(agent_name.lower().replace(' ', '_'))
                if current_agent:
                    AGENT_MANAGER.set_active_agent(current_agent, agent_name)
            except:
                # If we can't create the agent, continue anyway
                # The history might still be accessible
                pass
        
        # Temporarily set model/prompt if overrides provided
        original_model = self.compact_model
        original_prompt = self.custom_prompt
        
        if model_override:
            self.compact_model = model_override
            console.print(f"[dim]Using model override: {model_override}[/dim]")
        
        if prompt_override:
            self.custom_prompt = prompt_override
            console.print(f"[dim]Using custom prompt: {prompt_override[:50]}...[/dim]")
        
        try:
            # Generate memory name
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            memory_name = f"compact_{agent_name.replace(' ', '_').replace('#', '')}_{timestamp}"
            
            console.print(f"\n[cyan]Compacting conversation for {agent_name}...[/cyan]")
            
            # Use memory command's save functionality  
            # Pass the compact model if set
            if self.compact_model:
                # Temporarily override the model for this operation
                original_model = os.environ.get("CAI_MODEL", "alias0")
                os.environ["CAI_MODEL"] = self.compact_model
                try:
                    result = MEMORY_COMMAND_INSTANCE.handle_save([memory_name], preserve_history=False)
                finally:
                    os.environ["CAI_MODEL"] = original_model
            else:
                result = MEMORY_COMMAND_INSTANCE.handle_save([memory_name], preserve_history=False)
            
            if result:
                console.print(f"\n[green]✓ Conversation compacted successfully![/green]")
                console.print("[dim]The memory has been saved and applied to the agent[/dim]")
                console.print("[dim]Use '/memory list' to see all saved memories[/dim]")
                
                # IMPORTANT: Explicitly clear the history after compaction
                # The handle_save with preserve_history=False doesn't always clear properly
                console.print("\n[cyan]Clearing conversation history...[/cyan]")
                
                # Clear using AGENT_MANAGER (this uses .clear() to maintain reference)
                AGENT_MANAGER.clear_history(agent_name)
                
                # Also clear persistent history
                if agent_name in PERSISTENT_MESSAGE_HISTORIES:
                    PERSISTENT_MESSAGE_HISTORIES[agent_name].clear()
                
                # Get the current active agent and clear its model history too
                current_agent = AGENT_MANAGER.get_active_agent()
                if current_agent and hasattr(current_agent, 'model') and hasattr(current_agent.model, 'message_history'):
                    current_agent.model.message_history.clear()
                
                # Reset context usage since we cleared the history
                os.environ['CAI_CONTEXT_USAGE'] = '0.0'
                console.print("[green]✓ Conversation history cleared[/green]")
                
                # Debug: Verify histories are actually cleared
                if os.getenv("CAI_DEBUG", "1") == "2":
                    # Check AGENT_MANAGER
                    manager_history = AGENT_MANAGER.get_message_history(agent_name)
                    console.print(f"[dim]Debug: AGENT_MANAGER history length: {len(manager_history)}[/dim]")
                    
                    # Check active agent (re-fetch to ensure we have the current one)
                    current_active_agent = AGENT_MANAGER.get_active_agent()
                    if current_active_agent and hasattr(current_active_agent, 'model') and hasattr(current_active_agent.model, 'message_history'):
                        console.print(f"[dim]Debug: Active agent model history length: {len(current_active_agent.model.message_history)}[/dim]")
                
            else:
                console.print(f"[red]Failed to compact conversation[/red]")
            
            return result
            
        finally:
            # Restore original settings
            self.compact_model = original_model
            self.custom_prompt = original_prompt


# Global instance for access from other modules
COMPACT_COMMAND_INSTANCE = CompactCommand()

# Register the command
register_command(COMPACT_COMMAND_INSTANCE)


def get_compact_model() -> Optional[str]:
    """Get the configured compaction model.
    
    Returns:
        Model name if set, None to use current model
    """
    return COMPACT_COMMAND_INSTANCE.compact_model


def get_custom_prompt() -> Optional[str]:
    """Get the custom summarization prompt.
    
    Returns:
        Custom prompt if set, None to use default
    """
    return COMPACT_COMMAND_INSTANCE.custom_prompt