"""
Memory command for CAI REPL.
Manages memory storage in .cai/memory for persistent context.
"""

from typing import List, Optional, Dict, Any
import os
import asyncio
import json
import datetime
import tempfile
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from cai.repl.commands.base import Command, register_command
from cai.sdk.agents.models.openai_chatcompletions import (
    get_all_agent_histories, 
    get_agent_message_history,
    OpenAIChatCompletionsModel,
    get_current_active_model,
    ACTIVE_MODEL_INSTANCES,
    PERSISTENT_MESSAGE_HISTORIES
)
from cai.sdk.agents import Agent, Runner
from cai.repl.commands.parallel import PARALLEL_CONFIGS
from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
from openai import AsyncOpenAI

# Import get_compact_model function - imported later to avoid circular import
def get_compact_model():
    try:
        from cai.repl.commands.compact import get_compact_model as _get_compact_model
        return _get_compact_model()
    except ImportError:
        return None

console = Console()

# Memory directory path - use home directory for cross-platform compatibility
MEMORY_DIR = Path.home() / ".cai" / "memory"
MEMORY_INDEX_FILE = MEMORY_DIR / "index.json"

# Global storage for compacted summaries (deprecated - use file storage)
# Now supports multiple memories per agent
COMPACTED_SUMMARIES: Dict[str, List[str]] = {}

# Global storage for memory ID mappings per agent
# Now supports multiple memory IDs per agent
APPLIED_MEMORY_IDS: Dict[str, List[str]] = {}


class MemoryCommand(Command):
    """Command for managing memory storage and application."""
    
    def __init__(self):
        """Initialize the memory command."""
        super().__init__(
            name="/memory",
            description="Manage memory storage for agents",
            aliases=["/mem"]
        )
        
        # Add subcommands
        self.add_subcommand("list", "List all stored memories", self.handle_list)
        self.add_subcommand("save", "Save current agent history as memory", self.handle_save)
        self.add_subcommand("apply", "Apply a memory to an agent", self.handle_apply)
        self.add_subcommand("show", "Show memory content", self.handle_show)
        self.add_subcommand("delete", "Delete a stored memory", self.handle_delete)
        self.add_subcommand("merge", "Merge multiple memories into one", self.handle_merge)
        self.add_subcommand("status", "Show memory status", self.handle_status)
        self.add_subcommand("compact", "Compact and save agent history", self.handle_compact)
        self.add_subcommand("remove", "Remove a specific memory from an agent", self.handle_remove)
        self.add_subcommand("clear", "Clear all memories from an agent", self.handle_clear)
        self.add_subcommand("list-applied", "Show which memories are applied to an agent", self.handle_list_applied)
        
# Remove local compact_model since we'll use the one from compact command
        
        # Ensure memory directory exists
        self._ensure_memory_dir()
        
    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the memory command."""
        if not args:
            # Show control panel
            return self.handle_control_panel()
            
        # Check if first arg is a subcommand
        subcommand = args[0].lower()
        if subcommand in self.subcommands:
            handler = self.subcommands[subcommand]["handler"]
            return handler(args[1:] if len(args) > 1 else [])
            
        # Check if it's a memory ID (M001, M002, etc.) - if so, show the memory
        first_arg = args[0]
        if first_arg.upper().startswith("M") and len(first_arg) >= 4 and first_arg[1:].isdigit():
            return self.handle_show(args)
            
        # Otherwise show help
        console.print("[yellow]Unknown subcommand. Available commands:[/yellow]")
        console.print("[dim]  • /memory list                - List all stored memories[/dim]")
        console.print("[dim]  • /memory save                - Save current agent history as memory[/dim]")
        console.print("[dim]  • /memory apply               - Apply a memory to an agent[/dim]")
        console.print("[dim]  • /memory show                - Show memory content[/dim]")
        console.print("[dim]  • /memory delete              - Delete a stored memory[/dim]")
        console.print("[dim]  • /memory merge               - Merge multiple memories into one[/dim]")
        console.print("[dim]  • /memory status              - Show memory status[/dim]")
        console.print("[dim]  • /memory compact             - Compact and save agent history[/dim]")
        console.print("[dim]  • /memory remove              - Remove a specific memory from an agent[/dim]")
        console.print("[dim]  • /memory clear               - Clear all memories from an agent[/dim]")
        console.print("[dim]  • /memory list-applied        - Show which memories are applied to an agent[/dim]")
        return True
    
    def _ensure_memory_dir(self):
        """Ensure the memory directory exists."""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        
        # Initialize index file if it doesn't exist
        if not MEMORY_INDEX_FILE.exists():
            self._initialize_index()
    
    def _get_memory_id_by_filename(self, filename: str) -> Optional[str]:
        """Get the memory ID for a given filename."""
        index = self._load_index()
        for mem_id, mem_file in index.get("mappings", {}).items():
            if mem_file == filename:
                return mem_id
        return None
    
    def _get_memory_path(self, name_or_id: str) -> Path:
        """Get the path for a memory file, resolving ID if necessary."""
        # Check if it's an ID (M001, M002, etc.)
        if name_or_id.upper().startswith('M') and len(name_or_id) >= 4 and name_or_id[1:].isdigit():
            # Try to resolve ID to filename
            index = self._load_index()
            if name_or_id.upper() in index.get('mappings', {}):
                name = index['mappings'][name_or_id.upper()]
            else:
                raise ValueError(f"Memory ID '{name_or_id}' not found")
        else:
            name = name_or_id
            if not name.endswith('.md'):
                name += '.md'
        return MEMORY_DIR / name
    
    def _resolve_agent_name(self, identifier: str) -> Optional[str]:
        """Resolve an agent identifier (name or ID) to the actual agent name."""
        # Check if it's an ID (P1, P2, etc.)
        if identifier.upper().startswith("P") and len(identifier) >= 2 and identifier[1:].isdigit():
            agent_id = identifier.upper()
            
            # First check parallel configs if they exist - they are the authoritative source
            if PARALLEL_CONFIGS:
                from cai.agents import get_available_agents
                available_agents = get_available_agents()
                
                for config in PARALLEL_CONFIGS:
                    if config.id and config.id.upper() == agent_id:
                        # Special handling for patterns
                        if config.agent_name.endswith("_pattern"):
                            # For patterns, we need to get the actual entry agent
                            from cai.agents.patterns import get_pattern
                            pattern = get_pattern(config.agent_name)
                            if pattern:
                                if hasattr(pattern, 'entry_agent'):
                                    # For swarm patterns like red_team_pattern
                                    agent = pattern.entry_agent
                                    display_name = getattr(agent, "name", config.agent_name)
                                elif hasattr(pattern, 'name'):
                                    # For the pattern itself
                                    display_name = getattr(pattern, "name", config.agent_name)
                                else:
                                    display_name = config.agent_name
                            else:
                                display_name = config.agent_name
                        elif config.agent_name in available_agents:
                            agent = available_agents[config.agent_name]
                            display_name = getattr(agent, "name", config.agent_name)
                        else:
                            display_name = config.agent_name
                        
                        # Count instances for proper naming
                        total_count = sum(1 for c in PARALLEL_CONFIGS if c.agent_name == config.agent_name)
                        if total_count > 1:
                            # Find instance number
                            instance_num = 0
                            for c in PARALLEL_CONFIGS:
                                if c.agent_name == config.agent_name:
                                    instance_num += 1
                                    if c.id == config.id:
                                        break
                            return f"{display_name} #{instance_num}"
                        else:
                            return display_name
            
            # Fall back to AGENT_MANAGER if no parallel configs or not found
            agent_name = AGENT_MANAGER.get_agent_by_id(agent_id)
            if agent_name:
                return agent_name
        
        # Otherwise it's a direct agent name
        return identifier
    
    def _initialize_index(self):
        """Initialize the memory index file with existing memories."""
        index = {
            "next_id": 1,
            "mappings": {}
        }
        
        # Scan existing memory files and assign IDs
        existing_files = sorted(MEMORY_DIR.glob("*.md"))
        for idx, memory_file in enumerate(existing_files, 1):
            memory_id = f"M{idx:03d}"
            index["mappings"][memory_id] = memory_file.name
            index["next_id"] = idx + 1
        
        self._save_index(index)
    
    def _load_index(self) -> Dict[str, Any]:
        """Load the memory index from file."""
        if not MEMORY_INDEX_FILE.exists():
            self._initialize_index()
        
        try:
            with open(MEMORY_INDEX_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[red]Error loading index: {e}[/red]")
            return {"next_id": 1, "mappings": {}}
    
    def _save_index(self, index: Dict[str, Any]):
        """Save the memory index to file."""
        try:
            with open(MEMORY_INDEX_FILE, 'w') as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving index: {e}[/red]")
    
    def _get_next_memory_id(self) -> str:
        """Get the next available memory ID."""
        index = self._load_index()
        memory_id = f"M{index['next_id']:03d}"
        index['next_id'] += 1
        self._save_index(index)
        return memory_id
    
    def _register_memory(self, memory_id: str, filename: str):
        """Register a memory file with its ID in the index."""
        index = self._load_index()
        index['mappings'][memory_id] = filename
        self._save_index(index)
    
    def _unregister_memory(self, memory_id: str):
        """Remove a memory ID from the index."""
        index = self._load_index()
        if memory_id in index['mappings']:
            del index['mappings'][memory_id]
            self._save_index(index)
    
    def handle_control_panel(self) -> bool:
        """Show a control panel view of memory status."""
        console.print("[bold cyan]Memory Management Control Panel[/bold cyan]\n")
        
        # Show stored memories
        memories = list(MEMORY_DIR.glob("*.md"))
        if memories:
            console.print("[bold cyan]:floppy_disk: Stored Memories[/bold cyan]")
            
            # Load index to get ID mappings
            index = self._load_index()
            file_to_id = {v: k for k, v in index.get('mappings', {}).items()}
            
            table = Table(show_header=True, header_style="bold yellow")
            table.add_column("ID", style="bright_cyan", width=6)
            table.add_column("Name", style="cyan")
            table.add_column("Agent", style="green")
            table.add_column("Size", style="yellow")
            table.add_column("Modified", style="magenta")
            
            for memory_file in sorted(memories):
                memory_id = file_to_id.get(memory_file.name, "---")
                
                # Try to extract agent name from file
                agent_name = "Unknown"
                try:
                    content = memory_file.read_text()
                    for line in content.split('\n'):
                        if line.startswith("Agent: "):
                            agent_name = line[7:]
                            break
                except:
                    pass
                
                size = memory_file.stat().st_size
                modified = datetime.datetime.fromtimestamp(memory_file.stat().st_mtime)
                table.add_row(
                    memory_id,
                    memory_file.stem,
                    agent_name,
                    f"{size:,} bytes",
                    modified.strftime("%Y-%m-%d %H:%M")
                )
            
            console.print(table)
        else:
            console.print("[yellow]No memories stored yet[/yellow]")
        
        # Show applied memories
        if APPLIED_MEMORY_IDS:
            console.print("\n[bold cyan]:brain: Applied Memories[/bold cyan]")
            for agent_name, memory_ids in APPLIED_MEMORY_IDS.items():
                if isinstance(memory_ids, list):
                    ids_str = ", ".join(memory_ids) if memory_ids else "None"
                    console.print(f"  • {agent_name}: [{ids_str}]")
                else:
                    # Backward compatibility for single memory ID
                    console.print(f"  • {agent_name}: {memory_ids}")
        
        # Show usage hints
        console.print("\n[dim]Commands:[/dim]")
        console.print("[dim]  • /memory list                - List all stored memories[/dim]")
        console.print("[dim]  • /memory save <name>         - Save current agent as memory[/dim]")
        console.print("[dim]  • /memory apply <ID/name>     - Apply memory to P1 (default)[/dim]")
        console.print("[dim]  • /memory apply <ID> all      - Apply to all active agents[/dim]")
        console.print("[dim]  • /memory show <ID/name>      - View memory content[/dim]")
        console.print("[dim]  • /memory delete <ID/name>    - Delete a memory[/dim]")
        console.print("[dim]  • /memory merge <ID1> <ID2>   - Merge multiple memories[/dim]")
        console.print("[dim]  • /memory compact <agent>     - Compact agent history to memory[/dim]")
        console.print("[dim]  • /memory remove <ID> <agent> - Remove a specific memory from agent[/dim]")
        console.print("[dim]  • /memory clear <agent>       - Clear all memories from agent[/dim]")
        console.print("[dim]  • /memory list-applied        - Show applied memories by agent[/dim]")
        console.print("[dim]\nNote: You can use memory IDs (e.g., M001) instead of full names[/dim]")
        console.print("[dim]      Agents now support multiple memories![/dim]")
        
        return True
    
    def handle_list(self, args: Optional[List[str]] = None) -> bool:
        """List all stored memories."""
        memories = list(MEMORY_DIR.glob("*.md"))
        
        if not memories:
            console.print("[yellow]No memories stored yet[/yellow]")
            console.print("[dim]Use '/memory save' to create a memory from current history[/dim]")
            return True
        
        # Load index to get ID mappings
        index = self._load_index()
        id_to_file = index.get('mappings', {})
        file_to_id = {v: k for k, v in id_to_file.items()}
        
        # Create a table showing all memories
        table = Table(title="Stored Memories", show_header=True, header_style="bold yellow")
        table.add_column("ID", style="bright_cyan", width=6)
        table.add_column("Name", style="cyan")
        table.add_column("Agent", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("Created", style="magenta")
        
        for memory_file in sorted(memories):
            # Get ID for this memory
            memory_id = file_to_id.get(memory_file.name, "---")
            
            # Try to extract agent name from file
            content = memory_file.read_text()
            agent_name = "Unknown"
            created = "Unknown"
            
            # Parse metadata from memory file
            for line in content.split('\n'):
                if line.startswith("Agent: "):
                    agent_name = line[7:]
                elif line.startswith("Generated: "):
                    created = line[11:]
                if agent_name != "Unknown" and created != "Unknown":
                    break
            
            size = memory_file.stat().st_size
            table.add_row(
                memory_id,
                memory_file.stem,
                agent_name,
                f"{size:,} bytes",
                created
            )
        
        console.print(table)
        console.print("\n[dim]Commands:[/dim]")
        console.print("[dim]  • /memory show <ID/name>    - View memory content[/dim]")
        console.print("[dim]  • /memory apply <ID/name>   - Apply memory to P1 (default)[/dim]")
        console.print("[dim]  • /memory apply <ID/name> all - Apply to all active agents[/dim]")
        console.print("[dim]  • /memory delete <ID/name>  - Delete a memory[/dim]")
        console.print("[dim]  • /memory merge <ID1> <ID2> - Merge multiple memories[/dim]")
        console.print("[dim]\nNote: You can use either the memory ID (e.g., M001) or the full name[/dim]")
        
        return True
    
    def handle_save(self, args: Optional[List[str]] = None, preserve_history: bool = True) -> bool:
        """Save current agent history as memory."""
        if not args:
            # Use current active agent
            agent_name = self._get_current_agent_name()
            if not agent_name:
                console.print("[red]Error: No active agent found[/red]")
                console.print("Usage: /memory save <memory_name> [agent_name]")
                return False
            memory_name = f"{agent_name.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            memory_name = args[0]
            if len(args) > 1:
                agent_identifier = " ".join(args[1:])
                agent_name = self._resolve_agent_name(agent_identifier)
            else:
                agent_name = self._get_current_agent_name()
                if not agent_name:
                    console.print("[red]Error: No active agent found[/red]")
                    return False
        
        history = get_agent_message_history(agent_name)
        
        if not history:
            console.print(f"[yellow]No history found for agent '{agent_name}'[/yellow]")
            return True
        
        console.print(f"\n[cyan]Saving memory for {agent_name}...[/cyan]")
        
        # Generate summary
        summary = asyncio.run(self._ai_summarize_history(agent_name))
        
        if summary:
            # Generate unique ID for this memory
            memory_id = self._get_next_memory_id()
            
            # Ensure memory_name has .md extension
            if not memory_name.endswith('.md'):
                memory_name += '.md'
            
            memory_path = MEMORY_DIR / memory_name
            
            # Create memory content with metadata including ID
            memory_content = f"""# Memory: {memory_name}
ID: {memory_id}
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Agent: {agent_name}
Model: {get_compact_model() or os.environ.get("CAI_MODEL", "gpt-4")}

{summary}

## Metadata
- Original messages: {len(history)}
- Saved by: User request
"""
            
            memory_path.write_text(memory_content)
            
            # Register the memory in the index
            self._register_memory(memory_id, memory_name)
            
            console.print(f"[green]✓ Saved memory: {memory_name} (ID: {memory_id})[/green]")
            
            # Automatically apply the memory to the agent's system prompt
            if agent_name not in COMPACTED_SUMMARIES:
                COMPACTED_SUMMARIES[agent_name] = []
                APPLIED_MEMORY_IDS[agent_name] = []
            
            # Clear existing memories and add new one (maintain single memory behavior for save)
            COMPACTED_SUMMARIES[agent_name] = [summary]
            APPLIED_MEMORY_IDS[agent_name] = [memory_id]
            console.print(f"[green]✓ Memory {memory_id} automatically applied to {agent_name}'s system prompt[/green]")
            os.environ['CAI_MEMORY'] = 'true' 
            
            # Reload the agent with the new memory
            self._reload_agent_with_memory(agent_name, preserve_history=preserve_history)
            
            # Show memory panel
            console.print(Panel(
                summary[:500] + "..." if len(summary) > 500 else summary,
                title=f"[green]Memory: {memory_name} (ID: {memory_id})[/green]",
                border_style="green"
            ))
        else:
            console.print(f"[red]✗ Failed to save memory[/red]")
            
        return True
    
    def handle_apply(self, args: Optional[List[str]] = None) -> bool:
        """Apply a memory to an agent by injecting it into the system prompt."""
        if not args:
            console.print("[red]Error: Memory ID or name required[/red]")
            console.print("Usage: /memory apply <memory_id_or_name> [agent_name|all]")
            console.print("       /memory apply <memory_id_or_name>        - Applies to P1 by default")
            console.print("       /memory apply <memory_id_or_name> all    - Applies to all active agents")
            return False
        
        memory_identifier = args[0]
        
        try:
            memory_path = self._get_memory_path(memory_identifier)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
        
        if not memory_path.exists():
            console.print(f"[red]Error: Memory '{memory_identifier}' not found[/red]")
            return False
        
        # Determine target agent(s)
        target_agents = []
        
        if len(args) > 1:
            agent_identifier = " ".join(args[1:])
            
            # Check if user wants to apply to all agents
            if agent_identifier.lower() == "all":
                # Get all active agents
                from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                active_agents = AGENT_MANAGER.get_active_agents()
                
                if not active_agents:
                    console.print("[yellow]No active agents found[/yellow]")
                    return False
                
                # Apply to all active agents
                for agent_name, agent_id in active_agents.items():
                    target_agents.append(agent_name)
                    
                console.print(f"[cyan]Applying memory to {len(target_agents)} agents...[/cyan]")
            else:
                # Specific agent requested
                agent_name = self._resolve_agent_name(agent_identifier)
                if agent_name:
                    target_agents.append(agent_name)
                else:
                    console.print(f"[red]Error: Could not resolve agent '{agent_identifier}'[/red]")
                    return False
        else:
            # No agent specified - default to P1
            from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
            
            # Try to get the P1 agent
            p1_agent_name = AGENT_MANAGER.get_agent_by_id("P1")
            if p1_agent_name:
                target_agents.append(p1_agent_name)
                console.print(f"[dim]No agent specified, applying to P1 ({p1_agent_name}) by default[/dim]")
            else:
                # Fallback to current active agent
                agent_name = self._get_current_agent_name()
                if agent_name:
                    target_agents.append(agent_name)
                else:
                    console.print("[red]Error: No P1 agent found[/red]")
                    console.print("[dim]Specify an agent name or use 'all' to apply to all agents[/dim]")
                    return False
        
        # Read memory content - just use the entire content without filtering
        memory_content = memory_path.read_text()
        
        # Use the entire memory content as the summary
        summary = memory_content.strip()
        
        if not summary:
            console.print(f"[red]Error: Memory file is empty[/red]")
            return False
        
        # Get memory ID from the path or identifier
        memory_id = None
        if memory_identifier.upper().startswith("M") and memory_identifier[1:].isdigit():
            memory_id = memory_identifier.upper()
        else:
            # Try to find ID from index
            index = self._load_index()
            for mid, mfile in index.get("mappings", {}).items():
                if mfile == memory_path.name:
                    memory_id = mid
                    break
        
        # Apply memory to each target agent
        success_count = 0
        for agent_name in target_agents:
            try:
                # Initialize lists if not present
                if agent_name not in COMPACTED_SUMMARIES:
                    COMPACTED_SUMMARIES[agent_name] = []
                    APPLIED_MEMORY_IDS[agent_name] = []
                
                # Check if memory already applied
                if memory_id and memory_id in APPLIED_MEMORY_IDS[agent_name]:
                    console.print(f"[yellow]Memory {memory_id} already applied to {agent_name}[/yellow]")
                    continue
                
                # Append memory (supports multiple memories)
                COMPACTED_SUMMARIES[agent_name].append(summary)
                
                # Store the memory ID for this agent
                if memory_id:
                    APPLIED_MEMORY_IDS[agent_name].append(memory_id)
                    console.print(f"[green]✓ Applied memory {memory_id} to {agent_name}[/green]")
                else:
                    console.print(f"[green]✓ Applied memory '{memory_identifier}' to {agent_name}[/green]")
                
                # Reload the agent to apply the memory to system prompt
                self._reload_agent_with_memory(agent_name)
                success_count += 1
                
            except Exception as e:
                console.print(f"[red]Error applying memory to {agent_name}: {e}[/red]")
        
        if success_count > 0:
            os.environ['CAI_MEMORY'] = 'true' 
            console.print("[dim]The memory will be included in the agents' system prompts[/dim]")
            
            # Show summary with ID if available (only once)
            title_text = f"[green]Applied Memory{' (' + memory_id + ')' if memory_id else ''}[/green]"
            console.print(Panel(
                summary[:300] + "..." if len(summary) > 300 else summary,
                title=title_text,
                border_style="green"
            ))
            
            if len(target_agents) > 1:
                console.print(f"\n[bold green]Successfully applied memory to {success_count}/{len(target_agents)} agents[/bold green]")
        else:
            console.print(f"[red]Failed to apply memory to any agents[/red]")
        
        return True
    
    def handle_show(self, args: Optional[List[str]] = None) -> bool:
        """Show memory content."""
        if not args:
            console.print("[red]Error: Memory ID or name required[/red]")
            console.print("Usage: /memory show <memory_id_or_name>")
            return False
        
        memory_identifier = args[0]
        
        try:
            memory_path = self._get_memory_path(memory_identifier)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
        
        if not memory_path.exists():
            console.print(f"[red]Error: Memory '{memory_identifier}' not found[/red]")
            return False
        
        # Read and display memory content
        content = memory_path.read_text()
        
        # Extract ID from content if present
        memory_id = None
        for line in content.split('\n'):
            if line.startswith("ID: "):
                memory_id = line[4:]
                break
        
        title = f"[cyan]Memory: {memory_path.stem}"
        if memory_id:
            title += f" (ID: {memory_id})"
        title += "[/cyan]"
        
        console.print(Panel(
            content,
            title=title,
            border_style="cyan"
        ))
        
        return True
    
    def handle_delete(self, args: Optional[List[str]] = None) -> bool:
        """Delete a stored memory."""
        if not args:
            console.print("[red]Error: Memory ID or name required[/red]")
            console.print("Usage: /memory delete <memory_id_or_name>")
            return False
        
        memory_identifier = args[0]
        
        try:
            memory_path = self._get_memory_path(memory_identifier)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
        
        if not memory_path.exists():
            console.print(f"[red]Error: Memory '{memory_identifier}' not found[/red]")
            return False
        
        # Get the memory ID if we used a name
        index = self._load_index()
        memory_id = None
        for mid, fname in index.get('mappings', {}).items():
            if fname == memory_path.name:
                memory_id = mid
                break
        
        # Ask for confirmation
        display_name = f"{memory_path.stem}" + (f" (ID: {memory_id})" if memory_id else "")
        confirm = console.input(f"Delete memory '{display_name}'? (y/N): ")
        if confirm.lower() == 'y':
            memory_path.unlink()
            
            # Remove from index if it has an ID
            if memory_id:
                self._unregister_memory(memory_id)
            
            console.print(f"[green]✓ Deleted memory '{display_name}'[/green]")
        else:
            console.print("[dim]Cancelled[/dim]")
        
        return True
    
    def handle_merge(self, args: Optional[List[str]] = None) -> bool:
        """Merge multiple memories into one."""
        if not args or len(args) < 2:
            console.print("[red]Error: At least 2 memory IDs or names required[/red]")
            console.print("Usage: /memory merge <memory1> <memory2> [memory3...] [into:<new_name>]")
            console.print("Example: /memory merge M001 M002 M003 into:combined_memory")
            return False
        
        # Parse arguments - look for "into:" prefix for output name
        memory_identifiers = []
        output_name = None
        
        for arg in args:
            if arg.startswith("into:"):
                output_name = arg[5:]
            else:
                memory_identifiers.append(arg)
        
        if len(memory_identifiers) < 2:
            console.print("[red]Error: At least 2 memories required to merge[/red]")
            return False
        
        # Generate default output name if not provided
        if not output_name:
            output_name = f"merged_{len(memory_identifiers)}_memories_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Load all memories
        summaries = []
        agent_names = set()
        total_messages = 0
        
        for identifier in memory_identifiers:
            try:
                memory_path = self._get_memory_path(identifier)
                if not memory_path.exists():
                    console.print(f"[red]Error: Memory '{identifier}' not found[/red]")
                    return False
                
                # Read memory content
                content = memory_path.read_text()
                
                # Extract summary and metadata
                summary = ""
                in_summary = False
                agent_name = None
                msg_count = 0
                
                for line in content.split('\n'):
                    if line.startswith("Agent: "):
                        agent_name = line[7:]
                        agent_names.add(agent_name)
                    elif "Original messages: " in line:
                        try:
                            msg_count = int(line.split("Original messages: ")[1].split()[0])
                            total_messages += msg_count
                        except:
                            pass
                    elif line.strip() == "## Summary":
                        in_summary = True
                        continue
                    elif line.strip().startswith("## ") and in_summary:
                        break
                    elif in_summary:
                        summary += line + "\n"
                
                if summary.strip():
                    summaries.append(f"### Memory: {identifier}\n{summary.strip()}")
                    console.print(f"[green]✓ Loaded memory '{identifier}'[/green]")
                else:
                    console.print(f"[yellow]Warning: No summary found in memory '{identifier}'[/yellow]")
                    
            except Exception as e:
                console.print(f"[red]Error loading memory '{identifier}': {e}[/red]")
                return False
        
        if not summaries:
            console.print("[red]Error: No valid summaries found to merge[/red]")
            return False
        
        # Combine summaries
        combined_summary = "\n\n".join(summaries)
        
        # Generate unique ID for the merged memory
        memory_id = self._get_next_memory_id()
        
        # Ensure output_name has .md extension
        if not output_name.endswith('.md'):
            output_name += '.md'
        
        memory_path = MEMORY_DIR / output_name
        
        # Create merged memory content
        agents_str = ", ".join(sorted(agent_names)) if agent_names else "Multiple Agents"
        memory_content = f"""# Memory: Merged Memory
ID: {memory_id}
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Agent: {agents_str}
Model: Merged from {len(memory_identifiers)} memories

## Summary

{combined_summary}

## Metadata
- Source memories: {', '.join(memory_identifiers)}
- Total original messages: {total_messages}
- Merge date: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
        
        memory_path.write_text(memory_content)
        
        # Register the memory in the index
        self._register_memory(memory_id, output_name)
        
        console.print(f"\n[bold green]✓ Successfully merged {len(memory_identifiers)} memories into '{output_name}' (ID: {memory_id})[/bold green]")
        
        # Show merged memory panel
        console.print(Panel(
            combined_summary[:500] + "..." if len(combined_summary) > 500 else combined_summary,
            title=f"[green]Merged Memory: {output_name} (ID: {memory_id})[/green]",
            border_style="green"
        ))
        
        # Ask if user wants to apply the merged memory
        apply = console.input("\nApply merged memory to current agent? (y/N): ")
        if apply.lower() == 'y':
            agent_name = self._get_current_agent_name()
            if agent_name:
                # Initialize lists if not present
                if agent_name not in COMPACTED_SUMMARIES:
                    COMPACTED_SUMMARIES[agent_name] = []
                    APPLIED_MEMORY_IDS[agent_name] = []
                
                # Append the merged memory
                COMPACTED_SUMMARIES[agent_name].append(combined_summary)
                APPLIED_MEMORY_IDS[agent_name].append(memory_id)
                console.print(f"[green]✓ Applied merged memory {memory_id} to {agent_name}[/green]")
                # Reload the agent with the new memory
                self._reload_agent_with_memory(agent_name)
            else:
                console.print("[yellow]No active agent found to apply memory to[/yellow]")
        
        return True
    
    def handle_status(self, args: Optional[List[str]] = None) -> bool:
        """Show memory status."""
        console.print("[bold cyan]Memory Status[/bold cyan]\n")
        
        # Show memory storage
        memories = list(MEMORY_DIR.glob("*.md"))
        console.print(f"Stored Memories: {len(memories)}")
        if memories:
            total_size = sum(m.stat().st_size for m in memories)
            console.print(f"Total Size: {total_size:,} bytes")
        
        # Show applied memories (from COMPACTED_SUMMARIES)
        if COMPACTED_SUMMARIES:
            console.print("\n[yellow]Applied Memories:[/yellow]")
            for agent_name, summaries in COMPACTED_SUMMARIES.items():
                memory_ids = APPLIED_MEMORY_IDS.get(agent_name, [])
                display_name = "Global" if agent_name == "__global__" else agent_name
                if isinstance(summaries, list):
                    total_chars = sum(len(s) for s in summaries)
                    ids_str = ", ".join(memory_ids) if memory_ids else "Unknown"
                    console.print(f"  - {display_name}: {len(summaries)} memories, {total_chars} chars (IDs: {ids_str})")
                else:
                    # Backward compatibility
                    memory_id = memory_ids if isinstance(memory_ids, str) else "Unknown"
                    console.print(f"  - {display_name}: {len(summaries)} chars (ID: {memory_id})")
        else:
            console.print("\n[yellow]No memories currently applied[/yellow]")
        
        # Show context usage for all agents
        console.print("\n[yellow]Agent Context Usage:[/yellow]")
        all_histories = get_all_agent_histories()
        total_tokens = 0
        for agent_name, history in all_histories.items():
            if history:
                # Estimate tokens
                total_chars = sum(len(str(msg.get("content", ""))) for msg in history)
                estimated_tokens = total_chars // 4  # Rough estimate
                total_tokens += estimated_tokens
                console.print(f"  - {agent_name}: ~{estimated_tokens:,} tokens ({len(history)} messages)")
        
        if total_tokens > 0:
            console.print(f"\n[bold]Total estimated tokens: ~{total_tokens:,}[/bold]")
        
        return True
    
    def handle_compact(self, args: Optional[List[str]] = None) -> bool:
        """Compact a specific agent's history or all agents."""
        if not args:
            console.print("[red]Error: Agent name/ID or 'all' required[/red]")
            console.print("Usage: /memory compact <agent_name/ID|all>")
            return False
        
        if args[0].lower() == "all":
            return self._compact_all_agents()
        else:
            # Join all args to handle agent names with spaces
            agent_identifier = " ".join(args)
            return self._compact_single_agent(agent_identifier)
    
    def _compact_all_agents(self) -> bool:
        """Compact all agent histories."""
        all_histories = get_all_agent_histories()
        
        if not all_histories:
            console.print("[yellow]No agent histories to compact[/yellow]")
            return True
        
        # Ask for confirmation
        console.print("[yellow]This will compact all agent histories and save them as memories.[/yellow]")
        confirm = console.input("Continue? (y/N): ")
        if confirm.lower() != 'y':
            console.print("[dim]Cancelled[/dim]")
            return True
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for agent_name in all_histories:
            console.print(f"\n[cyan]Compacting {agent_name}...[/cyan]")
            # Generate summary for this agent
            summary = asyncio.run(self._ai_summarize_history(agent_name))
            
            if summary:
                # Generate unique ID for this memory
                memory_id = self._get_next_memory_id()
                
                # Save as memory
                memory_name = f"{agent_name.replace(' ', '_').replace('#', '')}_{timestamp}.md"
                memory_path = MEMORY_DIR / memory_name
                
                # Create memory content with metadata including ID
                memory_content = f"""# Memory: {agent_name}
ID: {memory_id}
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Agent: {agent_name}
Model: {get_compact_model() or os.environ.get("CAI_MODEL", "gpt-4")}

{summary}

## Metadata
- Original messages: {len(all_histories[agent_name])}
- Compaction method: AI Summary
"""
                
                memory_path.write_text(memory_content)
                
                # Register the memory in the index
                self._register_memory(memory_id, memory_name)

                os.environ['CAI_MEMORY'] = 'true'
                console.print(f"[green]✓ Saved memory: {memory_name} (ID: {memory_id})[/green]")
                
                # Automatically apply the memory to the agent's system prompt
                if agent_name not in COMPACTED_SUMMARIES:
                    COMPACTED_SUMMARIES[agent_name] = []
                    APPLIED_MEMORY_IDS[agent_name] = []
                
                # Clear existing memories and add new one (maintain single memory behavior for compact all)
                COMPACTED_SUMMARIES[agent_name] = [summary]
                APPLIED_MEMORY_IDS[agent_name] = [memory_id]
                console.print(f"[green]✓ Memory {memory_id} automatically applied to {agent_name}'s system prompt[/green]")
                
                # Clear the agent's history after saving
                self._clear_agent_history(agent_name)
                
                # Reload the agent with the new memory
                self._reload_agent_with_memory(agent_name)
            else:
                console.print(f"[red]✗ Failed to compact {agent_name}[/red]")
        
        console.print("\n[bold green]All agents compacted and saved as memories[/bold green]")
        return True
    
    def _compact_single_agent(self, agent_identifier: str) -> bool:
        """Compact a single agent's history."""
        # For simple P1 case, check the current active agent
        if agent_identifier.upper() == "P1":
            # Get the current active agent from environment or AGENT_MANAGER
            current_agent = AGENT_MANAGER.get_active_agent()
            if current_agent:
                agent_name = getattr(current_agent, "name", None)
                if not agent_name:
                    # Try to get from environment
                    import os
                    agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
                    from cai.agents import get_available_agents
                    agents = get_available_agents()
                    if agent_type in agents:
                        agent = agents[agent_type]
                        agent_name = getattr(agent, "name", agent_type)
            else:
                console.print("[red]No active agent found for P1[/red]")
                return False
        else:
            agent_name = self._resolve_agent_name(agent_identifier)
        
        if not agent_name:
            console.print(f"[red]Error: Could not resolve agent '{agent_identifier}'[/red]")
            return False
        
        # Get history from the actual model instance if possible
        history = None
        
        # First try to get from ACTIVE_MODEL_INSTANCES
        for (name, inst_id), model_ref in ACTIVE_MODEL_INSTANCES.items():
            if name == agent_name or (inst_id == "P1" and agent_identifier.upper() == "P1"):
                model = model_ref() if model_ref else None
                if model and hasattr(model, 'message_history'):
                    history = list(model.message_history)
                    break
        
        # If not found, try get_agent_message_history
        if not history:
            history = get_agent_message_history(agent_name)
        
        if not history:
            console.print(f"[yellow]No history found for agent '{agent_name}'[/yellow]")
            return True
        
        original_count = len(history)
        console.print(f"\n[cyan]Compacting {agent_name} ({original_count} messages)...[/cyan]")
        
        # Generate summary
        summary = asyncio.run(self._ai_summarize_history(agent_name))
        
        if summary:
            # Generate unique ID for this memory
            memory_id = self._get_next_memory_id()
            
            # Save as memory
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            memory_name = f"{agent_name.replace(' ', '_').replace('#', '')}_{timestamp}.md"
            memory_path = MEMORY_DIR / memory_name
            
            # Create memory content with metadata including ID
            memory_content = f"""# Memory: {agent_name}
ID: {memory_id}
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Agent: {agent_name}
Model: {get_compact_model() or os.environ.get("CAI_MODEL", "gpt-4")}

{summary}

## Metadata
- Original messages: {original_count}
- Compaction method: AI Summary
"""
            
            memory_path.write_text(memory_content)
            
            # Register the memory in the index
            self._register_memory(memory_id, memory_name)
            
            console.print(f"[green]✓ Saved memory: {memory_name} (ID: {memory_id})[/green]")
            os.environ['CAI_MEMORY'] = 'true'
            # Automatically apply the memory to the agent's system prompt
            if agent_name not in COMPACTED_SUMMARIES:
                COMPACTED_SUMMARIES[agent_name] = []
                APPLIED_MEMORY_IDS[agent_name] = []
            
            # Clear existing memories and add new one (maintain single memory behavior for compact single)
            COMPACTED_SUMMARIES[agent_name] = [summary]
            APPLIED_MEMORY_IDS[agent_name] = [memory_id]
            console.print(f"[green]✓ Memory {memory_id} automatically applied to {agent_name}'s system prompt[/green]")
            
            # Ask if user wants to clear history
            clear = console.input("\nClear agent history after compaction? (y/N): ")
            if clear.lower() == 'y':
                self._clear_agent_history(agent_name)
                console.print(f"[green]✓ Cleared history for {agent_name}[/green]")
            
            # Reload the agent with the new memory
            self._reload_agent_with_memory(agent_name, preserve_history=preserve_history)
            
            # Show memory panel
            console.print(Panel(
                summary[:500] + "..." if len(summary) > 500 else summary,
                title=f"[green]Compacted Memory: {memory_name} (ID: {memory_id})[/green]",
                border_style="green"
            ))
        else:
            console.print(f"[red]✗ Failed to compact {agent_name}[/red]")
            
        return True
    
    def _clear_agent_history(self, agent_name: str):
        """Clear an agent's message history."""
        # Find the matching model instance
        model_instance = None
        for (name, inst_id), model_ref in ACTIVE_MODEL_INSTANCES.items():
            if name == agent_name:
                model = model_ref() if model_ref else None
                if model:
                    model_instance = model
                    break
        
        if model_instance:
            # Clear the model's message history
            model_instance.message_history.clear()
            # Reset context usage since we cleared the history
            os.environ['CAI_CONTEXT_USAGE'] = '0.0'
        
        # Also clear persistent history
        if agent_name in PERSISTENT_MESSAGE_HISTORIES:
            PERSISTENT_MESSAGE_HISTORIES[agent_name].clear()
    
    async def _ai_summarize_history(self, agent_name: Optional[str] = None) -> Optional[str]:
        """Use an AI agent to summarize conversation history with optimized memory usage."""
        # Get history to summarize
        if agent_name:
            history = get_agent_message_history(agent_name)
            target = f"agent '{agent_name}'"
        else:
            # Get all histories
            all_histories = get_all_agent_histories()
            history = []
            for h in all_histories.values():
                history.extend(h)
            target = "all agents"

        if not history:
            console.print(f"[yellow]No history to summarize for {target}[/yellow]")
            return None

        console.print(f"[cyan]Preparing conversation history ({len(history)} messages)...[/cyan]")

        # Write history to temporary file to avoid memory issues
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
            temp_path = Path(temp_file.name)
            try:
                # Write history to file with progress indicator
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console,
                    transient=True
                ) as progress:
                    task = progress.add_task("[cyan]Writing history to temporary file...", total=len(history))

                    messages_written, file_size = self._write_history_to_file(history, temp_path)

                    progress.update(task, completed=len(history))

                file_size_mb = file_size / (1024 * 1024)
                console.print(f"[green]✓ Wrote {messages_written} messages ({file_size_mb:.2f} MB) to temporary file[/green]")

                # Check if file is too large and needs batching
                MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB threshold for batching
                if file_size > MAX_FILE_SIZE:
                    console.print(f"[yellow]Large history detected ({file_size_mb:.2f} MB), using batch processing...[/yellow]")
                    summary = await self._batch_summarize_from_file(temp_path, target, file_size, messages_written)
                else:
                    # Read file and summarize in one go
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        conversation_text = f.read()

                    summary = await self._summarize_text(conversation_text, target)

                return summary

            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

    async def _batch_summarize_from_file(self, file_path: Path, target: str, total_size: int, total_messages: int) -> Optional[str]:
        """Summarize large conversation history in batches to avoid memory/API limits.

        Args:
            file_path: Path to file containing conversation history
            target: Description of what is being summarized
            total_size: Total size in bytes
            total_messages: Total number of messages

        Returns:
            Final summary combining all batches
        """
        BATCH_SIZE = 3 * 1024 * 1024  # 3 MB per batch
        batch_summaries = []

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split into batches by size
        num_batches = (len(content) + BATCH_SIZE - 1) // BATCH_SIZE

        console.print(f"[cyan]Processing in {num_batches} batches...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]Summarizing batches...", total=num_batches)

            for i in range(num_batches):
                start = i * BATCH_SIZE
                end = min((i + 1) * BATCH_SIZE, len(content))
                batch_content = content[start:end]

                batch_summary = await self._summarize_text(
                    batch_content,
                    f"{target} (batch {i+1}/{num_batches})",
                    batch_mode=True
                )

                if batch_summary:
                    batch_summaries.append(batch_summary)

                progress.update(task, advance=1)

        if not batch_summaries:
            console.print("[red]Failed to generate any batch summaries[/red]")
            return None

        # Combine batch summaries into final summary
        if len(batch_summaries) == 1:
            return batch_summaries[0]

        console.print("[cyan]Combining batch summaries into final summary...[/cyan]")
        combined_text = "\n\n---\n\n".join(f"## Batch {i+1}\n{summary}" for i, summary in enumerate(batch_summaries))

        final_summary = await self._summarize_text(
            combined_text,
            target,
            batch_mode=False,
            is_final_pass=True
        )

        return final_summary

    async def _summarize_text(self, text: str, target: str, batch_mode: bool = False, is_final_pass: bool = False) -> Optional[str]:
        """Summarize a text using AI model.

        Args:
            text: Text to summarize
            target: Description of what is being summarized
            batch_mode: Whether this is a batch summary (uses simpler prompt)
            is_final_pass: Whether this is the final pass combining batch summaries

        Returns:
            Summary text or None on failure
        """
        from cai.repl.commands.compact import get_compact_model, get_custom_prompt

        # Create summary agent
        model_name = get_compact_model() or os.environ.get("CAI_MODEL", "alias0")

        # Use custom prompt if set, otherwise use default
        custom_prompt = get_custom_prompt()

        if custom_prompt:
            instructions = custom_prompt
        elif batch_mode and not is_final_pass:
            # Simpler instructions for batch processing
            instructions = """You are a conversation summarizer. Summarize this portion of a conversation, focusing on:
1. Main topics and user requests
2. Key technical details and file changes
3. Important errors and solutions
4. Current progress and outcomes

Keep the summary detailed but organized. This is part of a larger conversation."""
        elif is_final_pass:
            # Instructions for combining batch summaries
            instructions = """You are a conversation summarizer. You will receive multiple summaries of different parts of a conversation.
Combine these summaries into one comprehensive, well-organized summary that:
1. Maintains chronological flow
2. Eliminates redundancy
3. Preserves all critical technical details
4. Provides clear next steps

Create a cohesive summary that reads as if it was summarizing the entire conversation from the start."""
        else:
            instructions = """You are an advanced conversation summarizer specializing in creating comprehensive continuity summaries for technical conversations. Your task is to analyze the conversation and create a detailed summary that will serve as context for continuing the work in a new session.

## Primary Analysis Framework

When analyzing the conversation, focus on:

1. **Primary Request and Intent**
   - What was the user's original request or problem?
   - What were they trying to achieve?
   - Were there any specific requirements or constraints mentioned?

2. **Key Technical Concepts**
   - What technical systems, frameworks, or concepts were discussed?
   - What programming languages, tools, or technologies were involved?
   - Were there any architectural patterns or design decisions made?

3. **Files and Code Sections**
   - List all files that were read, created, or modified
   - Include file paths and brief descriptions of changes
   - Highlight any critical code sections or functions
   - Note any dependencies or relationships between files

4. **Errors and Solutions**
   - Document all errors encountered with their exact error messages
   - Describe the solutions or fixes that were applied
   - Note any workarounds or temporary solutions
   - Include any unresolved issues

5. **Problem Solving Progress**
   - What steps were taken to solve the problem?
   - What approaches were tried (both successful and unsuccessful)?
   - What debugging or investigation was performed?
   - What was the final state of the solution?

6. **Conversation Metadata**
   - All user messages in chronological order (verbatim if critical)
   - Key decisions made during the conversation
   - Any context switches or topic changes
   - Important clarifications or confirmations

7. **Current State and Next Steps**
   - What is the current state of the work?
   - What tasks were completed successfully?
   - What remains to be done?
   - Are there any pending questions or blockers?

8. **Technical Artifacts**
   - Any URLs, IPs, credentials, or configuration values discovered
   - Command outputs or tool results that are important
   - Error logs or stack traces
   - Performance metrics or test results

## Summary Structure

Your summary should follow this structure:

### Analysis
Provide a chronological analysis of the conversation, explaining what happened step by step. This should read like a technical narrative that someone could follow to understand the progression of work.

### Summary
After the analysis, provide a structured summary with these sections:

1. **Primary Request and Intent**: Brief description of what the user wanted
2. **Key Technical Concepts**: Technologies and systems involved
3. **Files and Code Sections**: List of all files touched with descriptions
4. **Errors and Fixes**: Comprehensive list of all errors and their resolutions
5. **Problem Solving**: Overview of approaches and solutions
6. **All User Messages**: Complete list of user messages in order
7. **Pending Tasks**: What still needs to be done
8. **Current Work**: What was being worked on when the conversation ended
9. **Optional Next Step**: If there's a clear next action, mention it

## Important Guidelines

- Be comprehensive but organized - include all important details but structure them clearly
- Preserve exact error messages, file paths, and technical specifications
- Include the complete chronological flow to maintain context
- If code snippets are critical to understanding, include them
- Maintain technical accuracy - don't paraphrase technical terms
- The summary will be used as the primary context for resuming work, so completeness is crucial
- When the conversation is resumed, it should feel like a natural continuation

This session is being continued from a previous conversation that ran out of context. The conversation is summarized below:"""

        summary_agent = Agent(
            name="Summary Agent",
            instructions=instructions,
            model=OpenAIChatCompletionsModel(
                model=model_name,
                openai_client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")),
                agent_name="Summary Agent"
            )
        )

        # Generate summary
        mode_desc = "batch " if batch_mode else ""
        mode_desc = "final combined " if is_final_pass else mode_desc
        console.print(f"[yellow]Generating {mode_desc}summary for {target} using {model_name}...[/yellow]")

        try:
            result = await Runner.run(
                starting_agent=summary_agent,
                input=f"Please summarize the following conversation:\n\n{text}",
                max_turns=1
            )

            if result.final_output:
                return str(result.final_output)
            else:
                return None

        except Exception as e:
            console.print(f"[red]Error generating summary: {e}[/red]")
            if os.getenv("CAI_DEBUG", "1") == "2":
                import traceback
                traceback.print_exc()
            return None
    
    def _format_history_for_summary(self, history: List[Dict[str, Any]]) -> str:
        """Format message history for summarization.

        NOTE: This method is deprecated and kept for backwards compatibility.
        Use _write_history_to_file for better memory efficiency with large histories.

        IMPORTANT: Preserves COMPLETE history without truncation or message limits.
        """
        formatted_parts = []

        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Skip empty messages
            if not content:
                continue

            # Format based on role - PRESERVE EVERYTHING
            if role == "user":
                formatted_parts.append(f"USER: {content}")
            elif role == "assistant":
                # Check for tool calls
                if "tool_calls" in msg and msg["tool_calls"]:
                    tool_info = []
                    for tc in msg["tool_calls"]:
                        if hasattr(tc, "function"):
                            # PRESERVE FULL ARGUMENTS
                            tool_info.append(f"{tc.function.name}({tc.function.arguments})")
                    if tool_info:
                        formatted_parts.append(f"ASSISTANT (tools): {', '.join(tool_info)}")
                if content:
                    formatted_parts.append(f"ASSISTANT: {content}")
            elif role == "tool":
                # PRESERVE FULL TOOL OUTPUT - no truncation
                formatted_parts.append(f"TOOL OUTPUT: {content}")

        # Return ALL messages, no limit
        return "\n\n".join(formatted_parts)

    def _write_history_to_file(self, history: List[Dict[str, Any]], output_file: Path) -> tuple[int, int]:
        """Write message history to file using streaming to avoid memory issues.

        IMPORTANT: This writes the COMPLETE history without any truncation or loss of data.
        All messages, tool outputs, and function arguments are preserved in full.

        Args:
            history: Message history to write
            output_file: Path to output file

        Returns:
            Tuple of (messages_written, total_size_bytes)
        """
        messages_written = 0
        total_size = 0

        with open(output_file, 'w', encoding='utf-8') as f:
            for msg in history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                # Skip empty messages
                if not content:
                    continue

                # Format based on role - PRESERVE EVERYTHING
                message_text = None
                if role == "user":
                    message_text = f"USER: {content}\n\n"
                elif role == "assistant":
                    # Check for tool calls
                    if "tool_calls" in msg and msg["tool_calls"]:
                        tool_info = []
                        for tc in msg["tool_calls"]:
                            if hasattr(tc, "function"):
                                # PRESERVE FULL ARGUMENTS - no truncation
                                args = str(tc.function.arguments)
                                tool_info.append(f"{tc.function.name}({args})")
                        if tool_info:
                            message_text = f"ASSISTANT (tools): {', '.join(tool_info)}\n\n"
                    if content:
                        if message_text:
                            message_text += f"ASSISTANT: {content}\n\n"
                        else:
                            message_text = f"ASSISTANT: {content}\n\n"
                elif role == "tool":
                    # PRESERVE FULL TOOL OUTPUT - no truncation
                    content_str = str(content)
                    message_text = f"TOOL OUTPUT: {content_str}\n\n"

                if message_text:
                    f.write(message_text)
                    messages_written += 1
                    total_size += len(message_text.encode('utf-8'))

        return messages_written, total_size
    
    def _get_current_agent_name(self) -> Optional[str]:
        """Get the name of the current active agent."""
        # First check AGENT_MANAGER for the active agent
        active_agent = AGENT_MANAGER.get_active_agent()
        if active_agent:
            agent_name = getattr(active_agent, 'name', None)
            if not agent_name:
                # If agent doesn't have a name attribute, try to get from environment
                import os
                agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
                from cai.agents import get_available_agents
                agents = get_available_agents()
                if agent_type in agents:
                    agent = agents[agent_type]
                    agent_name = getattr(agent, "name", agent_type)
            return agent_name
        
        # Check if there's an active agent name in AGENT_MANAGER
        if hasattr(AGENT_MANAGER, '_active_agent_name') and AGENT_MANAGER._active_agent_name:
            return AGENT_MANAGER._active_agent_name
        
        # Check registered agents
        registered = AGENT_MANAGER.get_registered_agents()
        if registered:
            # If there's only one registered agent, use it
            if len(registered) == 1:
                return list(registered.keys())[0]
            # Otherwise check which one is P1 (the active one in single agent mode)
            for agent_name, agent_id in registered.items():
                if agent_id == "P1":
                    return agent_name
        
        # Try to get from environment and available agents
        import os
        agent_type = os.getenv("CAI_AGENT_TYPE", "one_tool_agent")
        from cai.agents import get_available_agents
        agents = get_available_agents()
        if agent_type in agents:
            agent = agents[agent_type]
            return getattr(agent, "name", agent_type)
        
        # Fallback to checking the model
        current_model = get_current_active_model()
        if current_model and hasattr(current_model, 'agent_name'):
            return current_model.agent_name
        
        return None
        
        # Final fallback - check for any registered agent in AGENT_MANAGER
        registered = AGENT_MANAGER.get_registered_agents()
        if registered:
            # Get the first registered agent (should be P1 in single mode)
            for name, aid in registered.items():
                if aid == "P1":
                    return name
        
        return None
    
    def _reload_agent_with_memory(self, agent_name: str, preserve_history: bool = True):
        """Reload an agent to apply memory changes.
        
        Args:
            agent_name: Name of the agent to reload
            preserve_history: Whether to preserve message history (default True).
                            Set to False when called from compact to avoid restoring cleared history.
        """
        try:
            # Get the current agent instance and its history
            from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
            from cai.agents import get_agent_by_name, get_available_agents
            import os
            
            # ALWAYS skip reload when in parallel mode
            # Parallel agents are already configured and reloading causes duplicate registrations
            if PARALLEL_CONFIGS:
                console.print(f"[dim]Agent '{agent_name}' memory applied without reload (parallel mode)[/dim]")
                return
            
            # Find the agent type from available agents
            agent_type = None
            available_agents = get_available_agents()
            for atype, agent in available_agents.items():
                if hasattr(agent, 'name') and agent.name == agent_name:
                    agent_type = atype
                    break
            
            if not agent_type:
                # For pattern-based agents or custom named agents, skip reload
                console.print(f"[dim]Agent '{agent_name}' memory applied without reload[/dim]")
                return
            
            # Get the current agent's message history before reloading
            history_backup = []
            if preserve_history:
                current_history = get_agent_message_history(agent_name)
                if current_history:
                    # Store a copy of the history
                    history_backup = list(current_history)
            else:
                # When not preserving history (e.g., from compact), clear it before creating new agent
                AGENT_MANAGER.clear_history(agent_name)
            
            # Get the agent ID
            agent_id = AGENT_MANAGER.get_id_by_name(agent_name)
            if not agent_id:
                agent_id = "P1"  # Default for single agent mode
            
            # Create a new agent instance with memory already in system prompt
            new_agent = get_agent_by_name(agent_type, agent_id=agent_id)
            
            # Ensure the new agent has the memory applied in its system prompt
            # The get_agent_by_name function should already handle this via get_compacted_summary
            
            # Update the agent in AGENT_MANAGER based on mode
            if agent_id == "P1":
                # Single agent mode - use switch_to_single_agent
                AGENT_MANAGER.switch_to_single_agent(new_agent, agent_name)
            else:
                # Parallel mode - use set_parallel_agent
                AGENT_MANAGER.set_parallel_agent(agent_id, new_agent, agent_name)
            
            # Restore the message history to the new agent instance
            if preserve_history and hasattr(new_agent, 'model') and hasattr(new_agent.model, 'message_history'):
                # The switch_to_single_agent might have already transferred history
                # Only restore if the new agent's history is empty or different
                if not new_agent.model.message_history and history_backup:
                    new_agent.model.message_history.extend(history_backup)
                elif len(new_agent.model.message_history) != len(history_backup):
                    # Replace with our backup if different
                    new_agent.model.message_history.clear()
                    new_agent.model.message_history.extend(history_backup)
            
            # Also update PERSISTENT_MESSAGE_HISTORIES if needed
            if agent_name in PERSISTENT_MESSAGE_HISTORIES:
                PERSISTENT_MESSAGE_HISTORIES[agent_name].clear()
                if preserve_history:
                    PERSISTENT_MESSAGE_HISTORIES[agent_name].extend(history_backup)
            
            # Update the global active agent in CLI if we're in single agent mode
            if agent_id == "P1":
                # Import cli module to update the agent reference
                try:
                    import cai.cli
                    if hasattr(cai.cli, 'agent'):
                        cai.cli.agent = new_agent
                except:
                    pass
            
            console.print(f"[green]✓ Reloaded agent '{agent_name}' with memory applied[/green]")
            console.print("[dim]The memory is now included in the agent's system prompt[/dim]")
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not reload agent automatically: {e}[/yellow]")
            console.print("[dim]The memory will be applied on the next agent interaction[/dim]")
    
    def handle_remove(self, args: Optional[List[str]] = None) -> bool:
        """Remove a specific memory from an agent."""
        if not args or len(args) < 2:
            console.print("[red]Error: Memory ID and agent name required[/red]")
            console.print("Usage: /memory remove <memory_id> <agent_name>")
            return False
        
        memory_id = args[0].upper()
        agent_identifier = " ".join(args[1:])
        agent_name = self._resolve_agent_name(agent_identifier)
        
        if not agent_name:
            console.print(f"[red]Error: Could not resolve agent '{agent_identifier}'[/red]")
            return False
        
        # Check if agent has memories applied
        if agent_name not in APPLIED_MEMORY_IDS:
            console.print(f"[yellow]Agent '{agent_name}' has no memories applied[/yellow]")
            return True
        
        memory_ids = APPLIED_MEMORY_IDS[agent_name]
        summaries = COMPACTED_SUMMARIES.get(agent_name, [])
        
        # Handle backward compatibility
        if isinstance(memory_ids, str):
            if memory_ids == memory_id:
                del APPLIED_MEMORY_IDS[agent_name]
                if agent_name in COMPACTED_SUMMARIES:
                    del COMPACTED_SUMMARIES[agent_name]
                console.print(f"[green]✓ Removed memory {memory_id} from {agent_name}[/green]")
                self._reload_agent_with_memory(agent_name)
                return True
            else:
                console.print(f"[yellow]Memory {memory_id} not found for agent '{agent_name}'[/yellow]")
                return True
        
        # Handle list of memories
        if memory_id not in memory_ids:
            console.print(f"[yellow]Memory {memory_id} not found for agent '{agent_name}'[/yellow]")
            return True
        
        # Find index and remove
        idx = memory_ids.index(memory_id)
        memory_ids.pop(idx)
        if isinstance(summaries, list) and idx < len(summaries):
            summaries.pop(idx)
        
        # Clean up if no memories left
        if not memory_ids:
            del APPLIED_MEMORY_IDS[agent_name]
            if agent_name in COMPACTED_SUMMARIES:
                del COMPACTED_SUMMARIES[agent_name]
        
        console.print(f"[green]✓ Removed memory {memory_id} from {agent_name}[/green]")
        self._reload_agent_with_memory(agent_name)
        
        return True
    
    def handle_clear(self, args: Optional[List[str]] = None) -> bool:
        """Clear all memories from an agent."""
        if not args:
            console.print("[red]Error: Agent name required[/red]")
            console.print("Usage: /memory clear <agent_name>")
            return False
        
        agent_identifier = " ".join(args)
        agent_name = self._resolve_agent_name(agent_identifier)
        
        if not agent_name:
            console.print(f"[red]Error: Could not resolve agent '{agent_identifier}'[/red]")
            return False
        
        # Check if agent has memories applied
        if agent_name not in APPLIED_MEMORY_IDS:
            console.print(f"[yellow]Agent '{agent_name}' has no memories applied[/yellow]")
            return True
        
        # Ask for confirmation
        memory_ids = APPLIED_MEMORY_IDS.get(agent_name)
        count = len(memory_ids) if isinstance(memory_ids, list) else 1
        confirm = console.input(f"Clear {count} memory(ies) from '{agent_name}'? (y/N): ")
        
        if confirm.lower() == 'y':
            del APPLIED_MEMORY_IDS[agent_name]
            if agent_name in COMPACTED_SUMMARIES:
                del COMPACTED_SUMMARIES[agent_name]
            console.print(f"[green]✓ Cleared all memories from {agent_name}[/green]")
            self._reload_agent_with_memory(agent_name)
        else:
            console.print("[dim]Cancelled[/dim]")
        
        return True
    
    def handle_list_applied(self, args: Optional[List[str]] = None) -> bool:
        """Show which memories are applied to an agent."""
        if not args:
            # Show all agents with applied memories
            if not APPLIED_MEMORY_IDS:
                console.print("[yellow]No memories applied to any agents[/yellow]")
                return True
            
            console.print("[bold cyan]Applied Memories by Agent[/bold cyan]\n")
            
            for agent_name, memory_ids in APPLIED_MEMORY_IDS.items():
                console.print(f"[green]{agent_name}:[/green]")
                
                if isinstance(memory_ids, list):
                    for i, memory_id in enumerate(memory_ids):
                        # Try to get memory details
                        index = self._load_index()
                        memory_file = index.get('mappings', {}).get(memory_id, "Unknown")
                        console.print(f"  {i+1}. {memory_id} - {memory_file}")
                else:
                    # Backward compatibility
                    index = self._load_index()
                    memory_file = index.get('mappings', {}).get(memory_ids, "Unknown")
                    console.print(f"  1. {memory_ids} - {memory_file}")
                
                console.print()
        else:
            # Show memories for specific agent
            agent_identifier = " ".join(args)
            agent_name = self._resolve_agent_name(agent_identifier)
            
            if not agent_name:
                console.print(f"[red]Error: Could not resolve agent '{agent_identifier}'[/red]")
                return False
            
            if agent_name not in APPLIED_MEMORY_IDS:
                console.print(f"[yellow]No memories applied to '{agent_name}'[/yellow]")
                return True
            
            memory_ids = APPLIED_MEMORY_IDS[agent_name]
            summaries = COMPACTED_SUMMARIES.get(agent_name, [])
            
            console.print(f"[bold cyan]Memories applied to {agent_name}[/bold cyan]\n")
            
            if isinstance(memory_ids, list):
                for i, memory_id in enumerate(memory_ids):
                    # Get memory details
                    index = self._load_index()
                    memory_file = index.get('mappings', {}).get(memory_id, "Unknown")
                    
                    # Show summary preview
                    summary_preview = ""
                    if isinstance(summaries, list) and i < len(summaries):
                        summary_preview = summaries[i][:100] + "..." if len(summaries[i]) > 100 else summaries[i]
                    
                    console.print(f"[green]{i+1}. {memory_id}[/green] - {memory_file}")
                    if summary_preview:
                        console.print(f"   [dim]{summary_preview}[/dim]")
                    console.print()
            else:
                # Backward compatibility
                index = self._load_index()
                memory_file = index.get('mappings', {}).get(memory_ids, "Unknown")
                console.print(f"[green]1. {memory_ids}[/green] - {memory_file}")
                if isinstance(summaries, str) and summaries:
                    summary_preview = summaries[:100] + "..." if len(summaries) > 100 else summaries
                    console.print(f"   [dim]{summary_preview}[/dim]")
        
        return True


# Global instance for access from other modules
MEMORY_COMMAND_INSTANCE = MemoryCommand()

# Register the command
register_command(MEMORY_COMMAND_INSTANCE)


def get_compacted_summary(agent_name: Optional[str] = None) -> Optional[str]:
    """Get compacted summary for injection into system prompt.
    
    This retrieves any applied memory summaries for the agent.
    Now supports multiple memories per agent.
    
    Args:
        agent_name: Specific agent name or None for global summary
        
    Returns:
        Summary text if available, None otherwise
    """
    # First check for applied memories in COMPACTED_SUMMARIES
    if agent_name and agent_name in COMPACTED_SUMMARIES:
        summaries = COMPACTED_SUMMARIES[agent_name]
        if isinstance(summaries, list) and summaries:
            # Concatenate multiple memories with clear separators
            memory_ids = APPLIED_MEMORY_IDS.get(agent_name, [])
            parts = []
            for i, summary in enumerate(summaries):
                memory_id = memory_ids[i] if i < len(memory_ids) else "Unknown"
                parts.append(f"Memory {i+1}/{len(summaries)} (ID: {memory_id}):\n{summary}")
            return "\n\n---\n\n".join(parts)
        elif isinstance(summaries, str):
            # Backward compatibility for single memory
            return summaries
    
    # NEW: For parallel agents, try to find memory under base name
    # Example: "Bug bounty Triage Agent #1" -> "Bug bounty Triage Agent"
    if agent_name and " #" in agent_name:
        base_name = agent_name.split(" #")[0]
        if base_name in COMPACTED_SUMMARIES:
            summaries = COMPACTED_SUMMARIES[base_name]
            if isinstance(summaries, list) and summaries:
                # Concatenate multiple memories with clear separators
                memory_ids = APPLIED_MEMORY_IDS.get(base_name, [])
                parts = []
                for i, summary in enumerate(summaries):
                    memory_id = memory_ids[i] if i < len(memory_ids) else "Unknown"
                    parts.append(f"Memory {i+1}/{len(summaries)} (ID: {memory_id}):\n{summary}")
                return "\n\n---\n\n".join(parts)
            elif isinstance(summaries, str):
                # Backward compatibility for single memory
                return summaries
    elif "__global__" in COMPACTED_SUMMARIES:
        global_summaries = COMPACTED_SUMMARIES["__global__"]
        if isinstance(global_summaries, list) and global_summaries:
            return "\n\n---\n\n".join(global_summaries)
        elif isinstance(global_summaries, str):
            return global_summaries
    
    # Optionally, could auto-load the most recent memory for this agent
    # but for now we require explicit application
    return None


def get_applied_memory_id(agent_name: str) -> Optional[str]:
    """Get the ID of the memory currently applied to an agent.
    
    For backward compatibility, returns first memory ID if multiple exist.
    
    Args:
        agent_name: The agent name to check
        
    Returns:
        Memory ID if applied, None otherwise
    """
    memory_ids = APPLIED_MEMORY_IDS.get(agent_name)
    if isinstance(memory_ids, list) and memory_ids:
        return memory_ids[0]  # Return first for backward compatibility
    elif isinstance(memory_ids, str):
        return memory_ids
    return None


def get_applied_memory_ids(agent_name: str) -> List[str]:
    """Get all memory IDs currently applied to an agent.
    
    Args:
        agent_name: The agent name to check
        
    Returns:
        List of memory IDs if applied, empty list otherwise
    """
    memory_ids = APPLIED_MEMORY_IDS.get(agent_name, [])
    if isinstance(memory_ids, list):
        return memory_ids
    elif isinstance(memory_ids, str):
        return [memory_ids]  # Convert single ID to list
    return []