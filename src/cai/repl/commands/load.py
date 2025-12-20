"""
Load command for CAI REPL.

This module provides commands for loading a jsonl into
the context of the current session.
"""

import os
from typing import List, Optional

from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error

from cai.repl.commands.base import Command, register_command
from cai.repl.commands.parallel import PARALLEL_CONFIGS
from cai.sdk.agents.models.openai_chatcompletions import (
    get_agent_message_history,
    get_all_agent_histories,
)
from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
from cai.sdk.agents.run_to_jsonl import load_history_from_jsonl

console = Console()


class LoadCommand(Command):
    """Command for loading a jsonl into the context of the current session."""

    def __init__(self):
        """Initialize the load command."""
        super().__init__(
            name="/load",
            description="Merge a jsonl file into agent histories with duplicate control (uses logs/last if no file specified)",
            aliases=["/l"],
        )
        
        # Add subcommands
        self.add_subcommand("agent", "Load history into a specific agent", self.handle_agent)
        self.add_subcommand("all", "Show all available agents", self.handle_all)
        self.add_subcommand("parallel", "Load JSONL matching configured parallel agents", self.handle_parallel)
        self.add_subcommand("load-all", "Load JSONL into all parallel agents with same messages", self.handle_load_all)

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the load command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            # No arguments - load into default agent (P1)
            return self.handle_load_default()
        
        # Check if first arg is "all" (special case for showing all agents)
        if args[0].lower() == "all":
            return self.handle_all(args[1:] if len(args) > 1 else [])
        
        # Check if first arg is "agent" subcommand
        if args[0].lower() == "agent":
            return self.handle_agent(args[1:] if len(args) > 1 else [])
        
        # Check if first arg is "parallel" subcommand
        if args[0].lower() == "parallel":
            return self.handle_parallel(args[1:] if len(args) > 1 else [])
        
        # Check if first arg is "load-all" subcommand
        if args[0].lower() == "load-all":
            return self.handle_load_all(args[1:] if len(args) > 1 else [])
        
        # Check if first arg is a parallel pattern
        if args[0].startswith("parallel_") or args[0] in ["bb_triage", "red_team"]:
            from cai.agents.patterns import get_pattern
            from cai.repl.commands.parallel import PARALLEL_CONFIGS
            
            pattern = get_pattern(args[0])
            if pattern and hasattr(pattern, "configs"):
                # Clear existing configs
                PARALLEL_CONFIGS.clear()
                
                # Load pattern configs
                for idx, config in enumerate(pattern.configs, 1):
                    config.id = f"P{idx}"
                    PARALLEL_CONFIGS.append(config)
                
                # Enable parallel mode
                if len(PARALLEL_CONFIGS) >= 2:
                    os.environ["CAI_PARALLEL"] = str(len(PARALLEL_CONFIGS))
                    agent_names = [config.agent_name for config in PARALLEL_CONFIGS]
                    os.environ["CAI_PARALLEL_AGENTS"] = ",".join(agent_names)
                
                console.print(f"[green]Loaded parallel pattern: {pattern.description}[/green]")
                console.print(f"[cyan]{len(PARALLEL_CONFIGS)} agents configured[/cyan]")
                
                # Show configured agents with IDs
                for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                    model_info = f" [{config.model}]" if config.model else " [default]"
                    console.print(f"  [P{idx}] {config.agent_name}{model_info}")
                
                # Load history file if provided, or default to logs/last
                jsonl_file = args[1] if len(args) > 1 else "logs/last"
                
                # Try to load and match agent histories
                loaded = self.handle_load_pattern_from_jsonl(jsonl_file)
                if not loaded:
                    console.print(f"[yellow]No history loaded from {jsonl_file}[/yellow]")
                
                return True
            else:
                console.print(f"[red]Error: Unknown pattern '{args[0]}'[/red]")
                return False
        
        # Check if it's a file path (contains / or . or ends with .jsonl)
        if "/" in args[0] or "." in args[0] or args[0].endswith(".jsonl"):
            # It's a file path, load into default agent (P1)
            return self.handle_load_default(args[0])
        
        # Check if first arg is a numeric ID (like "14")
        if args[0].isdigit():
            # Convert to P format
            args[0] = f"P{args[0]}"
        
        # Check if first arg is an ID (P1, P2, etc.)
        if args[0].upper().startswith("P"):
            # Try to resolve ID to agent name
            from cai.repl.commands.parallel import PARALLEL_CONFIGS
            from cai.agents import get_available_agents
            
            identifier = args[0].upper()  # Normalize to uppercase
            agent_name = None
            available_agents = get_available_agents()
            
            # Import AGENT_MANAGER for single agent mode handling
            from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
            
            # Check if there are no parallel configs
            if not PARALLEL_CONFIGS:
                if identifier == "P1":
                    # P1 in single agent mode - load to the current active agent
                    current_agent = AGENT_MANAGER.get_active_agent()
                    current_agent_name = AGENT_MANAGER._active_agent_name
                    if current_agent and current_agent_name:
                        agent_name = current_agent_name
                        console.print(f"[cyan]Loading to current agent: {agent_name}[/cyan]")
                    else:
                        console.print(f"[red]Error: No active agent found[/red]")
                        return False
                else:
                    # Any other ID in single agent mode is invalid
                    console.print(f"[red]Error: No agent found with ID '{identifier}'[/red]")
                    console.print("[yellow]In single agent mode, only P1 is valid[/yellow]")
                    console.print("[dim]Use '/parallel' to configure multiple agents[/dim]")
                    return False
            else:
                # Look for matching ID in parallel configs
                for config in PARALLEL_CONFIGS:
                    if config.id and config.id.upper() == identifier:
                        if config.agent_name in available_agents:
                            agent = available_agents[config.agent_name]
                            display_name = getattr(agent, "name", config.agent_name)
                            
                            # Count how many instances of this agent type exist
                            total_count = sum(1 for c in PARALLEL_CONFIGS if c.agent_name == config.agent_name)
                            
                            # Count instances to find the right one
                            instance_num = 0
                            for c in PARALLEL_CONFIGS:
                                if c.agent_name == config.agent_name:
                                    instance_num += 1
                                    if c.id == config.id:
                                        break
                            
                            # Add instance number if there are duplicates
                            if total_count > 1:
                                agent_name = f"{display_name} #{instance_num}"
                            else:
                                agent_name = display_name
                            break
            
            if agent_name:
                # Replace ID with resolved agent name and process
                args[0] = agent_name
                return self.handle_load_to_agent(args)
            else:
                console.print(f"[red]Error: No agent found with ID '{identifier}'[/red]")
                console.print("[dim]Use '/parallel' to see configured agents with IDs[/dim]")
                return False
        
        # Otherwise, treat first arg as agent name and rest as file path
        return self.handle_load_to_agent(args)

    def handle_load_pattern_from_jsonl(self, jsonl_file: Optional[str] = None) -> bool:
        """Load a JSONL file and match agent messages to configured parallel agents.
        
        Args:
            jsonl_file: Optional jsonl file path, defaults to "logs/last"
            
        Returns:
            bool: True if successful
        """
        from cai.repl.commands.parallel import PARALLEL_CONFIGS
        import json
        
        if not PARALLEL_CONFIGS:
            # No parallel configs, fallback to default behavior
            return self.handle_load_default(jsonl_file)
        
        if not jsonl_file:
            jsonl_file = "logs/last"
            
        try:
            # First, try to parse agent names from JSONL if file exists
            agent_conversations = {}
            
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    current_agent = None
                    current_messages = []
                    
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            
                            # Check if this is a completion record with agent_name
                            if "agent_name" in record and record.get("object") == "chat.completion":
                                # Save previous agent's messages if any
                                if current_agent and current_messages:
                                    if current_agent not in agent_conversations:
                                        agent_conversations[current_agent] = []
                                    agent_conversations[current_agent].extend(current_messages)
                                
                                # Start tracking new agent
                                current_agent = record["agent_name"]
                                current_messages = []
                            
                            # Check if this is a request record with messages
                            elif "model" in record and "messages" in record and isinstance(record["messages"], list):
                                # These messages belong to the current agent
                                for msg in record["messages"]:
                                    if msg.get("role") != "system":  # Skip system messages
                                        current_messages.append(msg)
                        
                        except json.JSONDecodeError:
                            continue
                
                # Save last agent's messages
                if current_agent and current_messages:
                    if current_agent not in agent_conversations:
                        agent_conversations[current_agent] = []
                    agent_conversations[current_agent].extend(current_messages)
            except FileNotFoundError:
                # File doesn't exist, will use traditional parsing below
                pass
            
            # Also load traditional messages for backward compatibility
            messages = load_history_from_jsonl(jsonl_file)
            console.print(f"[green]Loaded {len(messages)} messages from {jsonl_file}[/green]")
            
            # Debug: Show what agent names were found
            if agent_conversations:
                console.print("[dim]Found agent conversations:[/dim]")
                for agent_name, msgs in agent_conversations.items():
                    console.print(f"[dim]  - {agent_name}: {len(msgs)} messages[/dim]")
            
            # If we didn't find agent names in completion records, try traditional parsing
            if not agent_conversations:
                agent_messages = {}
                current_agent = None
                
                for msg in messages:
                    # Check multiple ways agents can be identified
                    # 1. Direct "name" field in assistant messages
                    if msg.get("role") == "assistant" and "name" in msg:
                        current_agent = msg["name"]
                    # 2. "sender" field (used in multi-agent logs)
                    elif "sender" in msg:
                        current_agent = msg["sender"]
                    # 3. Look in nested message structure for agent_name
                    elif isinstance(msg, dict) and "agent_name" in msg:
                        current_agent = msg["agent_name"]
                    
                    # Initialize agent message list if needed
                    if current_agent and current_agent not in agent_messages:
                        agent_messages[current_agent] = []
                    
                    # Add message to current agent's list
                    if current_agent:
                        agent_messages[current_agent].append(msg)
                
                # Use traditional parsing result
                agent_conversations = agent_messages
                    
            # Match configured agents with loaded messages
            loaded_count = 0
            from cai.agents import get_available_agents
            agents = get_available_agents()
            
            # Count instances of each agent type
            agent_counts = {}
            for config in PARALLEL_CONFIGS:
                agent_counts[config.agent_name] = agent_counts.get(config.agent_name, 0) + 1
            
            # Track current instance for numbering
            agent_instances = {}
            
            for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                # Check if config.agent_name is a pattern name
                if config.agent_name.endswith("_pattern"):
                    # Try to get the pattern
                    from cai.agents.patterns import get_pattern
                    pattern = get_pattern(config.agent_name)
                    if pattern and hasattr(pattern, 'entry_agent'):
                        # For swarm patterns, use the entry agent
                        agent = pattern.entry_agent
                        agent_display_name = getattr(agent, "name", config.agent_name)
                    else:
                        # Skip if pattern not found
                        console.print(f"[yellow]Warning: Pattern '{config.agent_name}' not found[/yellow]")
                        continue
                elif config.agent_name in agents:
                    agent = agents[config.agent_name]
                    agent_display_name = getattr(agent, "name", config.agent_name)
                else:
                    # Skip if agent not found
                    console.print(f"[yellow]Warning: Agent '{config.agent_name}' not found[/yellow]")
                    continue
                    
                # Determine the instance name
                if agent_counts[config.agent_name] > 1:
                    if config.agent_name not in agent_instances:
                        agent_instances[config.agent_name] = 0
                    agent_instances[config.agent_name] += 1
                    instance_name = f"{agent_display_name} #{agent_instances[config.agent_name]}"
                else:
                    instance_name = agent_display_name
                    
                    # Look for matching messages in various formats
                    possible_names = [
                        instance_name,
                        agent_display_name,
                        f"{agent_display_name} #1",
                        f"{agent_display_name} #2",
                        f"{agent_display_name} #3",
                        config.agent_name,
                        # Also check without spaces
                        agent_display_name.replace(" ", ""),
                        config.agent_name.replace("_agent", ""),
                        config.agent_name.replace("_", " ").title(),
                        # Add pattern-specific names
                        "Red team manager",
                        "Bug bounty Triage Agent",
                        "ThoughtAgent",
                        "Retester Agent",
                    ]
                    
                    # Find the longest matching history
                    best_match = None
                    best_count = 0
                    
                    for name in possible_names:
                        if name in agent_conversations and len(agent_conversations[name]) > best_count:
                            best_match = name
                            best_count = len(agent_conversations[name])
                    
                    if best_match:
                        # Load these messages into the agent's history with the correct instance name
                        # CRITICAL: We need to get the actual model instance to add messages properly
                        # Using get_agent_message_history() and appending won't work as it returns a copy
                        from cai.sdk.agents.models.openai_chatcompletions import ACTIVE_MODEL_INSTANCES
                        
                        # Find the matching model instance
                        model_instance = None
                        for (name, inst_id), model_ref in ACTIVE_MODEL_INSTANCES.items():
                            if name == instance_name:
                                model = model_ref() if model_ref else None
                                if model:
                                    model_instance = model
                                    break
                        
                        # Check if we're in parallel mode with isolation
                        from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
                        
                        
                        # Check if we should be in parallel mode based on configs
                        if len(PARALLEL_CONFIGS) >= 2:
                            # Ensure parallel mode is enabled
                            PARALLEL_ISOLATION._parallel_mode = True
                        
                        if PARALLEL_ISOLATION.is_parallel_mode():
                            # Update the isolated history instead of the main history
                            agent_id = config.id or f"P{idx}"
                            # Replace the entire isolated history with the loaded messages
                            PARALLEL_ISOLATION.replace_isolated_history(agent_id, agent_conversations[best_match])
                            
                            # Verify it was stored
                            test_history = PARALLEL_ISOLATION.get_isolated_history(agent_id)
                            
                            # Also sync with AGENT_MANAGER for consistency
                            # Don't use set_message_history or any method that might register the agent
                            AGENT_MANAGER._message_history[instance_name] = list(agent_conversations[best_match])
                            
                            # Force sync the isolated histories back to AGENT_MANAGER for display
                            # This ensures /history and /graph see the loaded data
                            PARALLEL_ISOLATION.sync_with_agent_manager()
                        else:
                            # Normal mode - update as before
                            if model_instance:
                                # Add messages directly to the model's message history
                                for msg in agent_conversations[best_match]:
                                    model_instance.add_to_message_history(msg)
                            else:
                                # No active instance, store in persistent history
                                from cai.sdk.agents.models.openai_chatcompletions import PERSISTENT_MESSAGE_HISTORIES
                                PERSISTENT_MESSAGE_HISTORIES[instance_name] = list(agent_conversations[best_match])
                                
                                # CRITICAL: Also update AGENT_MANAGER to ensure consistency
                                # This ensures the history is available when the agent is created
                                # Don't use set_message_history or any method that might register the agent
                                AGENT_MANAGER._message_history[instance_name] = list(agent_conversations[best_match])
                        
                        console.print(f"[green]Loaded {best_count} messages into '{instance_name}' [P{idx}][/green]")
                        loaded_count += 1
                        
            if loaded_count > 0:
                console.print(f"[bold green]Successfully loaded history for {loaded_count} agents[/bold green]")
                
                # Final sync to ensure all histories are visible
                if PARALLEL_ISOLATION.is_parallel_mode():
                    console.print("[dim]Syncing loaded histories...[/dim]")
                    PARALLEL_ISOLATION.sync_with_agent_manager()
            else:
                console.print("[yellow]No matching agent histories found in JSONL[/yellow]")
                
                # If no agents were found, provide helpful information
                if not agent_conversations:
                    console.print("[dim]The JSONL file appears to be empty or does not contain agent messages[/dim]")
                    console.print("[dim]Agent names should be in 'name', 'sender', or 'agent_name' fields[/dim]")
                    return False
                else:
                    console.print(f"\n[dim]Found agents in JSONL:[/dim]")
                    for agent, messages in sorted(agent_conversations.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                        console.print(f"  • {agent} ({len(messages)} messages)")
                    if len(agent_conversations) > 5:
                        console.print(f"  ... and {len(agent_conversations) - 5} more")
                    
                    console.print(f"\n[dim]Configured agents expecting history:[/dim]")
                    for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                        if config.agent_name in agents:
                            agent = agents[config.agent_name]
                            display_name = getattr(agent, "name", config.agent_name)
                            console.print(f"  • [P{idx}] {display_name}")
                    
                    console.print("\n[dim]Tip: Agent names in JSONL must match the configured agent names[/dim]")
                
            return True
            
        except Exception as e:
            console.print(f"[red]Error loading pattern from JSONL: {str(e)}[/red]")
            return False

    def handle_load_default(self, jsonl_file: Optional[str] = None) -> bool:
        """Load a jsonl and merge it into all active agents.

        Args:
            jsonl_file: Optional jsonl file path, defaults to "logs/last"

        Returns:
            bool: True if the jsonl was loaded successfully
        """
        if not jsonl_file:
            jsonl_file = "logs/last"

        try:
            # Try to load the jsonl file
            try:
                # fetch messages from JSONL file
                messages = load_history_from_jsonl(jsonl_file)
                console.print(f"[green]Jsonl file {jsonl_file} loaded[/green]")
            except BaseException:  # pylint: disable=broad-exception-caught
                console.print(f"[red]Error: Failed to load jsonl file {jsonl_file}[/red]")
                return False

            # Check if there are any messages to load
            if not messages:
                console.print(f"[yellow]No messages found in {jsonl_file}[/yellow]")
                return True

            # Get the current active agent from AGENT_MANAGER
            from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
            
            current_agent = AGENT_MANAGER.get_active_agent()
            current_agent_name = AGENT_MANAGER._active_agent_name
            
            if not current_agent or not current_agent_name:
                console.print("[red]Error: No active agent found[/red]")
                console.print("[yellow]Please select an agent first with '/agent <name>'[/yellow]")
                return False
            
            # Get all active agents to merge into (including current agent)
            all_histories = get_all_agent_histories()
            
            # If no histories exist yet, create one for the current agent
            if not all_histories:
                all_histories = {f"{current_agent_name} [P1]": []}
            
            console.print(f"[cyan]Merging {len(messages)} messages into {len(all_histories)} active agent(s)...[/cyan]")
            
            # Merge messages into all active agents with duplicate control
            from cai.sdk.agents.models.openai_chatcompletions import ACTIVE_MODEL_INSTANCES, PERSISTENT_MESSAGE_HISTORIES
            from cai.repl.commands.parallel import ParallelCommand
            
            # Create a ParallelCommand instance to use its merge methods
            parallel_cmd = ParallelCommand()
            
            # Merge into each active agent
            agents_updated = []
            for agent_name, original_history in all_histories.items():
                # Build a set of message signatures from original history for duplicate detection
                original_signatures = set()
                for msg in original_history:
                    sig = parallel_cmd._get_message_signature(msg)
                    if sig:
                        original_signatures.add(sig)
                
                # Filter out duplicates from loaded messages
                unique_messages = []
                for msg in messages:
                    sig = parallel_cmd._get_message_signature(msg)
                    if sig and sig not in original_signatures:
                        unique_messages.append(msg)
                        original_signatures.add(sig)
                
                if not unique_messages:
                    console.print(f"[dim]No new messages to add to {agent_name}[/dim]")
                    continue
                
                # The final history is original + unique messages
                final_history = original_history + unique_messages
                
                # Extract base agent name if it has [ID] suffix
                base_name = agent_name
                agent_id = None
                if "[" in agent_name and agent_name.endswith("]"):
                    base_name = agent_name.rsplit("[", 1)[0].strip()
                    agent_id = agent_name.split("[")[1].rstrip("]")
                
                # Find the matching model instance
                model_instance = None
                for (model_agent_name, inst_id), model_ref in ACTIVE_MODEL_INSTANCES.items():
                    if model_agent_name == base_name or model_agent_name == agent_name:
                        model = model_ref() if callable(model_ref) else model_ref
                        if model:
                            model_instance = model
                            break
                
                if model_instance:
                    # Update existing model's history
                    model_instance.message_history.clear()
                    # Reset context usage since we're rebuilding history
                    os.environ['CAI_CONTEXT_USAGE'] = '0.0'
                    for msg in final_history:
                        model_instance.add_to_message_history(msg)
                    console.print(f"[green]✓ Updated {agent_name} - added {len(unique_messages)} new messages[/green]")
                else:
                    # No active instance, store in persistent history
                    PERSISTENT_MESSAGE_HISTORIES[agent_name] = final_history
                    console.print(f"[green]✓ Updated {agent_name} (persistent) - added {len(unique_messages)} new messages[/green]")
                
                # Also update AGENT_MANAGER - using _message_history directly to avoid registration
                AGENT_MANAGER._message_history[agent_name] = final_history
                
                # Update PARALLEL_ISOLATION if needed
                if agent_id:
                    from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
                    if PARALLEL_ISOLATION.get_isolated_history(agent_id) is not None:
                        PARALLEL_ISOLATION.replace_isolated_history(agent_id, final_history)
                
                agents_updated.append(agent_name)
            
            console.print(f"\n[bold green]Successfully merged {len(messages)} messages into {len(agents_updated)} agent(s)[/bold green]")
            console.print("[dim]All agents now have the combined history with duplicate control[/dim]")
            
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            console.print(f"[red]Error loading jsonl file: {str(e)}[/red]")
            return False
    
    def handle_load_to_agent(self, args: List[str]) -> bool:
        """Load a jsonl file into a specific agent by parsing agent name from args.
        
        Args:
            args: List where first elements form agent name, last is optional file
            
        Returns:
            bool: True if successful
        """
        if len(args) == 1:
            # Only agent name provided
            agent_name = args[0]
            jsonl_file = "logs/last"
        else:
            # Find where the file path starts
            file_idx = -1
            for i, arg in enumerate(args[1:], 1):  # Start from second arg
                if "/" in arg or "." in arg or arg.endswith(".jsonl"):
                    file_idx = i
                    break
            
            if file_idx == -1:
                # No clear file path indicator, treat last arg as file if exactly 2 args
                if len(args) == 2:
                    agent_name = args[0]
                    jsonl_file = args[1]
                else:
                    # Multiple args, all form agent name
                    agent_name = " ".join(args)
                    jsonl_file = "logs/last"
            else:
                # Everything before file path is agent name
                agent_name = " ".join(args[:file_idx])
                jsonl_file = args[file_idx]
        
        return self._load_to_agent(agent_name, jsonl_file)
    
    def handle_agent(self, args: Optional[List[str]] = None) -> bool:
        """Load a jsonl file into a specific agent's history using 'agent' subcommand.
        
        Args:
            args: List containing agent name and optional jsonl file path
            
        Returns:
            bool: True if successful
        """
        if not args:
            console.print("[red]Error: Agent name required[/red]")
            console.print("Usage: /load agent <agent_name> [jsonl_file]")
            console.print("Example: /load agent red_teamer")
            console.print('Example: /load agent "Bug Bounter #1" logs/last')
            return False
        
        # Parse using same logic as handle_load_to_agent
        return self.handle_load_to_agent(args)
    
    def _load_to_agent(self, agent_name: str, jsonl_file: str) -> bool:
        """Common method to merge a jsonl file into a specific agent's history.
        
        Args:
            agent_name: Name of the agent
            jsonl_file: Path to jsonl file
            
        Returns:
            bool: True if successful
        """
        try:
            # Load the jsonl file
            try:
                messages = load_history_from_jsonl(jsonl_file)
                console.print(f"[green]Jsonl file {jsonl_file} loaded[/green]")
            except FileNotFoundError:
                console.print(f"[red]Error: File '{jsonl_file}' not found[/red]")
                return False
            except Exception as e:
                console.print(f"[red]Error loading history from {jsonl_file}: {e}[/red]")
                return False
            
            # Check if there are any messages to load
            if not messages:
                console.print(f"[yellow]No messages found in {jsonl_file}[/yellow]")
                console.print("[dim]The file may be empty or contain only session events[/dim]")
                return True
            
            # If agent_name is an ID (P1, P2, etc.), resolve it to actual agent name
            from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
            resolved_agent_name = agent_name
            
            if agent_name.upper().startswith("P") and len(agent_name) >= 2 and agent_name[1:].isdigit():
                # This is an ID, resolve it
                agent_id = agent_name.upper()
                resolved_name = AGENT_MANAGER.get_agent_by_id(agent_id)
                if resolved_name:
                    resolved_agent_name = resolved_name
                    console.print(f"[cyan]Resolved {agent_id} to {resolved_agent_name}[/cyan]")
                else:
                    # ID not found, don't create agent
                    console.print(f"[red]Error: No agent found with ID '{agent_id}'[/red]")
                    console.print("[yellow]Available agents:[/yellow]")
                    all_histories = get_all_agent_histories()
                    for agent in sorted(all_histories.keys()):
                        console.print(f"  - {agent}")
                    return False
            
            # Merge messages into the specified agent's history with duplicate control
            from cai.sdk.agents.models.openai_chatcompletions import ACTIVE_MODEL_INSTANCES, PERSISTENT_MESSAGE_HISTORIES
            from cai.repl.commands.parallel import ParallelCommand
            
            # Get the current history for this agent
            current_history = AGENT_MANAGER.get_message_history(resolved_agent_name) or []
            
            # Create a ParallelCommand instance to use its merge methods
            parallel_cmd = ParallelCommand()
            
            # Build a set of message signatures from current history for duplicate detection
            original_signatures = set()
            for msg in current_history:
                sig = parallel_cmd._get_message_signature(msg)
                if sig:
                    original_signatures.add(sig)
            
            # Filter out duplicates from loaded messages
            unique_messages = []
            for msg in messages:
                sig = parallel_cmd._get_message_signature(msg)
                if sig and sig not in original_signatures:
                    unique_messages.append(msg)
                    original_signatures.add(sig)
            
            if not unique_messages:
                console.print(f"[yellow]No new messages to add - all {len(messages)} messages already exist in history[/yellow]")
                return True
            
            # The final history is original + unique messages
            final_history = current_history + unique_messages
            
            # Find the matching model instance
            model_instance = None
            for (name, inst_id), model_ref in ACTIVE_MODEL_INSTANCES.items():
                if name == resolved_agent_name:
                    model = model_ref() if model_ref else None
                    if model:
                        model_instance = model
                        break
            
            if model_instance:
                # Update existing model's history
                model_instance.message_history.clear()
                # Reset context usage since we're rebuilding history
                os.environ['CAI_CONTEXT_USAGE'] = '0.0'
                for msg in final_history:
                    model_instance.add_to_message_history(msg)
            else:
                # No active instance, store in persistent history
                PERSISTENT_MESSAGE_HISTORIES[resolved_agent_name] = final_history
            
            # Also update AGENT_MANAGER's history to ensure consistency
            AGENT_MANAGER._message_history[resolved_agent_name] = final_history
            
            # Don't register the agent - just update history
            # The agent should already exist if we're loading history into it
            # This prevents creating empty agents when loading
            
            console.print(f"[green]Merged {len(unique_messages)} new messages into agent '{resolved_agent_name}'[/green]")
            console.print(f"[dim]Skipped {len(messages) - len(unique_messages)} duplicate messages[/dim]")
            
            # Show current message count for this agent
            total_messages = len(final_history)
            console.print(f"[dim]Agent '{resolved_agent_name}' now has {total_messages} messages in history[/dim]")
            
            return True
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            console.print(f"[red]Error loading jsonl file: {str(e)}[/red]")
            return False
    
    def handle_parallel(self, args: Optional[List[str]] = None) -> bool:
        """Load a JSONL file matching messages to configured parallel agents.
        
        Args:
            args: Optional list containing jsonl file path
            
        Returns:
            bool: True if successful
        """
        # Get jsonl file from args or use default
        jsonl_file = args[0] if args else "logs/last"
        
        # Call the pattern loading method
        return self.handle_load_pattern_from_jsonl(jsonl_file)
    
    def handle_all(self, args: Optional[List[str]] = None) -> bool:
        """Show all available agents that can have history loaded.
        
        Returns:
            bool: True if successful
        """
        all_histories = get_all_agent_histories()
        
        # Also include agents from PARALLEL_CONFIGS that might not have history yet
        from cai.repl.commands.parallel import PARALLEL_CONFIGS
        from cai.agents import get_available_agents
        
        configured_agents = set()
        if PARALLEL_CONFIGS:
            available_agents = get_available_agents()
            for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                if config.agent_name in available_agents:
                    agent = available_agents[config.agent_name]
                    display_name = getattr(agent, "name", config.agent_name)
                    
                    # Count instances to get the right name
                    instance_count = sum(1 for c in PARALLEL_CONFIGS[:idx] if c.agent_name == config.agent_name)
                    if instance_count > 1:
                        display_name = f"{display_name} #{instance_count}"
                    
                    configured_agents.add(display_name)
        
        # Combine histories and configured agents
        all_agents = set(all_histories.keys()) | configured_agents
        
        if not all_agents:
            console.print("[yellow]No agents have been initialized or configured yet[/yellow]")
            console.print("[dim]Agents are created when they are first used in a conversation[/dim]")
            console.print("[dim]Or configured using '/parallel add <agent>'[/dim]")
            return True
        
        # Get agent IDs mapping from AGENT_MANAGER
        agent_ids = {}
        for agent_name, history in all_histories.items():
            # Extract ID from display format "Agent Name [ID]"
            if '[' in agent_name and ']' in agent_name:
                id_part = agent_name[agent_name.rindex('[') + 1:agent_name.rindex(']')]
                name_part = agent_name[:agent_name.rindex('[')].strip()
                agent_ids[name_part] = id_part
            
        # Also add configured but inactive agents from PARALLEL_CONFIGS
        if PARALLEL_CONFIGS:
            available_agents = get_available_agents()
            for config in PARALLEL_CONFIGS:
                if config.id:
                    agent_ids[config.agent_name] = config.id
        
        # Create a table showing all agents
        table = Table(title="Available Agents for Loading History", show_header=True, header_style="bold yellow")
        table.add_column("ID", style="magenta", width=4)
        table.add_column("Agent Name", style="cyan")
        table.add_column("Current Messages", style="green", justify="right")
        table.add_column("Message Types", style="magenta")
        table.add_column("Status", style="yellow")
        
        for agent_name in sorted(all_agents):
            history = all_histories.get(agent_name, [])
            msg_count = len(history)
            
            # Count message types if history exists
            if history:
                role_counts = {}
                for msg in history:
                    role = msg.get("role", "unknown")
                    role_counts[role] = role_counts.get(role, 0) + 1
                
                # Format role counts
                role_str = ", ".join([f"{role}: {count}" for role, count in sorted(role_counts.items())])
                status = "Active"
            else:
                role_str = "No messages"
                status = "Configured" if agent_name in configured_agents else "Empty"
            
            # Get ID for this agent
            id_str = agent_ids.get(agent_name, "-")
            
            table.add_row(id_str, agent_name, str(msg_count), role_str, status)
        
        console.print(table)
        console.print("\n[dim]Usage: /load agent <agent_name> [jsonl_file][/dim]")
        console.print("[dim]       /load <ID> [jsonl_file][/dim]")
        console.print("[dim]       /load load-all [jsonl_file] - Load same messages to all parallel agents[/dim]")
        console.print("[dim]Example: /load agent red_teamer logs/session_20240101.jsonl[/dim]")
        console.print('[dim]Example: /load agent "Bug Bounter #1"[/dim]')
        console.print("[dim]Example: /load P2 logs/last[/dim]")
        console.print("[dim]Example: /load load-all logs/session.jsonl[/dim]")
        
        # IDs are now shown in the table above
        
        return True
    
    def handle_load_all(self, args: Optional[List[str]] = None) -> bool:
        """Load the same JSONL messages into all configured parallel agents.
        
        Args:
            args: Optional list containing jsonl file path
            
        Returns:
            bool: True if successful
        """
        # Get jsonl file from args or use default
        jsonl_file = args[0] if args else "logs/last"
        
        # Check if there are parallel configs
        if not PARALLEL_CONFIGS:
            console.print("[yellow]No parallel agents configured[/yellow]")
            console.print("[dim]Use '/parallel add <agent>' to configure agents first[/dim]")
            return False
        
        try:
            # Load messages from JSONL file
            try:
                messages = load_history_from_jsonl(jsonl_file)
                console.print(f"[green]Loaded {len(messages)} messages from {jsonl_file}[/green]")
            except FileNotFoundError:
                console.print(f"[red]Error: File '{jsonl_file}' not found[/red]")
                return False
            except Exception as e:
                console.print(f"[red]Error loading history from {jsonl_file}: {e}[/red]")
                return False
            
            if not messages:
                console.print(f"[yellow]No messages found in {jsonl_file}[/yellow]")
                return True
            
            # Load the same messages into each parallel agent
            from cai.agents import get_available_agents
            from cai.sdk.agents.models.openai_chatcompletions import ACTIVE_MODEL_INSTANCES, PERSISTENT_MESSAGE_HISTORIES
            from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
            
            available_agents = get_available_agents()
            loaded_agents = []
            
            # Count instances of each agent type for proper naming
            agent_counts = {}
            for config in PARALLEL_CONFIGS:
                agent_counts[config.agent_name] = agent_counts.get(config.agent_name, 0) + 1
            
            agent_instances = {}
            
            for idx, config in enumerate(PARALLEL_CONFIGS, 1):
                if config.agent_name in available_agents:
                    agent = available_agents[config.agent_name]
                    display_name = getattr(agent, "name", config.agent_name)
                    
                    # Add instance number if there are duplicates
                    if agent_counts[config.agent_name] > 1:
                        if config.agent_name not in agent_instances:
                            agent_instances[config.agent_name] = 0
                        agent_instances[config.agent_name] += 1
                        instance_name = f"{display_name} #{agent_instances[config.agent_name]}"
                    else:
                        instance_name = display_name
                    
                    agent_id = config.id or f"P{idx}"
                    
                    # Check if we're in parallel mode with isolation
                    if PARALLEL_ISOLATION.is_parallel_mode():
                        # Replace the isolated history with the loaded messages
                        PARALLEL_ISOLATION.replace_isolated_history(agent_id, messages[:])
                        
                        # Also sync with AGENT_MANAGER for consistency
                        AGENT_MANAGER._message_history[instance_name] = messages[:]
                    else:
                        # Find the matching model instance
                        model_instance = None
                        for (name, inst_id), model_ref in ACTIVE_MODEL_INSTANCES.items():
                            if name == instance_name:
                                model = model_ref() if model_ref else None
                                if model:
                                    model_instance = model
                                    break
                        
                        if model_instance:
                            # Clear existing messages and add new ones
                            model_instance.message_history.clear()
                            os.environ['CAI_CONTEXT_USAGE'] = '0.0'
                            for message in messages:
                                model_instance.add_to_message_history(message)
                        else:
                            # No active instance, store in persistent history
                            PERSISTENT_MESSAGE_HISTORIES[instance_name] = messages[:]
                            # Also update AGENT_MANAGER
                            AGENT_MANAGER._message_history[instance_name] = messages[:]
                    
                    loaded_agents.append(f"{instance_name} [{agent_id}]")
                    console.print(f"[green]✓ Loaded into {instance_name} [{agent_id}][/green]")
            
            console.print(f"\n[bold green]Successfully loaded {len(messages)} messages into {len(loaded_agents)} agents[/bold green]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error loading jsonl file: {str(e)}[/red]")
            return False


# Register the command
register_command(LoadCommand())
