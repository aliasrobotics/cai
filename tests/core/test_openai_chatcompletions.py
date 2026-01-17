from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from openai import NOT_GIVEN
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from openai.types.completion_usage import CompletionUsage
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
)

from cai.sdk.agents import (
    ModelResponse,
    ModelSettings,
    ModelTracing,
    OpenAIChatCompletionsModel,
    OpenAIProvider,
    generation_span,
)
from cai.sdk.agents.models.fake_id import FAKE_RESPONSES_ID
import os
cai_model = os.getenv('CAI_MODEL', "qwen2.5:14b")

@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_get_response_with_text_message(monkeypatch) -> None:
    """
    When the model returns a ChatCompletionMessage with plain text content,
    `get_response` should produce a single `ResponseOutputMessage` containing
    a `ResponseOutputText` with that content, and a `Usage` populated from
    the completion's usage.
    """
    msg = ChatCompletionMessage(role="assistant", content="Hello")
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=CompletionUsage(completion_tokens=5, prompt_tokens=7, total_tokens=12),
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    resp: ModelResponse = await model.get_response(
        system_instructions=None,
        input="",
        model_settings=ModelSettings(),
        tools=[],
        output_schema=None,
        handoffs=[],
        tracing=ModelTracing.DISABLED,
    )
    # Should have produced exactly one output message with one text part
    assert isinstance(resp, ModelResponse)
    assert len(resp.output) == 1
    assert isinstance(resp.output[0], ResponseOutputMessage)
    msg_item = resp.output[0]
    assert len(msg_item.content) == 1
    assert isinstance(msg_item.content[0], ResponseOutputText)
    assert msg_item.content[0].text == "Hello"
    # Usage should be preserved from underlying ChatCompletion.usage
    assert resp.usage.input_tokens == 7
    assert resp.usage.output_tokens == 5
    assert resp.usage.total_tokens == 12
    assert resp.referenceable_id is None


@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_get_response_with_refusal(monkeypatch) -> None:
    """
    When the model returns a ChatCompletionMessage with a `refusal` instead
    of normal `content`, `get_response` should produce a single
    `ResponseOutputMessage` containing a `ResponseOutputRefusal` part.
    """
    msg = ChatCompletionMessage(role="assistant", refusal="No thanks")
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=None,
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    resp: ModelResponse = await model.get_response(
        system_instructions=None,
        input="",
        model_settings=ModelSettings(),
        tools=[],
        output_schema=None,
        handoffs=[],
        tracing=ModelTracing.DISABLED,
    )
    assert len(resp.output) == 1
    assert isinstance(resp.output[0], ResponseOutputMessage)
    refusal_part = resp.output[0].content[0]
    assert isinstance(refusal_part, ResponseOutputRefusal)
    assert refusal_part.refusal == "No thanks"
    # With no usage from the completion, usage defaults to zeros.
    assert resp.usage.requests == 1
    assert resp.usage.input_tokens == 5
    assert resp.usage.output_tokens == 0


@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_get_response_with_tool_call(monkeypatch) -> None:
    """
    If the ChatCompletionMessage includes one or more tool_calls, `get_response`
    should append corresponding `ResponseFunctionToolCall` items after the
    assistant message item with matching name/arguments.
    """
    tool_call = ChatCompletionMessageToolCall(
        id="call-id",
        type="function",
        function=Function(name="do_thing", arguments="{'x':1}"),
    )
    msg = ChatCompletionMessage(role="assistant", content="Hi", tool_calls=[tool_call])
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=None,
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    resp: ModelResponse = await model.get_response(
        system_instructions=None,
        input="",
        model_settings=ModelSettings(),
        tools=[],
        output_schema=None,
        handoffs=[],
        tracing=ModelTracing.DISABLED,
    )
    # Expect a message item followed by a function tool call item.
    assert len(resp.output) == 2
    assert isinstance(resp.output[0], ResponseOutputMessage)
    fn_call_item = resp.output[1]
    assert isinstance(fn_call_item, ResponseFunctionToolCall)
    assert fn_call_item.call_id == "call-id"
    assert fn_call_item.name == "do_thing"
    assert fn_call_item.arguments == "{'x':1}"

@pytest.mark.asyncio
async def test_fetch_response_non_stream(monkeypatch) -> None:
    """
    Verify that `_fetch_response` builds the correct OpenAI API call when not
    streaming and returns the ChatCompletion object directly. We supply a
    dummy ChatCompletion through a stubbed OpenAI client and inspect the
    captured kwargs.
    """

    # Dummy completions to record kwargs
    class DummyCompletions:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] = {}

        async def create(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            return chat

    class DummyClient:
        def __init__(self, completions: DummyCompletions) -> None:
            self.chat = type("_Chat", (), {"completions": completions})()
            self.base_url = httpx.URL("http://fake")

    msg = ChatCompletionMessage(role="assistant", content="ignored")
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
    )
    completions = DummyCompletions()
    dummy_client = DummyClient(completions)
    model = OpenAIChatCompletionsModel(model=cai_model, openai_client=dummy_client)  # type: ignore
    # Execute the private fetch with a system instruction and simple string input.
    with generation_span(disabled=True) as span:
        result = await model._fetch_response(
            system_instructions="sys",
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            span=span,
            tracing=ModelTracing.DISABLED,
            stream=False,
        )
   
    # Ensure expected args were passed through to OpenAI client.
    kwargs = completions.kwargs
    assert kwargs["stream"] is False
    assert kwargs["store"] is True
    assert kwargs["model"] == cai_model
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == "sys"
    assert kwargs["messages"][1]["role"] == "user"
    # Defaults for optional fields become the NOT_GIVEN sentinel
    assert kwargs["tools"] is NOT_GIVEN
    assert kwargs["tool_choice"] is NOT_GIVEN
    assert kwargs["response_format"] is NOT_GIVEN
    assert kwargs["stream_options"] is NOT_GIVEN


@pytest.mark.asyncio
async def test_fetch_response_stream(monkeypatch) -> None:
    """
    When `stream=True`, `_fetch_response` should return a bare `Response`
    object along with the underlying async stream. The OpenAI client call
    should include `stream_options` to request usage-delimited chunks.
    """
    os.environ['CAI_STREAM'] = 'true'
    async def event_stream() -> AsyncIterator[ChatCompletionChunk]:
        if False:  # pragma: no cover
            yield  # pragma: no cover

    class DummyCompletions:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] = {}

        async def create(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            return event_stream()

    class DummyClient:
        def __init__(self, completions: DummyCompletions) -> None:
            self.chat = type("_Chat", (), {"completions": completions})()
            self.base_url = httpx.URL("http://fake")

    completions = DummyCompletions()
    dummy_client = DummyClient(completions)
    model = OpenAIChatCompletionsModel(model=cai_model, openai_client=dummy_client)  # type: ignore
    with generation_span(disabled=True) as span:
        response, stream = await model._fetch_response(
            system_instructions=None,
            input="hi",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            span=span,
            tracing=ModelTracing.DISABLED,
            stream=True,
        )
    # Check OpenAI client was called for streaming
    assert completions.kwargs["stream"] is True
    assert completions.kwargs["store"] is True
    assert completions.kwargs["stream_options"] == {"include_usage": True}
    # Response is a proper openai Response
    assert isinstance(response, Response)
    assert response.id == FAKE_RESPONSES_ID
    assert response.model == cai_model
    assert response.object == "response"
    assert response.output == []
    # We returned the async iterator produced by our dummy.
    assert hasattr(stream, "__aiter__")


@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_interaction_counter_single_turn_with_tool_calls(monkeypatch) -> None:
    """
    Test that when the LLM returns both a message and tool calls in the same turn,
    the interaction counter is incremented only once (not separately for message and tool calls).
    """
    # Create a response with both message content and tool calls
    tool_call = ChatCompletionMessageToolCall(
        id="call-id",
        type="function",
        function=Function(name="do_thing", arguments='{"x":1}'),
    )
    msg = ChatCompletionMessage(
        role="assistant", 
        content="I'll help you with that. Let me use a tool.", 
        tool_calls=[tool_call]
    )
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15),
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    
    # Initial counter should be 0
    assert model.interaction_counter == 0
    
    # Make the request
    resp: ModelResponse = await model.get_response(
        system_instructions="You are a helpful assistant",
        input="Help me with something",
        model_settings=ModelSettings(),
        tools=[],
        output_schema=None,
        handoffs=[],
        tracing=ModelTracing.DISABLED,
    )
    
    # Counter should be incremented only once for the entire turn
    assert model.interaction_counter == 1
    
    # Verify response contains both message and tool call
    assert len(resp.output) == 2  # One message item, one tool call item
    assert isinstance(resp.output[0], ResponseOutputMessage)
    assert isinstance(resp.output[1], ResponseFunctionToolCall)
    
    # Make another request to ensure counter increments properly
    resp2: ModelResponse = await model.get_response(
        system_instructions="You are a helpful assistant",
        input="Another request",
        model_settings=ModelSettings(),
        tools=[],
        output_schema=None,
        handoffs=[],
        tracing=ModelTracing.DISABLED,
    )
    
    # Counter should now be 2 (one increment per turn, not per item)
    assert model.interaction_counter == 2


@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_empty_response_warning(monkeypatch, caplog) -> None:
    """
    When the model returns a response with empty content (no text, no tool calls, no refusal),
    a warning should be logged indicating potential model-agent compatibility issues.
    """
    import logging
    
    # Create a response with empty content
    msg = ChatCompletionMessage(role="assistant", content="")
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=CompletionUsage(completion_tokens=0, prompt_tokens=5, total_tokens=5),
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    
    # Enable logging capture
    with caplog.at_level(logging.WARNING, logger="openai.agents"):
        resp: ModelResponse = await model.get_response(
            system_instructions=None,
            input="Test",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=ModelTracing.DISABLED,
        )
    
    # Response should still be returned (non-breaking)
    assert isinstance(resp, ModelResponse)
    
    # Warning should have been logged
    assert any("Model completed without output" in record.message for record in caplog.records)


@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_sentinel_response_warning(monkeypatch, caplog) -> None:
    """
    When the model returns a response with sentinel token (<|endoftext|>),
    a warning should be logged indicating potential model-agent compatibility issues.
    """
    import logging
    
    # Create a response with sentinel token
    msg = ChatCompletionMessage(role="assistant", content="<|endoftext|>")
    choice = Choice(index=0, finish_reason="stop", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=CompletionUsage(completion_tokens=1, prompt_tokens=5, total_tokens=6),
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    
    # Enable logging capture
    with caplog.at_level(logging.WARNING, logger="openai.agents"):
        resp: ModelResponse = await model.get_response(
            system_instructions=None,
            input="Test",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=ModelTracing.DISABLED,
        )
    
    # Response should still be returned (non-breaking)
    assert isinstance(resp, ModelResponse)
    
    # Warning should have been logged with sentinel info
    assert any("sentinel token" in record.message for record in caplog.records)


@pytest.mark.allow_call_model_methods
@pytest.mark.asyncio
async def test_no_warning_for_tool_calls(monkeypatch, caplog) -> None:
    """
    When the model returns a response with tool calls (even without text content),
    no warning should be logged since this is expected behavior.
    """
    import logging
    
    # Create a response with tool calls but no text content
    tool_call = ChatCompletionMessageToolCall(
        id="call_123",
        type="function",
        function=Function(name="test_tool", arguments='{"arg": "value"}'),
    )
    msg = ChatCompletionMessage(role="assistant", content=None, tool_calls=[tool_call])
    choice = Choice(index=0, finish_reason="tool_calls", message=msg)
    chat = ChatCompletion(
        id="resp-id",
        created=0,
        model="fake",
        object="chat.completion",
        choices=[choice],
        usage=CompletionUsage(completion_tokens=10, prompt_tokens=5, total_tokens=15),
    )

    async def patched_fetch_response(self, *args, **kwargs):
        return chat

    monkeypatch.setattr(OpenAIChatCompletionsModel, "_fetch_response", patched_fetch_response)
    model = OpenAIProvider(use_responses=False).get_model(cai_model)
    
    # Enable logging capture
    with caplog.at_level(logging.WARNING, logger="openai.agents"):
        resp: ModelResponse = await model.get_response(
            system_instructions=None,
            input="Test",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=ModelTracing.DISABLED,
        )
    
    # Response should be returned
    assert isinstance(resp, ModelResponse)
    
    # No warning should be logged for tool calls
    assert not any("Model completed without output" in record.message for record in caplog.records)