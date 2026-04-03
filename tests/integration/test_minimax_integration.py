"""Integration tests for MiniMax provider.

These tests require a valid MINIMAX_API_KEY environment variable and network
access to the MiniMax API.

Run with:
    MINIMAX_API_KEY=<key> pytest tests/integration/test_minimax_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from cai.sdk.agents import (
    Agent,
    ModelSettings,
    RunConfig,
    Runner,
    set_tracing_disabled,
)
from cai.sdk.agents.models.minimax_provider import MiniMaxProvider

# Disable tracing for integration tests (no OpenAI key needed)
set_tracing_disabled(disabled=True)

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
pytestmark = [
    pytest.mark.skipif(
        not MINIMAX_API_KEY,
        reason="MINIMAX_API_KEY not set",
    ),
    pytest.mark.allow_call_model_methods,
]


@pytest.fixture
def minimax_provider() -> MiniMaxProvider:
    return MiniMaxProvider(api_key=MINIMAX_API_KEY)


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_minimax_m27_basic_response(minimax_provider: MiniMaxProvider) -> None:
    """MiniMax-M2.7 should return a basic text response."""
    set_tracing_disabled(disabled=True)
    agent = Agent(
        name="test",
        instructions="Respond with exactly: HELLO",
        model="MiniMax-M2.7",
    )
    result = await Runner.run(
        agent,
        "Say hello",
        run_config=RunConfig(
            model_provider=minimax_provider,
            model_settings=ModelSettings(temperature=0.01, max_tokens=50),
        ),
    )
    assert result.final_output is not None
    assert len(result.final_output) > 0


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_minimax_m25_highspeed(minimax_provider: MiniMaxProvider) -> None:
    """MiniMax-M2.5-highspeed should return a response."""
    set_tracing_disabled(disabled=True)
    agent = Agent(
        name="test",
        instructions="Respond with exactly: OK",
        model="MiniMax-M2.5-highspeed",
    )
    result = await Runner.run(
        agent,
        "Confirm",
        run_config=RunConfig(
            model_provider=minimax_provider,
            model_settings=ModelSettings(temperature=0.01, max_tokens=50),
        ),
    )
    assert result.final_output is not None
    assert len(result.final_output) > 0


@pytest.mark.asyncio
@pytest.mark.timeout(120)
async def test_minimax_m25(minimax_provider: MiniMaxProvider) -> None:
    """MiniMax-M2.5 should return a response."""
    set_tracing_disabled(disabled=True)
    agent = Agent(
        name="test",
        instructions="Respond with exactly: OK",
        model="MiniMax-M2.5",
    )
    result = await Runner.run(
        agent,
        "Confirm",
        run_config=RunConfig(
            model_provider=minimax_provider,
            model_settings=ModelSettings(temperature=0.01, max_tokens=50),
        ),
    )
    assert result.final_output is not None
    assert len(result.final_output) > 0
