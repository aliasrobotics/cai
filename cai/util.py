"""
This module contains utility functions for the CAI library.
"""

import inspect
from datetime import datetime
from typing import Any
import json
import os
from wasabi import color  # pylint: disable=import-error
from rich.text import Text  # pylint: disable=import-error
from rich.panel import Panel  # pylint: disable=import-error
from rich.box import ROUNDED  # pylint: disable=import-error
from rich.console import Console, Group  # pylint: disable=import-error
from rich.theme import Theme  # pylint: disable=import-error
from rich.traceback import install  # pylint: disable=import-error
from rich.pretty import install as install_pretty  # pylint: disable=import-error # noqa: 501


theme = Theme({
    # Primary colors - Material Design inspired
    "timestamp": "#00BCD4",  # Cyan 500
    "agent": "#4CAF50",      # Green 500
    "arrow": "#FFFFFF",      # White
    "content": "#ECEFF1",    # Blue Grey 50
    "tool": "#F44336",       # Red 500

    # Secondary colors
    "total_token_count": "#FFC107",  # Amber 500
    "cost": "#009688",        # Teal 500

    # UI elements
    "border": "#2196F3",      # Blue 500
    "model": "#673AB7",       # Deep Purple 500
    "dim": "#9E9E9E",         # Grey 500

    # Status indicators
    "success": "#4CAF50",     # Green 500
    "warning": "#FF9800",     # Orange 500
    "error": "#F44336"        # Red 500
})

console = Console(theme=theme)
_message_counters = {}
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


def cli_print(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements,too-many-nested-blocks,too-many-branches,broad-exception-caught # noqa: E501
    agent_name=None,
    message=None,
    tool_name=None,
    tool_args=None,
    tool_output=None,
    model=None,
    turn_token_count=None,
    total_token_count=None,
    debug=0,
    n_turn=0
) -> None:
    """
    Print a CLI message with improved formatting including timestamps
    token counts and costs.

    Args:
        agent_name: Name of the agent
        message: The message content
        tool_name: Name of the tool being called
        tool_args: Arguments passed to the tool
        tool_output: Output from the tool execution
        model: Model name being used
        turn_token_count: Number of tokens used in this turn
        total_token_count: Total number of tokens used
        debug: Whether to print in debug mode (0, 1, 2)
        n_turn: Number of the turn
    """
    if not debug:  # Add early return if debug is False
        return

    if debug != 2:  # debug level 2
        return

    # def _update_counter(agent_name):
    #     """Update and return message counter for an agent."""
    #     if agent_name not in _message_counters:
    #         _message_counters[agent_name] = 0
    #     _message_counters[agent_name] += 1
    #     return _message_counters[agent_name]

    def _print_agent_messages(message, counter, timestamp, model):
        """Print agent messages/thoughts."""
        if isinstance(message, list):  # pylint: disable=too-many-nested-blocks
            for msg in message:
                if msg.get("role") == "assistant":
                    content = msg.get('content')
                    if content and isinstance(content, str):
                        content = content.strip()
                        if content:
                            text = Text()
                            text.append(f"[{counter}] ", style="arrow")
                            text.append(
                                f"{msg.get('sender', 'AGENT')} >> ",
                                style="timestamp")
                            text.append(f"{content} ", style="agent")
                            text.append(f"[{timestamp}", style="dim")
                            if model:
                                text.append(
                                    f" ({model})", style="model")
                            text.append("]", style="dim")
                            console.print(text)

    def _print_tool_call(agent_name, tool_name, tool_args,
                         counter, timestamp, model):  # pylint: disable=too-many-arguments # noqa: E501
        """Print tool call information."""
        filtered_args = ({k: v for k, v in tool_args.items() if k != 'ctf'}
                         if tool_args else {})  # noqa: F541
        args_str = ", ".join(f"{k}={v}" for k, v in filtered_args.items())

        text = Text()
        text.append(f"[{counter}] ", style="arrow")
        text.append(f"{agent_name} >> ", style="timestamp")
        text.append(f"{tool_name}(", style="tool")
        text.append(args_str, style="total_token_count")
        text.append(
            ") ",
            style="tool")
        text.append(f"[{timestamp}", style="dim")
        if model:
            text.append(f" ({model})", style="model")
        text.append("]", style="dim")
        console.print(text)
        return args_str

    def _print_tool_output(tool_name, args_str,
                           tool_output, turn_token_count, total_token_count):
        """Print tool output with optional token information."""
        if tool_output:
            max_length = 5000
            output = str(tool_output)
            output = (output[:max_length] + "...\n[Output truncated]"
                      if len(output) > max_length else output)

            token_str = ""  # nosec B105:hardcoded_password_string
            if turn_token_count is not None and total_token_count is not None:
                token_str = f"Turn tokens: {
                    turn_token_count} Total tokens: {total_token_count}"

            main_panel = Panel(
                Group(
                    Text(output, style="content"),
                    Text(token_str, style="dim", justify="right")
                    if token_str else Text("")
                ),
                title=f"{tool_name}({args_str})",
                border_style="border",
                title_align="left",
                box=ROUNDED,
                padding=(1, 2),
                width=console.width,
                style="content"
            )
            console.print(main_panel)

    try:
        # TODO: consider using the timestamp from the message  # pylint: disable=fixme # noqa: E501
        # or the LLM interaction timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        # counter = _update_counter(agent_name) if agent_name else None

        if message:
            _print_agent_messages(message, n_turn, timestamp, model)

        if tool_name:
            args_str = _print_tool_call(agent_name, tool_name, tool_args,
                                        n_turn, timestamp, model)
            _print_tool_output(
                tool_name,
                args_str,
                tool_output,
                turn_token_count,
                total_token_count)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Error printing message: {str(exc)}")


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
        if param.default == inspect._empty  # pylint: disable=protected-access
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
