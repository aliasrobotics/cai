"""LiteLLM adapter for OpenAI and Ollama/Qwen model calls.

Wraps ``litellm.acompletion`` with provider-specific parameter filtering,
tool_call_id truncation retry, and Response object construction for streaming.

Extracted from openai_chatcompletions.py [F] to reduce monolith size.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any, Literal, cast

import litellm
from openai import NOT_GIVEN, NotGiven
from openai.types.responses import Response

from cai.util import get_ollama_api_base
from ..fake_id import FAKE_RESPONSES_ID

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletion,
        ChatCompletionChunk,
        ChatCompletionToolChoiceOptionParam,
    )
    from openai import AsyncStream
    from ...model_settings import ModelSettings


_DEFAULT_MODEL_TIMEOUT = 180.0


def _configured_model_timeout() -> float | None:
    """Return CAI's LiteLLM request timeout in seconds.

    ``CAI_MODEL_TIMEOUT`` is the public name. ``CAI_LLM_TIMEOUT`` is accepted
    as a compatibility alias for local configs/scripts. Values <= 0 disable the
    injected timeout and defer entirely to LiteLLM/provider defaults.
    """
    raw = os.getenv("CAI_MODEL_TIMEOUT")
    if raw is None:
        raw = os.getenv("CAI_LLM_TIMEOUT")
    if raw is None or raw == "":
        return _DEFAULT_MODEL_TIMEOUT
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MODEL_TIMEOUT
    if timeout <= 0:
        return None
    return timeout


def _apply_litellm_timeouts(kwargs: dict, *, stream: bool) -> dict:
    """Add bounded model request timeouts unless the caller already set them."""
    timeout = _configured_model_timeout()
    if timeout is None:
        return kwargs
    kwargs.setdefault("timeout", timeout)
    if stream:
        kwargs.setdefault("stream_timeout", timeout)
    return kwargs


def _build_response_obj(
    model: str,
    model_settings: "ModelSettings",
    tool_choice: "ChatCompletionToolChoiceOptionParam | NotGiven",
    parallel_tool_calls: bool,
) -> Response:
    """Create a stub Response object used for streaming wrappers."""
    return Response(
        id=FAKE_RESPONSES_ID,
        created_at=time.time(),
        model=model,
        object="response",
        output=[],
        tool_choice="auto"
        if tool_choice is None or tool_choice == NOT_GIVEN
        else cast(Literal["auto", "required", "none"], tool_choice),
        top_p=model_settings.top_p,
        temperature=model_settings.temperature,
        tools=[],
        parallel_tool_calls=parallel_tool_calls or False,
    )


async def fetch_response_litellm_openai(
    *,
    kwargs: dict,
    model_name: str,
    model_settings: "ModelSettings",
    tool_choice: "ChatCompletionToolChoiceOptionParam | NotGiven",
    stream: bool,
    parallel_tool_calls: bool,
) -> "ChatCompletion | tuple[Response, AsyncStream[ChatCompletionChunk]]":
    """Handle standard LiteLLM API calls for OpenAI and compatible models.

    If a ContextWindowExceededError occurs due to a tool_call id being
    too long, truncate all tool_call ids in the messages to 40 characters
    and retry once silently.
    """
    kwargs = _apply_litellm_timeouts(kwargs, stream=stream)

    try:
        if stream:
            stream_obj = await litellm.acompletion(**kwargs)
            return _build_response_obj(model_name, model_settings, tool_choice, parallel_tool_calls), stream_obj
        else:
            return await litellm.acompletion(**kwargs)
    except Exception as e:
        error_msg = str(e)
        if (
            "string too long" in error_msg
            or "Invalid 'messages" in error_msg
            and "tool_call_id" in error_msg
            and "maximum length" in error_msg
        ):
            # Truncate all tool_call ids to 40 characters and retry once
            messages = kwargs.get("messages", [])
            for msg in messages:
                if (
                    "tool_call_id" in msg
                    and isinstance(msg["tool_call_id"], str)
                    and len(msg["tool_call_id"]) > 40
                ):
                    msg["tool_call_id"] = msg["tool_call_id"][:40]
                if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                    for tool_call in msg["tool_calls"]:
                        if (
                            isinstance(tool_call, dict)
                            and "id" in tool_call
                            and isinstance(tool_call["id"], str)
                            and len(tool_call["id"]) > 40
                        ):
                            tool_call["id"] = tool_call["id"][:40]
            kwargs["messages"] = messages

            if stream:
                stream_obj = await litellm.acompletion(**kwargs)
                return _build_response_obj(model_name, model_settings, tool_choice, parallel_tool_calls), stream_obj
            else:
                return await litellm.acompletion(**kwargs)
        else:
            raise


async def fetch_response_litellm_ollama(
    *,
    kwargs: dict,
    model_name: str,
    model_settings: "ModelSettings",
    tool_choice: "ChatCompletionToolChoiceOptionParam | NotGiven",
    stream: bool,
    parallel_tool_calls: bool,
) -> "ChatCompletion | tuple[Response, AsyncStream[ChatCompletionChunk]]":
    """Fetch a response from an Ollama or Qwen model using LiteLLM.

    Ensures that the 'format' parameter is not set to a JSON string, which
    can cause issues with the Ollama API, and filters to only supported params.
    """
    # Extract only supported parameters for Ollama
    ollama_supported_params = {
        "model": kwargs.get("model", ""),
        "messages": kwargs.get("messages", []),
        "stream": kwargs.get("stream", False),
    }

    for param in ["temperature", "top_p", "max_tokens"]:
        if param in kwargs and kwargs[param] is not NOT_GIVEN:
            ollama_supported_params[param] = kwargs[param]

    if "extra_headers" in kwargs:
        ollama_supported_params["extra_headers"] = kwargs["extra_headers"]

    if "tools" in kwargs and kwargs.get("tools") and kwargs.get("tools") is not NOT_GIVEN:
        ollama_supported_params["tools"] = kwargs.get("tools")

    ollama_kwargs = {
        k: v
        for k, v in ollama_supported_params.items()
        if v is not None and k not in ["response_format", "store"]
    }

    api_base = get_ollama_api_base()

    ollama_kwargs = _apply_litellm_timeouts(ollama_kwargs, stream=stream)

    if stream:
        response = _build_response_obj(model_name, model_settings, tool_choice, parallel_tool_calls)
        stream_obj = await litellm.acompletion(
            **ollama_kwargs, api_base=api_base, custom_llm_provider="openai"
        )
        return response, stream_obj
    else:
        return await litellm.acompletion(
            **ollama_kwargs,
            api_base=api_base,
            custom_llm_provider="openai",
        )
