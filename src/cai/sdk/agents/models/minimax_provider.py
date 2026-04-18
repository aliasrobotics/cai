from __future__ import annotations

import os

import httpx
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from .interface import Model, ModelProvider
from .openai_chatcompletions import OpenAIChatCompletionsModel

MINIMAX_DEFAULT_MODEL: str = "MiniMax-M2.7"
MINIMAX_API_BASE_URL: str = "https://api.minimax.io/v1"

_http_client: httpx.AsyncClient | None = None


def _shared_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = DefaultAsyncHttpxClient()
    return _http_client


class MiniMaxProvider(ModelProvider):
    """A model provider that uses MiniMax's OpenAI-compatible API.

    MiniMax provides large language models accessible via an OpenAI-compatible
    chat completions endpoint. Supported models include MiniMax-M2.7,
    MiniMax-M2.5, and MiniMax-M2.5-highspeed.

    The provider reads the API key from the ``MINIMAX_API_KEY`` environment
    variable by default, or you can pass it explicitly.

    Example usage::

        from cai.sdk.agents import Agent, Runner, RunConfig
        from cai.sdk.agents.models.minimax_provider import MiniMaxProvider

        provider = MiniMaxProvider()
        agent = Agent(name="assistant", instructions="You are helpful.")
        result = await Runner.run(
            agent,
            "Hello!",
            run_config=RunConfig(model_provider=provider),
        )
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        """Create a new MiniMax provider.

        Args:
            api_key: The MiniMax API key. If not provided, reads from the
                ``MINIMAX_API_KEY`` environment variable.
            base_url: The base URL for the MiniMax API. Defaults to
                ``https://api.minimax.io/v1``.
            openai_client: An optional pre-configured AsyncOpenAI client.
                If provided, ``api_key`` and ``base_url`` are ignored.
        """
        if openai_client is not None:
            assert api_key is None and base_url is None, (
                "Don't provide api_key or base_url if you provide openai_client"
            )
            self._client: AsyncOpenAI | None = openai_client
        else:
            self._client = None
            self._stored_api_key = api_key
            self._stored_base_url = base_url

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = self._stored_api_key or os.environ.get("MINIMAX_API_KEY")
            if not api_key:
                raise ValueError(
                    "MiniMax API key not found. Set the MINIMAX_API_KEY environment "
                    "variable or pass api_key to MiniMaxProvider()."
                )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self._stored_base_url or MINIMAX_API_BASE_URL,
                http_client=_shared_http_client(),
            )
        return self._client

    def get_model(self, model_name: str | None) -> Model:
        if model_name is None:
            model_name = MINIMAX_DEFAULT_MODEL

        client = self._get_client()
        return OpenAIChatCompletionsModel(model=model_name, openai_client=client)
