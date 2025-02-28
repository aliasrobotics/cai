"""
Help command for CAI REPL.
This module provides commands for displaying help information.
"""
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from cai.repl.commands.base import Command, register_command, COMMANDS, COMMAND_ALIASES

console = Console()


class HelpCommand(Command):
    """Command for displaying help information."""

    def __init__(self):
        """Initialize the help command."""
        super().__init__(
            name="/help",
            description="Display help information about commands and features",
            aliases=["/h"]
        )

        # Add subcommands
        self.add_subcommand(
            "memory",
            "Show help for memory commands",
            self.handle_memory)
        self.add_subcommand(
            "agents",
            "Show help for agent-related features",
            self.handle_agents)
        self.add_subcommand(
            "graph",
            "Show help for graph visualization",
            self.handle_graph)
        self.add_subcommand(
            "platform",
            "Show help for platform-specific features",
            self.handle_platform)
        self.add_subcommand(
            "shell",
            "Show help for shell command execution",
            self.handle_shell)
        self.add_subcommand(
            "env",
            "Show help for environment variables",
            self.handle_env)
        self.add_subcommand(
            "aliases",
            "Show all command aliases",
            self.handle_aliases)
        self.add_subcommand(
            "model",
            "Show help for model selection",
            self.handle_model)
        self.add_subcommand(
            "turns",
            "Show help for managing turns",
            self.handle_turns)

    def handle_memory(self, args: Optional[List[str]] = None) -> bool:
        """Show help for memory commands."""
        # Get the memory command and show its help
        memory_cmd = next((cmd for cmd in COMMANDS.values()
                          if cmd.name == "/memory"), None)
        if memory_cmd and hasattr(memory_cmd, 'show_help'):
            memory_cmd.show_help()
            return True

        # Fallback if memory command not found or doesn't have show_help
        self.handle_help_memory()
        return True

    def handle_agents(self, args: Optional[List[str]] = None) -> bool:
        """Show help for agent-related features."""
        # TODO: Implement agent help
        console.print("[yellow]Agent help not implemented yet[/yellow]")
        return True

    def handle_graph(self, args: Optional[List[str]] = None) -> bool:
        """Show help for graph visualization."""
        # TODO: Implement graph help
        console.print("[yellow]Graph help not implemented yet[/yellow]")
        return True

    def handle_platform(self, args: Optional[List[str]] = None) -> bool:
        """Show help for platform-specific features."""
        # TODO: Implement platform help
        console.print("[yellow]Platform help not implemented yet[/yellow]")
        return True

    def handle_shell(self, args: Optional[List[str]] = None) -> bool:
        """Show help for shell command execution."""
        # TODO: Implement shell help
        console.print("[yellow]Shell help not implemented yet[/yellow]")
        return True

    def handle_env(self, args: Optional[List[str]] = None) -> bool:
        """Show help for environment variables."""
        # TODO: Implement env help
        console.print(
            "[yellow]Environment variables help not implemented yet[/yellow]")
        return True

    def handle_aliases(self, args: Optional[List[str]] = None) -> bool:
        """Show all command aliases."""
        return self.handle_help_aliases()

    def handle_model(self, args: Optional[List[str]] = None) -> bool:
        """Show help for model selection."""
        return self.handle_help_model()

    def handle_turns(self, args: Optional[List[str]] = None) -> bool:
        """Show help for managing turns."""
        return self.handle_help_turns()

    def handle_no_args(self) -> bool:
        """Handle the command when no arguments are provided."""
        return self.handle_help()

    def handle_help(self) -> bool:
        """Handle /help command with improved formatting and details."""
        # Create a styled header
        header = Text("CAI Command Reference", style="bold cyan")
        console.print(Panel(header, border_style="cyan"))

        # Memory Commands Table
        memory_table = Table(
            title="Memory Commands",
            show_header=True,
            header_style="bold yellow")
        memory_table.add_column("Command", style="yellow")
        memory_table.add_column("Alias", style="green")
        memory_table.add_column("Description", style="white")

        memory_table.add_row(
            "/memory list",
            "/m list",
            "List all memory collections")
        memory_table.add_row(
            "/memory load <collection>",
            "/m load <collection>",
            "Load a memory collection")
        memory_table.add_row(
            "/memory delete <collection>",
            "/m delete <collection>",
            "Delete a memory collection")
        memory_table.add_row(
            "/memory create <collection>",
            "/m create <collection>",
            "Create a new memory collection")

        # Collection types info
        collection_info = Text()
        collection_info.append("\nCollection Types:\n", style="bold")
        collection_info.append("• CTF_NAME", style="yellow")
        collection_info.append(
            " - Episodic memory for a specific CTF (e.g. ", style="white")
        collection_info.append("baby_first", style="bold white")
        collection_info.append(")\n", style="white")
        collection_info.append("• _all_", style="yellow")
        collection_info.append(
            " - Semantic memory across all CTFs",
            style="white")

        console.print(memory_table)
        console.print(collection_info)

        # Graph Commands Table
        graph_table = Table(
            title="Graph Commands",
            show_header=True,
            header_style="bold blue")
        graph_table.add_column("Command", style="blue")
        graph_table.add_column("Alias", style="green")
        graph_table.add_column("Description", style="white")

        graph_table.add_row(
            "/graph",
            "/g",
            "Show the graph of the current memory collection")
        console.print(graph_table)

        # Shell Commands Table
        shell_table = Table(
            title="Shell Commands",
            show_header=True,
            header_style="bold green")
        shell_table.add_column("Command", style="green")
        shell_table.add_column("Alias", style="green")
        shell_table.add_column("Description", style="white")

        shell_table.add_row(
            "/shell <command>",
            "/s <command>",
            "Execute a shell command (can be interrupted with CTRL+C)")
        console.print(shell_table)

        # Environment Commands Table
        env_table = Table(
            title="Environment Commands",
            show_header=True,
            header_style="bold cyan")
        env_table.add_column("Command", style="cyan")
        env_table.add_column("Alias", style="green")
        env_table.add_column("Description", style="white")

        env_table.add_row(
            "/env",
            "/e",
            "Display environment variables (CAI_* and CTF_*)")
        console.print(env_table)

        # Model Commands Table
        model_table = Table(
            title="Model Commands",
            show_header=True,
            header_style="bold magenta")
        model_table.add_column("Command", style="magenta")
        model_table.add_column("Alias", style="green")
        model_table.add_column("Description", style="white")

        model_table.add_row(
            "/model",
            "/mod",
            "Display current model and list available models")
        model_table.add_row(
            "/model <model_name>",
            "/mod <model_name>",
            "Change the model to <model_name>")
        console.print(model_table)

        # Turns Commands Table
        turns_table = Table(
            title="Turns Commands",
            show_header=True,
            header_style="bold magenta")
        turns_table.add_column("Command", style="magenta")
        turns_table.add_column("Alias", style="green")
        turns_table.add_column("Description", style="white")

        turns_table.add_row(
            "/turns",
            "/t",
            "Display current maximum number of turns")
        turns_table.add_row(
            "/turns <number>",
            "/t <number>",
            "Change the maximum number of turns")
        turns_table.add_row("/turns inf", "/t inf", "Set unlimited turns")
        console.print(turns_table)

        # Exit Commands Table
        exit_table = Table(
            title="Exit Commands",
            show_header=True,
            header_style="bold red")
        exit_table.add_column("Command", style="red")
        exit_table.add_column("Alias", style="green")
        exit_table.add_column("Description", style="white")

        exit_table.add_row("/exit", "/q", "Exit CAI")
        exit_table.add_row("", "/quit", "Exit CAI (alias)")
        console.print(exit_table)

        # Help Commands Table
        help_table = Table(
            title="Help Commands",
            show_header=True,
            header_style="bold grey70")
        help_table.add_column("Command", style="grey70")
        help_table.add_column("Alias", style="green")
        help_table.add_column("Description", style="white")

        help_table.add_row("/help", "/h", "Display this help information")
        help_table.add_row(
            "/help aliases",
            "/h aliases",
            "Show all command aliases")
        help_table.add_row(
            "/help model",
            "/h model",
            "Show detailed help for model selection")
        help_table.add_row(
            "/help turns",
            "/h turns",
            "Show detailed help for managing turns")
        console.print(help_table)

        # Platform Commands Table (if available)
        from cai import is_caiextensions_platform_available
        if is_caiextensions_platform_available():
            from caiextensions.platform.base import platform_manager

            platform_table = Table(
                title="Platform Commands",
                show_header=True,
                header_style="bold grey70")
            platform_table.add_column("Command", style="grey70")
            platform_table.add_column("Alias", style="green")
            platform_table.add_column("Description", style="white")

            platform_table.add_row(
                "/platform", "/p", "Show all available platforms")
            platform_table.add_row(
                "/platform list",
                "/p list",
                "List available platforms")

            # Add platform-specific commands if available
            platforms = platform_manager.list_platforms()
            for platform in platforms:
                platform_cmds = platform_manager.get_platform(
                    platform).get_commands()
                for cmd in platform_cmds:
                    platform_table.add_row(f"/platform {platform} {cmd}", f"/p {platform} {cmd}",
                                           f"Execute '{cmd}' command on {platform} platform")

            console.print(platform_table)

        # Tips section
        tips = Panel(
            Text.from_markup(
                "[bold cyan]Tips:[/bold cyan]\n"
                "• Use [bold]Tab[/bold] for command completion\n"
                "• Use [bold]↑/↓[/bold] to navigate command history\n"
                "• Use [bold]Ctrl+L[/bold] to clear the screen\n"
                "• Most commands have shorter aliases (e.g. [bold]/h[/bold] instead of [bold]/help[/bold])"
            ),
            title="Helpful Tips",
            border_style="cyan"
        )
        console.print(tips)

        return True

    def handle_help_aliases(self) -> bool:
        """Show all command aliases in a well-formatted table."""
        # Create a styled header
        console.print(
            Panel(
                "Command Aliases Reference",
                border_style="magenta",
                title="Aliases"))

        # Create a table for aliases
        alias_table = Table(show_header=True, header_style="bold magenta")
        alias_table.add_column("Alias", style="green")
        alias_table.add_column("Command", style="yellow")
        alias_table.add_column("Description", style="white")

        # Add rows for each alias
        for alias, command in sorted(COMMAND_ALIASES.items()):
            cmd = COMMANDS.get(command)
            description = cmd.description if cmd else ""
            alias_table.add_row(alias, command, description)

        console.print(alias_table)

        # Add a tip about using aliases
        console.print(
            "\n[cyan]Tip:[/cyan] Aliases can be used anywhere the full command would be used.")
        console.print(
            "[cyan]Example:[/cyan] [green]/m list[/green] instead of [yellow]/memory list[/yellow]")

        return True

    def handle_help_memory(self) -> bool:
        """Show help for memory commands with rich formatting."""
        # Create a styled header
        header = Text("Memory Command Help", style="bold yellow")
        console.print(Panel(header, border_style="yellow"))

        # Usage table
        usage_table = Table(
            title="Usage",
            show_header=True,
            header_style="bold white")
        usage_table.add_column("Command", style="yellow")
        usage_table.add_column("Description", style="white")

        usage_table.add_row(
            "/memory list",
            "Display all available memory collections")
        usage_table.add_row(
            "/memory load <collection>",
            "Set the active memory collection")
        usage_table.add_row(
            "/memory delete <collection>",
            "Delete a memory collection")
        usage_table.add_row(
            "/memory create <collection>",
            "Create a new memory collection")
        usage_table.add_row("/m", "Alias for /memory")

        console.print(usage_table)

        # Examples table
        examples_table = Table(
            title="Examples",
            show_header=True,
            header_style="bold cyan")
        examples_table.add_column("Example", style="cyan")
        examples_table.add_column("Description", style="white")

        examples_table.add_row(
            "/memory list",
            "List all available collections")
        examples_table.add_row(
            "/memory load _all_",
            "Load the semantic memory collection")
        examples_table.add_row(
            "/memory load my_ctf",
            "Load the episodic memory for 'my_ctf'")
        examples_table.add_row(
            "/memory create new_collection",
            "Create a new collection named 'new_collection'")
        examples_table.add_row(
            "/memory delete old_collection",
            "Delete the collection named 'old_collection'")

        console.print(examples_table)

        # Collection types table
        types_table = Table(
            title="Collection Types",
            show_header=True,
            header_style="bold green")
        types_table.add_column("Type", style="green")
        types_table.add_column("Description", style="white")

        types_table.add_row("_all_", "Semantic memory across all CTFs")
        types_table.add_row("<CTF_NAME>", "Episodic memory for a specific CTF")
        types_table.add_row("<custom_name>", "Custom memory collection")

        console.print(types_table)

        # Notes panel
        notes = Panel(
            Text.from_markup(
                "• Memory collections are stored in the Qdrant vector database\n"
                "• The active collection is stored in the CAI_MEMORY_COLLECTION environment variable\n"
                "• Episodic memory is used for specific CTFs or tasks\n"
                "• Semantic memory (_all_) is used across all CTFs\n"
                "• Memory is used to provide context to the agent"
            ),
            title="Notes",
            border_style="yellow"
        )
        console.print(notes)

        return True

    def handle_help_model(self) -> bool:
        """Show help for model command with rich formatting."""
        # Create a styled header
        header = Text("Model Command Help", style="bold magenta")
        console.print(Panel(header, border_style="magenta"))

        # Usage table
        usage_table = Table(
            title="Usage",
            show_header=True,
            header_style="bold white")
        usage_table.add_column("Command", style="magenta")
        usage_table.add_column("Description", style="white")

        usage_table.add_row(
            "/model",
            "Display current model and list available models")
        usage_table.add_row(
            "/model <model_name>",
            "Change the model to <model_name>")
        usage_table.add_row(
            "/model <number>",
            "Change the model using its number from the list")
        usage_table.add_row("/mod", "Alias for /model")

        console.print(usage_table)

        # Examples table
        examples_table = Table(
            title="Examples",
            show_header=True,
            header_style="bold cyan")
        examples_table.add_column("Example", style="cyan")
        examples_table.add_column("Description", style="white")

        examples_table.add_row(
            "/model 1",
            "Switch to the first model in the list (Claude 3.7 Sonnet)")
        examples_table.add_row(
            "/model claude-3-7-sonnet-20250219",
            "Switch to Claude 3.7 Sonnet model")
        examples_table.add_row(
            "/model o1",
            "Switch to OpenAI's O1 model (good for math)")
        examples_table.add_row(
            "/model gpt-4o",
            "Switch to OpenAI's GPT-4o model")

        console.print(examples_table)

        # Model categories table
        categories_table = Table(
            title="Model Categories",
            show_header=True,
            header_style="bold green")
        categories_table.add_column("Category", style="green")
        categories_table.add_column("Description", style="white")

        categories_table.add_row(
            "Claude 3.7",
            "Best models for complex reasoning and creative tasks")
        categories_table.add_row(
            "Claude 3.5",
            "Excellent balance of performance and efficiency")
        categories_table.add_row(
            "Claude 3",
            "Range of models from powerful (Opus) to fast (Haiku)")
        categories_table.add_row(
            "OpenAI O-series",
            "Specialized models with strong mathematical capabilities")
        categories_table.add_row(
            "OpenAI GPT-4",
            "Powerful general-purpose models")
        categories_table.add_row(
            "Ollama",
            "Local models running on your machine or Docker container")

        console.print(categories_table)

        # Notes panel
        notes = Panel(
            Text.from_markup(
                "• The model change takes effect on the next agent interaction\n"
                "• The model is stored in the CAI_MODEL environment variable\n"
                "• Some models may require specific API keys to be set\n"
                "• OpenAI models require OPENAI_API_KEY to be set\n"
                "• Anthropic models require ANTHROPIC_API_KEY to be set\n"
                "• Ollama models require Ollama to be running locally\n"
                "• Ollama is configured to run on host.docker.internal:8000"
            ),
            title="Notes",
            border_style="yellow"
        )
        console.print(notes)

        return True

    def handle_help_turns(self) -> bool:
        """Show help for turns command with rich formatting."""
        # Create a styled header
        header = Text("Turns Command Help", style="bold magenta")
        console.print(Panel(header, border_style="magenta"))

        # Usage table
        usage_table = Table(
            title="Usage",
            show_header=True,
            header_style="bold white")
        usage_table.add_column("Command", style="magenta")
        usage_table.add_column("Description", style="white")

        usage_table.add_row(
            "/turns", "Display current maximum number of turns")
        usage_table.add_row(
            "/turns <number>",
            "Change the maximum number of turns to <number>")
        usage_table.add_row("/turns inf", "Set unlimited turns")
        usage_table.add_row("/t", "Alias for /turns")

        console.print(usage_table)

        # Examples table
        examples_table = Table(
            title="Examples",
            show_header=True,
            header_style="bold cyan")
        examples_table.add_column("Example", style="cyan")
        examples_table.add_column("Description", style="white")

        examples_table.add_row("/turns 5", "Limit to 5 turns")
        examples_table.add_row("/turns 10", "Limit to 10 turns")
        examples_table.add_row("/turns inf", "Set unlimited turns")
        examples_table.add_row("/t 3", "Limit to 3 turns (using alias)")

        console.print(examples_table)

        # Notes panel
        notes = Panel(
            Text.from_markup(
                "• The turns setting takes effect on the next run\n"
                "• The setting is stored in the CAI_MAX_TURNS environment variable\n"
                "• Setting a lower number of turns can help control costs\n"
                "• 'inf' represents infinity (unlimited turns)"
            ),
            title="Notes",
            border_style="yellow"
        )
        console.print(notes)

        return True


# Register the command
register_command(HelpCommand())
