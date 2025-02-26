"""
Calculate the cost of LLM usages. In different ways.

https://github.com/AgentOps-AI/tokencost inspired by:
https://github.com/oca/boxpwnr
"""

from tokencost import (  # pylint: disable=import-error
    calculate_cost_by_tokens
    as
    cost_by_tokens_and_model
)


def calculate_conversation_cost(
    total_input_tokens: int,
    total_output_tokens: int,
    model: str
) -> dict:
    """
    Calculate the total cost of a conversation based on pre-calculated input and output tokens.

    Args:
        total_input_tokens (int): Number of input tokens
        total_output_tokens (int): Number of output tokens
        model (str): The model name used in the conversation

    Returns:
        dict: Dictionary containing input cost
              output cost, and total cost in USD

    Example:
        calculate_conversation_cost(1000, 2000, "gpt-4")
        {'input_cost': 0.03, 'output_cost': 0.12, 'total_cost': 0.15, 'input_tokens': 1000, 'output_tokens': 2000} # noqa: E501, # pylint: disable=line-too-long
    """
    try:
        input_cost = cost_by_tokens_and_model(
            total_input_tokens, model, "input")
        output_cost = cost_by_tokens_and_model(
            total_output_tokens, model, "output")
        total_cost = input_cost + output_cost
    except KeyError:
        # Local Model or not fetched models by token cost
        # Check https://github.com/AgentOps-AI/tokencost for more information
        return {
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens
        }
    return {
        "input_cost": float(input_cost),
        "output_cost": float(output_cost),
        "total_cost": float(total_cost),
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens
    }
