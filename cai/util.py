# pylint: disable=too-many-lines
"""
This module contains utility functions for the CAI library.
"""

# Standard library imports
import inspect
import time
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, Callable, Type, Literal
import importlib.resources
import pathlib

# Third-party imports
from litellm.types.utils import Message  # pylint: disable=import-error
from rich.box import ROUNDED  # pylint: disable=import-error
from rich.console import Console, Group  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.pretty import install as install_pretty  # pylint: disable=import-error # noqa: 501
from rich.text import Text  # pylint: disable=import-error
from rich.theme import Theme  # pylint: disable=import-error
from rich.traceback import install  # pylint: disable=import-error
from rich.tree import Tree  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error

# Local imports
from cai.graph import Node, get_default_graph
from cai.types import (
    Agent,
    ChatCompletionMessageToolCall
)

# Global timing variables
GLOBAL_START_TIME = None
LAST_TOOL_TIME = None
ACTIVE_TIME = 0.0
IDLE_TIME = 0.0
LAST_STATE_CHANGE = None
IS_ACTIVE = False


def format_time(seconds):
    """Format time in a hacker-like style."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {seconds:.1f}s"
    if minutes > 0:
        return f"{minutes}m {seconds:.1f}s"
    return f"{seconds:.1f}s"


def initialize_global_timer():
    """Initialize the global timer."""
    global GLOBAL_START_TIME, LAST_STATE_CHANGE, IS_ACTIVE  # pylint: disable=global-statement
    GLOBAL_START_TIME = time.time()
    LAST_STATE_CHANGE = time.time()
    IS_ACTIVE = False


def reset_global_timer():
    """Reset the global timer."""
    global GLOBAL_START_TIME, ACTIVE_TIME, IDLE_TIME  # pylint: disable=global-statement
    GLOBAL_START_TIME = None
    ACTIVE_TIME = 0.0
    IDLE_TIME = 0.0


def start_active_time():
    """Mark the start of active execution time."""
    global LAST_STATE_CHANGE, IS_ACTIVE, IDLE_TIME  # pylint: disable=global-statement
    current_time = time.time()
    if LAST_STATE_CHANGE is not None and not IS_ACTIVE:
        IDLE_TIME += current_time - LAST_STATE_CHANGE
    LAST_STATE_CHANGE = current_time
    IS_ACTIVE = True


def start_idle_time():
    """Mark the start of idle time."""
    global LAST_STATE_CHANGE, IS_ACTIVE, ACTIVE_TIME  # pylint: disable=global-statement
    current_time = time.time()
    if LAST_STATE_CHANGE is not None and IS_ACTIVE:
        ACTIVE_TIME += current_time - LAST_STATE_CHANGE
    LAST_STATE_CHANGE = current_time
    IS_ACTIVE = False


def get_active_time():
    """Get total active execution time."""
    active = ACTIVE_TIME
    if IS_ACTIVE and LAST_STATE_CHANGE is not None:
        active += time.time() - LAST_STATE_CHANGE
    return format_time(active)


def get_idle_time():
    """Get total idle waiting time."""
    idle = IDLE_TIME
    if not IS_ACTIVE and LAST_STATE_CHANGE is not None:
        idle += time.time() - LAST_STATE_CHANGE
    return format_time(idle)


def get_elapsed_time():
    """Get elapsed time since global start."""
    if GLOBAL_START_TIME is None:
        return "0.0s"
    return format_time(time.time() - GLOBAL_START_TIME)


def get_tool_elapsed_time():
    """Get elapsed time since last tool call."""
    if LAST_TOOL_TIME is None:
        return "0.0s"
    return format_time(time.time() - LAST_TOOL_TIME)


def get_model_input_tokens(model):
    """
    Get the number of input tokens for
    max context window capacity for a given model.
    """
    model_tokens = {
        "gpt": 128000,
        "o1": 200000,
        "claude": 200000,
        "qwen2.5": 32000,  # https://ollama.com/library/qwen2.5, 128K input, 8K output  # noqa: E501  # pylint: disable=C0301
        "llama3.1": 32000,  # https://ollama.com/library/llama3.1, 128K input  # noqa: E501  # pylint: disable=C0301
        "deepseek": 128000  # https://api-docs.deepseek.com/quick_start/pricing  # noqa: E501  # pylint: disable=C0301
    }
    for model_type, tokens in model_tokens.items():
        if model_type in model:
            return tokens
    return model_tokens["gpt"]


theme = Theme({
    # Primary colors - Material Design inspired
    "timestamp": "#00BCD4",  # Cyan 500
    "agent": "#4CAF50",      # Green 500
    "arrow": "#FFFFFF",      # White
    "content": "#ECEFF1",    # Blue Grey 50
    "tool": "#F44336",       # Red 500

    # Secondary colors
    "cost": "#009688",        # Teal 500
    "args_str": "#FFC107",  # Amber 500

    # UI elements
    "border": "#2196F3",      # Blue 500
    "border_state": "#FFD700",      # Yellow (Gold), complementary to Blue 500
    "model": "#673AB7",       # Deep Purple 500
    "dim": "#9E9E9E",         # Grey 500
    "current_token_count": "#E0E0E0",  # Grey 300 - Light grey
    "total_token_count": "#757575",    # Grey 600 - Medium grey
    "context_tokens": "#0A0A0A",       # Nearly black - Very high contrast

    # Status indicators
    "success": "#4CAF50",     # Green 500
    "warning": "#FF9800",     # Orange 500
    "error": "#F44336"        # Red 500
})

console = Console(theme=theme)
install()
install_pretty()

# ANSI color codes in a nice, readable palette
COLORS = {
    'timestamp': '\033[38;5;75m',    # Light blue
    'bracket': '\033[38;5;247m',     # Light gray
    'intro': '\033[38;5;141m',       # Light purple
    'object': '\033[38;5;215m',      # Light orange
    'arg_key': '\033[38;5;147m',     # Soft purple
    'arg_value': '\033[38;5;180m',   # Light tan
    'function': '\033[38;5;219m',    # Pink
    'tool': '\033[38;5;147m',        # Soft purple
    # Darker variants
    'timestamp_old': '\033[38;5;67m',  # Darker blue
    'intro_old': '\033[38;5;97m',     # Darker purple
    'object_old': '\033[38;5;172m',   # Darker orange
    'arg_key_old': '\033[38;5;103m',   # Darker soft purple
    'arg_value_old': '\033[38;5;137m',  # Darker tan
    'function_old': '\033[38;5;176m',  # Darker pink
    'tool_old': '\033[38;5;103m',     # Darker soft purple
    'reset': '\033[0m'
}

# Global cache for message history
_message_history = {}


def visualize_agent_graph(start_agent):
    """
    Visualize agent graph showing all bidirectional connections between agents.
    Uses Rich library for pretty printing.
    """
    console = Console()  # pylint: disable=redefined-outer-name
    if start_agent is None:
        console.print("[red]No agent provided to visualize.[/red]")
        return

    tree = Tree(
        f"🤖 {
            start_agent.name} (Current Agent)",
        guide_style="bold blue")

    # Track visited agents and their nodes to handle cross-connections
    visited = {}
    agent_nodes = {}
    agent_positions = {}  # Track positions in tree
    position_counter = 0  # Counter for tracking positions

    def add_agent_node(agent, parent=None, is_transfer=False):  # pylint: disable=too-many-branches # noqa: E501
        """Add agent node and track for cross-connections"""
        nonlocal position_counter

        if agent is None:
            return None

        # Create or get existing node for this agent
        if id(agent) in visited:
            if is_transfer:
                # Add reference with position for repeated agents
                original_pos = agent_positions[id(agent)]
                parent.add(
                    f"[cyan]↩ Return to {
                        agent.name} (Top Level Agent #{original_pos})[/cyan]")
            return agent_nodes[id(agent)]

        visited[id(agent)] = True
        position_counter += 1
        agent_positions[id(agent)] = position_counter

        # Create node for current agent
        if is_transfer:
            node = parent
        else:
            node = parent.add(
                f"[green]{agent.name} (#{position_counter})[/green]") if parent else tree  # noqa: E501 pylint: disable=line-too-long
        agent_nodes[id(agent)] = node

        # Add tools as children
        tools_node = node.add("[yellow]Tools[/yellow]")
        for fn in getattr(agent, "functions", []):
            if callable(fn):
                fn_name = getattr(fn, "__name__", "")
                if ("handoff" not in fn_name.lower() and
                        not fn_name.startswith("transfer_to")):
                    tools_node.add(f"[blue]{fn_name}[/blue]")

        # Add Handoffs section
        transfers_node = node.add("[magenta]Handoffs[/magenta]")

        # Process handoff functions
        for fn in getattr(agent, "functions", []):  # pylint: disable=too-many-nested-blocks # noqa: E501
            if callable(fn):
                fn_name = getattr(fn, "__name__", "")
                if ("handoff" in fn_name.lower() or
                        fn_name.startswith("transfer_to")):
                    try:
                        next_agent = fn()
                        if next_agent:
                            # Show bidirectional connection
                            transfer = transfers_node.add(
                                f"🤖 {next_agent.name}")  # noqa: E501
                            add_agent_node(next_agent, transfer, True)
                    except Exception:  # nosec: B112 # pylint: disable=broad-exception-caught # noqa: E501
                        continue
        return node
    # Start recursive traversal from root agent
    add_agent_node(start_agent)
    console.print(tree)


def format_value(value: Any, prev_value: Any = None, brief: bool = False) -> str:  # pylint: disable=too-many-locals # noqa: E501
    """
    Format a value for debug printing with appropriate colors.
    Compare with previous value to determine if content is new.
    """
    def get_color(key: str, current, previous) -> str:
        """Determine if we should use the normal or darker color variant"""
        if previous is not None and str(current) == str(previous):
            return COLORS.get(f'{key}_old', COLORS[key])
        return COLORS[key]

    # Handle lists
    if isinstance(value, list):  # pylint: disable=no-else-return
        items = []
        prev_items = prev_value if isinstance(prev_value, list) else []

        for i, item in enumerate(value):
            prev_item = prev_items[i] if i < len(prev_items) else None
            if isinstance(item, dict):
                # Format dictionary items in the list
                dict_items = []
                for k, v in item.items():
                    prev_v = prev_item.get(k) if prev_item and isinstance(
                        prev_item, dict) else None
                    color_key = get_color(
                        'arg_key', k, k if prev_item else None)
                    formatted_value = format_value(v, prev_v, brief)
                    if brief:
                        dict_items.append(
                            f"{color_key}{k}{
                                COLORS['reset']}: {formatted_value}")
                    else:
                        dict_items.append(
                            f"\n    {color_key}{k}{
                                COLORS['reset']}: {formatted_value}")
                items.append(
                    "{" + (" " if brief else ",").join(dict_items) + "}")
            else:
                items.append(format_value(item, prev_item, brief))
        if brief:
            return f"[{' '.join(items)}]"
        return f"[\n  {','.join(items)}\n]"

    # Handle dictionaries
    elif isinstance(value, dict):
        formatted_items = []
        for k, v in value.items():
            prev_v = prev_value.get(k) if prev_value and isinstance(
                prev_value, dict) else None
            color_key = get_color('arg_key', k, k if prev_value else None)
            formatted_value = format_value(v, prev_v, brief)
            formatted_items.append(
                f"{color_key}{k}{
                    COLORS['reset']}: {formatted_value}")
        return "{ " + (" " if brief else ", ").join(formatted_items) + " }"

    # Handle basic types
    else:
        colorcillo = get_color('arg_value', value, prev_value)
        return f"{colorcillo}{str(value)}{COLORS['reset']}"


def format_chat_completion(msg, prev_msg=None) -> str:  # pylint: disable=unused-argument # noqa: E501
    """
    Format a ChatCompletionMessage object with proper indentation and colors.
    """
    # Convert messages to dict and handle OpenAI types
    try:
        msg_dict = json.loads(msg.model_dump_json())
    except AttributeError:
        msg_dict = msg.__dict__

    # Clean up the dictionary
    msg_dict = {k: v for k, v in msg_dict.items() if v is not None}

    def process_line(line, depth=0):
        """Process each line with proper coloring
        and handle nested structures"""
        if ':' in line:  # pylint: disable=too-many-nested-blocks
            key, value = line.split(':', 1)
            key = key.strip(' "')
            value = value.strip()

            # Handle nested structures
            if value in ['{', '[']:  # pylint: disable=no-else-return
                return f"{COLORS['arg_key']}{key}{COLORS['reset']}: {value}"
            elif value in ['}', ']']:
                return value
            else:
                # Special handling for function arguments
                if key == "arguments":
                    try:
                        args_dict = json.loads(
                            value.strip('"')
                            if value.startswith('"') else value)
                        args_lines = json.dumps(
                            args_dict, indent=2).split('\n')
                        colored_args = []
                        for args_line in args_lines:
                            if ':' in args_line:
                                args_key, args_val = args_line.split(':', 1)
                                colored_args.append(
                                    f"{' ' * (depth * 2)}{COLORS['arg_key']}{
                                        args_key.strip()}{COLORS['reset']}: "
                                    f"{COLORS['arg_value']}{args_val.strip()}{
                                        COLORS['reset']}"
                                )
                            else:
                                colored_args.append(
                                    f"{' ' * (depth * 2)}{args_line}")
                        return f"{COLORS['arg_key']}{key}{
                            COLORS['reset']}: " + '\n'.join(colored_args)
                    except json.JSONDecodeError:
                        pass

                return f"{COLORS['arg_key']}{key}{COLORS['reset']}: {
                    COLORS['arg_value']}{value}{COLORS['reset']}"
        return line

    # Format with json.dumps for consistent indentation
    formatted_json = json.dumps(msg_dict, indent=2)

    # Process each line
    colored_lines = []
    for line in formatted_json.split('\n'):
        colored_lines.append(process_line(line))

    return f"\n  {COLORS['object']}ChatCompletionMessage{
        COLORS['reset']}(\n    " + '\n    '.join(colored_lines) + "\n  )"


def get_ollama_api_base() -> str:
    """
    Get the Ollama API base URL from the environment variable.
    """
    return os.getenv("OLLAMA_API_BASE", "http://host.docker.internal:8000/v1")


def cli_print_agent_messages(agent_name, message, counter, model, debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument # noqa: E501
                             interaction_input_tokens=None,
                             interaction_output_tokens=None,
                             interaction_reasoning_tokens=None,
                             total_input_tokens=None,
                             total_output_tokens=None,
                             total_reasoning_tokens=None,
                             interaction_cost=None,
                             total_cost=None):
    """Print agent messages/thoughts with enhanced visual formatting."""
    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    # Use the model from environment variable if available
    model_override = os.getenv('CAI_MODEL')
    if model_override:
        model = model_override

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Create a more hacker-like header
    text = Text()

    # Special handling for Reasoner Agent
    if agent_name == "Reasoner Agent":
        text.append(f"[{counter}] ", style="bold red")
        text.append(f"Agent: {agent_name} ", style="bold yellow")
        if message:
            text.append(f">> {message} ", style="green")
        text.append(f"[{timestamp}", style="dim")
        if model:
            text.append(f" ({os.getenv('CAI_SUPPORT_MODEL')})",
                        style="bold blue")
        text.append("]", style="dim")
    else:
        text.append(f"[{counter}] ", style="bold cyan")
        text.append(f"Agent: {agent_name} ", style="bold green")
        if message:
            text.append(f">> {message} ", style="yellow")
        text.append(f"[{timestamp}", style="dim")
        if model:
            text.append(f" ({model})", style="bold magenta")
        text.append("]", style="dim")

    # Add token information with enhanced formatting
    tokens_text = None
    if (interaction_input_tokens is not None and  # pylint: disable=R0916
            interaction_output_tokens is not None and
            interaction_reasoning_tokens is not None and
            total_input_tokens is not None and
            total_output_tokens is not None and
            total_reasoning_tokens is not None):

        tokens_text = _create_token_display(
            interaction_input_tokens,
            interaction_output_tokens,
            interaction_reasoning_tokens,
            total_input_tokens,
            total_output_tokens,
            total_reasoning_tokens,
            model,
            interaction_cost,
            total_cost
        )
        text.append(tokens_text)

    # Create a panel for better visual separation
    panel = Panel(
        text,
        border_style="red" if agent_name == "Reasoner Agent" else "blue",
        box=ROUNDED,
        padding=(0, 1),
        title=("[bold]Reasoning Analysis[/bold]"
               if agent_name == "Reasoner Agent"
               else "[bold]Agent Interaction[/bold]"),
        title_align="left"
    )
    console.print(panel)


def cli_print_state(agent_name, message, counter, model, debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument # noqa: E501
                    interaction_input_tokens, interaction_output_tokens,
                    interaction_reasoning_tokens, total_input_tokens,
                    total_output_tokens, total_reasoning_tokens,
                    interaction_cost=None,
                    total_cost=None):
    """Print network state messages with enhanced visual formatting."""
    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    # Use the model from environment variable if available
    model_override = os.getenv('CAI_MODEL')
    if model_override:
        model = model_override

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Create a more hacker-like header
    text = Text()
    text.append("[-]", style="bold cyan")
    text.append(f"Agent: {agent_name} ", style="bold green")
    text.append(f"[{timestamp}", style="dim")
    if model:
        text.append(f" ({model})", style="bold magenta")
    text.append("]", style="dim")

    # Add token information with enhanced formatting
    tokens_text = None
    if (interaction_input_tokens is not None and  # pylint: disable=R0916
            interaction_output_tokens is not None and
            interaction_reasoning_tokens is not None and
            total_input_tokens is not None and
            total_output_tokens is not None and
            total_reasoning_tokens is not None):

        tokens_text = _create_token_display(
            interaction_input_tokens,
            interaction_output_tokens,
            interaction_reasoning_tokens,
            total_input_tokens,
            total_output_tokens,
            total_reasoning_tokens,
            model,
            interaction_cost,
            total_cost
        )

    group_content = []
    try:
        parsed_message = json.loads(message)
        formatted_message = json.dumps(parsed_message, indent=2)
        group_content.extend([
            Text(formatted_message, style="yellow"),
            tokens_text if tokens_text else Text("")
        ])
    except json.JSONDecodeError:
        group_content.extend([
            Text("⚠️ Invalid JSON", style="bold red", justify="right"),
            Text(message, style="yellow"),
            tokens_text if tokens_text else Text("")
        ])

    if message:
        main_panel = Panel(
            Group(*group_content),
            title="[bold]Network State[/bold]",
            border_style="green",
            title_align="left",
            box=ROUNDED,
            padding=(1, 2),
            width=console.width,
            style="content"
        )

    # Create a header panel
    header_panel = Panel(
        text,
        border_style="blue",
        box=ROUNDED,
        padding=(0, 1),
        title="[bold]State Agent[/bold]",
        title_align="left"
    )

    console.print(header_panel)
    if message:
        console.print(main_panel)


def cli_print_codeagent_output(agent_name, message_content, code, counter, model, debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument,too-many-statements,too-many-branches # noqa: E501
                               interaction_input_tokens=None,
                               interaction_output_tokens=None,
                               interaction_reasoning_tokens=None,
                               total_input_tokens=None,
                               total_output_tokens=None,
                               total_reasoning_tokens=None,
                               interaction_cost=None,
                               total_cost=None):
    """
    Print CodeAgent output with both the generated code and execution results.

    Args:
        agent_name: Name of the agent
        message_content: The execution result message
        code: The generated Python code
        counter: Turn counter
        model: Model name
        debug: Debug level
        interaction_input_tokens: Input tokens for current interaction
        interaction_output_tokens: Output tokens for current interaction
        interaction_reasoning_tokens: Reasoning tokens for current interaction
        total_input_tokens: Total input tokens used
        total_output_tokens: Total output tokens used
        total_reasoning_tokens: Total reasoning tokens used
        interaction_cost: Cost of the current interaction
        total_cost: Total accumulated cost
    """
    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    # Use the model from environment variable if available
    model_override = os.getenv('CAI_MODEL')
    if model_override:
        model = model_override

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Create header text
    header_text = Text()
    header_text.append(f"[{counter}] ", style="arrow")
    header_text.append(f"Agent: {agent_name} ", style="timestamp")
    header_text.append(f"[{timestamp}", style="dim")
    if model:
        header_text.append(f" ({model})", style="model")
    header_text.append("]", style="dim")

    # Create a more hacker-like header with execution time
    global LAST_TOOL_TIME, GLOBAL_START_TIME  # pylint: disable=global-variable-not-assigned # noqa: E501
    current_time = time.time()

    # Add timing information
    total_elapsed = format_time(
        current_time - GLOBAL_START_TIME) if GLOBAL_START_TIME else "0.0s"
    tool_elapsed = format_time(
        current_time - LAST_TOOL_TIME) if LAST_TOOL_TIME else "0.0s"
    header_text.append(
        f" [Total: {total_elapsed} | Tool: {tool_elapsed}]",
        style="bold magenta")

    LAST_TOOL_TIME = current_time

    # Create token display if token information is available
    tokens_text = None
    if (interaction_input_tokens is not None and  # pylint: disable=R0916 # noqa: E501
            interaction_output_tokens is not None and
            interaction_reasoning_tokens is not None and
            total_input_tokens is not None and
            total_output_tokens is not None and
            total_reasoning_tokens is not None):

        tokens_text = _create_token_display(
            interaction_input_tokens,
            interaction_output_tokens,
            interaction_reasoning_tokens,
            total_input_tokens,
            total_output_tokens,
            total_reasoning_tokens,
            model,
            interaction_cost,
            total_cost
        )

    # Print header
    console.print(header_text)

    # Create and print code panel
    if code:
        try:
            # Try to format the code for better readability
            from rich.syntax import Syntax  # pylint: disable=import-outside-toplevel,import-error # noqa: E402,E501
            syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
            code_panel = Panel(
                syntax,
                title="Generated Code",
                border_style="arrow",
                title_align="left",
                box=ROUNDED,
                padding=(1, 2),
                width=console.width
            )
            console.print(code_panel)
        except Exception:  # pylint: disable=broad-exception-caught # noqa: E722,E501
            # Fallback if syntax highlighting fails
            code_panel = Panel(
                Text(code, style="content"),
                title="Generated Code",
                border_style="arrow",
                title_align="left",
                box=ROUNDED,
                padding=(1, 2),
                width=console.width
            )
            console.print(code_panel)

    # # Print separator
    # console.rule(style="dim")

    # Extract execution results from message_content
    # Look for execution logs section
    execution_logs = None
    output = None
    timeout_error = None

    # Check for timeout error
    if "Code execution timed out after" in message_content:
        try:
            # Extract the timeout message
            timeout_match = re.search(
                r"Code execution timed out after (\d+) seconds\.",
                message_content)
            if timeout_match:
                timeout_seconds = timeout_match.group(1)
                timeout_error = f"Code execution timed out after {
                    timeout_seconds} seconds."

                # Try to extract logs from timeout message
                logs_match = re.search(
                    r"Execution logs before timeout:\n```\n([\s\S]*?)\n```",
                    message_content)
                if logs_match:
                    execution_logs = logs_match.group(1)
        except Exception:  # pylint: disable=broad-exception-caught # noqa: E722,E501
            # nosec B110
            pass

    # If not a timeout, look for regular execution logs
    if not timeout_error and "Execution logs:" in message_content:
        try:
            # Try to extract execution logs between ```...``` markers
            logs_match = re.search(
                r"Execution logs:\n```\n([\s\S]*?)\n```",
                message_content)
            if logs_match:
                execution_logs = logs_match.group(1)
        except Exception:  # pylint: disable=broad-exception-caught # noqa: E722,E501
            # nosec B110
            pass

    # Look for output section
    if "Output:" in message_content:
        try:
            output_match = re.search(
                r"Output: ([\s\S]*?)(?:\n\n|$)",
                message_content)
            if output_match:
                output = output_match.group(1)
        except Exception:  # pylint: disable=broad-exception-caught # noqa: E722,E501
            # nosec B110
            pass

    # Create content for results panel
    result_content = []

    # Add timeout error if present
    if timeout_error:
        result_content.extend([
            Text("⚠️ " + timeout_error, style="bold red"),
            Text("")  # Empty line for spacing
        ])

    if execution_logs:
        result_content.extend([
            Text("Execution Logs:", style="timestamp"),
            Text(execution_logs, style="content"),
            Text("")  # Empty line for spacing
        ])

    if output:
        result_content.extend([
            Text("Output:", style="timestamp"),
            Text(output, style="content")
        ])

    # If we couldn't parse the message, just show the whole thing
    if not result_content:
        result_content = [Text(message_content, style="content")]

    # Add token information if available
    if tokens_text:
        result_content.append(tokens_text)

    # Create and print results panel
    results_panel = Panel(
        Group(*result_content),
        title="Execution Results",
        border_style="border",
        title_align="left",
        box=ROUNDED,
        padding=(1, 2),
        width=console.width
    )
    console.print(results_panel)


def _create_token_display(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements,too-many-branches # noqa: E501
    interaction_input_tokens,
    interaction_output_tokens,  # noqa: E501, pylint: disable=R0913
    interaction_reasoning_tokens,
    total_input_tokens,
    total_output_tokens,
    total_reasoning_tokens,
    model,
    interaction_cost=0.0,
    total_cost=None
) -> Text:  # noqa: E501
    """
    Create a Text object displaying token usage information
    with enhanced formatting.
    """
    tokens_text = Text(justify="left")

    # Create a more compact, horizontal display
    tokens_text.append(" ", style="bold")  # Small padding
    
    # Current interaction tokens
    tokens_text.append("Current: ", style="bold")
    tokens_text.append(f"I:{interaction_input_tokens} ", style="green")
    tokens_text.append(f"O:{interaction_output_tokens} ", style="red")
    tokens_text.append(f"R:{interaction_reasoning_tokens} ", style="yellow")
    
    # Current cost
    current_cost = float(interaction_cost) if interaction_cost is not None else 0.0
    tokens_text.append(f"(${current_cost:.4f}) ", style="bold")
    
    # Separator
    tokens_text.append("| ", style="dim")
    
    # Total tokens
    tokens_text.append("Total: ", style="bold")
    tokens_text.append(f"I:{total_input_tokens} ", style="green")
    tokens_text.append(f"O:{total_output_tokens} ", style="red")
    tokens_text.append(f"R:{total_reasoning_tokens} ", style="yellow")
    
    # Total cost
    total_cost_value = float(total_cost) if total_cost is not None else 0.0
    tokens_text.append(f"(${total_cost_value:.4f}) ", style="bold")
    
    # Separator
    tokens_text.append("| ", style="dim")
    
    # Context usage
    context_pct = interaction_input_tokens / get_model_input_tokens(model) * 100
    tokens_text.append("Context: ", style="bold")
    tokens_text.append(f"{context_pct:.1f}% ", style="bold")
    
    # Context indicator
    if context_pct < 50:
        indicator = "🟩"
        color_local = "green"
    elif context_pct < 80:
        indicator = "🟨"
        color_local = "yellow"
    else:
        indicator = "🟥"
        color_local = "red"
    
    tokens_text.append(f"{indicator}", style=color_local)

    return tokens_text

def cli_print_tool_call(tool_name, tool_args,  # pylint: disable=R0914,too-many-arguments # noqa: E501
                        tool_output,
                        interaction_input_tokens,
                        interaction_output_tokens,
                        interaction_reasoning_tokens,
                        total_input_tokens,
                        total_output_tokens,
                        total_reasoning_tokens,
                        model,
                        debug,
                        interaction_cost=None,
                        total_cost=None):
    """Print tool call information with enhanced visual formatting."""
    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    # Use the model from environment variable if available
    model_override = os.getenv('CAI_MODEL')
    if model_override:
        model = model_override

    filtered_args = ({k: v for k, v in tool_args.items() if k != 'ctf'}
                        if tool_args else {})  # noqa: F541, E127
    args_str = ", ".join(f"{k}={v}" for k, v in filtered_args.items())

    # Create a more hacker-like header with execution time
    global LAST_TOOL_TIME, GLOBAL_START_TIME  # pylint: disable=global-variable-not-assigned # noqa: E501
    current_time = time.time()

    text = Text()
    text.append(f"{tool_name}(", style="bold cyan")
    text.append(args_str, style="yellow")
    if "agent" in tool_name.lower() or "transfer" in tool_name.lower(
    ) or "handoff" in tool_name.lower():
        text.append("Handoff", style="bold green")
    text.append(")", style="bold cyan")

    # Add timing information
    total_elapsed = format_time(
        current_time - GLOBAL_START_TIME) if GLOBAL_START_TIME else "0.0s"
    tool_elapsed = format_time(
        current_time - LAST_TOOL_TIME) if LAST_TOOL_TIME else "0.0s"
    text.append(
        f" [Total: {total_elapsed} | Tool: {tool_elapsed}]",
        style="bold magenta")

    LAST_TOOL_TIME = current_time

    if tool_output:
        output = str(tool_output)
        tokens_text = None
        if (interaction_input_tokens is not None and  # pylint: disable=C0103, R0916 # noqa: E501
                interaction_output_tokens is not None and
                interaction_reasoning_tokens is not None and
                total_input_tokens is not None and
                total_output_tokens is not None and
                total_reasoning_tokens is not None):

            tokens_text = _create_token_display(
                interaction_input_tokens,
                interaction_output_tokens,
                interaction_reasoning_tokens,
                total_input_tokens,
                total_output_tokens,
                total_reasoning_tokens,
                model,
                interaction_cost,
                total_cost
            )

        # Handle panel width and content
        title_width = len(str(text))
        max_title_width = console.width - 4

        group_content = []
        if title_width > max_title_width:
            group_content.append(text)

        # Special handling for execute_code tool
        if tool_name == "execute_code" and "language" in filtered_args:
            try:
                from rich.syntax import Syntax  # pylint: disable=import-outside-toplevel,import-error # noqa: E402,E501
                
                language = filtered_args.get("language", "python")
                code = filtered_args.get("code", "")
                
                # Create syntax highlighted code panel
                syntax = Syntax(code, language, theme="monokai", line_numbers=True,
                               background_color="#272822", indent_guides=True)
                code_panel = Panel(
                    syntax,
                    title="Code",
                    border_style="arrow",
                    title_align="left",
                    box=ROUNDED,
                    padding=(1, 2)
                )
                
                # Create output panel
                output_panel = Panel(
                    Text(output, style="yellow"),
                    title="Output",
                    border_style="border",
                    title_align="left",
                    box=ROUNDED,
                    padding=(1, 2)
                )
                # Don't show code in arguments for execute_code tool
                if title_width > max_title_width:
                    # Just show the tool name without the code in args
                    simplified_text = Text()
                    simplified_text.append(f"{tool_name}(", style="bold cyan")
                    simplified_text.append("...", style="yellow")
                    simplified_text.append(")", style="bold cyan")
                    
                    # Show timeout and filename in the simplified display
                    timeout = filtered_args.get("timeout", 100)
                    filename = filtered_args.get("filename", "exploit")
                    simplified_text.append(
                        f" [File: {filename} | Timeout: {timeout}s | "
                        f"Total: {total_elapsed} | Tool: {tool_elapsed}]",
                        style="bold magenta")
                    
                    group_content[0] = simplified_text
                
                group_content.extend([
                    code_panel,
                    output_panel,
                    tokens_text if tokens_text else Text("")
                ])
            except Exception:  # pylint: disable=broad-exception-caught # noqa: E722,E501
                # Fallback if syntax highlighting fails
                group_content.extend([
                    Text(output, style="yellow"),
                    tokens_text if tokens_text else Text("")
                ])
        else:
            group_content.extend([
                Text(output, style="yellow"),
                tokens_text if tokens_text else Text("")
            ])

        # Create a more visually appealing panel
        main_panel = Panel(
            Group(*group_content),
            title="" if title_width > max_title_width else text,
            border_style="blue",
            title_align="left",
            box=ROUNDED,
            padding=(1, 2),
            width=console.width,
            style="content"
        )
        console.print(main_panel)
    else:
        # Calculate execution time for no output case
        exec_time = time.time() - current_time
        time_str = f"[{exec_time:.2f}s]"
        text.append(f" {time_str}", style="bold magenta")
        text.append("-> (No output)", style="dim")
        console.print(text)


def debug_print(debug: int, intro: str, *args: Any, brief: bool = False, colours: bool = True) -> None:  # pylint: disable=too-many-locals,line-too-long,too-many-branches # noqa: E501
    """
    Print debug messages if debug mode is enabled with color-coded components.
    If brief is True, prints a simplified timestamp and message format.
    """
    if not debug:
        return
    if debug != 1:  # debug level 1
        return
    if brief:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if colours:
            # Format args with colors even in brief mode
            formatted_args = []
            for arg in args:
                if isinstance(arg, str) and arg.startswith(
                        ('get_', 'list_', 'process_', 'handle_')):
                    formatted_args.append(f"{COLORS['function']}{
                        arg}{COLORS['reset']}")
                elif hasattr(arg, '__class__'):
                    formatted_args.append(format_value(arg, None, brief=True))
                else:
                    formatted_args.append(format_value(arg, None, brief=True))

            colored_intro = f"{COLORS['intro']}{intro}{COLORS['reset']}"
            message = " ".join([colored_intro] + formatted_args)
            print(f"{COLORS['bracket']}[{COLORS['timestamp']}{timestamp}{
                COLORS['bracket']}]{COLORS['reset']} {message}")
        else:
            message = " ".join(map(str, [intro] + list(args)))
            print(f"\033[97m[\033[90m{
                timestamp}\033[97m]\033[90m {message}\033[0m")
        return

    global _message_history  # pylint: disable=global-variable-not-assigned
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{COLORS['bracket']}[{COLORS['timestamp']}{
        timestamp}{COLORS['bracket']}]{COLORS['reset']}"
    # Generate a unique key for this message based on the intro
    msg_key = intro
    prev_args = _message_history.get(msg_key)
    # Special handling for tool call processing messages
    if "Processing tool call" in intro:
        if len(args) >= 2:
            tool_name, _, tool_args = args
            message = (
                f"{header} {
                    COLORS['intro']}Processing tool call:{
                    COLORS['reset']} "
                f"{COLORS['tool']}{tool_name}{COLORS['reset']} "
                f"{COLORS['intro']}with arguments{COLORS['reset']} "
                f"{format_value(tool_args)}"
            )
        else:
            message = f"{header} {COLORS['intro']}{intro}{COLORS['reset']}"
    # Special handling for "Received completion" messages
    elif "Received completion" in intro:
        message = f"{header} {COLORS['intro']}{intro}{COLORS['reset']}"
        if args:
            prev_msg = prev_args[0] if prev_args else None
            message += format_chat_completion(args[0], prev_msg)
    else:
        # Regular debug message handling
        formatted_intro = f"{COLORS['intro']}{intro}{COLORS['reset']}"
        formatted_args = []
        for i, arg in enumerate(args):
            prev_arg = prev_args[i] if prev_args and i < len(
                prev_args) else None
            if isinstance(arg, str) and arg.startswith(
                    ('get_', 'list_', 'process_', 'handle_')):
                formatted_args.append(f"{COLORS['function']}{
                                      arg}{COLORS['reset']}")
            elif hasattr(arg, '__class__'):
                formatted_args.append(format_value(arg, prev_arg))
            else:
                formatted_args.append(format_value(arg, prev_arg))

        message = f"{header} {formatted_intro} {
            ' '.join(map(str, formatted_args))}"

    # Update history
    _message_history[msg_key] = args
    print(message)


def merge_fields(target, source):
    """
    Merge fields from source into target.
    """
    for key, value in source.items():
        if isinstance(value, str):
            target[key] += value
        elif value is not None and isinstance(value, dict):
            merge_fields(target[key], value)


def merge_chunk(final_response: dict, delta: dict) -> None:
    """
    Merge fields from delta into final_response.
    """
    delta.pop("role", None)
    merge_fields(final_response, delta)
    tool_calls = delta.get("tool_calls")
    if tool_calls and len(tool_calls) > 0:
        index = tool_calls[0].pop("index")
        merge_fields(final_response["tool_calls"][index], tool_calls[0])


def function_to_json(
    func: Callable,
    format: Literal['gemini', 'original'] = 'original'
) -> Dict[str, Any]:
    """
    Converts a Python function into a JSON-serializable dictionary
    describing its signature. Supports multiple output formats.

    Args:
        func: The function to convert.
        format: The desired output format.
            'gemini': Schema compatible with Google Gemini Function Calling
                      (FunctionDeclaration).
            'original': The original nested structure with a top-level 'type'.
            Defaults to 'gemini'.

    Returns:
        A dictionary representing the function's signature in the specified format.

    Raises:
        ValueError: If the function signature cannot be obtained or if an
                    unsupported format is requested.
        KeyError: If an unknown type annotation is encountered for a parameter.
        TypeError: If a type annotation is not a valid type.
    """

    # Map Python types to OpenAPI/JSON schema types
    # Ref: https://swagger.io/docs/specification/data-models/data-types/
    # Ref: https://cloud.google.com/vertex-ai/docs/generative-ai/tool-use/function-calling#function-declaration
    type_map: Dict[Type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",   # Note: Further details (items type) might be needed
        dict: "object",  # Note: Further details (properties) might be needed
        type(None): "null", # Rarely used for parameters
    }

    try:
        signature = inspect.signature(func)
        func_description = inspect.getdoc(func) or "" # Cleaned function docstring
    except ValueError as e:
        raise ValueError(
            f"Failed to get signature for function {func.__name__}: {str(e)}"
        ) from e

    parameters_properties: Dict[str, Dict[str, Any]] = {}
    required_params: list[str] = []

    # --- Attempt to parse parameter descriptions from docstring (basic) ---
    # Assumes a simple Google Style or reStructuredText format.
    # For robust parsing, consider libraries like 'docstring_parser'.
    param_descriptions = {}
    if func_description:
        try:
            doc_lines = func_description.strip().split('\n')
            in_args_section = False
            current_param = None
            param_desc_buffer = []

            for line in doc_lines:
                stripped_line = line.strip()
                # Detect start of standard Args/Parameters sections
                if stripped_line.lower().startswith(('args:', 'arguments:', 'parameters:')):
                    in_args_section = True
                    continue
                # Detect end of section or change in indentation
                if in_args_section and (not stripped_line or not line.startswith('    ')):
                     # Process the last parameter's description buffer
                    if current_param and param_desc_buffer:
                         param_descriptions[current_param] = " ".join(param_desc_buffer).strip()
                    in_args_section = False
                    current_param = None
                    param_desc_buffer = []
                    # Don't process this line further if it ended the section unless it starts a new param
                    if not stripped_line or not line.startswith('    '):
                         continue # Skip blank lines or lines outside the args section indent

                if in_args_section:
                    # reST style: :param param_name: Description
                    if stripped_line.startswith((':param', ':parameter')):
                        # Process previous parameter's description buffer
                        if current_param and param_desc_buffer:
                           param_descriptions[current_param] = " ".join(param_desc_buffer).strip()
                        param_desc_buffer = [] # Reset buffer

                        parts = stripped_line.split(':', 2)
                        if len(parts) >= 3:
                           # Extract param name (robustness could be improved)
                           name_part = parts[1].strip()
                           # Handle ':param type param_name:' format too
                           potential_name = name_part.split()[-1]
                           current_param = potential_name
                           param_desc_buffer.append(parts[2].strip())
                        else:
                            current_param = None # Malformed line
                    # Google/Numpy style: param_name (type): Description
                    # Or just param_name: Description (simpler assumption)
                    elif ':' in stripped_line and not stripped_line.startswith(':'):
                         # Process previous parameter's description buffer
                         if current_param and param_desc_buffer:
                            param_descriptions[current_param] = " ".join(param_desc_buffer).strip()
                         param_desc_buffer = [] # Reset buffer

                         parts = stripped_line.split(':', 1)
                         param_name_part = parts[0].strip()
                         # Try to extract name, ignoring potential type hints in ()
                         current_param = param_name_part.split('(')[0].strip()
                         if len(parts) > 1:
                             param_desc_buffer.append(parts[1].strip())

                    # Handle continuation lines for the current parameter description
                    elif current_param and stripped_line:
                         param_desc_buffer.append(stripped_line)


            # Process the very last parameter's description buffer if loop finishes
            if current_param and param_desc_buffer:
               param_descriptions[current_param] = " ".join(param_desc_buffer).strip()

        except Exception as e:
            # Ignore docstring parsing errors, not critical but log potentially
            # print(f"Warning: Could not fully parse docstring for parameter descriptions in {func.__name__}: {e}")
            param_descriptions = {} # Reset if parsing fails badly
    # --- End of parameter description parsing ---


    for param in signature.parameters.values():
        # Skip the 'ctf' parameter if present (as per original logic)
        if param.name == "ctf":
            continue

        # Determine if the parameter is required
        is_required = param.default == inspect.Parameter.empty
        if is_required:
            required_params.append(param.name)

        # Get parameter type annotation
        param_type_annotation = param.annotation
        param_schema_type = "string" # Default if no annotation

        if param_type_annotation != inspect.Parameter.empty:
            # Handle generic types like list[str] or dict[str, int] (simplified)
            origin_type = getattr(param_type_annotation, '__origin__', None)
            param_base_type = origin_type if origin_type else param_type_annotation

            # Check if it's a valid type before lookup
            if not isinstance(param_base_type, type) and not origin_type:
                # Could be a typing alias like typing.List, etc.
                # Attempt mapping anyway, might fail if not in type_map
                 pass # Fall through to the type_map lookup

            try:
                param_schema_type = type_map[param_base_type]
            except KeyError as e:
                 # Provide more context in the error
                raise KeyError(
                    f"Unknown type annotation '{param_type_annotation}' (base type: {param_base_type}) "
                    f"for parameter '{param.name}' in function '{func.__name__}'. "
                    f"Supported base types: {list(type_map.keys())}"
                ) from e
            except TypeError as e:
                # Catch cases where annotation is not a type (e.g., a string literal)
                 raise TypeError(
                    f"Invalid type annotation '{param_type_annotation}' for parameter '{param.name}' "
                    f"in function '{func.__name__}'. Expected a type (like str, int, list[str]), "
                    f"but got {type(param_type_annotation)}."
                 ) from e

        # Build the schema for this parameter, including description
        parameter_schema: Dict[str, Any] = {
            "type": param_schema_type,
            "description": param_descriptions.get(param.name, "") # Use parsed description or empty string
        }

        # (Optional) Add 'items' detail for arrays if type hint specifies it
        # Example: list[str] -> {"type": "array", "items": {"type": "string"}}
        if param_schema_type == "array" and origin_type and hasattr(param_type_annotation, '__args__') and param_type_annotation.__args__:
            item_type_annotation = param_type_annotation.__args__[0]
            item_origin_type = getattr(item_type_annotation, '__origin__', None)
            item_base_type = item_origin_type if item_origin_type else item_type_annotation
            if item_base_type in type_map:
                 parameter_schema["items"] = {"type": type_map[item_base_type]}
            # Add nested handling here if needed (e.g., list[list[int]])

        parameters_properties[param.name] = parameter_schema


    # --- Construct the final output based on the requested format ---
    common_parameters_block = {
        "type": "object",
        "properties": parameters_properties,
        "required": required_params, # Include even if empty for Gemini
    }

    if format == 'gemini':
        # Gemini FunctionDeclaration Schema
        return {
            "name": func.__name__,
            "description": func_description,
            "parameters": common_parameters_block,
        }
    elif format == 'original':
        # Original nested schema
         # For this format, descriptions within properties are an enhancement
        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": func_description,
                "parameters": common_parameters_block,
            },
        }
    else:
        raise ValueError(f"Unsupported format: '{format}'. Choose 'gemini' or 'original'.")

def check_flag(output, ctf, challenge=None):
    """
    Check if the CTF flag is present in the output.

    Args:
        output (str): The output to check for the flag.
        ctf: The CTF environment object.
        challenge (str, optional): The specific challenge to check.
            Defaults to None.

    Returns:
        tuple: A tuple containing a boolean indicating if the flag was
            found and the flag itself if found, otherwise None.
    """
    # Get the challenge from the environment variable or default to the first
    # challenge
    challenge_key = os.getenv("CTF_CHALLENGE")
    challenges = list(ctf.get_challenges().keys())
    challenge = (
        challenge_key
        if challenge_key in challenges
        else (challenges[0] if len(challenges) > 0 else None))
    if ctf:
        if ctf.check_flag(
            output, challenge
        ):  # check if the flag is in the output
            flag = ctf.flags[challenge]
            print(
                color(
                    f"Flag found: {flag}",
                    fg="green") +
                " in output " +
                color(
                    f"{output}",
                    fg="blue"))
            return True, flag
    else:
        print(color("CTF environment not found or provided", fg="yellow"))
    return False, None


def fix_message_list(messages):  # pylint: disable=R0914,R0915,R0912
    """
    Sanitizes the message list passed as a parameter to align with the
    OpenAI API message format.

    Adjusts the message list to comply with the following rules:
        1. A tool call id appears no more than twice.
        2. Each tool call id appears as a pair, and both messages
            must have content.
        3. If a tool call id appears alone (without a pair), it is removed.
        4. There cannot be empty messages.

    Args:
        messages (List[dict]): List of message dictionaries containing
                            role, content, and optionally tool_calls or
                            tool_call_id fields.

    Returns:
        List[dict]: Sanitized list of messages with invalid tool calls
                   and empty messages removed.
    """
    # Step 1: Filter and discard empty messages (considered empty if 'content'
    # is None or only whitespace)
    cleaned_messages = []
    for msg in messages:
        content = msg.get("content")
        if content is not None and content.strip():
            cleaned_messages.append(msg)
    messages = cleaned_messages
    # Step 2: Collect tool call id occurrences.
    # In assistant messages, iterate through 'tool_calls' list.
    # In 'tool' type messages, use the 'tool_call_id' key.
    tool_calls_occurrences = {}
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and isinstance(
                msg.get("tool_calls"), list):
            for j, tool_call in enumerate(msg["tool_calls"]):
                tc_id = tool_call.get("id")
                if tc_id:
                    tool_calls_occurrences.setdefault(
                        tc_id, []).append((i, "assistant", j))
        elif msg.get("role") == "tool" and msg.get("tool_call_id"):
            tc_id = msg["tool_call_id"]
            tool_calls_occurrences.setdefault(
                tc_id, []).append(
                (i, "tool", None))
    # Step 3: Mark invalid or extra occurrences for removal
    removal_messages = set()  # Indices of messages (tool type) to remove
    # Maps message index (assistant) to set of indices (in tool_calls) to
    # remove
    removal_assistant_entries = {}
    for tc_id, occurrences in tool_calls_occurrences.items():
        # Only 2 occurrences allowed. Mark extras for removal.
        valid_occurrences = occurrences[:2]
        extra_occurrences = occurrences[2:]
        for occ in extra_occurrences:
            msg_idx, typ, j = occ
            if typ == "assistant":
                removal_assistant_entries.setdefault(msg_idx, set()).add(j)
            elif typ == "tool":
                removal_messages.add(msg_idx)
        # If valid occurrences aren't exactly 2 (i.e., a lonely tool call),
        # mark for removal
        if len(valid_occurrences) != 2:
            for occ in valid_occurrences:
                msg_idx, typ, j = occ
                if typ == "assistant":
                    removal_assistant_entries.setdefault(
                        msg_idx, set()).add(j)
                elif typ == "tool":
                    removal_messages.add(msg_idx)
        else:
            # If exactly 2 occurrences, ensure both have content
            remove_pair = False
            for occ in valid_occurrences:
                msg_idx, typ, _ = occ
                msg_content = messages[msg_idx].get("content")
                if msg_content is None or not msg_content.strip():
                    remove_pair = True
                    break
            if remove_pair:
                for occ in valid_occurrences:
                    msg_idx, typ, j = occ
                    if typ == "assistant":
                        removal_assistant_entries.setdefault(
                            msg_idx, set()).add(j)
                    elif typ == "tool":
                        removal_messages.add(msg_idx)
    # Step 4: Build new message list applying removals
    new_messages = []
    for i, msg in enumerate(messages):
        # Skip if message (tool type) is marked for removal
        if i in removal_messages:
            continue
        # For assistant messages, remove marked tool_calls
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            new_tool_calls = []
            for j, tc in enumerate(msg["tool_calls"]):
                if j not in removal_assistant_entries.get(i, set()):
                    new_tool_calls.append(tc)
            msg["tool_calls"] = new_tool_calls
        # If after modification message has no content and no tool_calls,
        # discard it
        msg_content = msg.get("content")
        if ((msg_content is None or not msg_content.strip()) and
                not msg.get("tool_calls")):
            continue
        new_messages.append(msg)
    return new_messages


def create_graph_from_history(history):
    """
    Creates a graph from a history of messages, emulating how CAI creates
    it during interactions.

    Args:
        history (list): List of messages loaded from JSONL file

    Returns:
        Graph: The constructed graph object
    """
    # Initialize graph
    graph = get_default_graph()

    # Track turn number
    turn = 0

    # Process each message in history
    i = 0
    while i < len(history):
        message = history[i]

        # Skip system messages as they don't need to be in the graph
        if message.get("role") == "system":
            i += 1
            continue

        # Create a basic agent object for the sender
        agent = Agent(
            name=message.get("sender", message.get("role", "unknown")),
            model=message.get("model", "unknown"),
            functions=[]  # We don't have access to original functions
        )

        # Create node for this interaction
        node = Node(
            name=agent.name,
            agent=agent,
            turn=turn,
            message=Message(**message),
            history=history[:i + 1],
            # NOTE: Include all history up to this point
            # but NOT the related tool responses, as that
            # doing so will affect the resulting network
            # state, if computed. These tool responses
            # will be handled in the next Node
        )

        # Handle tool calls and their responses
        if (message.get("role") == "assistant" and
            "tool_calls" in message and
                message["tool_calls"]):
            tool_responses = []
            num_tool_calls = len(message["tool_calls"])

            # Collect the corresponding tool responses
            for j in range(num_tool_calls):
                if (i + j + 1 < len(history) and
                        history[i + j + 1].get("role") == "tool"):
                    tool_response = history[i + j + 1]
                    tool_responses.append({
                        "tool_call_id": tool_response.get("tool_call_id"),
                        "name": tool_response.get("tool_name"),
                        "content": tool_response.get("content")
                    })

            # Add node with tool calls and their responses as action
            # by converting dict tool calls to ChatCompletionMessageToolCall
            # objects
            tool_calls = [
                ChatCompletionMessageToolCall(
                    id=tool_call["id"],
                    type=tool_call["type"],
                    function=tool_call["function"],
                    index=tool_call["index"] if "index" in tool_call else None
                ) for tool_call in message["tool_calls"]
            ]
            graph.add_to_graph(node, action=tool_calls)

            # Skip the tool response messages since we've processed them
            i += num_tool_calls + 1
        else:
            # Add node without action for non-tool-call messages
            graph.add_to_graph(node)
            i += 1
        turn += 1
    return graph

def flatten_gemini_fields(args_obj):
    if not isinstance(args_obj, dict):
        return args_obj
    
    # Check if this is a fields-style dictionary at any nesting level
    if 'fields' in args_obj:
        fields_data = args_obj['fields']
        # Process different formats of fields data
        if isinstance(fields_data, dict):
            # Single field case: {key: command, value: {string_value: ls}}
            key = fields_data.get('key')
            value_data = fields_data.get('value', {})
            
            # Handle case where value is another nested structure
            if isinstance(value_data, dict) and 'struct_value' in value_data:
                # Recursively process the struct_value
                return flatten_gemini_fields(value_data['struct_value'])
            
            # Extract simple value types
            value = (value_data.get('string_value', 
                   value_data.get('number_value',
                   value_data.get('bool_value', None))))
            
            if key and value is not None:
                return {key: value}
            
        elif isinstance(fields_data, list):
            # Multiple fields case
            result = {}
            for field in fields_data:
                if isinstance(field, dict):
                    key = field.get('key')
                    value_data = field.get('value', {})
                    
                    # Handle nested struct_value
                    if isinstance(value_data, dict) and 'struct_value' in value_data:
                        nested_result = flatten_gemini_fields(value_data['struct_value'])
                        if isinstance(nested_result, dict):
                            result.update(nested_result)
                        continue
                    
                    # Extract simple value types
                    value = (value_data.get('string_value', 
                           value_data.get('number_value',
                           value_data.get('bool_value', None))))
                    
                    if key and value is not None:
                        result[key] = value
            
            return result
    
    # Process all dictionary items to handle any nested fields
    result = {}
    for key, value in args_obj.items():
        if key == 'struct_value' and isinstance(value, dict):
            # Direct struct_value processing
            nested_result = flatten_gemini_fields(value)
            if isinstance(nested_result, dict):
                result.update(nested_result)
        elif isinstance(value, dict):
            # Recursively process nested dictionaries
            nested_result = flatten_gemini_fields(value)
            if isinstance(nested_result, dict) and key == 'fields':
                # If this is a fields key with a dict result, merge it up
                result.update(nested_result)
            else:
                result[key] = nested_result
        else:
            result[key] = value
    
    return result

def get_template_content(template_path):
    """
    Load a prompt template content from the package resources without rendering it.
    
    Args:
        template_path: Path to the template file relative to the cai package,
                      e.g., "prompts/system_bug_bounter.md"
    
    Returns:
        The raw template content as a string
    """
    try:
        # Normalize the path - remove 'cai/' prefix if it exists
        if template_path.startswith('cai/'):
            template_path = template_path[4:]  # Remove the 'cai/' prefix
        
        # Get the template file from package resources
        template_path_parts = template_path.split('/')
        package_path = ['cai'] + template_path_parts[:-1]
        package = '.'.join(package_path)
        filename = template_path_parts[-1]
        
        # Read the content from the package resources
        # Handle different importlib.resources APIs between Python versions
        try:
            # Python 3.9+ API
            template_content = importlib.resources.read_text(package, filename)
        except (TypeError, AttributeError):
            # Fallback for Python 3.8 and earlier
            with importlib.resources.path(package, filename) as path:
                template_content = pathlib.Path(path).read_text(encoding='utf-8')
        
        return template_content
    except Exception as e:
        debug_print(1, f"Failed to load template content '{template_path}': {str(e)}")
        raise ValueError(f"Failed to load template content '{template_path}': {str(e)}")

def load_prompt_template(template_path, **template_vars):
    """
    Load a prompt template from the package resources and render it with the given variables.
    
    Args:
        template_path: Path to the template file relative to the cai package,
                      e.g., "prompts/system_bug_bounter.md"
        **template_vars: Variables to use when rendering the template
    
    Returns:
        The rendered template as a string
    """
    try:
        template_content = get_template_content(template_path)
        
        # Render the template
        from mako.template import Template
        return Template(text=template_content).render(**template_vars)
    except Exception as e:
        debug_print(1, f"Failed to render template '{template_path}': {str(e)}")
        raise ValueError(f"Failed to render template '{template_path}': {str(e)}")