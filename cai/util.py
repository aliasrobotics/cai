"""
This module contains utility functions for the CAI library.
"""
import inspect
import time
import json
import os
from datetime import datetime
from typing import Any, List
from types import SimpleNamespace
from importlib.resources import files
from mako.template import Template  # pylint: disable=import-error
from wasabi import color  # pylint: disable=import-error
from rich.text import Text  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.box import ROUNDED  # pylint: disable=import-error
from rich.console import Console, Group  # pylint: disable=import-error
from rich.theme import Theme  # pylint: disable=import-error
from rich.traceback import install  # pylint: disable=import-error
from rich.pretty import install as install_pretty  # pylint: disable=import-error # noqa: 501
from rich.tree import Tree  # pylint: disable=import-error
from cai.rag.vector_db import QdrantConnector # pylint: disable=import-error # noqa: E501

collection_name = os.getenv('CTF_NAME', 'default')

def get_previous_memory(query: str, top_k: int = 20) -> str:
    """
    Get the previous memory from the vector database.
    Returns steps ordered by ID from 1 to top_k.
    """
    vector_db = QdrantConnector()
    return vector_db.search(collection_name=collection_name, query_text=query, limit=top_k, sort_by_id=True)

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
    """Print agent messages/thoughts."""
    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    # TODO: consider using the timestamp from the message  # pylint: disable=fixme # noqa: E501
    # or the LLM interaction timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")

    text = Text()
    text.append(f"[{counter}] ", style="arrow")
    text.append(f"Agent: {agent_name} ", style="timestamp")
    if message:
        text.append(f">> {message} ", style="agent")
    text.append(f"[{timestamp}", style="dim")
    if model:
        text.append(
            f" ({model})", style="model")
    text.append("]", style="dim")

    # state and tokens
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

    console.print(text)


def cli_print_state(agent_name, message, counter, model, debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument # noqa: E501
                    interaction_input_tokens, interaction_output_tokens,
                    interaction_reasoning_tokens, total_input_tokens,
                    total_output_tokens, total_reasoning_tokens):
    """Print network state messages/thoughts."""
    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    # TODO: consider using the timestamp from the message  # pylint: disable=fixme # noqa: E501
    # or the LLM interaction timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    # agent header
    text = Text()
    # text.append(f"[{counter}] ", style="arrow")
    text.append("[-]", style="arrow")  # do not report on the turn
    text.append(f"Agent: {agent_name} ", style="timestamp")
    # timestamp and model
    text.append(f"[{timestamp}", style="dim")
    if model:
        text.append(
            f" ({model})", style="model")
    text.append("]", style="dim")

    # state and tokens
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
            Text(formatted_message, style="content"),
            tokens_text if tokens_text else Text("")
        ])
    except json.JSONDecodeError:
        # If message is not valid JSON, use it as-is
        group_content.extend([
            Text("⚠️ Invalid JSON", style="warning", justify="right"),
            Text(message, style="content"),
            tokens_text if tokens_text else Text("")
        ])

    if message:
        main_panel = Panel(
            Group(*group_content),
            title="",
            border_style="border_state",
            title_align="left",
            box=ROUNDED,
            padding=(1, 2),
            width=console.width,
            style="content"
        )

    # print
    console.print(text)
    if message:
        console.print(main_panel)


def _create_token_display(interaction_input_tokens, interaction_output_tokens,  # noqa: E501, pylint: disable=R0913
                          interaction_reasoning_tokens, total_input_tokens,
                          total_output_tokens, total_reasoning_tokens, model) -> Text:  # noqa: E501
    """
    Create a Text object displaying token usage information.

    Args:
        interaction_input_tokens: Input tokens for current interaction
        interaction_output_tokens: Output tokens for current interaction
        interaction_reasoning_tokens: Reasoning tokens for current interaction
        total_input_tokens: Total input tokens used
        total_output_tokens: Total output tokens used
        total_reasoning_tokens: Total reasoning tokens used
        model: The model being used

    Returns:
        rich.text.Text: Formatted token display text
    """
    tokens_text = Text(justify="right")
    # Current interaction tokens
    tokens_text.append(
        "\n(tokens) Current: ",
        style="current_token_count")
    tokens_text.append(
        f"I:{interaction_input_tokens} ",
        style="current_token_count")
    tokens_text.append(
        f"O:{interaction_output_tokens} ",
        style="current_token_count")
    tokens_text.append(
        f"R:{interaction_reasoning_tokens} ",
        style="current_token_count")

    # Total tokens
    tokens_text.append("| Total: ", style="total_token_count")
    tokens_text.append(
        f"I:{total_input_tokens} ",
        style="total_token_count")
    tokens_text.append(
        f"O:{total_output_tokens} ",
        style="total_token_count")
    tokens_text.append(
        f"R:{total_reasoning_tokens} ",
        style="total_token_count")

    # Context usage
    context_pct = interaction_input_tokens / \
        get_model_input_tokens(model) * 100
    tokens_text.append("| Context: ", style="context_tokens")
    tokens_text.append(f"{context_pct:.1f}% ", style="context_tokens")
    tokens_text.append(
        f"{'🟩' if context_pct < 50 else '🟨' if context_pct <
            80 else '🟥'} ({get_model_input_tokens(model)})",
        style="context_tokens")

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
    """Print tool call information."""

    if not debug:
        return

    if debug != 2:  # debug level 2
        return

    filtered_args = ({k: v for k, v in tool_args.items() if k != 'ctf'}
                        if tool_args else {})  # noqa: F541, E127
    args_str = ", ".join(f"{k}={v}" for k, v in filtered_args.items())

    text = Text()
    text.append(f"{tool_name}(", style="tool")
    text.append(args_str, style="args_str")
    if "agent" in tool_name.lower() or "transfer" in tool_name.lower(
    ) or "handoff" in tool_name.lower():
        text.append("Handoff", style="agent")
    text.append(
        ") ",
        style="tool")

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

        # If title text is too long for panel width, show it in the groups
        # instead, Convert Text object to string to get length
        title_width = len(str(text))
        max_title_width = console.width - 4  # Account for panel borders

        group_content = []
        if title_width > max_title_width:
            group_content.append(text)

        group_content.extend([
            Text(output, style="content"),
            tokens_text if tokens_text else Text("")
        ])

        main_panel = Panel(
            Group(*group_content),
            title="" if title_width > max_title_width else text,
            border_style="border",
            title_align="left",
            box=ROUNDED,
            padding=(1, 2),
            width=console.width,
            style="content"
        )
        console.print(main_panel)
    else:
        text.append("-> (No output)")
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


def merge_report_dicts(base_dict, new_dict):
    """
    Merge two report dictionaries recursively,
    handling lists and nested structures.

    Args:
        base_dict: The base dictionary to merge into
        new_dict: The new dictionary with values to merge

    Returns:
        dict: The merged dictionary
    """
    if not isinstance(base_dict, dict) or not isinstance(new_dict, dict):
        return new_dict
    for key, value in new_dict.items():
        if key not in base_dict:
            base_dict[key] = value
        elif isinstance(value, list) and isinstance(base_dict[key], list):
            # Merge lists, avoiding duplicates for findings
            if key == "findings":
                existing_ids = {
                    f.get("finding_id") for f in base_dict[key] if isinstance(
                        f, dict) and "finding_id" in f}
                for item in value:
                    if isinstance(  # noqa: E501
                            item, dict) and "finding_id" in item and \
                                item["finding_id"] not in existing_ids:  # noqa: E501
                        base_dict[key].append(item)
                        existing_ids.add(item["finding_id"])
            else:
                base_dict[key].extend(value)
        elif isinstance(value, dict) and isinstance(base_dict[key], dict):
            base_dict[key] = merge_report_dicts(base_dict[key], value)
        else:
            # For scalar values, prefer non-empty new values
            if value is not None and value != "":
                base_dict[key] = value
    return base_dict


def create_report_from_messages(history: List[dict]):
    """
    Create a report from a list of messages,
    merging content from Report Agent messages.

    Args:
        history: List of message dictionaries containing sender and content
    """
    report_data = {}  # last JSON message from Report Agent
    merged_report = {}  # merged JSON messages from Report Agent

    def to_namespace(obj):
        if isinstance(obj, dict):
            return SimpleNamespace(**{k: to_namespace(v)
                                   for k, v in obj.items()})
        if isinstance(obj, list):
            return [to_namespace(item) for item in obj]
        return obj
    # NOTE: Generic.py dont return a list of messages, it returns a string
    # so we need to handle it differently
    #
    for message in history:
        if message.get("sender") == "Report Agent":
            try:
                report_data = json.loads(message["content"])
                merged_report = merge_report_dicts(merged_report, report_data)
            except json.JSONDecodeError:
                # Continue if because some times report
                # agent sends non-JSON content (plain text responses)
                # and it's not a valid JSON
                continue
        merged_report = merge_report_dicts(merged_report, report_data)

    # To python variables
    report_data = {k: to_namespace(v) for k, v in merged_report.items()}
    report_data["history"] = history
    template = Template(
        str(files('caiextensions.report.ctf') / 'template.md')  # nosec: B702
    )
    report_output = template.render(**report_data)

    report_dir = "./report"
    os.makedirs(report_dir, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    save_path = f"Report_{timestamp}.md"
    report_path = os.path.join(report_dir, save_path)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_output)
    print(f"!Report generated at: {report_path}")


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
                    removal_assistant_entries.setdefault(msg_idx, set()).add(j)
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
