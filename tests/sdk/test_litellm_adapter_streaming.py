import pytest
from openai import NOT_GIVEN

from cai.sdk.agents.model_settings import ModelSettings
from cai.sdk.agents.models.chatcompletions.litellm_adapter import (
    fetch_response_litellm_openai,
)


@pytest.mark.asyncio
async def test_litellm_streaming_fetch_opens_one_completion(monkeypatch):
    calls = []
    sentinel_stream = object()

    async def fake_acompletion(**kwargs):
        calls.append(kwargs.copy())
        return sentinel_stream

    monkeypatch.setattr(
        "cai.sdk.agents.models.chatcompletions.litellm_adapter.litellm.acompletion",
        fake_acompletion,
    )

    response, stream = await fetch_response_litellm_openai(
        kwargs={"model": "deepseek/deepseek-v4-pro", "messages": [], "stream": True},
        model_name="deepseek/deepseek-v4-pro",
        model_settings=ModelSettings(),
        tool_choice=NOT_GIVEN,
        stream=True,
        parallel_tool_calls=False,
    )

    assert stream is sentinel_stream
    assert response.model == "deepseek/deepseek-v4-pro"
    assert len(calls) == 1
    assert calls[0]["stream"] is True


@pytest.mark.asyncio
async def test_litellm_streaming_tool_call_id_retry_opens_one_retry_stream(monkeypatch):
    calls = []
    sentinel_stream = object()

    async def fake_acompletion(**kwargs):
        calls.append(kwargs.copy())
        if len(calls) == 1:
            raise Exception("Invalid 'messages': tool_call_id string too long maximum length")
        return sentinel_stream

    monkeypatch.setattr(
        "cai.sdk.agents.models.chatcompletions.litellm_adapter.litellm.acompletion",
        fake_acompletion,
    )

    long_id = "call_" + "x" * 80
    kwargs = {
        "model": "deepseek/deepseek-v4-pro",
        "messages": [
            {"role": "tool", "tool_call_id": long_id, "content": "ok"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": long_id,
                        "type": "function",
                        "function": {"name": "probe", "arguments": "{}"},
                    }
                ],
            },
        ],
        "stream": True,
    }

    _response, stream = await fetch_response_litellm_openai(
        kwargs=kwargs,
        model_name="deepseek/deepseek-v4-pro",
        model_settings=ModelSettings(),
        tool_choice=NOT_GIVEN,
        stream=True,
        parallel_tool_calls=False,
    )

    assert stream is sentinel_stream
    assert len(calls) == 2
    assert kwargs["messages"][0]["tool_call_id"] == long_id[:40]
    assert kwargs["messages"][1]["tool_calls"][0]["id"] == long_id[:40]


@pytest.mark.asyncio
async def test_litellm_streaming_applies_default_model_timeout(monkeypatch):
    monkeypatch.delenv("CAI_MODEL_TIMEOUT", raising=False)
    monkeypatch.delenv("CAI_LLM_TIMEOUT", raising=False)
    calls = []
    sentinel_stream = object()

    async def fake_acompletion(**kwargs):
        calls.append(kwargs.copy())
        return sentinel_stream

    monkeypatch.setattr(
        "cai.sdk.agents.models.chatcompletions.litellm_adapter.litellm.acompletion",
        fake_acompletion,
    )

    _response, stream = await fetch_response_litellm_openai(
        kwargs={"model": "deepseek/deepseek-v4-pro", "messages": [], "stream": True},
        model_name="deepseek/deepseek-v4-pro",
        model_settings=ModelSettings(),
        tool_choice=NOT_GIVEN,
        stream=True,
        parallel_tool_calls=False,
    )

    assert stream is sentinel_stream
    assert calls[0]["timeout"] == 180.0
    assert calls[0]["stream_timeout"] == 180.0


@pytest.mark.asyncio
async def test_litellm_model_timeout_uses_env_override(monkeypatch):
    monkeypatch.setenv("CAI_MODEL_TIMEOUT", "45")
    calls = []
    sentinel_response = object()

    async def fake_acompletion(**kwargs):
        calls.append(kwargs.copy())
        return sentinel_response

    monkeypatch.setattr(
        "cai.sdk.agents.models.chatcompletions.litellm_adapter.litellm.acompletion",
        fake_acompletion,
    )

    response = await fetch_response_litellm_openai(
        kwargs={"model": "deepseek/deepseek-v4-pro", "messages": [], "stream": False},
        model_name="deepseek/deepseek-v4-pro",
        model_settings=ModelSettings(),
        tool_choice=NOT_GIVEN,
        stream=False,
        parallel_tool_calls=False,
    )

    assert response is sentinel_response
    assert calls[0]["timeout"] == 45.0
    assert "stream_timeout" not in calls[0]
