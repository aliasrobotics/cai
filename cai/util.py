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
from typing import Any

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
from cai.cost.llm_cost import calculate_conversation_cost
from cai.graph import Node, get_default_graph
from cai.types import (
    Agent,
    ChatCompletionMessageToolCall
)

# Global timing variables
GLOBAL_START_TIME = None
LAST_TOOL_TIME = None


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
    global GLOBAL_START_TIME  # pylint: disable=global-statement
    GLOBAL_START_TIME = time.time()


def reset_global_timer():
    """Reset the global timer."""
    global GLOBAL_START_TIME  # pylint: disable=global-statement
    GLOBAL_START_TIME = None


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
                             total_reasoning_tokens=None):
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
            model
        )
        text.append(tokens_text)

    # Create a panel for better visual separation
    panel = Panel(
        text,
        border_style="blue",
        box=ROUNDED,
        padding=(0, 1),
        title="[bold]Agent Interaction[/bold]",
        title_align="left"
    )
    console.print(panel)


def cli_print_state(agent_name, message, counter, model, debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument # noqa: E501
                    interaction_input_tokens, interaction_output_tokens,
                    interaction_reasoning_tokens, total_input_tokens,
                    total_output_tokens, total_reasoning_tokens):
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
            model
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
                               total_reasoning_tokens=None):
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
            model
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
    model
) -> Text:  # noqa: E501
    """
    Create a Text object displaying token usage information
    with enhanced formatting.
    """
    tokens_text = Text(justify="right")

    # Current interaction tokens with enhanced styling
    tokens_text.append("\n", style="bold")
    tokens_text.append("(tokens)", style="")
    tokens_text.append(" Interaction: ", style="bold")
    tokens_text.append(f"I:{interaction_input_tokens} ", style="green")
    tokens_text.append(f"O:{interaction_output_tokens} ", style="red")
    tokens_text.append(f"R:{interaction_reasoning_tokens} ", style="yellow")

    # Calculate and display current interaction cost
    current_costs = calculate_conversation_cost(
        interaction_input_tokens,
        interaction_output_tokens,
        model
    )
    tokens_text.append(f"(${current_costs['total_cost']:.4f}) ", style="bold")

    # Total tokens with enhanced styling
    tokens_text.append("| Total: ", style="bold")
    tokens_text.append(f"I:{total_input_tokens} ", style="green")
    tokens_text.append(f"O:{total_output_tokens} ", style="red")
    tokens_text.append(f"R:{total_reasoning_tokens} ", style="yellow")

    total_costs = calculate_conversation_cost(
        total_input_tokens,
        total_output_tokens,
        model
    )
    tokens_text.append(f"(${total_costs['total_cost']:.4f}) ", style="bold")

    # Context usage with enhanced styling
    context_pct = interaction_input_tokens / \
        get_model_input_tokens(model) * 100
    tokens_text.append("| Context: ", style="bold")
    tokens_text.append(f"{context_pct:.1f}% ", style="bold")

    # Enhanced context indicator
    if context_pct < 50:
        indicator = "🟩"
        color_local = "green"
    elif context_pct < 80:
        indicator = "🟨"
        color_local = "yellow"
    else:
        indicator = "🟥"
        color_local = "red"

    tokens_text.append(
        f"{indicator} ({get_model_input_tokens(model)})",
        style=color_local
    )

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
                        debug):
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
                model
            )

        # Handle panel width and content
        title_width = len(str(text))
        max_title_width = console.width - 4

        group_content = []
        if title_width > max_title_width:
            group_content.append(text)

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


def function_to_json(func) -> dict:
    """
    Converts a Python function into a JSON-serializable dictionary
    that describes the function's signature, including its name,
    description, and parameters.

    Args:
        func: The function to be converted.

    Returns:
        A dictionary representing the function's signature in JSON format.
    """
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }
    try:
        signature = inspect.signature(func)
    except ValueError as e:
        raise ValueError(
            f"Failed to get signature for function {func.__name__}: {str(e)}"
        ) from e
    parameters = {}
    for param in signature.parameters.values():
        # Skip the ctf parameter
        if param.name == "ctf":
            continue
        try:
            param_type = type_map.get(param.annotation, "string")
        except KeyError as e:
            raise KeyError(
                f"Unknown type annotation {param.annotation} for parameter {param.name}: {str(e)}"  # noqa: E501 # pylint: disable=C0301
            ) from e
        parameters[param.name] = {"type": param_type}

    required = [
        param.name
        for param in signature.parameters.values()
        if param.default == inspect._empty and param.name != "ctf"  # pylint: disable=protected-access # noqa: E501
    ]
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        },
    }


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
        else (challenges[0] if len(challenges) > 0 else None)
    )
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
