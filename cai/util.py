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
    'object': '\033[38;5;215m',     # Light orange
    'arg_key': '\033[38;5;228m',    # Light yellow
    'arg_value': '\033[38;5;180m',  # Light tan
    'function': '\033[38;5;219m',   # Pink
    'tool': '\033[38;5;147m',       # Soft purple
    'reset': '\033[0m'
}


def format_value(value: Any) -> str:
    """
    Format a value for debug printing with appropriate colors.
    """
    # Handle ChatCompletionMessage objects
    if hasattr(
            value, '__class__') and 'ChatCompletionMessage' in value.__class__.__name__:  # noqa: E501 # pylint: disable=C0301
        return format_chat_completion(value)

    # Handle lists
    if isinstance(value, list):  # pylint: disable=R1705
        items = []
        for item in value:
            if isinstance(item, dict):
                # Format dictionary items in the list
                dict_items = [
                    f"\n    {
                        COLORS['arg_key']}{k}{
                        COLORS['reset']}: {
                        format_value(v)}"
                    for k, v in item.items()
                ]
                items.append("{" + ",".join(dict_items) + "\n  }")
            else:
                items.append(format_value(item))
        return f"[\n  {','.join(items)}\n]"

    # Handle dictionaries
    elif isinstance(value, dict):
        formatted_items = [
            f"{COLORS['arg_key']}{k}{COLORS['reset']}: {format_value(v)}"
            for k, v in value.items()
        ]
        return "{ " + ", ".join(formatted_items) + " }"

    # Handle basic types
    else:
        return f"{COLORS['arg_value']}{str(value)}{COLORS['reset']}"


def format_chat_completion(msg) -> str:
    """
    Format a ChatCompletionMessage object with proper indentation and colors.
    """
    # Convert message to dict and handle OpenAI types
    try:
        msg_dict = json.loads(msg.model_dump_json())
    except AttributeError:
        msg_dict = msg.__dict__

    # Clean up the dictionary
    msg_dict = {k: v for k, v in msg_dict.items() if v is not None}

    # Format with json.dumps for consistent indentation
    formatted_json = json.dumps(msg_dict, indent=2)

    # Color the different parts
    colored_lines = []
    for line in formatted_json.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            # Handle nested structures
            if value.strip() in ['{', '[', '}', ']']:
                colored_lines.append(f"{COLORS['arg_key']}{key}{
                                     COLORS['reset']}:{value}")
            else:
                colored_lines.append(
                    f"{COLORS['arg_key']}{key}{COLORS['reset']}: "
                    f"{COLORS['arg_value']}{value.strip()}{COLORS['reset']}"
                )
        else:
            colored_lines.append(line)

    return f"\n  {COLORS['object']}ChatCompletionMessage{
        COLORS['reset']}(\n    " + '\n    '.join(colored_lines) + "\n  )"


def debug_print(debug: bool, intro: str, *args: Any) -> None:
    """
    Print debug messages if debug mode is enabled with color-coded components.
    """
    if not debug:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{COLORS['bracket']}[{COLORS['timestamp']}{
        timestamp}{COLORS['bracket']}]{COLORS['reset']}"

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
    else:
        formatted_intro = f"{COLORS['intro']}{intro}{COLORS['reset']}"
        formatted_args = []
        for arg in args:
            if isinstance(arg, str) and arg.startswith(
                    ('get_', 'list_', 'process_', 'handle_')):
                formatted_args.append(f"{COLORS['function']}{
                                      arg}{COLORS['reset']}")
            elif hasattr(arg, '__class__'):
                formatted_args.append(format_value(arg))
            else:
                formatted_args.append(format_value(arg))

        message = f"{header} {formatted_intro} {
            ' '.join(map(str, formatted_args))}"

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
