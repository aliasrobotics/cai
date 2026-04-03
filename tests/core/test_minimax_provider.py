"""Unit tests for MiniMaxProvider."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import AsyncOpenAI

from cai.sdk.agents import Agent, RunConfig, Runner
from cai.sdk.agents.models.interface import Model, ModelProvider
from cai.sdk.agents.models.minimax_provider import (
    MINIMAX_API_BASE_URL,
    MINIMAX_DEFAULT_MODEL,
    MiniMaxProvider,
)
from cai.sdk.agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from tests.fake_model import FakeModel
from tests.core.test_responses import get_text_message


class TestMiniMaxProviderInit:
    """Tests for MiniMaxProvider initialization."""

    def test_default_init_without_api_key_raises(self) -> None:
        """Creating a provider without an API key and without env var should
        raise ValueError on first use."""
        provider = MiniMaxProvider()
        with patch.dict(os.environ, {}, clear=True):
            # Remove MINIMAX_API_KEY if set
            env = os.environ.copy()
            env.pop("MINIMAX_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValueError, match="MiniMax API key not found"):
                    provider._get_client()

    def test_init_with_api_key(self) -> None:
        """Provider should accept an explicit API key."""
        provider = MiniMaxProvider(api_key="test-key-123")
        client = provider._get_client()
        assert isinstance(client, AsyncOpenAI)
        assert client.api_key == "test-key-123"

    def test_init_with_base_url(self) -> None:
        """Provider should accept a custom base URL."""
        provider = MiniMaxProvider(
            api_key="test-key",
            base_url="https://custom.minimax.io/v1",
        )
        client = provider._get_client()
        assert str(client.base_url).rstrip("/") == "https://custom.minimax.io/v1"

    def test_init_with_openai_client(self) -> None:
        """Provider should accept a pre-configured AsyncOpenAI client."""
        custom_client = AsyncOpenAI(
            api_key="custom-key",
            base_url="https://api.minimax.io/v1",
        )
        provider = MiniMaxProvider(openai_client=custom_client)
        assert provider._get_client() is custom_client

    def test_init_with_client_and_key_raises(self) -> None:
        """Providing both openai_client and api_key should raise."""
        custom_client = AsyncOpenAI(
            api_key="custom-key",
            base_url="https://api.minimax.io/v1",
        )
        with pytest.raises(AssertionError):
            MiniMaxProvider(openai_client=custom_client, api_key="extra-key")

    def test_init_with_env_api_key(self) -> None:
        """Provider should read from MINIMAX_API_KEY env var."""
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "env-key-456"}):
            provider = MiniMaxProvider()
            client = provider._get_client()
            assert client.api_key == "env-key-456"

    def test_default_base_url(self) -> None:
        """Provider should default to MiniMax API base URL."""
        provider = MiniMaxProvider(api_key="test-key")
        client = provider._get_client()
        assert str(client.base_url).rstrip("/") == MINIMAX_API_BASE_URL


class TestMiniMaxProviderGetModel:
    """Tests for MiniMaxProvider.get_model()."""

    def test_get_model_returns_chat_completions_model(self) -> None:
        """get_model should return an OpenAIChatCompletionsModel."""
        provider = MiniMaxProvider(api_key="test-key")
        model = provider.get_model("MiniMax-M2.7")
        assert isinstance(model, OpenAIChatCompletionsModel)

    def test_get_model_with_none_uses_default(self) -> None:
        """get_model(None) should use the default MiniMax model name."""
        provider = MiniMaxProvider(api_key="test-key")
        model = provider.get_model(None)
        assert isinstance(model, OpenAIChatCompletionsModel)
        assert model.model == MINIMAX_DEFAULT_MODEL

    def test_get_model_with_custom_name(self) -> None:
        """get_model should pass through a custom model name."""
        provider = MiniMaxProvider(api_key="test-key")
        model = provider.get_model("MiniMax-M2.5-highspeed")
        assert isinstance(model, OpenAIChatCompletionsModel)
        assert model.model == "MiniMax-M2.5-highspeed"

    def test_get_model_m2_5(self) -> None:
        """get_model should work with MiniMax-M2.5."""
        provider = MiniMaxProvider(api_key="test-key")
        model = provider.get_model("MiniMax-M2.5")
        assert isinstance(model, OpenAIChatCompletionsModel)
        assert model.model == "MiniMax-M2.5"

    def test_lazy_client_initialization(self) -> None:
        """Client should not be created until get_model is called."""
        provider = MiniMaxProvider(api_key="test-key")
        assert provider._client is None
        provider.get_model("MiniMax-M2.7")
        assert provider._client is not None


class TestMiniMaxProviderIsModelProvider:
    """Tests that MiniMaxProvider implements ModelProvider correctly."""

    def test_is_model_provider(self) -> None:
        """MiniMaxProvider should be an instance of ModelProvider."""
        provider = MiniMaxProvider(api_key="test-key")
        assert isinstance(provider, ModelProvider)

    def test_get_model_returns_model(self) -> None:
        """get_model should return an instance of Model."""
        provider = MiniMaxProvider(api_key="test-key")
        model = provider.get_model("MiniMax-M2.7")
        assert isinstance(model, Model)


class TestMiniMaxProviderWithRunner:
    """Tests for MiniMaxProvider integration with Runner."""

    @pytest.mark.asyncio
    async def test_run_config_with_minimax_provider(self) -> None:
        """MiniMaxProvider should work with RunConfig and Runner."""
        fake_model = FakeModel(initial_output=[get_text_message("minimax-response")])

        class MockMiniMaxProvider(ModelProvider):
            def __init__(self) -> None:
                self.last_requested: str | None = None

            def get_model(self, model_name: str | None) -> Model:
                self.last_requested = model_name
                return fake_model

        provider = MockMiniMaxProvider()
        agent = Agent(name="test", model="MiniMax-M2.7")
        run_config = RunConfig(model_provider=provider)
        result = await Runner.run(agent, input="Hello", run_config=run_config)

        assert provider.last_requested == "MiniMax-M2.7"
        assert result.final_output == "minimax-response"

    @pytest.mark.asyncio
    async def test_run_config_model_override(self) -> None:
        """Model name override in RunConfig should work with MiniMax provider."""
        fake_model = FakeModel(
            initial_output=[get_text_message("highspeed-response")]
        )

        class MockMiniMaxProvider(ModelProvider):
            def __init__(self) -> None:
                self.last_requested: str | None = None

            def get_model(self, model_name: str | None) -> Model:
                self.last_requested = model_name
                return fake_model

        provider = MockMiniMaxProvider()
        agent = Agent(name="test", model="MiniMax-M2.7")
        run_config = RunConfig(
            model="MiniMax-M2.5-highspeed", model_provider=provider
        )
        result = await Runner.run(agent, input="Hello", run_config=run_config)

        assert provider.last_requested == "MiniMax-M2.5-highspeed"
        assert result.final_output == "highspeed-response"


class TestMiniMaxProviderConstants:
    """Tests for MiniMax provider constants."""

    def test_default_model(self) -> None:
        assert MINIMAX_DEFAULT_MODEL == "MiniMax-M2.7"

    def test_api_base_url(self) -> None:
        assert MINIMAX_API_BASE_URL == "https://api.minimax.io/v1"
