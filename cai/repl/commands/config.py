"""
Config command for CAI via environmental variables.
"""
# Standard library imports
import os
from typing import Dict, List, Optional

# Third party imports
from rich.console import Console  # pylint: disable=import-error
from rich.table import Table  # pylint: disable=import-error

# Local imports
from cai.repl.commands.base import Command, register_command

console = Console()

# Define environment variables with descriptions and default values
ENV_VARS = {
    # CTF variables
    1: {
        "name": "CTF_NAME",
        "description": "Name of the CTF challenge to run",
        "default": None
    },
    2: {
        "name": "CTF_CHALLENGE",
        "description": "Specific challenge name within the CTF to test",
        "default": None
    },
    3: {
        "name": "CTF_SUBNET",
        "description": "Network subnet for the CTF container",
        "default": "192.168.2.0/24"
    },
    4: {
        "name": "CTF_IP",
        "description": "IP address for the CTF container",
        "default": "192.168.2.100"
    },
    5: {
        "name": "CTF_INSIDE",
        "description": "Whether to conquer the CTF from within container",
        "default": "true"
    },
    # CAI variables
    6: {
        "name": "CAI_MODEL",
        "description": "Model to use for agents",
        "default": "qwen2.5:14b"
    },
    7: {
        "name": "CAI_DEBUG",
        "description": "Set debug output level (0: Only tool outputs, 1: Verbose debug output, 2: CLI debug output)",  # noqa: E501 # pylint: disable=line-too-long
        "default": "1"
    },
    8: {
        "name": "CAI_BRIEF",
        "description": "Enable/disable brief output mode",
        "default": "false"
    },
    9: {
        "name": "CAI_MAX_TURNS",
        "description": "Maximum number of turns for agent interactions",
        "default": "inf"
    },
    10: {
        "name": "CAI_TRACING",
        "description": "Enable/disable OpenTelemetry tracing",
        "default": "true"
    },
    11: {
        "name": "CAI_AGENT_TYPE",
        "description": "Specify the agents to use (boot2root, one_tool...)",  # noqa: E501 # pylint: disable=line-too-long
        "default": "one_tool"
    },
    12: {
        "name": "CAI_STATE",
        "description": "Enable/disable stateful mode",
        "default": "false"
    },
    13: {
        "name": "CAI_MEMORY",
        "description": "Enable/disable memory mode (episodic, semantic, all)",
        "default": "false"
    },
    14: {
        "name": "CAI_MEMORY_ONLINE",
        "description": "Enable/disable online memory mode",
        "default": "false"
    },
    15: {
        "name": "CAI_MEMORY_OFFLINE",
        "description": "Enable/disable offline memory",
        "default": "false"
    },
    16: {
        "name": "CAI_ENV_CONTEXT",
        "description": "Add dirs and current env to llm context",
        "default": "true"
    },
    17: {
        "name": "CAI_MEMORY_ONLINE_INTERVAL",
        "description": "Number of turns between online memory updates",
        "default": "5"
    },
    18: {
        "name": "CAI_PRICE_LIMIT",
        "description": "Price limit for the conversation in dollars",
        "default": "1"
    },
    19: {
        "name": "CAI_REPORT",
        "description": "Enable/disable reporter mode (ctf, nis2, pentesting)",
        "default": "ctf"
    },
    20: {
        "name": "CAI_SUPPORT_MODEL",
        "description": "Model to use for the support agent",
        "default": "o3-mini"
    },
    21: {
        "name": "CAI_SUPPORT_INTERVAL",
        "description": "Number of turns between support agent executions",
        "default": "5"
    },
    22: {
        "name": "CAI_WORKSPACE",
        "description": "Name of the current workspace (affects log file naming)",
        "default": None  # Default to no workspace
    },
}


def get_env_var_value(var_name: str) -> str:
    """Get the current value of an environment variable.

    Args:
        var_name: The name of the environment variable

    Returns:
        The current value or the default value if not set
    """
    for var_info in ENV_VARS.values():
        if var_info["name"] == var_name:
            return os.environ.get(var_name, var_info["default"] or "Not set")
    return "Unknown variable"


def set_env_var(var_name: str, value: str) -> bool:
    """Set an environment variable.

    Args:
        var_name: The name of the environment variable
        value: The value to set

    Returns:
        True if successful, False otherwise
    """
    os.environ[var_name] = value
    return True


class ConfigCommand(Command):
    """Command for displaying and configuring environment variables."""

    def __init__(self):
        """Initialize the config command."""
        super().__init__(
            name="/config",
            description=(
                "Display and configure environment variables"
            ),
            aliases=["/cfg"]
        )

        # Add subcommands
        self.add_subcommand(
            "list",
            "List all environment variables and their values",
            self.handle_list
        )
        self.add_subcommand(
            "set",
            "Set an environment variable by its number",
            self.handle_set
        )
        self.add_subcommand(
            "get",
            "Get the value of an environment variable by its number",
            self.handle_get
        )

    def handle_no_args(self, messages: Optional[List[Dict]] = None) -> bool:
        """Handle the command when no arguments are provided.

        Args:
            messages: Optional list of conversation messages

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.handle_list(None, messages)

    def handle_list(self, _: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """List all environment variables and their values.

        Args:
            _: Ignored arguments
            messages: Optional list of conversation messages

        Returns:
            True if successful
        """
        table = Table(
            title="Environment Variables",
            show_header=True,
            header_style="bold yellow"
        )
        table.add_column("#", style="dim")
        table.add_column("Variable", style="yellow")
        table.add_column("Value", style="green")
        table.add_column("Default", style="blue")
        table.add_column("Description")

        for num, var_info in ENV_VARS.items():
            var_name = var_info["name"]
            current_value = get_env_var_value(var_name)
            default_value = var_info["default"] or "Not set"

            table.add_row(
                str(num),
                var_name,
                current_value,
                default_value,
                var_info["description"]
            )

        console.print(table)
        console.print(
            "\nUsage: /config set <number> <value> to configure a variable"
        )
        return True

    def handle_get(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Get the value of an environment variable by its number.

        Args:
            args: Command arguments [var_number]
            messages: Optional list of conversation messages

        Returns:
            True if successful, False otherwise
        """
        if not args or len(args) < 1:
            console.print(
                "[yellow]Usage: /config get <number>[/yellow]"
            )
            return False

        try:
            var_num = int(args[0])
            if var_num not in ENV_VARS:
                console.print(
                    f"[red]Error: Variable number {var_num} not found[/red]"
                )
                return False

            var_info = ENV_VARS[var_num]
            var_name = var_info["name"]
            current_value = get_env_var_value(var_name)

            console.print(
                f"[yellow]{var_name}[/yellow]: "
                f"[green]{current_value}[/green] "
                f"(Default: [blue]{var_info['default'] or 'Not set'}[/blue])"
            )
            return True
        except ValueError:
            console.print(
                "[red]Error: Variable number must be an integer[/red]"
            )
            return False

    def handle_set(self, args: Optional[List[str]] = None, messages: Optional[List[Dict]] = None) -> bool:
        """Set an environment variable by its number.

        Args:
            args: Command arguments [var_number, value]
            messages: Optional list of conversation messages

        Returns:
            True if successful, False otherwise
        """
        if not args or len(args) < 2:
            console.print(
                "[yellow]Usage: /config set <number> <value>[/yellow]"
            )
            return False

        try:
            var_num = int(args[0])
            if var_num not in ENV_VARS:
                console.print(
                    f"[red]Error: Variable number {var_num} not found[/red]"
                )
                return False

            value = args[1]
            var_info = ENV_VARS[var_num]
            var_name = var_info["name"]

            old_value = get_env_var_value(var_name)
            set_env_var(var_name, value)

            console.print(
                f"[green]Set {var_name} to '{value}' "
                f"(was: '{old_value}')[/green]"
            )
            return True
        except ValueError:
            console.print(
                "[red]Error: Variable number must be an integer[/red]"
            )
            return False


# Register the command
register_command(ConfigCommand())
