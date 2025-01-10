"""
This module contains utility functions for the CAI library.
"""

import inspect
from datetime import datetime
from typing import Any
import json

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


def format_value(value: Any, prev_value: Any = None) -> str:  # pylint: disable=too-many-locals # noqa: E501
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
                    formatted_value = format_value(v, prev_v)
                    dict_items.append(
                        f"\n    {color_key}{k}{
                            COLORS['reset']}: {formatted_value}")
                items.append("{" + ",".join(dict_items) + "\n  }")
            else:
                items.append(format_value(item, prev_item))
        return f"[\n  {','.join(items)}\n]"

    # Handle dictionaries
    elif isinstance(value, dict):
        formatted_items = []
        for k, v in value.items():
            prev_v = prev_value.get(k) if prev_value and isinstance(
                prev_value, dict) else None
            color_key = get_color('arg_key', k, k if prev_value else None)
            formatted_value = format_value(v, prev_v)
            formatted_items.append(
                f"{color_key}{k}{
                    COLORS['reset']}: {formatted_value}")
        return "{ " + ", ".join(formatted_items) + " }"

    # Handle basic types
    else:
        color = get_color('arg_value', value, prev_value)
        return f"{color}{str(value)}{COLORS['reset']}"


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


def debug_print(debug: bool, intro: str, *args: Any, brief: bool = False) -> None:  # pylint: disable=too-many-locals # noqa: E501
    """
    Print debug messages if debug mode is enabled with color-coded components.
    If brief is True, prints a simplified timestamp and message format.
    """
    if not debug:
        return

    if brief:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
