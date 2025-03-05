"""
Help command for CAI REPL.
This module provides commands for displaying help information.
"""
from typing import List, Optional
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
except ImportError as exc:
    raise ImportError(
        "The 'rich' package is required. Please install it with: "
        "pip install rich"
    ) from exc

from cai.repl.commands.base import (
    Command,
    register_command,
    COMMANDS,
    COMMAND_ALIASES
)

try:
    from cai import is_caiextensions_platform_available
    from caiextensions.platform.base.platform_manager import PlatformManager
    HAS_PLATFORM_EXTENSIONS = True
except ImportError:
    HAS_PLATFORM_EXTENSIONS = False

console = Console()


def create_styled_table(
    title: str,
    headers: List[tuple[str, str]],
    header_style: str = "bold white"
) -> Table:
    """Create a styled table with consistent formatting.

    Args:
        title: The table title
        headers: List of (header_name, style) tuples
        header_style: Style for the header row

    Returns:
        A configured Table instance
    """
    table = Table(
        title=title,
        show_header=True,
        header_style=header_style
    )
    for header, style in headers:
        table.add_column(header, style=style)
    return table


def create_notes_panel(
    notes: List[str],
    title: str = "Notes",
    border_style: str = "yellow"
) -> Panel:
    """Create a notes panel with consistent formatting.

    Args:
        notes: List of note strings
        title: Panel title
        border_style: Style for the panel border

    Returns:
        A configured Panel instance
    """
    notes_text = Text.from_markup(
        "\n".join(f"• {note}" for note in notes)
    )
    return Panel(
        notes_text,
        title=title,
        border_style=border_style
    )


class HelpCommand(Command):
    """Command for displaying help information."""

    def __init__(self):
        """Initialize the help command."""
        super().__init__(
            name="/help",
            description=(
                "Display help information about commands "
                "and features"
            ),
            aliases=["/h"]
        )

        # Add subcommands
        self.add_subcommand(
            "memory",
            "Display help for memory commands",
            self.handle_memory
        )
        self.add_subcommand(
            "agents",
            "Display help for agent commands",
            self.handle_agents
        )
        self.add_subcommand(
            "graph",
            "Display help for graph commands",
            self.handle_graph
        )
        self.add_subcommand(
            "platform",
            "Display help for platform commands",
            self.handle_platform
        )
        self.add_subcommand(
            "shell",
            "Display help for shell commands",
            self.handle_shell
        )
        self.add_subcommand(
            "env",
            "Display help for environment commands",
            self.handle_env
        )
        self.add_subcommand(
            "aliases",
            "Display command aliases",
            self.handle_aliases
        )
        self.add_subcommand(
            "model",
            "Display help for model commands",
            self.handle_model
        )
        self.add_subcommand(
            "turns",
            "Display help for turns commands",
            self.handle_turns
        )
        self.add_subcommand(
            "config",
            "Display help for config commands",
            self.handle_config
        )

    def handle_memory(self, _: Optional[List[str]] = None) -> bool:
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

    def handle_agents(self, _: Optional[List[str]] = None) -> bool:
        """Show help for agent-related features."""
        console.print(Panel(
            "Agents are autonomous AI assistants that can perform specific "
            "tasks.\n\n"
            "[bold]Available Commands:[/bold]\n"
            "• [yellow]/agent list[/yellow] - List all available agents\n"
            "• [yellow]/agent use <n>[/yellow] - Switch to a specific agent\n"
            "• [yellow]/agent info <n>[/yellow] - Show details about an "
            "agent\n\n"
            "[bold]Examples:[/bold]\n"
            "• [green]/agent use boot2root_agent[/green] - Switch to the CLI "
            "security testing agent\n"
            "• [green]/agent use dns_smtp_agent[/green] - Switch to the "
            "DNS/SMTP reconnaissance agent",
            title="Agent Commands",
            border_style="blue"
        ))
        return True

    def handle_graph(self, _: Optional[List[str]] = None) -> bool:
        """Show help for graph visualization."""
        console.print(Panel(
            "Graph visualization helps you understand the relationships "
            "between different pieces of information in your session.\n\n"
            "[bold]Available Commands:[/bold]\n"
            "• [yellow]/graph show[/yellow] - Display the current memory "
            "graph\n"
            "• [yellow]/graph export <filename>[/yellow] - Export graph to a "
            "file\n"
            "• [yellow]/graph focus <node_id>[/yellow] - Focus on a specific "
            "node\n\n"
            "[bold]Examples:[/bold]\n"
            "• [green]/graph show[/green] - Display the current memory graph\n"
            "• [green]/graph export session_graph.png[/green] - Save graph "
            "as PNG",
            title="Graph Visualization Commands",
            border_style="blue"
        ))
        return True

    def handle_platform(self, _: Optional[List[str]] = None) -> bool:
        """Show help for platform-specific features."""
        platform_cmd = next(
            (cmd for cmd in COMMANDS.values() if cmd.name == "/platform"),
            None
        )

        if platform_cmd and hasattr(platform_cmd, 'show_help'):
            platform_cmd.show_help()
            return True

        console.print(Panel(
            "Platform commands provide access to platform-specific "
            "features.\n\n"
            "[bold]Available Commands:[/bold]\n"
            "• [yellow]/platform list[/yellow] - List available platforms\n"
            "• [yellow]/platform <platform> <command>[/yellow] - Run "
            "platform-specific command\n\n"
            "[bold]Examples:[/bold]\n"
            "• [green]/platform list[/green] - Show all available platforms\n"
            "• [green]/p list[/green] - Shorthand for platform list",
            title="Platform Commands",
            border_style="blue"
        ))
        return True

    def handle_shell(self, _: Optional[List[str]] = None) -> bool:
        """Show help for shell command execution."""
        console.print(Panel(
            "Shell commands allow you to execute system commands directly.\n\n"
            "[bold]Available Commands:[/bold]\n"
            "• [yellow]/shell <command>[/yellow] - Execute a shell command\n"
            "• [yellow]/![/yellow] - Shorthand for /shell\n\n"
            "[bold]Session Management:[/bold]\n"
            "• [yellow]/shell session list[/yellow] - List active sessions\n"
            "• [yellow]/shell session output <id>[/yellow] - Get output from "
            "a session\n"
            "• [yellow]/shell session kill <id>[/yellow] - Terminate a "
            "session\n\n"
            "[bold]Examples:[/bold]\n"
            "• [green]/shell ls -la[/green] - List files in current "
            "directory\n"
            "• [green]/! pwd[/green] - Show current working directory",
            title="Shell Commands",
            border_style="blue"
        ))
        return True

    def handle_env(self, _: Optional[List[str]] = None) -> bool:
        """Show help for environment variables."""
        console.print(Panel(
            "Environment variables control CAI's behavior.\n\n"
            "[bold]Key Variables:[/bold]\n"
            "• [yellow]CAI_MODEL[/yellow] - Default AI model (e.g., "
            "'claude-3-7-sonnet-20250219')\n"
            "• [yellow]CAI_MEMORY_DIR[/yellow] - Directory for storing memory "
            "collections\n"
            "• [yellow]OPENAI_API_KEY[/yellow] - API key for OpenAI models\n"
            "• [yellow]ANTHROPIC_API_KEY[/yellow] - API key for Anthropic "
            "models\n\n"
            "[bold]Available Commands:[/bold]\n"
            "• [yellow]/env list[/yellow] - Show all environment variables\n"
            "• [yellow]/env set <n> <value>[/yellow] - Set an environment "
            "variable\n"
            "• [yellow]/env get <n>[/yellow] - Get the value of an "
            "environment variable",
            title="Environment Variables",
            border_style="blue"
        ))
        return True

    def handle_aliases(self, _: Optional[List[str]] = None) -> bool:
        """Show all command aliases."""
        return self.handle_help_aliases()

    def handle_model(self, _: Optional[List[str]] = None) -> bool:
        """Show help for model selection."""
        return self.handle_help_model()

    def handle_turns(self, _: Optional[List[str]] = None) -> bool:
        """Show help for managing turns."""
        return self.handle_help_turns()

    def handle_config(self, _: Optional[List[str]] = None) -> bool:
        """Display help for config commands.

        Args:
            _: Ignored arguments

        Returns:
            True if successful
        """
        return self.handle_help_config()

    def handle_no_args(self) -> bool:
        """Handle the command when no arguments are provided."""
        return self.handle_help()

    def _print_command_table(
        self,
        title: str,
        commands: List[tuple[str, str, str]],
        header_style: str = "bold yellow",
        command_style: str = "yellow"
    ) -> None:
        """Print a table of commands with consistent formatting."""
        table = create_styled_table(
            title,
            [
                ("Command", command_style),
                ("Alias", "green"),
                ("Description", "white")
            ],
            header_style
        )

        for cmd, alias, desc in commands:
            table.add_row(cmd, alias, desc)

        console.print(table)

    def handle_help(self) -> bool:
        """Display general help information.

        Returns:
            True if successful
        """
        console.print(
            Panel(
                Text.from_markup(
                    "Welcome to the CAI help system. "
                    "This system provides information about "
                    "available commands and features."
                ),
                title="CAI Help",
                border_style="yellow"
            )
        )

        # Memory Commands
        memory_commands = [
            ("/memory list", "/m list",
             "List all available memory collections"),
            ("/memory load <collection>", "/m load <collection>",
             "Load a memory collection"),
            ("/memory delete <collection>", "/m delete <collection>",
             "Delete a memory collection"),
            ("/memory create <collection>", "/m create <collection>",
             "Create a new memory collection")
        ]
        self._print_command_table("Memory Commands", memory_commands)

        # Collection types info
        collection_info = Text()
        collection_info.append("\nCollection Types:\n", style="bold")
        collection_info.append("• CTF_NAME", style="yellow")
        collection_info.append(
            " - Episodic memory for a specific CTF (e.g. ",
            style="white"
        )
        collection_info.append("baby_first", style="bold white")
        collection_info.append(")\n", style="white")
        collection_info.append("• _all_", style="yellow")
        collection_info.append(
            " - Semantic memory across all CTFs",
            style="white"
        )
        console.print(collection_info)

        # Graph Commands
        graph_commands = [
            ("/graph", "/g",
             "Show the graph of the current memory collection")
        ]
        self._print_command_table(
            "Graph Commands",
            graph_commands,
            "bold blue",
            "blue"
        )

        # Shell Commands
        shell_commands = [
            ("/shell <command>", "/s <command>",
             "Execute a shell command (can be interrupted with CTRL+C)")
        ]
        self._print_command_table(
            "Shell Commands",
            shell_commands,
            "bold green",
            "green"
        )

        # Config Commands
        config_commands = [
            ("/config", "/cfg",
             "List all environment variables and their values"),
            ("/config list", "/cfg list",
             "List all environment variables and their values"),
            ("/config get <number>", "/cfg get <number>",
             "Get the value of a specific environment variable"),
            ("/config set <number> <value>", "/cfg set <number> <value>",
             "Set the value of a specific environment variable")
        ]
        self._print_command_table(
            "Config Commands",
            config_commands,
            "bold magenta",
            "magenta"
        )

        # Environment Commands
        env_commands = [
            ("/env", "/e",
             "Display environment variables (CAI_* and CTF_*)")
        ]
        self._print_command_table(
            "Environment Commands",
            env_commands,
            "bold cyan",
            "cyan"
        )

        # Model Commands
        model_commands = [
            ("/model", "/mod",
             "Display current model and list available models"),
            ("/model <model_name>", "/mod <model_name>",
             "Change the model to <model_name>")
        ]
        self._print_command_table(
            "Model Commands",
            model_commands,
            "bold magenta",
            "magenta"
        )

        # Turns Commands
        turns_commands = [
            ("/turns", "/t", "Display current maximum number of turns"),
            ("/turns <number>", "/t <number>",
             "Change the maximum number of turns")
        ]
        self._print_command_table(
            "Turns Commands",
            turns_commands,
            "bold magenta",
            "magenta"
        )

        # Platform Commands
        self.handle_help_platform_manager()

        # Tips section
        tips = Panel(
            Text.from_markup(
                "Tips:\n"
                "• Use [bold]Tab[/bold] for command completion\n"
                "• Use [bold]↑/↓[/bold] to navigate command history\n"
                "• Use [bold]Ctrl+L[/bold] to clear the screen\n"
                "• Most commands have shorter aliases (e.g. [bold]/h[/bold] "
                "instead of [bold]/help[/bold])"
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
                title="Aliases"
            )
        )

        # Create a table for aliases
        alias_table = create_styled_table(
            "Command Aliases",
            [
                ("Alias", "green"),
                ("Command", "yellow"),
                ("Description", "white")
            ],
            "bold magenta"
        )

        # Add rows for each alias
        for alias, command in sorted(COMMAND_ALIASES.items()):
            cmd = COMMANDS.get(command)
            description = cmd.description if cmd else ""
            alias_table.add_row(alias, command, description)

        console.print(alias_table)

        # Add tips
        tips = [
            "Aliases can be used anywhere the full command would be used",
            (
                "Example: [green]/m list[/green] instead of "
                "[yellow]/memory list[/yellow]"
            )
        ]
        console.print("\n")
        console.print(create_notes_panel(tips, "Tips", "cyan"))

        return True

    def handle_help_memory(self) -> bool:
        """Show help for memory commands with rich formatting."""
        # Create a styled header
        header = Text("Memory Command Help", style="bold yellow")
        console.print(Panel(header, border_style="yellow"))

        # Usage table
        usage_table = create_styled_table(
            "Usage",
            [("Command", "yellow"), ("Description", "white")]
        )

        usage_table.add_row(
            "/memory list",
            "Display all available memory collections"
        )
        usage_table.add_row(
            "/memory load <collection>",
            "Set the active memory collection"
        )
        usage_table.add_row(
            "/memory delete <collection>",
            "Delete a memory collection"
        )
        usage_table.add_row(
            "/memory create <collection>",
            "Create a new memory collection"
        )
        usage_table.add_row("/m", "Alias for /memory")

        console.print(usage_table)

        # Examples table
        examples_table = create_styled_table(
            "Examples",
            [("Example", "cyan"), ("Description", "white")],
            "bold cyan"
        )

        examples = [
            ("/memory list", "List all available collections"),
            ("/memory load _all_", "Load the semantic memory collection"),
            ("/memory load my_ctf", "Load the episodic memory for 'my_ctf'"),
            (
                "/memory create new_collection",
                "Create a new collection named 'new_collection'"
            ),
            (
                "/memory delete old_collection",
                "Delete the collection named 'old_collection'"
            )
        ]

        for example, desc in examples:
            examples_table.add_row(example, desc)

        console.print(examples_table)

        # Collection types table
        types_table = create_styled_table(
            "Collection Types",
            [("Type", "green"), ("Description", "white")],
            "bold green"
        )

        types = [
            ("_all_", "Semantic memory across all CTFs"),
            ("<CTF_NAME>", "Episodic memory for a specific CTF"),
            ("<custom_name>", "Custom memory collection")
        ]

        for type_name, desc in types:
            types_table.add_row(type_name, desc)

        console.print(types_table)

        # Notes panel
        notes = [
            "Memory collections are stored in the Qdrant vector database",
            "The active collection is stored in the CAI_MEMORY_COLLECTION "
            "env var",
            "Episodic memory is used for specific CTFs or tasks",
            "Semantic memory (_all_) is used across all CTFs",
            "Memory is used to provide context to the agent"
        ]

        console.print(create_notes_panel(notes))

        return True

    def handle_help_model(self) -> bool:
        """Show help for model command with rich formatting."""
        # Create a styled header
        header = Text("Model Command Help", style="bold magenta")
        console.print(Panel(header, border_style="magenta"))

        # Usage table
        usage_table = create_styled_table(
            "Usage",
            [("Command", "magenta"), ("Description", "white")]
        )

        usage_commands = [
            ("/model", "Display current model and list available models"),
            ("/model <model_name>", "Change the model to <model_name>"),
            (
                "/model <number>",
                "Change the model using its number from the list"
            ),
            ("/mod", "Alias for /model")
        ]

        for cmd, desc in usage_commands:
            usage_table.add_row(cmd, desc)

        console.print(usage_table)

        # Examples table
        examples_table = create_styled_table(
            "Examples",
            [("Example", "cyan"), ("Description", "white")],
            "bold cyan"
        )

        examples = [
            (
                "/model 1",
                "Switch to the first model in the list (Claude 3.7 Sonnet)"
            ),
            (
                "/model claude-3-7-sonnet-20250219",
                "Switch to Claude 3.7 Sonnet model"
            ),
            (
                "/model o1",
                "Switch to OpenAI's O1 model (good for math)"
            ),
            (
                "/model gpt-4o",
                "Switch to OpenAI's GPT-4o model"
            )
        ]

        for example, desc in examples:
            examples_table.add_row(example, desc)

        console.print(examples_table)

        # Model categories table
        categories_table = create_styled_table(
            "Model Categories",
            [("Category", "green"), ("Description", "white")],
            "bold green"
        )

        categories = [
            (
                "Claude 3.7",
                "Best models for complex reasoning and creative tasks"
            ),
            (
                "Claude 3.5",
                "Excellent balance of performance and efficiency"
            ),
            (
                "Claude 3",
                "Range of models from powerful (Opus) to fast (Haiku)"
            ),
            (
                "OpenAI O-series",
                "Specialized models with strong mathematical capabilities"
            ),
            (
                "OpenAI GPT-4",
                "Powerful general-purpose models"
            ),
            (
                "Ollama",
                "Local models running on your machine or Docker container"
            )
        ]

        for category, desc in categories:
            categories_table.add_row(category, desc)

        console.print(categories_table)

        # Notes panel
        notes = [
            "The model change takes effect on the next agent interaction",
            "The model is stored in the CAI_MODEL environment variable",
            "Some models may require specific API keys to be set",
            "OpenAI models require OPENAI_API_KEY to be set",
            "Anthropic models require ANTHROPIC_API_KEY to be set",
            "Ollama models require Ollama to be running locally",
            (
                "Ollama is configured to run on "
                "host.docker.internal:8000"
            )
        ]

        console.print(create_notes_panel(notes))

        return True

    def handle_help_turns(self) -> bool:
        """Show help for turns command with rich formatting."""
        # Create a styled header
        header = Text("Turns Command Help", style="bold magenta")
        console.print(Panel(header, border_style="magenta"))

        # Usage table
        usage_table = create_styled_table(
            "Usage",
            [("Command", "magenta"), ("Description", "white")]
        )

        usage_commands = [
            ("/turns", "Display current maximum number of turns"),
            ("/turns <number>", "Change the maximum number of turns"),
            ("/turns inf", "Set unlimited turns"),
            ("/t", "Alias for /turns")
        ]

        for cmd, desc in usage_commands:
            usage_table.add_row(cmd, desc)

        console.print(usage_table)

        # Examples table
        examples_table = create_styled_table(
            "Examples",
            [("Example", "cyan"), ("Description", "white")],
            "bold cyan"
        )

        examples = [
            ("/turns", "Show current maximum turns"),
            ("/turns 10", "Set maximum turns to 10"),
            ("/turns inf", "Set unlimited turns"),
            ("/t 5", "Set maximum turns to 5 (using alias)")
        ]

        for example, desc in examples:
            examples_table.add_row(example, desc)

        console.print(examples_table)

        # Notes panel
        notes = [
            (
                "The maximum turns limit controls how many responses the "
                "agent will give"
            ),
            "Setting turns to 'inf' allows unlimited responses",
            (
                "The turns count is stored in the CAI_MAX_TURNS "
                "environment variable"
            ),
            "Each agent response counts as one turn"
        ]

        console.print(create_notes_panel(notes))

        return True

    def handle_help_platform_manager(self) -> bool:
        """Show help for platform manager commands."""
        if HAS_PLATFORM_EXTENSIONS and is_caiextensions_platform_available():
            try:
                from caiextensions.platform.base import platform_manager
                platforms = platform_manager.list_platforms()

                if not platforms:
                    console.print(
                        "[yellow]No platforms registered.[/yellow]"
                    )
                    return True

                platform_table = create_styled_table(
                    "Available Platforms",
                    [
                        ("Platform", "magenta"),
                        ("Description", "white")
                    ],
                    "bold magenta"
                )

                for platform_name in platforms:
                    platform = platform_manager.get_platform(platform_name)
                    description = getattr(
                        platform, 'description', platform_name.capitalize())
                    platform_table.add_row(
                        platform_name,
                        description
                    )

                console.print(platform_table)

                # Add platform command examples
                examples = []
                for platform_name in platforms:
                    platform = platform_manager.get_platform(platform_name)
                    commands = platform.get_commands()
                    if commands:
                        examples.append(
                            f"[green]/platform {platform_name} {
                                commands[0]}[/green] - Example {platform_name} command")

                if examples:
                    console.print(Panel(
                        "\n".join(examples),
                        title="Platform Command Examples",
                        border_style="blue"
                    ))

                return True
            except (ImportError, Exception) as e:
                console.print(
                    f"[yellow]Error loading platforms: {e}[/yellow]"
                )
                return True

        console.print(
            "[yellow]No platform extensions available.[/yellow]"
        )
        return True

    def handle_help_config(self) -> bool:
        """Display help for config commands.

        Returns:
            True if successful
        """
        console.print(
            Panel(
                Text.from_markup(
                    "The [bold yellow]/config[/bold yellow] command allows you"
                    "to view and configure environment variables that control"
                    "the behavior of CAI."
                ),
                title="Config Commands",
                border_style="yellow"
            )
        )

        # Create table for subcommands
        table = create_styled_table(
            "Available Subcommands",
            [("Command", "yellow"), ("Description", "white")]
        )

        table.add_row(
            "/config",
            "List all environment variables and their current values"
        )
        table.add_row(
            "/config list",
            "List all environment variables and their current values"
        )
        table.add_row(
            "/config get <number>",
            "Get the value of a specific environment variable by its number"
        )
        table.add_row(
            "/config set <number> <value>",
            "Set the value of a specific environment variable by its number"
        )

        console.print(table)

        # Create notes panel
        notes = [
            "Environment variables control various aspects of CAI behavior.",
            "Changes environment variables only affect the current session.",
            "Use the [yellow]/config list[/yellow] command to see options.",
            "Each variable is assigned a number for easy reference."
        ]
        console.print(create_notes_panel(notes))

        return True


# Register the command
register_command(HelpCommand())
