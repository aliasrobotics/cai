"""LiteLLM adapter for OpenAI and Ollama/Qwen model calls.

Wraps ``litellm.acompletion`` with provider-specific parameter filtering,
tool_call_id truncation retry, and Response object construction for streaming.

Extracted from openai_chatcompletions.py [F] to reduce monolith size.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any, Literal, cast

import litellm
from openai import NOT_GIVEN, NotGiven
from openai.types.responses import Response

from cai.errors import LLMTimeout
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


def configured_model_timeout() -> float | None:
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


def apply_litellm_timeouts(kwargs: dict, *, stream: bool = False) -> dict:
    """Add bounded LiteLLM request timeouts unless the caller already set them."""
    timeout = configured_model_timeout()
    if timeout is None:
        return kwargs
    kwargs.setdefault("timeout", timeout)
    if stream:
        kwargs.setdefault("stream_timeout", timeout)
    return kwargs


def _timeout_from_kwargs(kwargs: dict) -> float | None:
    """Return the effective numeric timeout for CAI's outer asyncio guard."""
    raw_timeout = kwargs.get("timeout", configured_model_timeout())
    if raw_timeout is None:
        return None
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError):
        return configured_model_timeout()
    if timeout <= 0:
        return None
    return timeout


def wrap_stream_with_idle_timeout(stream_obj: Any, *, model_name: str, timeout: float | None = None) -> Any:
    """Bound waits for each streamed chunk.

    Some LiteLLM/provider combinations return the stream object quickly, then
    stall while the caller awaits the next SSE chunk. ``timeout``/
    ``stream_timeout`` do not consistently protect that phase, so CAI wraps the
    async iterator itself. Non-async-iterable test doubles are returned as-is.
    """
    if timeout is None:
        timeout = configured_model_timeout()
    if timeout is None or not hasattr(stream_obj, "__aiter__"):
        return stream_obj

    async def _iter_with_timeout():
        iterator = stream_obj.__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
            except StopAsyncIteration:
                return
            except asyncio.TimeoutError as exc:
                raise LLMTimeout(
                    f"Timed out waiting for streamed model chunk after {timeout:g}s "
                    f"[{model_name}]"
                ) from exc
            yield chunk

    return _iter_with_timeout()


async def acompletion_with_timeout(
    kwargs: dict,
    *,
    stream: bool = False,
    model_name: str | None = None,
) -> Any:
    """Call LiteLLM with CAI request and stream-idle timeouts applied."""
    kwargs = apply_litellm_timeouts(kwargs, stream=stream)
    timeout = _timeout_from_kwargs(kwargs)
    model_label = str(model_name or kwargs.get("model") or "unknown model")

    completion_coro = litellm.acompletion(**kwargs)
    try:
        if timeout is None:
            result = await completion_coro
        else:
            result = await asyncio.wait_for(completion_coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise LLMTimeout(
            f"Timed out waiting for model response after {timeout:g}s [{model_label}]"
        ) from exc

    if stream:
        return wrap_stream_with_idle_timeout(result, model_name=model_label, timeout=timeout)
    return result


# Backward-compatible private aliases for local/internal imports.
_configured_model_timeout = configured_model_timeout
_apply_litellm_timeouts = apply_litellm_timeouts
_wrap_stream_with_idle_timeout = wrap_stream_with_idle_timeout
_acompletion_with_timeout = acompletion_with_timeout


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
            stream_obj = await acompletion_with_timeout(kwargs, stream=True, model_name=model_name)
            return _build_response_obj(model_name, model_settings, tool_choice, parallel_tool_calls), stream_obj
        else:
            return await acompletion_with_timeout(kwargs, stream=False, model_name=model_name)
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
                stream_obj = await acompletion_with_timeout(kwargs, stream=True, model_name=model_name)
                return _build_response_obj(model_name, model_settings, tool_choice, parallel_tool_calls), stream_obj
            else:
                return await acompletion_with_timeout(kwargs, stream=False, model_name=model_name)
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

    call_kwargs = {
        **ollama_kwargs,
        "api_base": api_base,
        "custom_llm_provider": "openai",
    }

    if stream:
        response = _build_response_obj(model_name, model_settings, tool_choice, parallel_tool_calls)
        stream_obj = await acompletion_with_timeout(call_kwargs, stream=True, model_name=model_name)
        return response, stream_obj
    else:
        return await acompletion_with_timeout(call_kwargs, stream=False, model_name=model_name)
