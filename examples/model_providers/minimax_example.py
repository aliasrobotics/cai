"""Example of using MiniMax as an LLM provider with CAI.

Prerequisites:
    - Set the MINIMAX_API_KEY environment variable.

Usage:
    python examples/model_providers/minimax_example.py
"""

from __future__ import annotations

import asyncio
import os

from agents import (
    Agent,
    RunConfig,
    Runner,
    function_tool,
    set_tracing_disabled,
)
from agents.models.minimax_provider import MiniMaxProvider

# Disable tracing if you don't have an OpenAI API key for trace uploads
set_tracing_disabled(disabled=True)

# Create the MiniMax provider (reads MINIMAX_API_KEY from env)
minimax_provider = MiniMaxProvider()


@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is sunny and 22°C."


async def main():
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant. Keep answers concise.",
        tools=[get_weather],
    )

    # Use MiniMax-M2.7 (default)
    result = await Runner.run(
        agent,
        "What's the weather in Tokyo?",
        run_config=RunConfig(model_provider=minimax_provider),
    )
    print("MiniMax-M2.7 response:", result.final_output)

    # Use MiniMax-M2.5-highspeed for faster responses
    highspeed_provider = MiniMaxProvider()
    agent_fast = Agent(
        name="Fast Assistant",
        instructions="You are a helpful assistant. Keep answers concise.",
        model="MiniMax-M2.5-highspeed",
    )

    result = await Runner.run(
        agent_fast,
        "Tell me a short joke.",
        run_config=RunConfig(model_provider=highspeed_provider),
    )
    print("MiniMax-M2.5-highspeed response:", result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
