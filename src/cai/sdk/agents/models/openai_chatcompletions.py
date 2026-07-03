"""OpenAI ChatCompletions model -- backward-compatible module.

The utilities that used to live here have been refactored into the
``chatcompletions/`` sub-package.  This file re-exports them so that
all existing ``from cai.sdk.agents.models.openai_chatcompletions import X``
statements continue to work.
"""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import hashlib
import inspect
import json
import os
import re
import sys
import time
import uuid
import weakref
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Final, Literal, Optional, cast, overload

import random

import httpx
import litellm
import tiktoken
from openai import NOT_GIVEN, AsyncOpenAI, AsyncStream, NotGiven
from openai._models import BaseModel
from openai.types import ChatModel
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionChunk,
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionDeveloperMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from openai.types.chat.completion_create_params import ResponseFormat
from openai.types.completion_usage import CompletionUsage
from openai.types.responses import (
    EasyInputMessageParam,
    Response,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseFileSearchToolCallParam,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseInputContentParam,
    ResponseInputImageParam,
    ResponseInputTextParam,
    ResponseOutputItem,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputMessageParam,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseRefusalDeltaEvent,
    ResponseTextDeltaEvent,
    ResponseUsage,
)
from openai.types.responses.response_input_param import FunctionCallOutput, ItemReference, Message
from openai.types.responses.response_usage import OutputTokensDetails
from wasabi import color

from cai.util._worker_silence import worker_display_silenced
from cai.sdk.agents.simple_agent_manager import SimpleAgentManager, AGENT_MANAGER
from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
from cai.sdk.agents.run_to_jsonl import get_session_recorder
from cai.sdk.agents.global_usage_tracker import GLOBAL_USAGE_TRACKER
from cai.util import (
    _LIVE_STREAMING_PANELS,
    COST_TRACKER,
    calculate_model_cost,
    cli_print_agent_messages,
    cli_print_tool_output,
    create_agent_streaming_context,
    finish_agent_streaming,
    get_ollama_api_base,
    start_active_timer,
    start_claude_thinking_if_applicable,
    start_idle_timer,
    stop_active_timer,
    stop_idle_timer,
    update_agent_streaming_content,
)

# --- Refactored submodule imports (new chatcompletions/ package) ------
from .chatcompletions.token_counter import (
    count_tokens_with_tiktoken,
    _check_reasoning_compatibility,
)
from .chatcompletions.usage_tracker import InputTokensDetails, CustomResponseUsage
from .chatcompletions.cache_manager import (
    normalize_and_apply_cache,
    normalize_messages_for_cache,
    apply_cache_control,
    has_cache_control as _has_cache_control_fn,
    debug_cache_messages,
)
from .chatcompletions.stream_handler import StreamingState
from .chatcompletions.message_builder import (
    Converter as _NewConverter,
    ToolConverter,
)
from .chatcompletions.auto_compactor import (
    auto_compact_if_needed as _auto_compact_if_needed_impl,
    get_model_max_tokens as _get_model_max_tokens_impl,
)
from .chatcompletions.httpx_client import (
    direct_httpx_completion as _direct_httpx_completion_impl,
    verbose_http_retries,
)
from .chatcompletions.litellm_adapter import (
    fetch_response_litellm_openai as _fetch_litellm_openai_impl,
    fetch_response_litellm_ollama as _fetch_litellm_ollama_impl,
)
from .chatcompletions.model import (
    ACTIVE_MODEL_INSTANCES,
    PERSISTENT_MESSAGE_HISTORIES,
    _PREVIOUS_TURN_MSG_HASHES,
    _compaction_in_progress,
    _current_model_context,
    set_current_active_model,
    get_current_active_model,
    get_agent_message_history,
    get_all_agent_histories,
    clear_agent_history,
    clear_all_histories,
)

from cai.config import get_config
from cai.util.llm_api_base import (
    explicit_custom_llm_api_base_configured,
    resolve_llm_openai_compatible_base,
    resolve_llm_openai_compatible_api_key,
)
from cai.errors import LLMEmptyAssistantError, LLMRateLimited, LLMTimeout
from cai.util.gateway_rate_limiter import (
    COMPLETION_BUDGET_TOKENS,
    get_gateway_rate_limiter,
    make_pace_overlay_callback,
)
from cai.util.wait_hints import (
    ModelStreamWaitHints,
    model_wait_hints,
    set_model_wait_retry_overlay,
    sleep_with_retry_backoff_hint,
)
from cai.output import OUTPUT, StatusEvent
from cai.internal.components.metrics import process_intermediate_logs

from .. import _debug
from ..agent_output import AgentOutputSchema
from ..exceptions import AgentsException, UserError
from ..handoffs import Handoff
from ..items import ModelResponse, TResponseInputItem, TResponseOutputItem, TResponseStreamEvent
from ..logger import logger
from ..tool import FunctionTool, Tool
from ..tracing import generation_span
from ..tracing.span_data import GenerationSpanData
from ..tracing.spans import Span
from ..usage import Usage
from ..version import __version__
from .fake_id import FAKE_RESPONSES_ID
from .interface import Model, ModelTracing

if TYPE_CHECKING:
    from ..model_settings import ModelSettings

# --- Crash-prevention helpers -----------------------------------------

def _get_first_choice(response):
    """Safely get first choice from response, or None."""
    if response.choices and len(response.choices) > 0:
        return response.choices[0]
    return None


def _empty_completion_max_failures() -> int:
    """Consecutive empty assistant completions before surfacing ``LLMEmptyAssistantError`` (default 3)."""
    raw = (os.environ.get("CAI_EMPTY_COMPLETION_MAX_FAILURES") or "3").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 3
    return max(1, min(n, 12))


# Observed alias1 (~150k window) empty bursts around ~40k prompt tokens while 80%
# auto-compact only runs near ~120k. Force compact after repeated empties when
# estimated input exceeds max(floor, fraction * model_max).
EMPTY_COMPLETION_FORCE_COMPACT_FRACTION: Final[float] = 0.17
EMPTY_COMPLETION_FORCE_COMPACT_FLOOR: Final[int] = 8_000
# Matches overflow-recovery path in _fetch_response_litellm_openai (81% > 80% cap).
EMPTY_COMPLETION_FORCE_COMPACT_CONTEXT_FRACTION: Final[float] = 0.81


def _empty_completion_force_compact_threshold(model_max_tokens: int) -> int:
    """Estimated input tokens above which forced compact may run on empty streaks."""
    override = (os.environ.get("CAI_EMPTY_COMPLETION_FORCE_COMPACT_MIN_TOKENS") or "").strip()
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            pass
    scaled = int(model_max_tokens * EMPTY_COMPLETION_FORCE_COMPACT_FRACTION)
    return max(EMPTY_COMPLETION_FORCE_COMPACT_FLOOR, scaled)


def _should_force_compact_on_empty_streak(
    empty_streak: int,
    estimated_input_tokens: int,
    model_max_tokens: int,
) -> bool:
    """True when a second+ empty completion should trigger forced compaction."""
    if empty_streak < 2:
        return False
    return estimated_input_tokens >= _empty_completion_force_compact_threshold(model_max_tokens)


def _assistant_reasoning_text(message: Any) -> str:
    """Visible reasoning/thinking text when a provider omits regular content."""
    if message is None:
        return ""
    rc = getattr(message, "reasoning_content", None)
    if rc is None and isinstance(message, dict):
        rc = message.get("reasoning_content")
    if isinstance(rc, str) and rc.strip():
        return rc.strip()
    thinking = getattr(message, "thinking", None)
    if thinking is None and isinstance(message, dict):
        thinking = message.get("thinking")
    if isinstance(thinking, str) and thinking.strip():
        return thinking.strip()
    blocks = getattr(message, "thinking_blocks", None)
    if blocks is None and isinstance(message, dict):
        blocks = message.get("thinking_blocks")
    if blocks:
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "thinking":
                text = block.get("thinking", "")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return ""


def _is_effectively_empty_assistant_message(message: Any) -> bool:
    """True when the API assistant message has no tools, no refusal, and no visible text."""
    if message is None:
        return True
    refusal = getattr(message, "refusal", None)
    if refusal:
        return False
    tc = getattr(message, "tool_calls", None)
    if tc:
        return False
    if _assistant_reasoning_text(message):
        return False
    content = getattr(message, "content", None)
    if content is None:
        return True
    if isinstance(content, str):
        return not content.strip()
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and str(part.get("text", "")).strip():
                    return False
            else:
                txt = getattr(part, "text", None)
                if txt and str(txt).strip():
                    return False
        return True
    return False


def _safe_json_loads(json_str: str, context: str = "") -> dict:
    """Parse JSON with graceful fallback on decode errors."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON{' in ' + context if context else ''}: {e}")
        return {}


# --- Module-level setup (kept here for full backward compat) ----------
litellm.suppress_debug_info = True

_startup_model = get_config().model
if _startup_model in ("o3-mini", "gemini-1.5-pro"):
    litellm.drop_params = True

_USER_AGENT = f"Agents/Python {__version__}"
_HEADERS = {"User-Agent": _USER_AGENT}

# Backward-compat alias for _StreamingState
@dataclass
class _StreamingState:
    started: bool = False
    sequence_number: int = 0
    text_content_index_and_output: tuple[int, ResponseOutputText] | None = None
    refusal_content_index_and_output: tuple[int, ResponseOutputRefusal] | None = None
    function_calls: dict[int, ResponseFunctionToolCall] = field(default_factory=dict)


def _is_effectively_empty_stream_accumulation(
    state: _StreamingState,
    streamed_tool_calls: list[Any],
    output_text: str,
    streaming_reasoning_text: str,
) -> bool:
    """True when a finished stream has no tool calls and no visible assistant text."""
    if state.function_calls:
        return False
    if streamed_tool_calls:
        return False
    text = (output_text or "").strip()
    if not text and state.text_content_index_and_output:
        text = (getattr(state.text_content_index_and_output[1], "text", None) or "").strip()
    probe = SimpleNamespace(
        content=text or None,
        tool_calls=None,
        refusal=None,
        reasoning_content=(streaming_reasoning_text or None),
    )
    return _is_effectively_empty_assistant_message(probe)


# One-shot stderr line when CAI_UNRESTRICTED_LOG=1 (confirm client sends steering payload).
_UNRESTRICTED_EXTRA_BODY_LOGGED = False


class OpenAIChatCompletionsModel(Model):
    """OpenAI Chat Completions Model"""

    INTERMEDIATE_LOG_INTERVAL = 5

    def __init__(
        self,
        model: str | ChatModel,
        openai_client: AsyncOpenAI,
        agent_name: str = "CTF agent",  # Default to CTF agent instead of generic "Agent"
        agent_id: str | None = None,
        agent_type: str | None = None,  # The type of agent (e.g., "red_teamer")
    ) -> None:
        self.model = model
        self._client = openai_client
        # Check if we're using OLLAMA models
        self.is_ollama = os.getenv("OLLAMA") is not None and os.getenv("OLLAMA").lower() != "false"
        # Detect alias models for direct httpx bypass (skip LiteLLM overhead)
        _m = str(model).lower()
        self._is_alias_model = (
            "alias" in _m and "alias1.5" not in _m
        ) or _m == "alias2-mini"
        self.empty_content_error_shown = False

        # Track interaction counter and token totals for cli display
        self.interaction_counter = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_reasoning_tokens = 0
        self.total_cost = 0.0
        # Per-interaction token tracking
        self.interaction_input_tokens = 0
        self.interaction_output_tokens = 0
        self.interaction_reasoning_tokens = 0
        # Cache token tracking
        self.cache_read_tokens = 0
        self.cache_creation_tokens = 0
        self.agent_name = agent_name
        self.agent_type = agent_type or agent_name.lower().replace(" ", "_")  # For registry tracking
        self.uses_unified_context = False  # Flag to indicate if using shared message history
        
        # For SimpleAgentManager, we don't auto-register
        # The agent will be registered when explicitly created by cli.py
        self.agent_id = agent_id or AGENT_MANAGER.get_agent_id()
        self._display_name = self.agent_name

        # Instance-based message history
        # Check if we have an isolated history for this agent (parallel mode)
        if agent_id and PARALLEL_ISOLATION.is_parallel_mode():
            isolated_history = PARALLEL_ISOLATION.get_isolated_history(agent_id)
            if isolated_history is not None:
                self.message_history = isolated_history
            else:
                self.message_history = []
        else:
            # Get or create history from AGENT_MANAGER to ensure we share the same list reference
            # This is critical for proper history clearing to work
            existing_history = AGENT_MANAGER.get_message_history(self.agent_name)
            if existing_history is not None and isinstance(existing_history, list):
                # Use the existing list reference from AGENT_MANAGER
                self.message_history = existing_history
            else:
                # Create new history and ensure AGENT_MANAGER has it too
                self.message_history = []
                if self.agent_name not in AGENT_MANAGER._message_history:
                    AGENT_MANAGER._message_history[self.agent_name] = self.message_history
        
        # NOTE: Models should NOT register themselves with AGENT_MANAGER
        # The agent that owns this model will handle registration
        # This prevents duplicate registrations with agent keys
        
        # CRITICAL: Ensure AGENT_MANAGER uses the same list reference as the model
        # This is necessary for proper history clearing to work
        if agent_id is not None and not PARALLEL_ISOLATION.is_parallel_mode():
            if self.agent_name in AGENT_MANAGER._message_history:
                # Share the same list reference
                self.message_history = AGENT_MANAGER._message_history[self.agent_name]

        # Instance-based converter
        self._converter = _Converter()

        # Flags for CLI integration
        self.disable_rich_streaming = False  # Prevents creating a rich panel in the model
        self.suppress_final_output = False  # Prevents duplicate output at end of streaming

        # Initialize the session logger
        self.logger = get_session_recorder()
        
        # DEPRECATED: Still maintain backward compatibility with ACTIVE_MODEL_INSTANCES
        # TODO: Remove this after updating all dependent code
        ACTIVE_MODEL_INSTANCES[(self._display_name, self.agent_id)] = weakref.ref(self)

    def _shallow_copy_history_messages(self) -> list[dict]:
        """Shallow-copy ``message_history`` for API requests; keep ``cache_control`` when present."""
        converted: list[dict] = []
        if self.message_history:
            for msg in self.message_history:
                msg_copy = msg.copy()
                if "cache_control" in msg:
                    msg_copy["cache_control"] = msg["cache_control"]
                converted.append(msg_copy)
        return converted

    def _messages_for_token_count_after_history_mutation(
        self,
        *,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
    ) -> list[dict]:
        """Rebuild the message list the API will send (same rules as ``_fetch_response``).

        After auto-compaction mutates ``message_history`` in place, token estimates must not
        rebuild from ``input`` alone — that drops history and makes ``CAI_CONTEXT_USAGE`` look
        near zero while the model still receives the full thread.
        """
        converted_messages = self._shallow_copy_history_messages()
        if not self.message_history:
            converted_messages.extend(self._converter.items_to_messages(input, model_instance=self))
        if system_instructions:
            has_system = any(msg.get("role") == "system" for msg in converted_messages)
            if not has_system:
                converted_messages.insert(
                    0,
                    {"role": "system", "content": system_instructions},
                )
            else:
                for msg in converted_messages:
                    if msg.get("role") == "system":
                        msg["content"] = system_instructions
                        break
        try:
            from cai.util import fix_message_list

            return fix_message_list(converted_messages)
        except Exception:
            return converted_messages

    # ------------------------------------------------------------------
    # Retry helper – exponential backoff with jitter
    # ------------------------------------------------------------------
    @staticmethod
    def _backoff_delay(attempt: int, base: float = 5.0, cap: float = 120.0) -> float:
        """Return seconds to wait: min(cap, base * 2^attempt) + jitter."""
        delay = min(cap, base * (2 ** attempt)) + random.uniform(0, 3)
        return delay

    async def _retry_with_backoff(self, attempt: int, kind: str) -> None:
        """Wait with exponential backoff. Console noise only if CAI_VERBOSE_LLM_RETRY is set."""
        delay = self._backoff_delay(attempt)
        msg = f"{kind} (attempt {attempt + 1}/3) — retrying in {delay:.0f}s..."
        self.logger.warning(f"LLM backoff: {msg}")
        if verbose_http_retries():
            OUTPUT.emit(StatusEvent(message=msg, level="warning", agent_id=self.agent_name))
            from rich.console import Console
            console = Console()
            console.print(f"\n[yellow]⚠️  {msg}[/yellow]")
            await sleep_with_retry_backoff_hint(delay)
            console.print("[green]↻ Retrying now...[/green]\n")
        else:
            await sleep_with_retry_backoff_hint(delay)

    async def _recover_after_empty_completion(
        self,
        *,
        empty_streak: int,
        estimated_input_tokens: int,
        input: str | list[TResponseInputItem],
        system_instructions: str | None,
    ) -> tuple[str | list[TResponseInputItem], str | None, int]:
        """Backoff and optionally force compact before retrying after an empty provider response."""
        model_max = self._get_model_max_tokens(str(self.model))
        will_force_compact = _should_force_compact_on_empty_streak(
            empty_streak, estimated_input_tokens, model_max
        )
        await self._retry_with_backoff(empty_streak - 1, "Empty assistant completion")
        if not will_force_compact:
            return input, system_instructions, estimated_input_tokens
        try:
            force_est = max(
                estimated_input_tokens,
                int(model_max * EMPTY_COMPLETION_FORCE_COMPACT_CONTEXT_FRACTION),
            )
            input, system_instructions, compacted = await self._auto_compact_if_needed(
                force_est,
                input,
                system_instructions,
            )
            if compacted:
                converted_messages = self._messages_for_token_count_after_history_mutation(
                    system_instructions=system_instructions,
                    input=input,
                )
                estimated_input_tokens, _ = count_tokens_with_tiktoken(converted_messages)
                if model_max > 0:
                    os.environ["CAI_CONTEXT_USAGE"] = str(
                        min(1.0, max(0.0, estimated_input_tokens / model_max))
                    )
        except Exception as e:
            self.logger.warning("Forced compaction after empty completion failed: %s", e)
        return input, system_instructions, estimated_input_tokens

    def get_full_display_name(self) -> str:
        """Get the full display name including ID."""
        return f"{self._display_name} [{self.agent_id}]"
    
    def __del__(self):
        """Clean up when the model instance is destroyed."""
        try:
            # DEPRECATED: Remove from old registry for backward compatibility
            if hasattr(self, '_display_name') and hasattr(self, 'agent_id'):
                key = (self._display_name, self.agent_id)
                if key in ACTIVE_MODEL_INSTANCES:
                    del ACTIVE_MODEL_INSTANCES[key]
            
            # SimpleAgentManager handles history persistence
            # No need to save to PERSISTENT_MESSAGE_HISTORIES
                        
        except Exception:
            # Ignore any errors during cleanup
            pass

    def add_to_message_history(self, msg, skip_deduplication: bool = False):
        """Add a message to this instance's history.

        Args:
            msg: The message dictionary to add
            skip_deduplication: If True, skip all duplicate checking and just append.
                              Use this when loading session history where messages
                              are already in correct order and deduplication would
                              cause reordering issues.

        Now only adds to the instance's local history, no global registry.
        """
        # When loading session history, skip all deduplication to preserve order
        if skip_deduplication:
            self.message_history.append(msg)
            manager_history = AGENT_MANAGER.get_message_history(self.agent_name)
            if manager_history is not self.message_history:
                AGENT_MANAGER.add_to_history(self.agent_name, msg)
            if PARALLEL_ISOLATION.is_parallel_mode() and self.agent_id:
                PARALLEL_ISOLATION.update_isolated_history(self.agent_id, msg)
            return

        is_duplicate = False

        if self.message_history:
            if msg.get("role") in ["system", "user"]:
                is_duplicate = any(
                    existing.get("role") == msg.get("role")
                    and existing.get("content") == msg.get("content")
                    for existing in self.message_history
                )
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                # For tool calls, check if message with same tool call ID already exists
                # If it does, UPDATE IN PLACE to preserve message order
                tool_call_id = msg["tool_calls"][0].get("id") if msg.get("tool_calls") else None
                if tool_call_id:
                    existing_idx = None
                    for i, existing in enumerate(self.message_history):
                        if (existing.get("role") == "assistant"
                            and existing.get("tool_calls")
                            and existing["tool_calls"][0].get("id") == tool_call_id):
                            existing_idx = i
                            break

                    if existing_idx is not None:
                        # UPDATE IN PLACE to preserve order (don't remove and re-add!)
                        self.message_history[existing_idx] = msg
                        is_duplicate = True  # Mark as duplicate so we don't append again
                    else:
                        is_duplicate = False
            elif msg.get("role") == "tool":
                is_duplicate = any(
                    existing.get("role") == "tool"
                    and existing.get("tool_call_id") == msg.get("tool_call_id")
                    for existing in self.message_history
                )

        if not is_duplicate:
            self.message_history.append(msg)
            # Also update SimpleAgentManager ONLY if they're not the same list reference
            # This avoids double-adding when they share the same list
            manager_history = AGENT_MANAGER.get_message_history(self.agent_name)
            if manager_history is not self.message_history:
                AGENT_MANAGER.add_to_history(self.agent_name, msg)
            # Update isolated history if in parallel mode
            if PARALLEL_ISOLATION.is_parallel_mode() and self.agent_id:
                PARALLEL_ISOLATION.update_isolated_history(self.agent_id, msg)

    def set_agent_name(self, name: str) -> None:
        """Set the agent name for CLI display purposes."""
        self.agent_name = name

    def _non_null_or_not_given(self, value: Any) -> Any:
        return value if value is not None else NOT_GIVEN

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
    ) -> ModelResponse:
        # Close any open streaming panels from the previous cycle
        # This ensures panels don't stay open when the model starts a new inference
        try:
            from cai.util import close_all_streaming_panels
            close_all_streaming_panels()
        except ImportError:
            pass

        # Increment the interaction counter for CLI display
        self.interaction_counter += 1
        self._intermediate_logs()

        # Set this as the current active model for tool execution context
        set_current_active_model(self)

        # Stop idle timer and start active timer to track LLM processing time
        stop_idle_timer()
        start_active_timer()

        with generation_span(
            model=str(self.model),
            model_config=dataclasses.asdict(model_settings)
            | {"base_url": str(self._get_client().base_url)},
            disabled=tracing.is_disabled(),
        ) as span_generation:
            # Prepare the messages for consistent token counting
            # IMPORTANT: Include existing message history for context
            converted_messages = self._shallow_copy_history_messages()

            # Then convert and add the new input
            new_messages = self._converter.items_to_messages(input, model_instance=self)
            converted_messages.extend(new_messages)

            if system_instructions:
                # Check if we already have a system message
                has_system = any(msg.get("role") == "system" for msg in converted_messages)
                if not has_system:
                    converted_messages.insert(
                        0,
                        {
                            "content": system_instructions,
                            "role": "system",
                        },
                    )

            # # --- Add to message_history: user, system, and assistant tool call messages ---
            # # Add system prompt to message_history
            # if system_instructions:
            #     sys_msg = {
            #         "role": "system",
            #         "content": system_instructions
            #     }
            #     self.add_to_message_history(sys_msg)

            # Add user messages to message_history.
            # add_to_message_history() has built-in dedup (same role+content),
            # so repeated calls with the same message within a Runner loop are safe.
            if isinstance(input, str):
                self.add_to_message_history({"role": "user", "content": input})
                self.logger.log_user_message(input)
            elif isinstance(input, list):
                for item in input:
                    if isinstance(item, dict) and item.get("role") == "user":
                        self.add_to_message_history(
                            {"role": "user", "content": item.get("content", "")}
                        )

            # IMPORTANT: Ensure the message list has valid tool call/result pairs
            # This needs to happen before the API call AND before applying cache_control
            try:
                from cai.util import fix_message_list

                converted_messages = fix_message_list(converted_messages)
            except Exception:
                pass

            # Request-path message normalization/cache-control is applied in _fetch_response().
            # Keep startup estimation lightweight to avoid duplicate per-turn preprocessing work.

            # Get token count estimate before API call for consistent counting
            estimated_input_tokens, _ = count_tokens_with_tiktoken(converted_messages)
            
            # Calculate and set context usage for toolbar
            max_tokens = self._get_model_max_tokens(str(self.model))
            context_usage = estimated_input_tokens / max_tokens if max_tokens > 0 else 0.0
            os.environ['CAI_CONTEXT_USAGE'] = str(context_usage)

            # Check if auto-compaction is needed
            input, system_instructions, compacted = await self._auto_compact_if_needed(estimated_input_tokens, input, system_instructions)
            
            # If compaction occurred, recalculate tokens from the same view ``_fetch_response`` uses
            if compacted:
                converted_messages = self._messages_for_token_count_after_history_mutation(
                    system_instructions=system_instructions,
                    input=input,
                )
                estimated_input_tokens, _ = count_tokens_with_tiktoken(converted_messages)
                max_tok = self._get_model_max_tokens(str(self.model))
                if max_tok > 0:
                    os.environ["CAI_CONTEXT_USAGE"] = str(
                        min(1.0, max(0.0, estimated_input_tokens / max_tok))
                    )

            # Pre-check price limit using estimated input tokens and a conservative estimate for output
            # This prevents starting a request that would immediately exceed the price limit
            if hasattr(COST_TRACKER, "check_price_limit"):
                # Use a conservative estimate for output tokens (roughly equal to input)
                estimated_cost = calculate_model_cost(
                    str(self.model), estimated_input_tokens, estimated_input_tokens
                )  # Conservative estimate
                try:
                    COST_TRACKER.check_price_limit(estimated_cost)
                except Exception:
                    # Stop active timer and start idle timer before re-raising the exception
                    stop_active_timer()
                    start_idle_timer()
                    raise

            try:
                max_empty_failures = _empty_completion_max_failures()
                empty_streak = 0
                response = None
                # ``model_wait_hints`` wraps the whole retry loop so the body
                # stays published across attempts (no flicker between iterations).
                # The ``try/finally`` clears any retry/pacing overlay even when
                # ``_fetch_response`` raises a typed error that propagates out.
                _on_pace = make_pace_overlay_callback()
                async with model_wait_hints():
                    try:
                        while True:
                            # Proactive client-side pacing for the alias gateway
                            # (TPM/RPM per API key). The projection adds a small
                            # completion-token buffer because the gateway counts
                            # input+output against TPM but we only know input
                            # before the call; ``Reservation.update_actual``
                            # reconciles to the real total once the response
                            # arrives. The limiter's 85% safety margin absorbs
                            # any residual drift between our tiktoken estimate
                            # and the gateway's authoritative accounting (the
                            # gateway does not expose ``x-ratelimit-*`` headers,
                            # confirmed by direct probe).
                            if self._is_alias_model:
                                _projection = estimated_input_tokens + COMPLETION_BUDGET_TOKENS
                                async with get_gateway_rate_limiter().alias_gateway_slot(
                                    _projection,
                                    on_pace=_on_pace,
                                ) as _reservation:
                                    response = await self._fetch_response(
                                        system_instructions,
                                        input,
                                        model_settings,
                                        tools,
                                        output_schema,
                                        handoffs,
                                        span_generation,
                                        tracing,
                                        stream=False,
                                    )
                                    # Reconcile pre-flight estimate with the
                                    # gateway's real ``prompt + completion``
                                    # so the deque tracks ground truth for
                                    # subsequent pacing decisions.
                                    try:
                                        _usage = getattr(response, "usage", None)
                                        if _usage is not None:
                                            _real = (
                                                int(getattr(_usage, "prompt_tokens", 0) or 0)
                                                + int(getattr(_usage, "completion_tokens", 0) or 0)
                                            )
                                            _reservation.update_actual(_real)
                                    except Exception:
                                        pass
                            else:
                                response = await self._fetch_response(
                                    system_instructions,
                                    input,
                                    model_settings,
                                    tools,
                                    output_schema,
                                    handoffs,
                                    span_generation,
                                    tracing,
                                    stream=False,
                                )
                            first_choice = _get_first_choice(response)
                            if not first_choice:
                                raise AgentsException("LLM returned response with no choices")
                            if _is_effectively_empty_assistant_message(first_choice.message):
                                empty_streak += 1
                                _empty_usage = getattr(response, "usage", None)
                                _empty_msg = first_choice.message
                                self.logger.warning(
                                    "Empty assistant completion (%s/%s); "
                                    "pt=%s ct=%s reasoning_len=%s tools=%s; repeating.",
                                    empty_streak,
                                    max_empty_failures,
                                    (
                                        getattr(_empty_usage, "prompt_tokens", None)
                                        if _empty_usage
                                        else None
                                    ),
                                    (
                                        getattr(_empty_usage, "completion_tokens", None)
                                        if _empty_usage
                                        else None
                                    ),
                                    len(
                                        str(
                                            getattr(_empty_msg, "reasoning_content", None)
                                            or ""
                                        )
                                    ),
                                    len(getattr(_empty_msg, "tool_calls", None) or []),
                                )
                                if empty_streak >= max_empty_failures:
                                    stop_active_timer()
                                    start_idle_timer()
                                    raise LLMEmptyAssistantError(
                                        "Consecutive empty assistant completions from the provider.",
                                        {"attempts": max_empty_failures},
                                    )
                                input, system_instructions, estimated_input_tokens = (
                                    await self._recover_after_empty_completion(
                                        empty_streak=empty_streak,
                                        estimated_input_tokens=estimated_input_tokens,
                                        input=input,
                                        system_instructions=system_instructions,
                                    )
                                )
                                set_model_wait_retry_overlay(
                                    "Provider returned an empty response; "
                                    f"retrying ({empty_streak}/{max_empty_failures})…"
                                )
                                continue
                            break
                    finally:
                        set_model_wait_retry_overlay(None)
            except KeyboardInterrupt:
                # Handle KeyboardInterrupt during API call.
                # ``alias_gateway_slot`` already released any in-flight
                # reservation before KbInt propagated to this handler.
                if hasattr(self, "_pending_tool_calls"):
                    self._pending_tool_calls.clear()

                # Let the interrupt propagate up to end the current operation
                stop_active_timer()
                start_idle_timer()

                raise

            except (litellm.exceptions.Timeout, LLMTimeout) as e:
                # High-level timeout recovery with exponential backoff
                self.logger.warning(f"Timeout error: {e}")
                stop_active_timer()
                start_idle_timer()

                if not hasattr(self, "_high_level_retry_count"):
                    self._high_level_retry_count = 0
                self._high_level_retry_count += 1

                if self._high_level_retry_count > 3:
                    self._high_level_retry_count = 0
                    raise LLMTimeout(f"Timed out after 3 attempts [{self.model}]") from e

                # Exponential backoff — NO "continue" injected into history
                await self._retry_with_backoff(self._high_level_retry_count - 1, "Timeout")

                # Clean retry: re-send the SAME input, don't pollute history
                result = await self.get_response(
                    system_instructions, input, model_settings,
                    tools, output_schema, handoffs, tracing,
                )
                self._high_level_retry_count = 0
                return result

            except (litellm.exceptions.RateLimitError, LLMRateLimited) as e:
                # High-level rate-limit recovery with exponential backoff
                self.logger.warning(f"Rate limit (high-level): {e}")
                stop_active_timer()
                start_idle_timer()

                if not hasattr(self, "_high_level_retry_count"):
                    self._high_level_retry_count = 0
                self._high_level_retry_count += 1

                if self._high_level_retry_count > 3:
                    self._high_level_retry_count = 0
                    raise LLMRateLimited(
                        f"Rate limit after 3 attempts [{self.model}]",
                        retry_after=getattr(e, "retry_after", None),
                    ) from e

                # Exponential backoff — NO "continue" injected into history
                await self._retry_with_backoff(self._high_level_retry_count - 1, "Rate limit")

                # Clean retry: re-send the SAME input
                result = await self.get_response(
                    system_instructions, input, model_settings,
                    tools, output_schema, handoffs, tracing,
                )
                self._high_level_retry_count = 0
                return result

            except (
                litellm.exceptions.BadGatewayError,
                litellm.exceptions.ServiceUnavailableError,
                litellm.exceptions.InternalServerError,
            ) as e:
                # Transient server errors (502, 503, 500): retry with backoff
                self.logger.warning(f"Server error (high-level recovery): {str(e)[:200]}")

                stop_active_timer()
                start_idle_timer()

                if not hasattr(self, "_high_level_retry_count"):
                    self._high_level_retry_count = 0
                self._high_level_retry_count += 1

                if self._high_level_retry_count > 3:
                    self._high_level_retry_count = 0
                    if verbose_http_retries():
                        print(f"\n❌ Server error after 3 recovery attempts [{self.model}]")
                    raise

                wait_secs = 10 * self._high_level_retry_count  # 10s, 20s, 30s
                self.logger.warning(
                    f"Server error recovery attempt {self._high_level_retry_count}/3 "
                    f"({type(e).__name__}), waiting {wait_secs}s"
                )
                if verbose_http_retries():
                    from rich.console import Console
                    console = Console()
                    console.print(
                        f"\n[yellow]⚠️  Server error (attempt {self._high_level_retry_count}/3): "
                        f"{type(e).__name__}[/yellow]"
                    )
                    console.print(f"[yellow]Waiting {wait_secs}s before retrying...[/yellow]")

                await sleep_with_retry_backoff_hint(wait_secs)

                if verbose_http_retries():
                    from rich.console import Console
                    Console().print("[green]Retrying request...[/green]\n")

                stop_idle_timer()
                start_active_timer()

                result = await self.get_response(
                    system_instructions,
                    input,
                    model_settings,
                    tools,
                    output_schema,
                    handoffs,
                    tracing,
                )
                self._high_level_retry_count = 0
                return result

            if _debug.DONT_LOG_MODEL_DATA:
                logger.debug("Received model response")
            else:
                import json

                _first = _get_first_choice(response)
                if _first:
                    if _is_effectively_empty_assistant_message(_first.message):
                        logger.debug(
                            "LLM resp: assistant message is empty (no full JSON dump — "
                            "see CAI_DEBUG=2 if you need the raw object)."
                        )
                    else:
                        logger.debug(
                            f"LLM resp:\n{json.dumps(_first.message.model_dump(), indent=2)}\n"
                        )

            # Ensure we have reasonable token counts
            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens

                # Use estimated tokens if API returns zeroes or implausible values
                if input_tokens == 0 or input_tokens < (len(str(input)) // 10):  # Sanity check
                    input_tokens = estimated_input_tokens
                    total_tokens = input_tokens + output_tokens

                # # Debug information
                # print(f"\nDEBUG CONSISTENT TOKEN COUNTS - API tokens: input={input_tokens}, output={output_tokens}, total={total_tokens}")
                # print(f"Estimated tokens were: input={estimated_input_tokens}")
            else:
                # If no usage info, use our estimates
                input_tokens = estimated_input_tokens
                output_tokens = 0
                total_tokens = input_tokens
                # print(f"\nDEBUG CONSISTENT TOKEN COUNTS - No API tokens, using estimates: input={input_tokens}, output={output_tokens}")

            # Update token totals for CLI display
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            # Update per-interaction tokens (reset each call)
            self.interaction_input_tokens = input_tokens
            self.interaction_output_tokens = output_tokens
            # Extract and update cache tokens
            # Support both Anthropic format (cache_read_input_tokens) and OpenAI format (prompt_tokens_details.cached_tokens)
            if response.usage:
                # Try Anthropic format first
                cache_read = getattr(response.usage, 'cache_read_input_tokens', 0) or 0
                # Fallback to OpenAI format (prompt_tokens_details.cached_tokens)
                if not cache_read:
                    prompt_details = getattr(response.usage, 'prompt_tokens_details', None)
                    if prompt_details:
                        cache_read = getattr(prompt_details, 'cached_tokens', 0) or 0
                self.cache_read_tokens = cache_read
                # cache_creation_tokens is Anthropic-only (OpenAI doesn't charge for cache writes)
                self.cache_creation_tokens = getattr(response.usage, 'cache_creation_input_tokens', 0) or 0

                # Also update COST_TRACKER so it's available for tool panels
                try:
                    import cai.util
                    cai.util.COST_TRACKER.interaction_input_tokens = self.interaction_input_tokens
                    cai.util.COST_TRACKER.interaction_output_tokens = self.interaction_output_tokens
                    cai.util.COST_TRACKER.interaction_reasoning_tokens = self.interaction_reasoning_tokens
                    cai.util.COST_TRACKER.cache_read_tokens = self.cache_read_tokens
                    cai.util.COST_TRACKER.cache_creation_tokens = self.cache_creation_tokens
                except Exception:
                    pass
            else:
                self.cache_read_tokens = 0
                self.cache_creation_tokens = 0
            reasoning_tokens = 0
            if (
                response.usage
                and hasattr(response.usage, "completion_tokens_details")
                and response.usage.completion_tokens_details
                and hasattr(response.usage.completion_tokens_details, "reasoning_tokens")
            ):
                # Guard against None or unexpected types for reasoning_tokens
                try:
                    reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens
                    if reasoning_tokens is None:
                        reasoning_tokens = 0
                    else:
                        # coerce numeric-like values to int
                        reasoning_tokens = int(reasoning_tokens)
                except Exception:
                    reasoning_tokens = 0

                self.total_reasoning_tokens += reasoning_tokens
            # Update per-interaction reasoning tokens
            self.interaction_reasoning_tokens = reasoning_tokens

            # Process costs for non-streaming mode
            model_name = str(self.model)
            interaction_cost = calculate_model_cost(model_name, input_tokens, output_tokens)
            
            # Process the costs through COST_TRACKER only once
            if interaction_cost > 0.0:
                # Check price limit before processing
                if hasattr(COST_TRACKER, "check_price_limit"):
                    COST_TRACKER.check_price_limit(interaction_cost)
                
                # Process interaction cost
                COST_TRACKER.process_interaction_cost(
                    model_name,
                    input_tokens,
                    output_tokens,
                    reasoning_tokens,
                    interaction_cost,
                    agent_name=self.agent_name,
                    agent_id=self.agent_id
                )
                
                # Process total cost
                total_cost = COST_TRACKER.process_total_cost(
                    model_name,
                    self.total_input_tokens,
                    self.total_output_tokens,
                    self.total_reasoning_tokens,
                    None,
                    agent_name=self.agent_name,
                    agent_id=self.agent_id
                )
                
                # Track usage globally
                GLOBAL_USAGE_TRACKER.track_usage(
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=interaction_cost,
                    agent_name=self.agent_name
                )
            else:
                # For free models
                total_cost = COST_TRACKER.session_total_cost
                
                # Still track token usage even for free models
                GLOBAL_USAGE_TRACKER.track_usage(
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=0.0,
                    agent_name=self.agent_name
                )

            # Check if this message contains tool calls
            tool_output = None
            should_display_message = True

            _first_choice = _get_first_choice(response)
            if (
                _first_choice
                and hasattr(_first_choice.message, "tool_calls")
                and _first_choice.message.tool_calls
            ):
                # For each tool call in the message, get corresponding output if available
                for tool_call in _first_choice.message.tool_calls:
                    call_id = tool_call.id

                    # Check if this tool call has already been displayed
                    if (
                        hasattr(_Converter, "tool_outputs")
                        and call_id in self._converter.tool_outputs
                    ):
                        tool_output_content = self._converter.tool_outputs[call_id]

                        # Check if this is a command sent to an existing async session
                        is_async_session_input = False
                        has_auto_output = False
                        is_regular_command = False
                        try:
                            import json

                            # Handle empty arguments before trying to parse JSON
                            tool_args = tool_call.function.arguments
                            if tool_args is None or (isinstance(tool_args, str) and tool_args.strip() == ""):
                                tool_args = "{}"
                            
                            args = _safe_json_loads(tool_args, "tool_call arguments")
                            # Check if this is a regular command (not a session command)
                            if (
                                isinstance(args, dict)
                                and args.get("command")
                                and not args.get("session_id")
                                and not args.get("async_mode")
                            ):
                                is_regular_command = True
                            # Only consider it an async session input if it has session_id AND it's not creating a new session
                            elif (
                                isinstance(args, dict)
                                and args.get("session_id")
                                and not args.get("async_mode")  # Not creating a new session
                                and not args.get("creating_session")
                            ):  # Not marked as session creation
                                is_async_session_input = True
                                # Check if this has auto_output flag
                                has_auto_output = args.get("auto_output", False)
                        except (json.JSONDecodeError, AttributeError, TypeError):
                            pass

                        # For regular commands that were already shown via streaming, suppress the agent message
                        if (
                            is_regular_command
                            and tool_call.function.name == "generic_linux_command"
                        ):
                            # Check if this was executed very recently (likely shown via streaming)
                            if (
                                hasattr(_Converter, "recent_tool_calls")
                                and call_id in self._converter.recent_tool_calls
                            ):
                                tool_call_info = self._converter.recent_tool_calls[call_id]
                                if "start_time" in tool_call_info:
                                    import time

                                    time_since_execution = (
                                        time.time() - tool_call_info["start_time"]
                                    )
                                    # If executed within last 2 seconds, it was likely shown via streaming
                                    if time_since_execution < 2.0:
                                        should_display_message = False
                                        tool_output = None
                        elif is_async_session_input:
                            should_display_message = True
                            tool_output = None
                        # For async session inputs without auto_output, always show the agent message
                        elif is_async_session_input and not has_auto_output:
                            should_display_message = True
                            tool_output = None
                        # For session creation messages, also show them
                        elif (
                            "Started async session" in tool_output_content
                            or "session" in tool_output_content.lower()
                            and "async" in tool_output_content.lower()
                        ):
                            should_display_message = True
                            tool_output = None
                        else:
                            # For other tool calls, check if we should suppress based on timing
                            # Only suppress if this tool was JUST executed (within last 2 seconds)
                            if (
                                hasattr(_Converter, "recent_tool_calls")
                                and call_id in self._converter.recent_tool_calls
                            ):
                                tool_call_info = self._converter.recent_tool_calls[call_id]
                                if "start_time" in tool_call_info:
                                    import time

                                    time_since_execution = (
                                        time.time() - tool_call_info["start_time"]
                                    )
                                    # Only suppress if this was executed very recently
                                    if time_since_execution < 2.0:
                                        should_display_message = False
                                    else:
                                        # For older tool calls, show the message
                                        should_display_message = True
                        break

            # Additional check: Always show messages that have text content
            # This ensures agent explanations are not suppressed
            _fc = _get_first_choice(response)
            if (
                _fc
                and hasattr(_fc.message, "content")
                and _fc.message.content
                and str(_fc.message.content).strip()
            ):
                # If the message has actual text content, always show it
                should_display_message = True

            # Display the agent message (this will show the command for async sessions)
            if should_display_message:
                # Ensure we're in non-streaming mode for proper markdown parsing
                previous_stream_setting = os.environ.get("CAI_STREAM", "false")
                os.environ["CAI_STREAM"] = "false"  # Force non-streaming mode for markdown parsing

                # Extract cache metrics for display
                # Support both Anthropic format and OpenAI format (prompt_tokens_details.cached_tokens)
                cache_create = getattr(response.usage, 'cache_creation_input_tokens', None) if response.usage else None
                cache_read = getattr(response.usage, 'cache_read_input_tokens', None) if response.usage else None
                # Fallback to OpenAI format if Anthropic format not available
                if not cache_read and response.usage:
                    prompt_details = getattr(response.usage, 'prompt_tokens_details', None)
                    if prompt_details:
                        cache_read = getattr(prompt_details, 'cached_tokens', None)

                # Print the agent message for CLI display
                cli_print_agent_messages(
                    agent_name=getattr(self, "agent_name", "Agent"),
                    message=_get_first_choice(response).message if _get_first_choice(response) else None,
                    counter=getattr(self, "interaction_counter", 0),
                    model=str(self.model),
                    debug=False,
                    interaction_input_tokens=input_tokens,
                    interaction_output_tokens=output_tokens,
                    interaction_reasoning_tokens=reasoning_tokens,
                    total_input_tokens=getattr(self, "total_input_tokens", 0),
                    total_output_tokens=getattr(self, "total_output_tokens", 0),
                    total_reasoning_tokens=getattr(self, "total_reasoning_tokens", 0),
                    interaction_cost=interaction_cost,
                    total_cost=total_cost,
                    tool_output=tool_output,  # Pass tool_output only when needed
                    suppress_empty=True,  # Keep suppress_empty=True as requested
                    cache_creation_tokens=cache_create,
                    cache_read_tokens=cache_read,
                )

                # Restore previous streaming setting
                os.environ["CAI_STREAM"] = previous_stream_setting

            # --- DEFERRED: Tool calls are no longer added immediately ---
            # Tool calls will be added atomically with their responses
            # to prevent incomplete message history on interruption
            _first_for_msg = _get_first_choice(response)
            if not _first_for_msg:
                raise AgentsException("LLM returned response with no choices")
            assistant_msg = _first_for_msg.message
            if hasattr(assistant_msg, "tool_calls") and assistant_msg.tool_calls:
                # Store pending tool calls but don't add to history yet
                if not hasattr(self, "_pending_tool_calls"):
                    self._pending_tool_calls = {}


                # Fix Google Gemini OpenAI compatibility issues.
                # When using the OpenAI-compatible API to call tools with Google Gemini
                # tool_call.id is returned as an empty string.
                if "openai/gemini" in get_config().model:
                    for tool_call in assistant_msg.tool_calls:
                        if tool_call.id is None or tool_call.id == "":
                            tool_call.id = uuid.uuid4().hex[:16]

                for tool_call in assistant_msg.tool_calls:
                    # Handle empty arguments before storing
                    tool_args = tool_call.function.arguments
                    if tool_args is None or (isinstance(tool_args, str) and tool_args.strip() == ""):
                        tool_args = "{}"
                    
                    # Compose a message for the tool call
                    tool_call_msg = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_args,
                                },
                            }
                        ],
                    }

                    # Store for later atomic addition with response
                    self._pending_tool_calls[tool_call.id] = tool_call_msg

                    # Save the tool call details for later matching with output
                    # This is important for non-streaming mode to track tool calls properly
                    if not hasattr(self._converter, "recent_tool_calls"):
                        self._converter.recent_tool_calls = {}

                    # Store the tool call by ID for later reference
                    import time

                    current_time = time.time()

                    # Periodic cleanup of old tool calls (older than 5 minutes)
                    # This prevents unbounded growth and memory issues
                    if len(self._converter.recent_tool_calls) > 50:
                        stale_threshold = current_time - 300  # 5 minutes
                        stale_keys = [
                            k for k, v in self._converter.recent_tool_calls.items()
                            if v.get("start_time", 0) < stale_threshold
                        ]
                        for k in stale_keys:
                            del self._converter.recent_tool_calls[k]

                    self._converter.recent_tool_calls[tool_call.id] = {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                        "start_time": current_time,
                        "execution_info": {"start_time": current_time},
                    }

                # Log the assistant tool call message
                tool_calls_list = []
                for tool_call in assistant_msg.tool_calls:
                    tool_calls_list.append(
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    )
                self.logger.log_assistant_message(None, tool_calls_list)
            # If the assistant message is just text, add it as well
            else:
                text_out = None
                if hasattr(assistant_msg, "content") and assistant_msg.content:
                    text_out = assistant_msg.content
                else:
                    reasoning_text = _assistant_reasoning_text(assistant_msg)
                    if reasoning_text:
                        text_out = reasoning_text
                if text_out:
                    asst_msg = {"role": "assistant", "content": text_out}
                    self.add_to_message_history(asst_msg)
                    self.logger.log_assistant_message(text_out)

            # En no-streaming, también necesitamos añadir cualquier tool output al message_history
            # Esto se hace procesando los items de output del ModelResponse
            items = self._converter.message_to_output_items(assistant_msg)

            # Además, necesitamos añadir los tool outputs que se hayan generado
            # durante la ejecución de las herramientas
            if hasattr(_Converter, "tool_outputs"):
                for call_id, output_content in self._converter.tool_outputs.items():
                    # Verificar si ya existe un mensaje tool con este call_id en self.message_history
                    tool_msg_exists = any(
                        msg.get("role") == "tool" and msg.get("tool_call_id") == call_id
                        for msg in self.message_history
                    )

                    if not tool_msg_exists:
                        # Añadir el mensaje tool al message_history
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": output_content,
                        }
                        self.add_to_message_history(tool_msg)

            # Log the complete response for the session
            self.logger.rec_training_data(
                {
                    "model": str(self.model),
                    "messages": converted_messages,
                    "stream": False,
                    "tools": [t.params_json_schema for t in tools] if tools else [],
                    "tool_choice": model_settings.tool_choice,
                },
                response,
                self.total_cost,
                self.agent_name,
            )

            # Extract cache metrics from response if available
            # Support both Anthropic format and OpenAI format (prompt_tokens_details.cached_tokens)
            cache_creation = None
            cache_read = None
            if response.usage:
                cache_creation = getattr(response.usage, 'cache_creation_input_tokens', None)
                cache_read = getattr(response.usage, 'cache_read_input_tokens', None)
                # Fallback to OpenAI format if Anthropic format not available
                if not cache_read:
                    prompt_details = getattr(response.usage, 'prompt_tokens_details', None)
                    if prompt_details:
                        cache_read = getattr(prompt_details, 'cached_tokens', None)

            usage = (
                Usage(
                    requests=1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    cache_creation_input_tokens=cache_creation,
                    cache_read_input_tokens=cache_read,
                )
                if response.usage or input_tokens > 0
                else Usage()
            )
            _trace_choice = _get_first_choice(response)
            if tracing.include_data() and _trace_choice:
                span_generation.span_data.output = [_trace_choice.message.model_dump()]
            span_generation.span_data.usage = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }

            if not _trace_choice:
                raise AgentsException("LLM returned response with no choices")
            items = self._converter.message_to_output_items(_trace_choice.message)

            # For non-streaming responses, make sure we also log token usage with compatible field names
            # This ensures both streaming and non-streaming use consistent naming
            if not hasattr(response, "usage"):
                response.usage = {}
            if hasattr(response.usage, "prompt_tokens") and not hasattr(
                response.usage, "input_tokens"
            ):
                response.usage.input_tokens = response.usage.prompt_tokens
            if hasattr(response.usage, "completion_tokens") and not hasattr(
                response.usage, "output_tokens"
            ):
                response.usage.output_tokens = response.usage.completion_tokens

            # Ensure cost is properly initialized
            if not hasattr(response, "cost"):
                response.cost = None

            return ModelResponse(
                output=items,
                usage=usage,
                referenceable_id=None,
            )

        # Stop active timer and start idle timer when response is complete
        stop_active_timer()
        start_idle_timer()

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        _empty_completion_streak: int = 0,
    ) -> AsyncIterator[TResponseStreamEvent]:
        """
        Yields a partial message as it is generated, as well as the usage information.
        """
        # Close any open streaming panels from the previous cycle
        # This ensures panels don't stay open when the model starts a new inference
        try:
            from cai.util import close_all_streaming_panels
            close_all_streaming_panels()
        except ImportError:
            pass

        # Initialize streaming contexts as None
        streaming_context = None
        thinking_context = None
        stream_interrupted = False
        stream_wait_hints: ModelStreamWaitHints | None = None

        try:
            # IMPORTANT: Pre-process input to ensure it's in the correct format
            # for streaming. This helps prevent errors during stream handling.
            if not isinstance(input, str):
                # Convert input items to messages and verify structure
                try:
                    input_items = list(input)  # Make sure it's a list
                    # Pre-verify the input messages to avoid errors during streaming
                    from cai.util import fix_message_list

                    # Apply fix_message_list to the input items that are dictionaries
                    dict_items = [item for item in input_items if isinstance(item, dict)]
                    if dict_items:
                        fixed_dict_items = fix_message_list(dict_items)

                        # Replace the original dict items with fixed ones while preserving non-dict items
                        new_input = []
                        dict_index = 0
                        for item in input_items:
                            if isinstance(item, dict):
                                if dict_index < len(fixed_dict_items):
                                    new_input.append(fixed_dict_items[dict_index])
                                    dict_index += 1
                            else:
                                new_input.append(item)

                        # Update input with the fixed version
                        input = new_input
                except Exception as e:
                    # Silently continue with original input if pre-processing failed
                    # This is not critical and shouldn't show warnings
                    pass

            # Increment the interaction counter for CLI display
            self.interaction_counter += 1
            self._intermediate_logs()

            # Stop idle timer and start active timer to track LLM processing time
            stop_idle_timer()
            start_active_timer()

            # --- Check if streaming should be shown in rich panel ---
            # Sub-agents invoked as tools by the orchestration agent must not
            # render Rich streaming panels — only the orchestrator's final
            # synthesis is shown to the user. See ``_worker_silence``.
            should_show_rich_stream = (
                get_config().stream
                and not self.disable_rich_streaming
                and not worker_display_silenced()
            )

            # Lazy-init Rich Live: build streaming_context on first text delta (not before HTTP),
            # so startup work (terminal sizing, Live allocation) stays off the pre-TTFT path.

            with generation_span(
                model=str(self.model),
                model_config=dataclasses.asdict(model_settings)
                | {"base_url": str(self._get_client().base_url)},
                disabled=tracing.is_disabled(),
            ) as span_generation:
                # Prepare messages for consistent token counting
                # IMPORTANT: Include existing message history for context (matching get_response pattern)
                converted_messages = self._shallow_copy_history_messages()

                # Then convert and add the new input
                new_messages = self._converter.items_to_messages(input, model_instance=self)
                converted_messages.extend(new_messages)

                if system_instructions:
                    # Check if we already have a system message
                    has_system = any(msg.get("role") == "system" for msg in converted_messages)
                    if not has_system:
                        converted_messages.insert(
                            0,
                            {
                                "content": system_instructions,
                                "role": "system",
                            },
                        )

                #    # --- Add to message_history: user, system prompts ---
                #     if system_instructions:
                #         sys_msg = {
                #             "role": "system",
                #             "content": system_instructions
                #         }
                #         self.add_to_message_history(sys_msg)

                if isinstance(input, str):
                    user_msg = {"role": "user", "content": input}
                    self.add_to_message_history(user_msg)
                    # Log the user message
                    self.logger.log_user_message(input)
                elif isinstance(input, list):
                    for item in input:
                        if isinstance(item, dict):
                            if item.get("role") == "user":
                                user_msg = {"role": "user", "content": item.get("content", "")}
                                self.add_to_message_history(user_msg)
                                # Log the user message
                                if item.get("content"):
                                    self.logger.log_user_message(item.get("content"))

                # IMPORTANT: Ensure the message list has valid tool call/result pairs
                # This needs to happen before the API call AND before applying cache_control
                try:
                    from cai.util import fix_message_list

                    converted_messages = fix_message_list(converted_messages)
                except Exception:
                    pass

                # Request-path message normalization/cache-control is applied in _fetch_response().
                # Keep startup estimation lightweight to avoid duplicate per-turn preprocessing work.

                # Get token count estimate before API call for consistent counting
                estimated_input_tokens, _ = count_tokens_with_tiktoken(converted_messages)

                # Check if auto-compaction is needed
                input, system_instructions, compacted = await self._auto_compact_if_needed(estimated_input_tokens, input, system_instructions)
                
                # If compaction occurred, recalculate tokens from the same view ``_fetch_response`` uses
                if compacted:
                    converted_messages = self._messages_for_token_count_after_history_mutation(
                        system_instructions=system_instructions,
                        input=input,
                    )
                    estimated_input_tokens, _ = count_tokens_with_tiktoken(converted_messages)
                    max_tok = self._get_model_max_tokens(str(self.model))
                    if max_tok > 0:
                        os.environ["CAI_CONTEXT_USAGE"] = str(
                            min(1.0, max(0.0, estimated_input_tokens / max_tok))
                        )

                # Pre-check price limit using estimated input tokens and a conservative estimate for output
                # This prevents starting a stream that would immediately exceed the price limit
                if hasattr(COST_TRACKER, "check_price_limit"):
                    # Use a conservative estimate for output tokens (roughly equal to input)
                    estimated_cost = calculate_model_cost(
                        str(self.model), estimated_input_tokens, estimated_input_tokens
                    )  # Conservative estimate
                    try:
                        COST_TRACKER.check_price_limit(estimated_cost)
                    except Exception:
                        # Ensure streaming context is cleaned up in case of errors
                        if streaming_context:
                            try:
                                finish_agent_streaming(streaming_context, None)
                            except Exception:
                                pass
                        # Stop active timer and start idle timer before re-raising the exception
                        stop_active_timer()
                        start_idle_timer()
                        raise

                stream_wait_hints = ModelStreamWaitHints()
                await stream_wait_hints.start()
                # Proactive client-side pacing for the alias gateway. The
                # stream wait hint is already active and reads
                # ``_retry_overlay_message``, so the overlay surfaces
                # automatically. ``alias_gateway_slot`` auto-releases on
                # pre-gateway errors (connect failures, KbInt) so a burst
                # doesn't pin the budget for 60s.
                _stream_on_pace = make_pace_overlay_callback()
                try:
                    if self._is_alias_model:
                        # Streaming pacing: same projection (+completion buffer)
                        # as get_response. ``Reservation.update_actual`` is NOT
                        # called here — final ``usage`` arrives at end-of-stream
                        # outside the slot. The limiter's 85% safety margin
                        # absorbs that residual estimation gap.
                        _stream_projection = estimated_input_tokens + COMPLETION_BUDGET_TOKENS
                        async with get_gateway_rate_limiter().alias_gateway_slot(
                            _stream_projection,
                            on_pace=_stream_on_pace,
                        ):
                            response, stream = await self._fetch_response(
                                system_instructions,
                                input,
                                model_settings,
                                tools,
                                output_schema,
                                handoffs,
                                span_generation,
                                tracing,
                                stream=True,
                            )
                    else:
                        response, stream = await self._fetch_response(
                            system_instructions,
                            input,
                            model_settings,
                            tools,
                            output_schema,
                            handoffs,
                            span_generation,
                            tracing,
                            stream=True,
                        )
                    # Clear any pacing overlay so the default stream body
                    # ("Esperando…") shows during the HTTP response read.
                    set_model_wait_retry_overlay(None)
                except KeyboardInterrupt:
                    await stream_wait_hints.stop()
                    set_model_wait_retry_overlay(None)
                    stop_active_timer()
                    start_idle_timer()
                    raise
                except (litellm.exceptions.Timeout, LLMTimeout) as e:
                    await stream_wait_hints.stop()
                    # Streaming timeout with exponential backoff — clean retry
                    self.logger.warning(f"Timeout in stream_response: {e}")
                    stop_active_timer()
                    start_idle_timer()

                    if not hasattr(self, "_high_level_retry_count"):
                        self._high_level_retry_count = 0
                    self._high_level_retry_count += 1

                    if self._high_level_retry_count > 3:
                        self._high_level_retry_count = 0
                        raise LLMTimeout(f"Timed out after 3 attempts [{self.model}]") from e

                    await self._retry_with_backoff(self._high_level_retry_count - 1, "Timeout")

                    # Clean retry: same input, no "continue" in history
                    async for event in self.stream_response(
                        system_instructions, input, model_settings,
                        tools, output_schema, handoffs, tracing,
                    ):
                        yield event
                    self._high_level_retry_count = 0
                    return

                except (litellm.exceptions.RateLimitError, LLMRateLimited) as e:
                    await stream_wait_hints.stop()
                    # Streaming rate-limit with exponential backoff — clean retry
                    self.logger.warning(f"Rate limit in stream_response: {e}")
                    stop_active_timer()
                    start_idle_timer()

                    if not hasattr(self, "_high_level_retry_count"):
                        self._high_level_retry_count = 0
                    self._high_level_retry_count += 1

                    if self._high_level_retry_count > 3:
                        self._high_level_retry_count = 0
                        raise LLMRateLimited(
                            f"Rate limit after 3 attempts [{self.model}]",
                            retry_after=getattr(e, "retry_after", None),
                        ) from e

                    await self._retry_with_backoff(self._high_level_retry_count - 1, "Rate limit")

                    # Clean retry: same input, no "continue" in history
                    async for event in self.stream_response(
                        system_instructions, input, model_settings,
                        tools, output_schema, handoffs, tracing,
                    ):
                        yield event
                    self._high_level_retry_count = 0
                    return

                except BaseException:
                    await stream_wait_hints.stop()
                    raise

                usage: CompletionUsage | None = None
                state = _StreamingState()

                def next_sequence_number() -> int:
                    sequence_number = state.sequence_number
                    state.sequence_number += 1
                    return sequence_number

                # Manual token counting (when API doesn't provide it)
                output_text = ""
                estimated_output_tokens = 0
                streaming_reasoning_text = ""

                # Initialize a streaming text accumulator for rich display
                streaming_text_buffer = ""
                # For tool call streaming, accumulate tool_calls to add to message_history at the end
                streamed_tool_calls = []

                # Initialize Claude thinking display if applicable
                if should_show_rich_stream:  # Only show thinking in rich streaming mode
                    thinking_context = start_claude_thinking_if_applicable(
                        str(self.model), self.agent_name, self.interaction_counter
                    )

                # Ollama specific: accumulate full content to check for function calls at the end
                # Some Ollama models output the function call as JSON in the text content
                ollama_full_content = ""
                is_ollama = False

                model_str = str(self.model).lower()
                is_ollama = (
                    self.is_ollama
                    or "ollama" in model_str
                    or ":" in model_str
                    or "qwen" in model_str
                )

                # Add visual separation before agent output
                if streaming_context and should_show_rich_stream:
                    # If we're using rich context, we'll add separation through that
                    pass
                else:
                    # Removed clear visual separator to avoid blank lines during streaming
                    pass

                try:
                    async for chunk in stream:
                        await stream_wait_hints.stop()

                        # Check if we've been interrupted
                        if stream_interrupted:
                            break

                        if not state.started:
                            state.started = True
                            yield ResponseCreatedEvent(
                                response=response,
                                sequence_number=next_sequence_number(),
                                type="response.created",
                            )

                        # The usage is only available in the last chunk
                        if hasattr(chunk, "usage"):
                            usage = chunk.usage
                        # For Ollama/LiteLLM streams that don't have usage attribute
                        else:
                            usage = None

                        # Handle different stream chunk formats
                        if hasattr(chunk, "choices") and chunk.choices:
                            choices = chunk.choices
                        elif hasattr(chunk, "delta") and chunk.delta:
                            # Some providers might return delta directly
                            choices = [{"delta": chunk.delta}]
                        elif isinstance(chunk, dict) and "choices" in chunk:
                            choices = chunk["choices"]
                        # Special handling for Qwen/Ollama chunks
                        elif isinstance(chunk, dict) and (
                            "content" in chunk or "function_call" in chunk
                        ):
                            # Qwen direct delta format - convert to standard
                            choices = [{"delta": chunk}]
                        else:
                            # Skip chunks that don't contain choice data
                            continue

                        if not choices or len(choices) == 0:
                            continue

                        # Get the delta content
                        delta = None
                        if hasattr(choices[0], "delta"):
                            delta = choices[0].delta
                        elif isinstance(choices[0], dict) and "delta" in choices[0]:
                            delta = choices[0]["delta"]

                        if not delta:
                            continue

                        # Handle Claude reasoning content first (before regular content)
                        reasoning_content = None

                        # Check for Claude reasoning in different possible formats
                        if (
                            hasattr(delta, "reasoning_content")
                            and delta.reasoning_content is not None
                        ):
                            reasoning_content = delta.reasoning_content
                        elif (
                            isinstance(delta, dict)
                            and "reasoning_content" in delta
                            and delta["reasoning_content"] is not None
                        ):
                            reasoning_content = delta["reasoning_content"]

                        # Also check for thinking_blocks structure (Claude 4 format)
                        thinking_blocks = None
                        if hasattr(delta, "thinking_blocks") and delta.thinking_blocks is not None:
                            thinking_blocks = delta.thinking_blocks
                        elif (
                            isinstance(delta, dict)
                            and "thinking_blocks" in delta
                            and delta["thinking_blocks"] is not None
                        ):
                            thinking_blocks = delta["thinking_blocks"]

                        # Extract reasoning content from thinking blocks if available
                        if thinking_blocks and not reasoning_content:
                            for block in thinking_blocks:
                                if isinstance(block, dict) and block.get("type") == "thinking":
                                    reasoning_content = block.get("thinking", "")
                                    break
                                elif (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                    and "thinking" in str(block)
                                ):
                                    # Sometimes thinking content comes as text blocks
                                    reasoning_content = block.get("text", "")
                                    break

                        # Check for direct thinking field (some Claude models)
                        if not reasoning_content:
                            if hasattr(delta, "thinking") and delta.thinking is not None:
                                reasoning_content = delta.thinking
                            elif (
                                isinstance(delta, dict)
                                and "thinking" in delta
                                and delta["thinking"] is not None
                            ):
                                reasoning_content = delta["thinking"]

                        # Update thinking display if we have reasoning content
                        if reasoning_content:
                            if isinstance(reasoning_content, str):
                                streaming_reasoning_text += reasoning_content
                            if thinking_context:
                                # Streaming mode: Update the rich thinking display
                                from cai.util import update_claude_thinking_content

                                update_claude_thinking_content(thinking_context, reasoning_content)
                            else:
                                # Non-streaming mode: Use simple text output
                                from cai.util import (
                                    detect_claude_thinking_in_stream,
                                    print_claude_reasoning_simple,
                                )

                                # Check if model supports reasoning (Claude or DeepSeek)
                                model_str_lower = str(self.model).lower()
                                if detect_claude_thinking_in_stream(str(self.model)):
                                    print_claude_reasoning_simple(
                                        reasoning_content, self.agent_name, str(self.model)
                                    )

                        # Handle text
                        content = None
                        if hasattr(delta, "content") and delta.content is not None:
                            content = delta.content
                        elif (
                            isinstance(delta, dict)
                            and "content" in delta
                            and delta["content"] is not None
                        ):
                            content = delta["content"]

                        if content:
                            # IMPORTANT: If we have content and thinking_context is active,
                            # it means thinking is complete and normal content is starting
                            # Close the thinking display automatically
                            if thinking_context:
                                from cai.util import finish_claude_thinking_display

                                finish_claude_thinking_display(thinking_context)
                                thinking_context = None  # Clear the context

                            # For Ollama, we need to accumulate the full content to check for function calls
                            if is_ollama:
                                ollama_full_content += content

                            # Add to the streaming text buffer
                            streaming_text_buffer += content

                            # Update streaming display if enabled - ALWAYS respect CAI_STREAM setting
                            # Both thinking and regular content should stream if streaming is enabled
                            if (
                                should_show_rich_stream
                                and streaming_context is None
                            ):
                                try:
                                    streaming_context = create_agent_streaming_context(
                                        agent_name=self.agent_name,
                                        counter=self.interaction_counter,
                                        model=str(self.model),
                                    )
                                except Exception:
                                    streaming_context = None

                            if streaming_context:
                                # Calculate cost for current interaction
                                current_cost = calculate_model_cost(
                                    str(self.model), estimated_input_tokens, estimated_output_tokens
                                )

                                # Check price limit only for paid models
                                if (
                                    current_cost > 0
                                    and hasattr(COST_TRACKER, "check_price_limit")
                                    and estimated_output_tokens % 50 == 0
                                ):
                                    try:
                                        COST_TRACKER.check_price_limit(current_cost)
                                    except Exception:
                                        # Ensure streaming context is cleaned up
                                        if streaming_context:
                                            try:
                                                finish_agent_streaming(streaming_context, None)
                                            except Exception:
                                                pass
                                        # Stop timers and re-raise the exception
                                        stop_active_timer()
                                        start_idle_timer()
                                        raise

                                # Update session total cost for real-time display
                                # This is a temporary estimate during streaming that will be properly updated at the end
                                estimated_session_total = getattr(
                                    COST_TRACKER, "session_total_cost", 0.0
                                )

                                # For free models, don't add to the total cost
                                display_total_cost = estimated_session_total
                                if current_cost > 0:
                                    display_total_cost += current_cost

                                # Create token stats with both current interaction cost and updated total cost
                                token_stats = {
                                    "input_tokens": estimated_input_tokens,
                                    "output_tokens": estimated_output_tokens,
                                    "cost": current_cost,
                                    "total_cost": display_total_cost,
                                }

                                update_agent_streaming_content(
                                    streaming_context, content, token_stats
                                )

                            # More accurate token counting for text content
                            output_text += content
                            token_count, _ = count_tokens_with_tiktoken(output_text)
                            estimated_output_tokens = token_count

                            # Periodically check price limit during streaming
                            # This allows early termination if price limit is reached mid-stream
                            if (
                                estimated_output_tokens > 0 and estimated_output_tokens % 50 == 0
                            ):  # Check every ~50 tokens
                                # Calculate current estimated cost
                                current_estimated_cost = calculate_model_cost(
                                    str(self.model), estimated_input_tokens, estimated_output_tokens
                                )

                                # Check price limit only for paid models
                                if current_estimated_cost > 0 and hasattr(
                                    COST_TRACKER, "check_price_limit"
                                ):
                                    try:
                                        COST_TRACKER.check_price_limit(current_estimated_cost)
                                    except Exception:
                                        # Ensure streaming context is cleaned up
                                        if streaming_context:
                                            try:
                                                finish_agent_streaming(streaming_context, None)
                                            except Exception:
                                                pass
                                        # Stop timers and re-raise the exception
                                        stop_active_timer()
                                        start_idle_timer()
                                        raise

                                # Update the COST_TRACKER with the running cost for accurate display
                                if hasattr(COST_TRACKER, "interaction_cost"):
                                    COST_TRACKER.interaction_cost = current_estimated_cost

                                # Also update streaming context if available for live display
                                if streaming_context:
                                    # For free models, don't add to the session total
                                    if current_estimated_cost == 0:
                                        session_total = getattr(
                                            COST_TRACKER, "session_total_cost", 0.0
                                        )
                                    else:
                                        session_total = (
                                            getattr(COST_TRACKER, "session_total_cost", 0.0)
                                            + current_estimated_cost
                                        )

                                    updated_token_stats = {
                                        "input_tokens": estimated_input_tokens,
                                        "output_tokens": estimated_output_tokens,
                                        "cost": current_estimated_cost,
                                        "total_cost": session_total,
                                    }
                                    update_agent_streaming_content(
                                        streaming_context, "", updated_token_stats
                                    )

                            if not state.text_content_index_and_output:
                                # Initialize a content tracker for streaming text
                                state.text_content_index_and_output = (
                                    0 if not state.refusal_content_index_and_output else 1,
                                    ResponseOutputText(
                                        text="",
                                        type="output_text",
                                        annotations=[],
                                    ),
                                )
                                # Start a new assistant message stream
                                assistant_item = ResponseOutputMessage(
                                    id=FAKE_RESPONSES_ID,
                                    content=[],
                                    role="assistant",
                                    type="message",
                                    status="in_progress",
                                )
                                # Notify consumers of the start of a new output message + first content part
                                yield ResponseOutputItemAddedEvent(
                                    item=assistant_item,
                                    output_index=0,
                                    sequence_number=next_sequence_number(),
                                    type="response.output_item.added",
                                )
                                yield ResponseContentPartAddedEvent(
                                    content_index=state.text_content_index_and_output[0],
                                    item_id=FAKE_RESPONSES_ID,
                                    output_index=0,
                                    part=ResponseOutputText(
                                        text="",
                                        type="output_text",
                                        annotations=[],
                                    ),
                                    sequence_number=next_sequence_number(),
                                    type="response.content_part.added",
                                )
                            # Emit the delta for this segment of content
                            yield ResponseTextDeltaEvent(
                                content_index=state.text_content_index_and_output[0],
                                delta=content,
                                item_id=FAKE_RESPONSES_ID,
                                logprobs=[],
                                sequence_number=next_sequence_number(),
                                output_index=0,
                                type="response.output_text.delta",
                            )
                            # Accumulate the text into the response part
                            state.text_content_index_and_output[1].text += content

                        # Handle refusals (model declines to answer)
                        refusal_content = None
                        if hasattr(delta, "refusal") and delta.refusal:
                            refusal_content = delta.refusal
                        elif isinstance(delta, dict) and "refusal" in delta and delta["refusal"]:
                            refusal_content = delta["refusal"]

                        if refusal_content:
                            if not state.refusal_content_index_and_output:
                                # Initialize a content tracker for streaming refusal text
                                state.refusal_content_index_and_output = (
                                    0 if not state.text_content_index_and_output else 1,
                                    ResponseOutputRefusal(refusal="", type="refusal"),
                                )
                                # Start a new assistant message if one doesn't exist yet (in-progress)
                                assistant_item = ResponseOutputMessage(
                                    id=FAKE_RESPONSES_ID,
                                    content=[],
                                    role="assistant",
                                    type="message",
                                    status="in_progress",
                                )
                                # Notify downstream that assistant message + first content part are starting
                                yield ResponseOutputItemAddedEvent(
                                    item=assistant_item,
                                    output_index=0,
                                    sequence_number=next_sequence_number(),
                                    type="response.output_item.added",
                                )
                                yield ResponseContentPartAddedEvent(
                                    content_index=state.refusal_content_index_and_output[0],
                                    item_id=FAKE_RESPONSES_ID,
                                    output_index=0,
                                    part=ResponseOutputText(
                                        text="",
                                        type="output_text",
                                        annotations=[],
                                    ),
                                    sequence_number=next_sequence_number(),
                                    type="response.content_part.added",
                                )
                            # Emit the delta for this segment of refusal
                            yield ResponseRefusalDeltaEvent(
                                content_index=state.refusal_content_index_and_output[0],
                                delta=refusal_content,
                                item_id=FAKE_RESPONSES_ID,
                                sequence_number=next_sequence_number(),
                                output_index=0,
                                type="response.refusal.delta",
                            )
                            # Accumulate the refusal string in the output part
                            state.refusal_content_index_and_output[1].refusal += refusal_content

                        # Handle tool calls
                        # Because we don't know the name of the function until the end of the stream, we'll
                        # save everything and yield events at the end
                        tool_calls = self._detect_and_format_function_calls(delta)

                        if tool_calls:
                            for tc_delta in tool_calls:
                                tc_index = (
                                    tc_delta.index
                                    if hasattr(tc_delta, "index")
                                    else tc_delta.get("index", 0)
                                )
                                if tc_index not in state.function_calls:
                                    state.function_calls[tc_index] = ResponseFunctionToolCall(
                                        id=FAKE_RESPONSES_ID,
                                        arguments="",
                                        name="",
                                        type="function_call",
                                        call_id="",
                                    )

                                tc_function = None
                                if hasattr(tc_delta, "function"):
                                    tc_function = tc_delta.function
                                elif isinstance(tc_delta, dict) and "function" in tc_delta:
                                    tc_function = tc_delta["function"]

                                if tc_function:
                                    # Handle both object and dict formats
                                    args = ""
                                    if hasattr(tc_function, "arguments"):
                                        args = tc_function.arguments or ""
                                    elif (
                                        isinstance(tc_function, dict) and "arguments" in tc_function
                                    ):
                                        args = tc_function.get("arguments", "") or ""

                                    name = ""
                                    if hasattr(tc_function, "name"):
                                        name = tc_function.name or ""
                                    elif isinstance(tc_function, dict) and "name" in tc_function:
                                        name = tc_function.get("name", "") or ""

                                    state.function_calls[tc_index].arguments += args
                                    state.function_calls[tc_index].name += name

                                # Handle call_id in both formats
                                call_id = ""
                                if hasattr(tc_delta, "id"):
                                    call_id = tc_delta.id or ""
                                elif isinstance(tc_delta, dict) and "id" in tc_delta:
                                    call_id = tc_delta.get("id", "") or ""
                                else:
                                    # For Qwen models, generate a predictable ID if none is provided
                                    if state.function_calls[tc_index].name:
                                        # Generate a stable ID from the function name and arguments
                                        call_id = f"call_{hashlib.md5(state.function_calls[tc_index].name.encode()).hexdigest()[:8]}"

                                state.function_calls[tc_index].call_id += call_id

                                # --- Accumulate tool call for message_history ---
                                # Only add if not already present (avoid duplicates in streaming)
                                # Handle empty arguments before storing
                                tool_args = state.function_calls[tc_index].arguments
                                if tool_args is None or (isinstance(tool_args, str) and tool_args.strip() == ""):
                                    tool_args = "{}"
                                
                                tool_call_msg = {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": state.function_calls[tc_index].call_id,
                                            "type": "function",
                                            "function": {
                                                "name": state.function_calls[tc_index].name,
                                                "arguments": tool_args,
                                            },
                                        }
                                    ],
                                }
                                # Only add if not already in streamed_tool_calls
                                if tool_call_msg not in streamed_tool_calls:
                                    streamed_tool_calls.append(tool_call_msg)
                                    # Don't add to message history here - wait for tool output
                                    # to add both tool call and response atomically

                                    # NEW: Display tool call immediately when detected in streaming mode
                                    # But only if it has complete arguments and name
                                    if (
                                        state.function_calls[tc_index].name
                                        and state.function_calls[tc_index].arguments
                                        and state.function_calls[tc_index].call_id
                                    ):
                                        # First, finish any existing streaming context if it exists
                                        if streaming_context:
                                            try:
                                                finish_agent_streaming(streaming_context, None)
                                                streaming_context = None
                                            except Exception:
                                                pass

                                        # Create a message-like object for displaying the function call
                                        tool_msg = type(
                                            "ToolCallStreamDisplay",
                                            (),
                                            {
                                                "content": None,
                                                "tool_calls": [
                                                    type(
                                                        "ToolCallDetail",
                                                        (),
                                                        {
                                                            "function": type(
                                                                "FunctionDetail",
                                                                (),
                                                                {
                                                                    "name": state.function_calls[
                                                                        tc_index
                                                                    ].name,
                                                                    "arguments": state.function_calls[
                                                                        tc_index
                                                                    ].arguments,
                                                                },
                                                            ),
                                                            "id": state.function_calls[
                                                                tc_index
                                                            ].call_id,
                                                            "type": "function",
                                                        },
                                                    )
                                                ],
                                            },
                                        )

                                        # Display the tool call during streaming
                                        cli_print_agent_messages(
                                            agent_name=getattr(self, "agent_name", "Agent"),
                                            message=tool_msg,
                                            counter=getattr(self, "interaction_counter", 0),
                                            model=str(self.model),
                                            debug=False,
                                            interaction_input_tokens=estimated_input_tokens,
                                            interaction_output_tokens=estimated_output_tokens,
                                            interaction_reasoning_tokens=0,
                                            total_input_tokens=getattr(
                                                self, "total_input_tokens", 0
                                            )
                                            + estimated_input_tokens,
                                            total_output_tokens=getattr(
                                                self, "total_output_tokens", 0
                                            )
                                            + estimated_output_tokens,
                                            total_reasoning_tokens=getattr(
                                                self, "total_reasoning_tokens", 0
                                            ),
                                            interaction_cost=None,
                                            total_cost=None,
                                            tool_output=None,
                                            suppress_empty=True,
                                        )
                                        # Set flag to suppress final output to avoid duplication
                                        self.suppress_final_output = True

                except KeyboardInterrupt:
                    # Handle interruption during streaming
                    stream_interrupted = True
                    print("\n[Streaming interrupted by user]", file=sys.stderr)

                    # Let the exception propagate after cleanup
                    raise

                except Exception as e:
                    # Handle other exceptions during streaming
                    logger.error(f"Error during streaming: {e}")
                    if "token" in str(e).lower() or "limit" in str(e).lower():
                        print("\n📏 Token limit exceeded - Response truncated")
                    raise

                # Special handling for Ollama - check if accumulated text contains a valid function call
                if is_ollama and ollama_full_content and len(state.function_calls) == 0:
                    # Look for JSON object that might be a function call
                    try:
                        # Try to extract a JSON object from the content
                        json_start = ollama_full_content.find("{")
                        json_end = ollama_full_content.rfind("}") + 1

                        if json_start >= 0 and json_end > json_start:
                            json_str = ollama_full_content[json_start:json_end]
                            # Try to parse the JSON
                            parsed = _safe_json_loads(json_str, "Ollama function call")
                            if not parsed:
                                raise ValueError("Failed to parse Ollama function call JSON")

                            # Check if it looks like a function call
                            if "name" in parsed and "arguments" in parsed:
                                logger.debug(
                                    f"Found valid function call in Ollama output: {json_str}"
                                )

                                # Create a tool call ID
                                tool_call_id = f"call_{hashlib.md5((parsed['name'] + str(time.time())).encode()).hexdigest()[:8]}"

                                # Ensure arguments is a valid JSON string
                                arguments_str = ""
                                if isinstance(parsed["arguments"], dict):
                                    # Remove 'ctf' field if it exists
                                    if "ctf" in parsed["arguments"]:
                                        del parsed["arguments"]["ctf"]
                                    arguments_str = json.dumps(parsed["arguments"])
                                elif isinstance(parsed["arguments"], str):
                                    # If it's already a string, check if it's valid JSON
                                    # Try parsing to validate and remove 'ctf' if present
                                    args_dict = _safe_json_loads(parsed["arguments"], "Ollama tool arguments")
                                    if args_dict:
                                        if isinstance(args_dict, dict) and "ctf" in args_dict:
                                            del args_dict["ctf"]
                                        arguments_str = json.dumps(args_dict)
                                    else:
                                        # If not valid JSON, encode it as a JSON string
                                        arguments_str = json.dumps(parsed["arguments"])
                                else:
                                    # For any other type, convert to string and then JSON
                                    arguments_str = json.dumps(str(parsed["arguments"]))
                                # Add it to our function_calls state
                                state.function_calls[0] = ResponseFunctionToolCall(
                                    id=FAKE_RESPONSES_ID,
                                    arguments=arguments_str,
                                    name=parsed["name"],
                                    type="function_call",
                                    call_id=tool_call_id[:40],
                                )

                                # Display the tool call in CLI
                                try:
                                    # First, finish any existing streaming context if it exists
                                    if streaming_context:
                                        try:
                                            finish_agent_streaming(streaming_context, None)
                                            streaming_context = None
                                        except Exception:
                                            pass

                                    # Create a message-like object to display the function call
                                    tool_msg = type(
                                        "ToolCallWrapper",
                                        (),
                                        {
                                            "content": None,
                                            "tool_calls": [
                                                type(
                                                    "ToolCallDetail",
                                                    (),
                                                    {
                                                        "function": type(
                                                            "FunctionDetail",
                                                            (),
                                                            {
                                                                "name": parsed["name"],
                                                                "arguments": arguments_str,
                                                            },
                                                        ),
                                                        "id": tool_call_id[:40],
                                                        "type": "function",
                                                    },
                                                )
                                            ],
                                        },
                                    )

                                    # Print the tool call using the CLI utility
                                    cli_print_agent_messages(
                                        agent_name=getattr(self, "agent_name", "Agent"),
                                        message=tool_msg,
                                        counter=getattr(self, "interaction_counter", 0),
                                        model=str(self.model),
                                        debug=False,
                                        interaction_input_tokens=estimated_input_tokens,
                                        interaction_output_tokens=estimated_output_tokens,
                                        interaction_reasoning_tokens=0,
                                        total_input_tokens=getattr(
                                            self, "total_input_tokens", 0
                                        )
                                        + estimated_input_tokens,
                                        total_output_tokens=getattr(
                                            self, "total_output_tokens", 0
                                        )
                                        + estimated_output_tokens,
                                        total_reasoning_tokens=getattr(
                                            self, "total_reasoning_tokens", 0
                                        ),
                                        interaction_cost=None,
                                        total_cost=None,
                                        tool_output=None,
                                        suppress_empty=True,
                                    )

                                    # Set flag to suppress final output to avoid duplication
                                    self.suppress_final_output = True
                                except Exception as e:
                                    # Silently log the error - don't disrupt the flow
                                    logger.debug(f"Display error (non-critical): {e}")

                                # Add to message history
                                tool_call_msg = {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": tool_call_id,
                                            "type": "function",
                                            "function": {
                                                "name": parsed["name"],
                                                "arguments": arguments_str,
                                            },
                                        }
                                    ],
                                }

                                streamed_tool_calls.append(tool_call_msg)
                                # Don't add to message history here - wait for tool output
                                # to add both tool call and response atomically

                                logger.debug(
                                    f"Added function call: {parsed['name']} with args: {arguments_str}"
                                )
                    except Exception:
                        pass

                if _is_effectively_empty_stream_accumulation(
                    state,
                    streamed_tool_calls,
                    output_text,
                    streaming_reasoning_text,
                ):
                    empty_streak = _empty_completion_streak + 1
                    max_empty_failures = _empty_completion_max_failures()
                    self.logger.warning(
                        "Empty streamed assistant completion (%s/%s); "
                        "pt_est=%s reasoning_len=%s tools=%s; repeating.",
                        empty_streak,
                        max_empty_failures,
                        estimated_input_tokens,
                        len(streaming_reasoning_text),
                        len(streamed_tool_calls) + len(state.function_calls),
                    )
                    if empty_streak >= max_empty_failures:
                        stop_active_timer()
                        start_idle_timer()
                        raise LLMEmptyAssistantError(
                            "Consecutive empty assistant completions from the provider.",
                            {"attempts": max_empty_failures},
                        )
                    if streaming_context:
                        try:
                            finish_agent_streaming(streaming_context, None)
                        except Exception:
                            pass
                        streaming_context = None
                    if thinking_context:
                        try:
                            from cai.util import finish_claude_thinking_display

                            finish_claude_thinking_display(thinking_context)
                        except Exception:
                            pass
                        thinking_context = None
                    await stream_wait_hints.stop()
                    set_model_wait_retry_overlay(None)
                    input, system_instructions, estimated_input_tokens = (
                        await self._recover_after_empty_completion(
                            empty_streak=empty_streak,
                            estimated_input_tokens=estimated_input_tokens,
                            input=input,
                            system_instructions=system_instructions,
                        )
                    )
                    set_model_wait_retry_overlay(
                        "Provider returned an empty response; "
                        f"retrying ({empty_streak}/{max_empty_failures})…"
                    )
                    async for event in self.stream_response(
                        system_instructions,
                        input,
                        model_settings,
                        tools,
                        output_schema,
                        handoffs,
                        tracing,
                        _empty_completion_streak=empty_streak,
                    ):
                        yield event
                    return

                function_call_starting_index = 0
                if state.text_content_index_and_output:
                    function_call_starting_index += 1
                    # Send end event for this content part
                    yield ResponseContentPartDoneEvent(
                        content_index=state.text_content_index_and_output[0],
                        item_id=FAKE_RESPONSES_ID,
                        output_index=0,
                        part=state.text_content_index_and_output[1],
                        sequence_number=next_sequence_number(),
                        type="response.content_part.done",
                    )

                if state.refusal_content_index_and_output:
                    function_call_starting_index += 1
                    # Send end event for this content part
                    yield ResponseContentPartDoneEvent(
                        content_index=state.refusal_content_index_and_output[0],
                        item_id=FAKE_RESPONSES_ID,
                        output_index=0,
                        part=state.refusal_content_index_and_output[1],
                        sequence_number=next_sequence_number(),
                        type="response.content_part.done",
                    )

                # Actually send events for the function calls
                for function_call in state.function_calls.values():
                    # First, a ResponseOutputItemAdded for the function call
                    yield ResponseOutputItemAddedEvent(
                        item=ResponseFunctionToolCall(
                            id=FAKE_RESPONSES_ID,
                            call_id=function_call.call_id[:40],
                            arguments=function_call.arguments,
                            name=function_call.name,
                            type="function_call",
                        ),
                        output_index=function_call_starting_index,
                        sequence_number=next_sequence_number(),
                        type="response.output_item.added",
                    )
                    # Then, yield the args
                    yield ResponseFunctionCallArgumentsDeltaEvent(
                        delta=function_call.arguments,
                        item_id=FAKE_RESPONSES_ID,
                        output_index=function_call_starting_index,
                        sequence_number=next_sequence_number(),
                        type="response.function_call_arguments.delta",
                    )
                    # Finally, the ResponseOutputItemDone
                    yield ResponseOutputItemDoneEvent(
                        item=ResponseFunctionToolCall(
                            id=FAKE_RESPONSES_ID,
                            call_id=function_call.call_id[:40],
                            arguments=function_call.arguments,
                            name=function_call.name,
                            type="function_call",
                        ),
                        output_index=function_call_starting_index,
                        sequence_number=next_sequence_number(),
                        type="response.output_item.done",
                    )

                # Finally, send the Response completed event
                outputs: list[ResponseOutputItem] = []
                if state.text_content_index_and_output or state.refusal_content_index_and_output:
                    assistant_msg = ResponseOutputMessage(
                        id=FAKE_RESPONSES_ID,
                        content=[],
                        role="assistant",
                        type="message",
                        status="completed",
                    )
                    if state.text_content_index_and_output:
                        assistant_msg.content.append(state.text_content_index_and_output[1])
                    if state.refusal_content_index_and_output:
                        assistant_msg.content.append(state.refusal_content_index_and_output[1])
                    outputs.append(assistant_msg)

                    # send a ResponseOutputItemDone for the assistant message
                    yield ResponseOutputItemDoneEvent(
                        item=assistant_msg,
                        output_index=0,
                        sequence_number=next_sequence_number(),
                        type="response.output_item.done",
                    )

                for function_call in state.function_calls.values():
                    outputs.append(function_call)

                final_response = response.model_copy()
                final_response.output = outputs

                # Get final token counts using consistent method
                input_tokens = estimated_input_tokens
                output_tokens = estimated_output_tokens

                # Use API token counts if available and reasonable
                if usage and hasattr(usage, "prompt_tokens") and usage.prompt_tokens > 0:
                    input_tokens = usage.prompt_tokens
                if usage and hasattr(usage, "completion_tokens") and usage.completion_tokens > 0:
                    output_tokens = usage.completion_tokens

                # Extract cache metrics from the usage object (if available from direct HTTP path)
                # Support both Anthropic format and OpenAI format (prompt_tokens_details.cached_tokens)
                cache_creation = getattr(usage, 'cache_creation_input_tokens', None) if usage else None
                cache_read = getattr(usage, 'cache_read_input_tokens', None) if usage else None
                # Fallback to OpenAI format if Anthropic format not available
                if not cache_read and usage:
                    prompt_details = getattr(usage, 'prompt_tokens_details', None)
                    if prompt_details:
                        cache_read = getattr(prompt_details, 'cached_tokens', None)

                # Create a proper usage object with our token counts
                final_response.usage = CustomResponseUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    output_tokens_details=OutputTokensDetails(
                        reasoning_tokens=usage.completion_tokens_details.reasoning_tokens
                        if usage
                        and hasattr(usage, "completion_tokens_details")
                        and usage.completion_tokens_details
                        and hasattr(usage.completion_tokens_details, "reasoning_tokens")
                        and usage.completion_tokens_details.reasoning_tokens
                        else 0
                    ),
                    input_tokens_details={
                        "prompt_tokens": input_tokens,
                        "cached_tokens": usage.prompt_tokens_details.cached_tokens
                        if usage
                        and hasattr(usage, "prompt_tokens_details")
                        and usage.prompt_tokens_details
                        and hasattr(usage.prompt_tokens_details, "cached_tokens")
                        and usage.prompt_tokens_details.cached_tokens
                        else 0,
                    },
                    cache_creation_input_tokens=cache_creation,
                    cache_read_input_tokens=cache_read,
                )

                yield ResponseCompletedEvent(
                    response=final_response,
                    sequence_number=next_sequence_number(),
                    type="response.completed",
                )

                # Update token totals for CLI display
                if final_response.usage:
                    # Always update the total counters with the best available counts
                    self.total_input_tokens += final_response.usage.input_tokens
                    self.total_output_tokens += final_response.usage.output_tokens
                    if final_response.usage.output_tokens_details and hasattr(
                        final_response.usage.output_tokens_details, "reasoning_tokens"
                    ):
                        self.total_reasoning_tokens += (
                            final_response.usage.output_tokens_details.reasoning_tokens
                        )

                # Prepare final statistics for display
                interaction_input = final_response.usage.input_tokens if final_response.usage else 0
                interaction_output = (
                    final_response.usage.output_tokens if final_response.usage else 0
                )
                total_input = getattr(self, "total_input_tokens", 0)
                total_output = getattr(self, "total_output_tokens", 0)

                # Calculate costs for this model
                model_name = str(self.model)
                interaction_cost = calculate_model_cost(
                    model_name, interaction_input, interaction_output
                )
                # Get the previous total cost and add this interaction's cost
                # Don't recalculate cost for all tokens - that causes double-counting
                previous_total = getattr(COST_TRACKER, "session_total_cost", 0.0)
                total_cost = previous_total + interaction_cost

                # If interaction cost is zero, this is a free model
                if interaction_cost == 0:
                    # For free models, keep existing total and ensure cost tracking system knows it's free
                    total_cost = getattr(COST_TRACKER, "session_total_cost", 0.0)
                    if hasattr(COST_TRACKER, "reset_cost_for_local_model"):
                        COST_TRACKER.reset_cost_for_local_model(model_name)

                # Explicit conversion to float with fallback to ensure they're never None or 0
                interaction_cost = float(interaction_cost if interaction_cost is not None else 0.0)
                total_cost = float(total_cost if total_cost is not None else 0.0)

                # Process costs through COST_TRACKER only once per interaction
                if interaction_cost > 0.0:
                    # Check price limit before processing the new cost
                    if hasattr(COST_TRACKER, "check_price_limit"):
                        try:
                            COST_TRACKER.check_price_limit(interaction_cost)
                        except Exception:
                            # Ensure streaming context is cleaned up
                            if streaming_context:
                                try:
                                    finish_agent_streaming(streaming_context, None)
                                except Exception:
                                    pass
                            # Stop timers and re-raise the exception
                            stop_active_timer()
                            start_idle_timer()
                            raise

                    # Process the interaction cost (updates internal tracking)
                    COST_TRACKER.process_interaction_cost(
                        model_name,
                        interaction_input,
                        interaction_output,
                        final_response.usage.output_tokens_details.reasoning_tokens
                        if final_response.usage
                        and final_response.usage.output_tokens_details
                        and hasattr(final_response.usage.output_tokens_details, "reasoning_tokens")
                        else 0,
                        interaction_cost,
                        agent_name=self.agent_name,
                        agent_id=self.agent_id
                    )
                    
                    # Process the total cost (updates session total correctly)
                    total_cost = COST_TRACKER.process_total_cost(
                        model_name,
                        total_input,
                        total_output,
                        getattr(self, "total_reasoning_tokens", 0),
                        None,  # Let it calculate from tokens
                        agent_name=self.agent_name,
                        agent_id=self.agent_id
                    )
                    
                    # Track usage globally
                    GLOBAL_USAGE_TRACKER.track_usage(
                        model_name=model_name,
                        input_tokens=interaction_input,
                        output_tokens=interaction_output,
                        cost=interaction_cost,
                        agent_name=self.agent_name
                    )
                else:
                    # For free models, still track token usage
                    GLOBAL_USAGE_TRACKER.track_usage(
                        model_name=model_name,
                        input_tokens=interaction_input,
                        output_tokens=interaction_output,
                        cost=0.0,
                        agent_name=self.agent_name
                    )

                # Store the total cost for future recording
                self.total_cost = total_cost
                # Update per-interaction tokens for tool panels
                self.interaction_input_tokens = int(interaction_input)
                self.interaction_output_tokens = int(interaction_output)
                self.interaction_reasoning_tokens = int(
                    final_response.usage.output_tokens_details.reasoning_tokens
                    if final_response.usage
                    and final_response.usage.output_tokens_details
                    and hasattr(final_response.usage.output_tokens_details, "reasoning_tokens")
                    else 0
                )
                # Update cache tokens for tool panels
                self.cache_read_tokens = int(cache_read) if cache_read else 0
                self.cache_creation_tokens = int(cache_creation) if cache_creation else 0

                # Also update COST_TRACKER so it's available for tool panels
                try:
                    import cai.util
                    cai.util.COST_TRACKER.interaction_input_tokens = self.interaction_input_tokens
                    cai.util.COST_TRACKER.interaction_output_tokens = self.interaction_output_tokens
                    cai.util.COST_TRACKER.interaction_reasoning_tokens = self.interaction_reasoning_tokens
                    cai.util.COST_TRACKER.cache_read_tokens = self.cache_read_tokens
                    cai.util.COST_TRACKER.cache_creation_tokens = self.cache_creation_tokens
                except Exception:
                    pass

                # Create final stats with explicit type conversion for all values
                final_stats = {
                    "interaction_input_tokens": int(interaction_input),
                    "interaction_output_tokens": int(interaction_output),
                    "interaction_reasoning_tokens": int(
                        final_response.usage.output_tokens_details.reasoning_tokens
                        if final_response.usage
                        and final_response.usage.output_tokens_details
                        and hasattr(final_response.usage.output_tokens_details, "reasoning_tokens")
                        else 0
                    ),
                    "total_input_tokens": int(total_input),
                    "total_output_tokens": int(total_output),
                    "total_reasoning_tokens": int(getattr(self, "total_reasoning_tokens", 0)),
                    "interaction_cost": float(interaction_cost),
                    "total_cost": float(total_cost),
                    "cache_read_tokens": int(cache_read) if cache_read else 0,
                    "cache_creation_tokens": int(cache_creation) if cache_creation else 0,
                }

                # At the end of streaming, finish the streaming context if we were using it
                if streaming_context:
                    # Create a direct copy of the costs to ensure they remain as floats
                    direct_stats = final_stats.copy()
                    direct_stats["interaction_cost"] = float(interaction_cost)
                    direct_stats["total_cost"] = float(total_cost)
                    # Use the direct copy with guaranteed float costs
                    finish_agent_streaming(streaming_context, direct_stats)
                    streaming_context = None

                    # Removed extra newline after streaming completes to avoid blank lines
                    pass

                # Finish Claude thinking display if it was active
                if thinking_context:
                    from cai.util import finish_claude_thinking_display

                    finish_claude_thinking_display(thinking_context)

                    # Note: Content is now displayed during streaming, no need to show it again here

                if tracing.include_data():
                    span_generation.span_data.output = [final_response.model_dump()]

                span_generation.span_data.usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }

                # --- DEFERRED: Tool calls are no longer added immediately ---
                # Store pending tool calls but don't add to history yet
                if not hasattr(self, "_pending_tool_calls"):
                    self._pending_tool_calls = {}

                for tool_call_msg in streamed_tool_calls:
                    # Extract tool call ID from the message
                    if tool_call_msg.get("tool_calls"):
                        for tc in tool_call_msg["tool_calls"]:
                            self._pending_tool_calls[tc["id"]] = tool_call_msg

                # Log the assistant tool call message if any tool calls were collected
                if streamed_tool_calls:
                    tool_calls_list = []
                    for tool_call_msg in streamed_tool_calls:
                        for tool_call in tool_call_msg.get("tool_calls", []):
                            tool_calls_list.append(tool_call)
                    self.logger.log_assistant_message(None, tool_calls_list)

                # Always log text content if it exists, regardless of suppress_final_output
                # The suppress_final_output flag is only for preventing duplicate tool call display
                if (
                    state.text_content_index_and_output
                    and state.text_content_index_and_output[1].text
                ):
                    asst_msg = {
                        "role": "assistant",
                        "content": state.text_content_index_and_output[1].text,
                    }
                    self.add_to_message_history(asst_msg)
                    # Log the assistant message
                    self.logger.log_assistant_message(state.text_content_index_and_output[1].text)

                # Reset the suppress flag for future requests
                self.suppress_final_output = False

                # Log the complete response
                self.logger.rec_training_data(
                    {
                        "model": str(self.model),
                        "messages": converted_messages,
                        "stream": True,
                        "tools": [t.params_json_schema for t in tools] if tools else [],
                        "tool_choice": model_settings.tool_choice,
                    },
                    final_response,
                    self.total_cost,
                    self.agent_name,
                )

                # Stop active timer and start idle timer when streaming is complete
                stop_active_timer()
                start_idle_timer()

        except KeyboardInterrupt:
            # Handle keyboard interruption specifically
            stream_interrupted = True

            # Ensure message history consistency by adding synthetic tool results
            # for any tool calls that were added but don't have corresponding results
            try:
                # Find all tool calls in recent assistant messages
                orphaned_tool_calls = []
                for msg in reversed(self.message_history[-10:]):  # Check recent messages
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tool_call in msg["tool_calls"]:
                            call_id = tool_call.get("id")
                            if call_id:
                                # Check if this tool call has a corresponding tool result
                                has_result = any(
                                    m.get("role") == "tool" and m.get("tool_call_id") == call_id
                                    for m in self.message_history
                                )
                                if not has_result:
                                    orphaned_tool_calls.append((call_id, tool_call))

                # Add synthetic tool results for orphaned tool calls
                for call_id, tool_call in orphaned_tool_calls:
                    tool_response_msg = {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": "Tool execution interrupted"
                    }
                    self.add_to_message_history(tool_response_msg)
                    
            except Exception as cleanup_error:
                # Don't let cleanup errors mask the original KeyboardInterrupt
                logger.debug(f"Error during interrupt cleanup: {cleanup_error}")

            # Make sure to clean up and re-raise
            raise

        except Exception as e:
            # Handle other exceptions
            logger.error(f"Error in stream_response: {e}")
            raise

        finally:
            # Always clean up resources
            # This block executes whether the try block succeeds, fails, or is interrupted

            if stream_wait_hints is not None:
                try:
                    await stream_wait_hints.stop()
                except Exception:
                    pass

            # Clean up streaming context
            if streaming_context:
                try:
                    # Check if we need to force stop the streaming panel
                    if streaming_context.get("is_started", False) and streaming_context.get("live"):
                        streaming_context["live"].stop()

                    # Remove from active streaming contexts
                    if hasattr(create_agent_streaming_context, "_active_streaming"):
                        for key, value in list(
                            create_agent_streaming_context._active_streaming.items()
                        ):
                            if value is streaming_context:
                                del create_agent_streaming_context._active_streaming[key]
                                break
                except Exception as cleanup_error:
                    logger.debug(f"Error cleaning up streaming context: {cleanup_error}")

            # Clean up thinking context
            if thinking_context:
                try:
                    # Force finish the thinking display
                    from cai.util import finish_claude_thinking_display

                    finish_claude_thinking_display(thinking_context)
                except Exception as cleanup_error:
                    logger.debug(f"Error cleaning up thinking context: {cleanup_error}")

            # Clean up any live streaming panels
            if hasattr(cli_print_tool_output, "_streaming_sessions"):
                # Find any sessions related to this stream
                for call_id in list(cli_print_tool_output._streaming_sessions.keys()):
                    if call_id in _LIVE_STREAMING_PANELS:
                        try:
                            live = _LIVE_STREAMING_PANELS[call_id]
                            live.stop()
                            del _LIVE_STREAMING_PANELS[call_id]
                        except Exception:
                            pass

            # Stop active timer and start idle timer
            try:
                stop_active_timer()
                start_idle_timer()
            except Exception:
                pass

            # Stream cleanup completed

    @overload
    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        span: Span[GenerationSpanData],
        tracing: ModelTracing,
        stream: Literal[True],
    ) -> tuple[Response, AsyncStream[ChatCompletionChunk]]: ...

    @overload
    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        span: Span[GenerationSpanData],
        tracing: ModelTracing,
        stream: Literal[False],
    ) -> ChatCompletion: ...

    async def _fetch_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchema | None,
        handoffs: list[Handoff],
        span: Span[GenerationSpanData],
        tracing: ModelTracing,
        stream: bool = False,
    ) -> ChatCompletion | tuple[Response, AsyncStream[ChatCompletionChunk]]:
        # Debug: Print when entering _fetch_response
        if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
            print(f"[CACHE-DEBUG] _fetch_response called, stream={stream}, model={self.model}")

        # start by re-fetching self.is_ollama
        self.is_ollama = os.getenv("OLLAMA") is not None and os.getenv("OLLAMA").lower() == "true"

        # IMPORTANT: Include existing message history for context
        converted_messages = self._shallow_copy_history_messages()

        # IMPORTANT: We maintain our own message_history which already contains all messages.
        # The SDK also passes 'input' with conversation items, but these duplicate what we have.
        # To avoid duplication: if we have message_history, DON'T add anything from input.
        # The caller (get_response/get_streamed_response) already adds messages to our history.
        if not self.message_history:
            # First turn: no history yet, so we need to use input
            new_messages = self._converter.items_to_messages(input, model_instance=self)
            converted_messages.extend(new_messages)

        if system_instructions:
            # Check if we already have a system message
            has_system = any(msg.get("role") == "system" for msg in converted_messages)
            if not has_system:
                # Inject shared session context if available
                from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                shared_context = AGENT_MANAGER.get_shared_context_injection()
                
                final_system_instructions = system_instructions + shared_context
                
                converted_messages.insert(
                    0,
                    {
                        "content": final_system_instructions,
                        "role": "system",
                    },
                )
            else:
                # System message already exists, append shared context to it
                from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                shared_context = AGENT_MANAGER.get_shared_context_injection()
                
                if shared_context:
                    for msg in converted_messages:
                        if msg.get("role") == "system":
                            msg["content"] = str(msg.get("content", "")) + shared_context
                            break

        # IMPORTANT: Always sanitize the message list to prevent tool call errors
        # This is critical to fix common errors with tool/assistant sequences
        # Must happen BEFORE applying cache_control
        try:
            from cai.util import fix_message_list

            prev_length = len(converted_messages)
            converted_messages = fix_message_list(converted_messages)
            new_length = len(converted_messages)

            # Log if the message list was changed significantly
            if new_length != prev_length:
                logger.debug(f"Message list was fixed: {prev_length} -> {new_length} messages")
        except Exception:
            pass

        # Add support for prompt caching for claude (not automatically applied)
        # Gemini supports it too
        # https://www.anthropic.com/news/token-saving-updates
        # Maximize cache efficiency by using up to 4 cache_control blocks
        # IMPORTANT: Apply cache_control AFTER fix_message_list() to ensure it's preserved
        # Note: Use "claude" in string to support both direct and openrouter/anthropic/claude models
        model_str = str(self.model).lower()
        if ("claude" in model_str or "gemini" in model_str) and len(
            converted_messages
        ) > 0:
            # Debug: Show messages BEFORE normalization
            if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
                print(f"[CACHE-DEBUG] BEFORE normalization: {len(converted_messages)} messages")
                # Compute pre-normalization hashes to see if messages change during normalization
                for i, msg in enumerate(converted_messages[:5]):  # Show first 5 only
                    role = msg.get("role", "?")
                    content = msg.get("content")
                    content_type = type(content).__name__
                    has_cc = False
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and "cache_control" in block:
                                has_cc = True
                                break
                    elif isinstance(content, dict) and "cache_control" in content:
                        has_cc = True
                    cc_note = " (has cache_control)" if has_cc else ""
                    pre_hash = hashlib.md5(json.dumps(msg, sort_keys=True, default=str).encode()).hexdigest()[:8]
                    print(f"  [PRE-{i}] {role}: content={content_type}{cc_note} hash={pre_hash}")
            # STEP 1: Normalize messages for consistent structure
            # This is CRITICAL for cache matching - the content structure must be identical
            # between turns for Anthropic to recognize the prefix and read from cache.
            #
            # IMPORTANT: Normalize ALL messages to block format for cache_control support
            # The proxy converts to Anthropic format anyway, so block format works for all roles.
            # - system/user/assistant/tool: All use block format [{"type": "text", "text": "..."}]
            # - assistant with tool_calls: Content can be None, tool_calls is separate
            for msg in converted_messages:
                role = msg.get("role")
                content = msg.get("content")

                # Skip messages without content (e.g., assistant with only tool_calls)
                if content is None:
                    continue

                # Normalize ALL messages to block format (including tool messages)
                # This allows us to add cache_control to any message
                if isinstance(content, str):
                    msg["content"] = [{"type": "text", "text": content}]
                elif isinstance(content, list):
                    normalized = []
                    for block in content:
                        if isinstance(block, str):
                            normalized.append({"type": "text", "text": block})
                        elif isinstance(block, dict):
                            # Remove any existing cache_control - we'll add fresh ones
                            block_copy = {k: v for k, v in block.items() if k != "cache_control"}
                            normalized.append(block_copy)
                        else:
                            normalized.append(block)
                    msg["content"] = normalized

                # Remove message-level cache_control
                if "cache_control" in msg:
                    del msg["cache_control"]

            # STEP 2: Determine cache breakpoints
            # Anthropic's recommended caching strategy for multi-turn conversations:
            # 1. ALWAYS mark the LAST message with cache_control - this caches the ENTIRE
            #    conversation prefix (system + all messages including tool_use/tool_results)
            # 2. Optionally mark system message for when cache expires and needs rebuilding
            #
            # From Anthropic docs: "During each turn, we mark the final block of the final
            # message with cache_control so the conversation can be incrementally cached."
            #
            # IMPORTANT: Not all messages can have cache_control in OpenAI format:
            # - tool messages have string content (no block format)
            # - assistant with only tool_calls has None content
            # For these, we find the nearest cacheable message before them.

            def can_have_cache_control(msg):
                """Check if a message can have cache_control applied."""
                role = msg.get("role")
                content = msg.get("content")
                # Tool messages now use block format, so they CAN have cache_control
                # (They were normalized to block format above)
                # Assistant with only tool_calls - no content to add cache_control
                if content is None and msg.get("tool_calls"):
                    return False
                # Must have list content (normalized block format)
                if isinstance(content, list) and content:
                    return True
                return False

            cache_indices = []

            # 1. Find and mark system message (for cache rebuild after expiry)
            for i, msg in enumerate(converted_messages):
                if msg.get("role") == "system":
                    cache_indices.append(i)
                    break

            # 2. Find the last CACHEABLE message for incremental caching
            # Start from the end and go back until we find a message that can have cache_control
            last_cacheable_idx = None
            for i in range(len(converted_messages) - 1, -1, -1):
                if can_have_cache_control(converted_messages[i]):
                    last_cacheable_idx = i
                    break

            if last_cacheable_idx is not None and last_cacheable_idx not in cache_indices:
                cache_indices.append(last_cacheable_idx)

            # STEP 3: Apply cache_control ONLY to breakpoint messages
            for idx in cache_indices:
                msg = converted_messages[idx]
                content = msg.get("content")
                # For list content (normalized block format), add to last block
                if isinstance(content, list) and content:
                    last_block = content[-1]
                    if isinstance(last_block, dict):
                        last_block["cache_control"] = {"type": "ephemeral"}

            # Debug: Show cache_control was applied
            if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
                global _PREVIOUS_TURN_MSG_HASHES
                print(f"[CACHE-DEBUG] Applied cache_control to indices: {cache_indices}, total messages: {len(converted_messages)}")

                # Collect hashes for this turn
                current_turn_hashes = []

                # Show message structure with hashes for cache debugging
                # Hash helps identify which messages change between turns
                for i, msg in enumerate(converted_messages):
                    role = msg.get("role", "?")
                    content = msg.get("content")
                    has_tc = "tool_calls" in msg
                    tool_id = msg.get("tool_call_id", "")[:8] if msg.get("tool_call_id") else ""

                    # Compute hash of message content (excluding cache_control for comparison)
                    msg_for_hash = msg.copy()
                    if isinstance(msg_for_hash.get("content"), list):
                        # Remove cache_control from blocks for hashing
                        clean_content = []
                        for block in msg_for_hash["content"]:
                            if isinstance(block, dict):
                                clean_block = {k: v for k, v in block.items() if k != "cache_control"}
                                clean_content.append(clean_block)
                            else:
                                clean_content.append(block)
                        msg_for_hash["content"] = clean_content
                    msg_hash = hashlib.md5(json.dumps(msg_for_hash, sort_keys=True, default=str).encode()).hexdigest()[:8]
                    current_turn_hashes.append(msg_hash)

                    # Check if this message matches the same position in previous turn
                    match_marker = ""
                    if i < len(_PREVIOUS_TURN_MSG_HASHES):
                        if _PREVIOUS_TURN_MSG_HASHES[i] == msg_hash:
                            match_marker = " ✓MATCH"
                        else:
                            match_marker = f" ✗CHANGED (was {_PREVIOUS_TURN_MSG_HASHES[i]})"

                    if isinstance(content, list) and content:
                        last_block = content[-1]
                        has_cc = isinstance(last_block, dict) and "cache_control" in last_block
                        cc_marker = " ✓CC" if has_cc else ""
                        # Show first text content preview
                        text_preview = ""
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")[:40].replace('\n', ' ')
                                text_preview = f" '{text}...'" if len(block.get("text", "")) > 40 else f" '{text}'"
                                break
                        print(f"  [{i}] {role} [hash:{msg_hash}]: list({len(content)} blocks){cc_marker}{match_marker}{text_preview}")
                    elif isinstance(content, str):
                        # String content should not happen after normalization - warn if it does
                        content_preview = content[:30].replace('\n', ' ') + "..." if len(content) > 30 else content.replace('\n', ' ')
                        print(f"  [{i}] {role} [hash:{msg_hash}]: string({len(content)} chars) - SHOULD BE LIST!{match_marker} '{content_preview}'")
                    elif content is None:
                        tc_info = ""
                        if has_tc:
                            tc_list = msg.get("tool_calls", [])
                            tc_ids = [tc.get("id", "?")[:12] for tc in tc_list]
                            tc_info = f", tool_calls={len(tc_list)} ids={tc_ids}"
                        print(f"  [{i}] {role} [hash:{msg_hash}]: None{tc_info}{match_marker}")

                # Summary of matches (before storing new hashes)
                if len(_PREVIOUS_TURN_MSG_HASHES) > 0:
                    common_len = min(len(current_turn_hashes), len(_PREVIOUS_TURN_MSG_HASHES))
                    matches = sum(1 for i in range(common_len) if current_turn_hashes[i] == _PREVIOUS_TURN_MSG_HASHES[i])
                    print(f"[CACHE-DEBUG] PREFIX MATCH: {matches}/{common_len} messages match previous turn (cache needs prefix match)")
                    if matches < common_len:
                        # Find first mismatch for detailed debugging
                        for i in range(common_len):
                            if current_turn_hashes[i] != _PREVIOUS_TURN_MSG_HASHES[i]:
                                print(f"[CACHE-DEBUG] FIRST MISMATCH at index {i}: messages diverge here, cache breaks")
                                # Print full JSON of mismatched message for debugging
                                msg = converted_messages[i]
                                msg_json = json.dumps(msg, indent=2, default=str)[:500]
                                print(f"[CACHE-DEBUG] Current message[{i}] JSON (truncated):\n{msg_json}")
                                break

                # Store current turn's hashes for next comparison
                _PREVIOUS_TURN_MSG_HASHES = current_turn_hashes
                print(f"[CACHE-DEBUG] Stored {len(current_turn_hashes)} message hashes for next turn comparison")

        if tracing.include_data():
            span.span_data.input = converted_messages

        parallel_tool_calls = (
            True if model_settings.parallel_tool_calls and tools and len(tools) > 0 else NOT_GIVEN
        )
        tool_choice = self._converter.convert_tool_choice(model_settings.tool_choice)
        response_format = self._converter.convert_response_format(output_schema)
        converted_tools = [ToolConverter.to_openai(tool) for tool in tools] if tools else []

        for handoff in handoffs:
            converted_tools.append(ToolConverter.convert_handoff_tool(handoff))

        if _debug.DONT_LOG_MODEL_DATA:
            logger.debug("Calling LLM")
        else:
            logger.debug(
                f"{json.dumps(converted_messages, indent=2)}\n"
                f"Tools:\n{json.dumps(converted_tools, indent=2)}\n"
                f"Stream: {stream}\n"
                f"Tool choice: {tool_choice}\n"
                f"Response format: {response_format}\n"
                f"Using OLLAMA: {self.is_ollama}\n"
            )

        # Use NOT_GIVEN for store if not explicitly set to avoid compatibility issues
        store = self._non_null_or_not_given(model_settings.store)

        # Check if we should use the agent's model instead of self.model
        # This prioritizes the model from Agent when available
        agent_model = None
        if hasattr(model_settings, "agent_model") and model_settings.agent_model:
            agent_model = model_settings.agent_model
            logger.debug(f"Using agent model: {agent_model} instead of {self.model}")

        # Prepare kwargs for the API call
        kwargs = {
            "model": agent_model if agent_model else self.model,
            "messages": converted_messages,
            "tools": converted_tools or NOT_GIVEN,
            "temperature": self._non_null_or_not_given(model_settings.temperature),
            "top_p": self._non_null_or_not_given(model_settings.top_p),
            "frequency_penalty": self._non_null_or_not_given(model_settings.frequency_penalty),
            "presence_penalty": self._non_null_or_not_given(model_settings.presence_penalty),
            "max_tokens": self._non_null_or_not_given(model_settings.max_tokens),
            "tool_choice": tool_choice,
            "response_format": response_format,
            "parallel_tool_calls": parallel_tool_calls,
            "stream": stream,
            "stream_options": {"include_usage": True} if stream else NOT_GIVEN,
            "store": store,
            "extra_headers": _HEADERS,
        }

        # Determine provider based on model string
        model_str = str(kwargs["model"]).lower()

        # Gateway base: CSI_CUSTOM_ENDPOINT / ALIAS_API_URL if model qualifies; else OPENAI_API_BASE (see llm_api_base).
        _model_for_base = str(kwargs.get("model") or os.getenv("CAI_MODEL") or "")
        _alias_gateway_base = resolve_llm_openai_compatible_base(_model_for_base).rstrip("/")
        if model_str == "alias2-mini":
            kwargs["api_base"] = _alias_gateway_base
            kwargs["custom_llm_provider"] = "openai"
            kwargs["api_key"] = (get_config().alias_api_key or "sk-alias-1234567890").strip()
        elif "alias" in model_str and "alias1.5" not in model_str:  # NOTE: exclude alias1.5
            kwargs["api_base"] = _alias_gateway_base
            kwargs["custom_llm_provider"] = "openai"
            kwargs["api_key"] = (get_config().alias_api_key or "sk-alias-1234567890").strip()
        elif "/" in model_str:
            # Handle provider/model format
            provider = model_str.split("/")[0]

            # Apply provider-specific configurations
            if provider == "ollama_cloud":
                # Ollama Cloud configuration
                ollama_api_key = os.getenv("OLLAMA_API_KEY")
                ollama_api_base = os.getenv("OLLAMA_API_BASE", "https://ollama.com")
                
                if ollama_api_key:
                    kwargs["api_key"] = ollama_api_key
                if ollama_api_base:
                    kwargs["api_base"] = ollama_api_base
                    
                # Drop params not supported by Ollama
                litellm.drop_params = True
                kwargs.pop("parallel_tool_calls", None)
                kwargs.pop("store", None)
                if not converted_tools:
                    kwargs.pop("tool_choice", None)
            elif provider == "deepseek":
                litellm.drop_params = True
                kwargs.pop("parallel_tool_calls", None)
                kwargs.pop("store", None)  # DeepSeek doesn't support store parameter
                # Remove tool_choice if no tools are specified
                if not converted_tools:
                    kwargs.pop("tool_choice", None)

                # Add reasoning support for DeepSeek
                # DeepSeek supports reasoning_effort parameter
                if hasattr(model_settings, "reasoning_effort") and model_settings.reasoning_effort:
                    kwargs["reasoning_effort"] = model_settings.reasoning_effort
                else:
                    # Default to "high" reasoning effort if model supports it
                    kwargs["reasoning_effort"] = "high"
            elif provider == "claude" or "claude" in model_str:
                litellm.drop_params = True
                kwargs.pop("store", None)
                kwargs.pop(
                    "parallel_tool_calls", None
                )  # Claude doesn't support parallel tool calls
                # Remove tool_choice if no tools are specified
                if not converted_tools:
                    kwargs.pop("tool_choice", None)

                # Add extended reasoning support for Claude models
                # Supports Claude 3.7, Claude 4, and any model with "thinking" in the name
                has_reasoning_capability = (
                    "thinking" in model_str
                    or
                    # Claude 4 models support reasoning
                    "-4-" in model_str
                    or "sonnet-4" in model_str
                    or "haiku-4" in model_str
                    or "opus-4" in model_str
                    or "3.7" in model_str
                )

                if has_reasoning_capability:
                    # Clean the model name by removing "thinking" before sending to API
                    clean_model = kwargs["model"]
                    if isinstance(clean_model, str) and "thinking" in clean_model.lower():
                        # Remove "thinking" and clean up any extra spaces/separators
                        clean_model = re.sub(
                            r"[_-]?thinking[_-]?", "", clean_model, flags=re.IGNORECASE
                        )
                        clean_model = re.sub(
                            r"[-_]{2,}", "-", clean_model
                        )  # Clean up multiple separators
                        clean_model = clean_model.strip(
                            "-_"
                        )  # Clean up leading/trailing separators
                        kwargs["model"] = clean_model

                    # Check if message history is compatible with reasoning
                    messages = kwargs.get("messages", [])
                    is_compatible = _check_reasoning_compatibility(messages)

                    if is_compatible:
                        kwargs["reasoning_effort"] = (
                            "high"  # Use reasoning_effort instead of thinking
                        )
            elif provider == "gemini":
                kwargs.pop("parallel_tool_calls", None)
                # Add any specific gemini settings if needed
        else:
            # Handle models without provider prefix
            if "claude" in model_str or "anthropic" in model_str:
                litellm.drop_params = True
                # Remove parameters that Anthropic doesn't support
                kwargs.pop("store", None)
                kwargs.pop("parallel_tool_calls", None)
                # Remove tool_choice if no tools are specified
                if not converted_tools:
                    kwargs.pop("tool_choice", None)

                # Add extended reasoning support for Claude models
                # Supports Claude 3.7, Claude 4, and any model with "thinking" in the name
                has_reasoning_capability = "thinking" in model_str

                if has_reasoning_capability:
                    # Clean the model name by removing "thinking" before sending to API
                    clean_model = kwargs["model"]
                    if isinstance(clean_model, str) and "thinking" in clean_model.lower():
                        # Remove "thinking" and clean up any extra spaces/separators
                        clean_model = re.sub(
                            r"[_-]?thinking[_-]?", "", clean_model, flags=re.IGNORECASE
                        )
                        clean_model = re.sub(
                            r"[-_]{2,}", "-", clean_model
                        )  # Clean up multiple separators
                        clean_model = clean_model.strip(
                            "-_"
                        )  # Clean up leading/trailing separators
                        kwargs["model"] = clean_model

                    # Check if message history is compatible with reasoning
                    messages = kwargs.get("messages", [])
                    is_compatible = _check_reasoning_compatibility(messages)

                    if is_compatible:
                        kwargs["reasoning_effort"] = (
                            "high"  # Use reasoning_effort instead of thinking
                        )
            elif "gemini" in model_str:
                kwargs.pop("parallel_tool_calls", None)
            elif "qwen" in model_str or ":" in model_str:
                # Handle Ollama-served models with custom formats (e.g., alias1)
                # These typically need the Ollama provider
                litellm.drop_params = True
                kwargs.pop("parallel_tool_calls", None)
                kwargs.pop("store", None)  # Ollama doesn't support store parameter
                # These models may not support certain parameters
                if not converted_tools:
                    kwargs.pop("tool_choice", None)
                # Don't add custom_llm_provider here to avoid duplication with Ollama provider
                if self.is_ollama:
                    # Clean kwargs for ollama to avoid parameter conflicts
                    for param in ["custom_llm_provider"]:
                        kwargs.pop(param, None)
            elif any(x in model_str for x in ["o1", "o3", "o4"]):
                # Handle OpenAI reasoning models (o1, o3, o4)
                kwargs.pop("parallel_tool_calls", None)
                # Add reasoning effort if provided
                if hasattr(model_settings, "reasoning_effort"):
                    kwargs["reasoning_effort"] = model_settings.reasoning_effort

        # Filter out NotGiven values to avoid JSON serialization issues
        filtered_kwargs = {}
        for key, value in kwargs.items():
            if value is not NOT_GIVEN:
                filtered_kwargs[key] = value
        kwargs = filtered_kwargs

        # Abliteration steering: CAI_UNRESTRICTED=true → steering ON + thinking OFF.
        # `steering_enabled` is an alias-backend-only field. Injecting it into
        # vanilla Anthropic/OpenAI/OpenRouter requests causes upstream 400s
        # ("extra_body: Extra inputs are not permitted") which LiteLLM
        # misclassifies as InternalServerError → silent retry-loop hang.
        # Gate steering payload on Alias-backed models only. CAI_UNRESTRICTED must not
        # inject extra_body for Azure/OpenAI/Anthropic — upstream rejects it and LiteLLM
        # may retry (see comment above).
        _unrestricted = os.getenv("CAI_UNRESTRICTED", "false").strip().lower() in ("true", "1", "yes")
        if self._is_alias_model:
            kwargs.setdefault("extra_body", {})
            kwargs["extra_body"]["steering_enabled"] = _unrestricted
            if _unrestricted:
                kwargs["extra_body"]["chat_template_kwargs"] = {"enable_thinking": False}

        global _UNRESTRICTED_EXTRA_BODY_LOGGED
        if _unrestricted and not _UNRESTRICTED_EXTRA_BODY_LOGGED:
            if os.getenv("CAI_UNRESTRICTED_LOG", "").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            ):
                _UNRESTRICTED_EXTRA_BODY_LOGGED = True
                print(
                    "[CAI] Unrestricted: client will send extra_body="
                    f"{kwargs.get('extra_body')!r} (steering_enabled / chat_template_kwargs). "
                    "If the model behaves like the normal route, LiteLLM or the backend may be ignoring these fields.",
                    file=sys.stderr,
                )

        # Add retry logic for rate limits
        max_retries = 3
        retry_count = 0

        # Use httpx directly when a custom base is configured and messages carry cache_control
        # (LiteLLM strips cache_control from messages when using the OpenAI client).
        _model_for_openai_base = str(kwargs.get("model") or os.getenv("CAI_MODEL") or "")
        openai_api_base = (
            kwargs.get("api_base") or resolve_llm_openai_compatible_base(_model_for_openai_base)
        ).rstrip("/")

        def has_cache_control(messages):
            """Check if any message has cache_control (at message level or in content blocks)"""
            for msg in messages:
                # Check message-level cache_control
                if msg.get("cache_control"):
                    return True
                # Check content blocks for cache_control
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("cache_control"):
                            return True
            return False

        use_direct_request = explicit_custom_llm_api_base_configured(
            _model_for_openai_base
        ) and has_cache_control(kwargs.get("messages", []))

        # Debug: Show whether direct HTTP path is being used
        if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
            has_cc = has_cache_control(kwargs.get("messages", []))
            print(
                f"[CACHE-DEBUG] api_base={openai_api_base}, has_cache_control={has_cc}, "
                f"use_direct={use_direct_request}, stream={stream}"
            )

        if use_direct_request:
            logger.debug(f"[CACHE] Using direct HTTP path to preserve cache_control (stream={stream})")
            try:
                import httpx

                # Build the request body preserving all fields including cache_control
                request_body = {
                    "model": kwargs.get("model", self.model),
                    "messages": kwargs.get("messages", []),
                    "max_tokens": kwargs.get("max_tokens"),
                    "temperature": kwargs.get("temperature"),
                    "top_p": kwargs.get("top_p"),
                    "stream": stream,  # Match the requested stream mode
                }

                # Add tools if present
                if kwargs.get("tools") and kwargs["tools"] is not NOT_GIVEN:
                    request_body["tools"] = kwargs["tools"]

                # Add tool_choice if present
                if kwargs.get("tool_choice") and kwargs["tool_choice"] is not NOT_GIVEN:
                    request_body["tool_choice"] = kwargs["tool_choice"]

                # Propagate extra_body fields (steering_enabled, chat_template_kwargs, etc.)
                for eb_key, eb_val in kwargs.get("extra_body", {}).items():
                    request_body[eb_key] = eb_val

                # Remove None values
                request_body = {k: v for k, v in request_body.items() if v is not None}

                api_url = f"{openai_api_base.rstrip('/')}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {get_config().openai_api_key or 'sk-placeholder'}",
                }

                if stream:
                    # Streaming mode: Return an async generator for SSE chunks
                    # We need to create an httpx client that stays open during streaming
                    client = httpx.AsyncClient(timeout=120.0)

                    async def stream_response():
                        """Async generator that yields SSE chunks from the proxy"""
                        try:
                            async with client.stream("POST", api_url, json=request_body, headers=headers) as resp:
                                resp.raise_for_status()
                                buffer = ""
                                async for chunk in resp.aiter_text():
                                    buffer += chunk
                                    while "\n" in buffer:
                                        line, buffer = buffer.split("\n", 1)
                                        line = line.strip()
                                        if line.startswith("data: "):
                                            data_str = line[6:]
                                            if data_str == "[DONE]":
                                                return
                                            try:
                                                data = json.loads(data_str)
                                                # Yield the parsed chunk as a ModelResponse-like object
                                                from litellm import ModelResponse
                                                from litellm.types.utils import StreamingChoices, Delta

                                                delta_data = data.get("choices", [{}])[0].get("delta", {})
                                                delta = Delta(
                                                    role=delta_data.get("role"),
                                                    content=delta_data.get("content"),
                                                    tool_calls=delta_data.get("tool_calls")
                                                )

                                                choices = [StreamingChoices(
                                                    index=0,
                                                    delta=delta,
                                                    finish_reason=data.get("choices", [{}])[0].get("finish_reason")
                                                )]

                                                # Extract usage if present (usually in final chunk)
                                                usage_data = data.get("usage")
                                                usage = None
                                                if usage_data:
                                                    # Extract cache metrics - support both Anthropic and OpenAI formats
                                                    cache_read = usage_data.get("cache_read_input_tokens")
                                                    cache_creation = usage_data.get("cache_creation_input_tokens")
                                                    # Fallback to OpenAI format (prompt_tokens_details.cached_tokens)
                                                    if not cache_read:
                                                        prompt_details = usage_data.get("prompt_tokens_details", {})
                                                        if prompt_details:
                                                            cache_read = prompt_details.get("cached_tokens")

                                                    # Debug: Log cache metrics from streaming
                                                    if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
                                                        print(f"[CACHE-DEBUG] Direct HTTP streaming usage: CR={cache_read}, CW={cache_creation}")

                                                    from litellm.types.utils import Usage
                                                    usage = Usage(
                                                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                                                        completion_tokens=usage_data.get("completion_tokens", 0),
                                                        total_tokens=usage_data.get("total_tokens", 0),
                                                        cache_creation_input_tokens=cache_creation,
                                                        cache_read_input_tokens=cache_read,
                                                    )

                                                chunk_response = ModelResponse(
                                                    id=data.get("id", "chatcmpl-proxy"),
                                                    created=data.get("created", int(time.time())),
                                                    model=data.get("model", str(self.model)),
                                                    choices=choices,
                                                    usage=usage,
                                                    object="chat.completion.chunk"
                                                )
                                                yield chunk_response
                                            except json.JSONDecodeError:
                                                continue
                        finally:
                            await client.aclose()

                    # Return Response object and stream generator (similar to LiteLLM streaming)
                    response_obj = Response(
                        id=FAKE_RESPONSES_ID,
                        created_at=time.time(),
                        model=self.model,
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
                    return response_obj, stream_response()

                else:
                    # Non-streaming mode
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(api_url, json=request_body, headers=headers)
                        response.raise_for_status()
                        data = response.json()

                        usage_data = data.get("usage", {})

                        # Extract cache metrics - support both Anthropic and OpenAI formats
                        cache_read = usage_data.get("cache_read_input_tokens")
                        cache_creation = usage_data.get("cache_creation_input_tokens")
                        # Fallback to OpenAI format (prompt_tokens_details.cached_tokens)
                        if not cache_read:
                            prompt_details = usage_data.get("prompt_tokens_details", {})
                            if prompt_details:
                                cache_read = prompt_details.get("cached_tokens")

                        # Debug: Log what the proxy returned
                        if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
                            print(f"[CACHE-DEBUG] Direct HTTP non-streaming usage from proxy: CR={cache_read}, CW={cache_creation}, full_usage={usage_data}")

                        # Use litellm's ModelResponse which handles the structure automatically
                        from litellm import ModelResponse
                        result = ModelResponse(**data)

                        # Ensure cache metrics are preserved in usage
                        if result.usage:
                            result.usage.cache_creation_input_tokens = cache_creation
                            result.usage.cache_read_input_tokens = cache_read

                        return result

            except Exception as e:
                # Fall back to LiteLLM if direct request fails
                if os.getenv("CAI_SHOW_CACHE", "").lower() in ("true", "1", "yes"):
                    print(f"[CACHE-DEBUG] Direct HTTP path FAILED, falling back to LiteLLM: {e}")
                logger.debug(f"Direct request failed, falling back to LiteLLM: {e}")

        # Check if this is Ollama Cloud (ollama_cloud/ prefix)
        # Ollama Cloud is OpenAI-compatible, so we bypass LiteLLM to avoid parsing issues
        is_ollama_cloud = "ollama_cloud/" in model_str
        
        if is_ollama_cloud:
            # Use AsyncOpenAI client directly for Ollama Cloud
            # Ollama Cloud is fully OpenAI-compatible at /v1/chat/completions
            try:
                # Configure the client with Ollama Cloud settings
                ollama_api_key = os.getenv("OLLAMA_API_KEY") or os.getenv("OPENAI_API_KEY")
                ollama_base_url = os.getenv("OLLAMA_API_BASE", "https://ollama.com")
                
                # Ensure the URL has /v1 for OpenAI compatibility
                if not ollama_base_url.endswith("/v1"):
                    ollama_base_url = f"{ollama_base_url}/v1"
                
                # Create a temporary client configured for Ollama Cloud
                ollama_client = AsyncOpenAI(
                    api_key=ollama_api_key,
                    base_url=ollama_base_url
                )
                
                # Remove the ollama_cloud/ prefix from the model name
                clean_model = kwargs["model"].replace("ollama_cloud/", "")
                kwargs["model"] = clean_model
                
                # Remove LiteLLM-specific parameters
                kwargs.pop("extra_headers", None)
                kwargs.pop("api_key", None)
                kwargs.pop("api_base", None)
                kwargs.pop("custom_llm_provider", None)
                
                # Call Ollama Cloud using OpenAI-compatible API
                if stream:
                    return await ollama_client.chat.completions.create(**kwargs)
                else:
                    return await ollama_client.chat.completions.create(**kwargs)
                    
            except Exception as e:
                # If Ollama Cloud fails, raise with helpful message
                raise Exception(
                    f"Error connecting to Ollama Cloud: {str(e)}\n"
                    f"Verify OLLAMA_API_KEY and OLLAMA_API_BASE are configured correctly."
                ) from e
        
        while retry_count < max_retries:
            try:
                cfg = get_config()
                if (self._is_alias_model or cfg.force_httpx) and not self.is_ollama:
                    # [N] Direct httpx — bypass LiteLLM for alias/forced models
                    return await self._direct_httpx_completion(
                        kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                    )
                elif self.is_ollama:
                    return await self._fetch_response_litellm_ollama(
                        kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                    )
                else:
                    return await self._fetch_response_litellm_openai(
                        kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                    )
            except (litellm.exceptions.RateLimitError, LLMRateLimited) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.error(f"Rate limit exceeded after {max_retries} retries")
                    if verbose_http_retries():
                        print(f"\n❌ Rate limit exceeded after {max_retries} retries")
                    raise

                self.logger.warning(
                    f"Rate limit retry {retry_count}/{max_retries}: {str(e)[:200]}"
                )
                if verbose_http_retries():
                    print(f"\n⏳ Rate limit reached - Too many requests (attempt {retry_count}/{max_retries})")
                # Extract retry delay: check LLMRateLimited.retry_after, VertexAI
                # JSON details, common header patterns, or fall back to exp backoff
                retry_delay: float | None = None

                # Check if LLMRateLimited carries an explicit retry_after
                if isinstance(e, LLMRateLimited) and getattr(e, "retry_after", None):
                    retry_delay = float(e.retry_after)
                else:
                    try:
                        # VertexAI format: parse RetryInfo from JSON details
                        error_msg = str(e.args[0]) if e.args else str(e)
                        json_str = error_msg.split("VertexAIException - ")[-1]
                        error_details = json.loads(json_str)
                        retry_info = next(
                            (d for d in error_details.get("error", {}).get("details", [])
                             if d.get("@type") == "type.googleapis.com/google.rpc.RetryInfo"),
                            None,
                        )
                        if retry_info and "retryDelay" in retry_info:
                            retry_delay = float(retry_info["retryDelay"].rstrip("s"))
                    except Exception:
                        # Try common retry-after patterns in error message
                        error_str = str(e)
                        for pattern in [
                            r'retry[_-]?after[:\s]+(\d+)',
                            r'wait\s+(\d+)\s+seconds?',
                            r'retry\s+in\s+(\d+)\s+seconds?',
                        ]:
                            m = re.search(pattern, error_str, re.IGNORECASE)
                            if m:
                                retry_delay = float(m.group(1))
                                break

                # Exponential backoff with jitter if no explicit delay
                if retry_delay is None:
                    retry_delay = self._backoff_delay(retry_count - 1)

                if verbose_http_retries():
                    print(f"💤 Waiting {retry_delay:.0f}s before retry... (Rate limit protection)")
                await sleep_with_retry_backoff_hint(retry_delay)
                continue

            except litellm.exceptions.ServiceUnavailableError as e:
                # Handle 503 "queue is full" errors from the LiteLLM proxy server
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.error(f"Service unavailable after {max_retries} retries")
                    if verbose_http_retries():
                        print(f"\n❌ Service unavailable after {max_retries} retries")
                    raise

                error_msg = str(e)
                self.logger.warning(
                    f"Service unavailable retry {retry_count}/{max_retries}: {error_msg[:200]}"
                )
                if verbose_http_retries():
                    if "queue is full" in error_msg.lower():
                        print(f"\n⏳ Server queue is full (attempt {retry_count}/{max_retries})")
                    else:
                        print(f"\n⏳ Service unavailable: {error_msg[:100]} (attempt {retry_count}/{max_retries})")

                # Exponential backoff with jitter for 503 errors
                retry_delay = self._backoff_delay(retry_count - 1, base=10.0, cap=120.0)

                if verbose_http_retries():
                    print(f"💤 Waiting {retry_delay}s before retry... (Server overload protection)")
                await sleep_with_retry_backoff_hint(retry_delay)
                continue  # Retry the request

            except litellm.exceptions.BadGatewayError as e:
                # Handle 502 Bad Gateway errors (e.g. nginx proxy to litellm)
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.error(
                        f"Bad Gateway (502) after {max_retries} retries [{self.model}]"
                    )
                    if verbose_http_retries():
                        print(f"\n❌ Bad Gateway (502) after {max_retries} retries [{self.model}]")
                    raise

                error_msg = str(e)[:150]
                self.logger.warning(
                    f"Bad Gateway retry {retry_count}/{max_retries}: {error_msg}"
                )
                if verbose_http_retries():
                    print(f"\n⏳ Bad Gateway (502): {error_msg} (attempt {retry_count}/{max_retries})")

                import random
                base_delay = 10
                retry_delay = min(120, base_delay * (2 ** (retry_count - 1))) + random.randint(0, 5)

                if verbose_http_retries():
                    print(f"💤 Waiting {retry_delay}s before retry... (Backend unavailable)")
                await sleep_with_retry_backoff_hint(retry_delay)
                continue

            except litellm.exceptions.APIConnectionError as e:
                self.logger.warning(f"API connection error [{self.model}]: {e}")
                if verbose_http_retries():
                    print(f"\n🌐 Connection Error [{self.model}]: {str(e)}")
                    print("💡 Check your internet connection or API endpoint")
                raise

            except (litellm.exceptions.Timeout, LLMTimeout) as e:
                self.logger.warning(f"Request timed out [{self.model}]: {e}")
                if verbose_http_retries():
                    print(f"\n⏱️  Request timed out [{self.model}]: {str(e)}")
                    print("💡 The model took too long to respond. Try:")
                    print("  • Using a faster model")
                    print("  • Reducing the prompt size")
                    print("  • Checking your internet connection")
                raise

            except litellm.exceptions.BadRequestError as e:
                error_msg = str(e)

                # Handle Claude reasoning/thinking compatibility errors
                if (
                    "Expected `thinking` or `redacted_thinking`, but found `text`" in error_msg
                    or "When `thinking` is enabled, a final `assistant` message must start with a thinking block"
                    in error_msg
                ):
                    # Retry without reasoning_effort
                    retry_kwargs = kwargs.copy()
                    retry_kwargs.pop("reasoning_effort", None)

                    try:
                        if stream:
                            response = Response(
                                id=FAKE_RESPONSES_ID,
                                created_at=time.time(),
                                model=self.model,
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
                            stream_obj = await litellm.acompletion(**retry_kwargs)
                            return response, stream_obj
                        else:
                            ret = await litellm.acompletion(**retry_kwargs)
                            return ret
                    except Exception:
                        # If retry also fails, raise the original error
                        raise e

                # print(color("BadRequestError encountered: " + str(e), fg="yellow"))
                if "LLM Provider NOT provided" in str(e):
                    model_str = str(self.model).lower()
                    provider = None
                    is_qwen = "qwen" in model_str or ":" in model_str

                    # Special handling for Qwen models
                    if is_qwen:
                        try:
                            # Use the specialized Qwen approach first
                            return await self._fetch_response_litellm_ollama(
                                kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                            )
                        except Exception as qwen_e:
                            print(qwen_e)
                            # If that fails, try our direct OpenAI approach
                            qwen_params = kwargs.copy()
                            qwen_params["api_base"] = get_ollama_api_base()
                            qwen_params["custom_llm_provider"] = "openai"  # Use openai provider

                            # Make sure tools are passed
                            if "tools" in kwargs and kwargs["tools"]:
                                qwen_params["tools"] = kwargs["tools"]
                            if "tool_choice" in kwargs and kwargs["tool_choice"] is not NOT_GIVEN:
                                qwen_params["tool_choice"] = kwargs["tool_choice"]

                            try:
                                if stream:
                                    # Streaming case
                                    response = Response(
                                        id=FAKE_RESPONSES_ID,
                                        created_at=time.time(),
                                        model=self.model,
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
                                    stream_obj = await litellm.acompletion(**qwen_params)
                                    return response, stream_obj
                                else:
                                    # Non-streaming case
                                    ret = await litellm.acompletion(**qwen_params)
                                    return ret
                            except Exception as direct_e:
                                # All approaches failed, log and raise the original error
                                print(
                                    f"All Qwen approaches failed. Original error: {str(e)}, Direct error: {str(direct_e)}"
                                )
                                raise e

                    # Try to detect provider from model string
                    if "/" in model_str:
                        provider = model_str.split("/")[0]

                    if provider:
                        # Add provider-specific settings based on detected provider
                        provider_kwargs = kwargs.copy()
                        if provider == "deepseek":
                            provider_kwargs["custom_llm_provider"] = "deepseek"
                            provider_kwargs.pop(
                                "store", None
                            )  # DeepSeek doesn't support store parameter
                            provider_kwargs.pop(
                                "parallel_tool_calls", None
                            )  # DeepSeek doesn't support parallel tool calls

                            # Add reasoning support for DeepSeek
                            if (
                                hasattr(model_settings, "reasoning_effort")
                                and model_settings.reasoning_effort
                            ):
                                provider_kwargs["reasoning_effort"] = model_settings.reasoning_effort
                            else:
                                # Default to "high" reasoning effort
                                provider_kwargs["reasoning_effort"] = "high"
                        elif provider == "claude" or "claude" in model_str:
                            provider_kwargs["custom_llm_provider"] = "anthropic"
                            provider_kwargs.pop("store", None)  # Claude doesn't support store parameter
                            provider_kwargs.pop(
                                "parallel_tool_calls", None
                            )  # Claude doesn't support parallel tool calls

                            # Add extended reasoning support for Claude models
                            if "thinking" in model_str:
                                # Clean the model name by removing "thinking" before sending to API
                                clean_model = provider_kwargs["model"]
                                if isinstance(clean_model, str) and "thinking" in clean_model.lower():
                                    # Remove "thinking" and clean up any extra spaces/separators
                                    clean_model = re.sub(
                                        r"[_-]?thinking[_-]?", "", clean_model, flags=re.IGNORECASE
                                    )
                                    clean_model = re.sub(
                                        r"[-_]{2,}", "-", clean_model
                                    )  # Clean up multiple separators
                                    clean_model = clean_model.strip(
                                        "-_"
                                    )  # Clean up leading/trailing separators
                                    provider_kwargs["model"] = clean_model

                                # Check if message history is compatible with reasoning
                                messages = provider_kwargs.get("messages", [])
                                is_compatible = _check_reasoning_compatibility(messages)

                                if is_compatible:
                                    provider_kwargs["reasoning_effort"] = (
                                        "high"  # Use reasoning_effort instead of thinking
                                    )
                        elif provider == "gemini":
                            provider_kwargs["custom_llm_provider"] = "gemini"
                            provider_kwargs.pop("store", None)  # Gemini doesn't support store parameter
                            provider_kwargs.pop(
                                "parallel_tool_calls", None
                            )  # Gemini doesn't support parallel tool calls
                        else:
                            # For unknown providers, try ollama as fallback
                            return await self._fetch_response_litellm_ollama(
                                kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                            )
                
                # Check for message sequence errors
                if (
                    "An assistant message with 'tool_calls'" in str(e)
                    or "`tool_use` blocks must be followed by a user message with `tool_result`"
                    in str(e)  # noqa: E501 # pylint: disable=C0301
                    or "`tool_use` ids were found without `tool_result` blocks immediately after"
                    in str(e)  # noqa: E501 # pylint: disable=C0301
                    or "An assistant message with 'tool_calls' must be followed by tool messages"
                    in str(e)
                    or "messages with role 'tool' must be a response to a preceeding message with 'tool_calls'"
                    in str(e)
                ):
                    print("⚠️  Message sequence error - Tool calls and results are out of order")

                    # Use the pretty message history printer instead of the simple loop
                    try:
                        from cai.util import print_message_history

                        print("\n📋 Current message sequence:")
                        print_message_history(kwargs["messages"], title="Message History")
                    except ImportError:
                        # Fall back to simple printing if the function isn't available
                        print("\n📋 Current message sequence:")
                        for i, msg in enumerate(kwargs["messages"]):
                            role = msg.get("role", "unknown")
                            content_type = (
                                "text"
                                if isinstance(msg.get("content"), str)
                                else "list"
                                if isinstance(msg.get("content"), list)
                                else "None"
                                if msg.get("content") is None
                                else type(msg.get("content")).__name__
                            )
                            tool_calls = "with tool_calls" if msg.get("tool_calls") else ""
                            tool_call_id = (
                                f", tool_call_id: {msg.get('tool_call_id')}"
                                if msg.get("tool_call_id")
                                else ""
                            )

                            print(
                                f"  [{i}] {role}{tool_call_id} (content: {content_type}) {tool_calls}"
                            )

                    # NOTE: EDGE CASE: Report Agent CTRL C error
                    #
                    # This fix CTRL-C error when message list is incomplete
                    # When a tool is not finished but the LLM generates a tool call
                    try:
                        from cai.util import fix_message_list

                        print("🔧 Auto-fixing message sequence...")
                        fixed_messages = fix_message_list(kwargs["messages"])

                        # Show the fixed messages if they're different
                        if fixed_messages != kwargs["messages"]:
                            try:
                                from cai.util import print_message_history

                                print_message_history(fixed_messages, title="Fixed Message Sequence")
                            except ImportError:
                                print("✅ Message sequence fixed successfully")

                        kwargs["messages"] = fixed_messages
                    except Exception:
                        pass

                    return await self._fetch_response_litellm_openai(
                        kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                    )

                # this captures an error related to the fact
                # that the messages list contains an empty
                # content position
                if "expected a string, got null" in str(e):
                    print("⚠️  Empty content detected - Filling with placeholder")
                    # Fix for null content in messages
                    kwargs["messages"] = [
                        msg if msg.get("content") is not None else {**msg, "content": ""}
                        for msg in kwargs["messages"]
                    ]
                    return await self._fetch_response_litellm_openai(
                        kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                    )

                # Handle Anthropic error for empty text content blocks
                if "text content blocks must be non-empty" in str(
                    e
                ) or "cache_control cannot be set for empty text blocks" in str(e):  # noqa
                    # Print the error message only once
                    print("⚠️  Empty text blocks detected - Adding placeholder content") if not self.empty_content_error_shown else None
                    self.empty_content_error_shown = True

                    # Fix for empty content in messages for Anthropic models
                    kwargs["messages"] = [
                        msg
                        if msg.get("content") not in [None, ""]
                        else {**msg, "content": "Empty content block"}
                        for msg in kwargs["messages"]
                    ]
                    return await self._fetch_response_litellm_openai(
                        kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                    )
                # Check for Python formatting errors - NOT context errors
                if "Cannot specify ',' with 's'" in str(e):
                    print("\n❌ Python formatting error - Not a context error")
                    print("⚠️  There's a bug in the code trying to format strings as numbers")
                    print(f"Error: {str(e)}")
                    raise
                # Check for context length errors in BadRequestError
                if (
                    "context_length_exceeded" in str(e) 
                    or "prompt is too long" in str(e).lower()
                    or "maximum context length" in str(e).lower()
                    or "max_tokens" in str(e) and "exceeded" in str(e).lower()
                    or "too many tokens" in str(e).lower()
                    or "token limit" in str(e).lower()
                ):
                    print("\n📦 Context window exceeded - Message history too long")
                    
                    # Try to extract token info from different error formats
                    # NOTE: re is imported at module level — do NOT re-import here
                    # as it causes UnboundLocalError for earlier uses in this scope
                    error_str = str(e)
                    
                    # Pattern 1: "X tokens > Y maximum" (Anthropic)
                    match1 = re.search(r'(\d+)\s*tokens?\s*>\s*(\d+)\s*maximum', error_str)
                    # Pattern 2: "requested X tokens...maximum context length is Y" (OpenAI)
                    match2 = re.search(r'requested\s+(\d+)\s+tokens.*maximum.*?(\d+)', error_str)
                    # Pattern 3: "This model's maximum context length is X tokens, however you requested Y"
                    match3 = re.search(r'maximum context length is\s+(\d+).*requested\s+(\d+)', error_str)
                    
                    if match1:
                        used_tokens = int(match1.group(1))
                        max_tokens = int(match1.group(2))
                        print(f"🎯 Actual: {used_tokens:,} / {max_tokens:,} tokens")
                    elif match2:
                        used_tokens = int(match2.group(1))
                        max_tokens = int(match2.group(2))
                        print(f"🎯 Requested: {used_tokens:,} tokens (max: {max_tokens:,})")
                    elif match3:
                        max_tokens = int(match3.group(1))
                        used_tokens = int(match3.group(2))
                        print(f"🎯 Requested: {used_tokens:,} tokens (max: {max_tokens:,})")
                    elif 'estimated_input_tokens' in locals():
                        print(f"📊 Estimated tokens: ~{estimated_input_tokens:,}")
                        # Get model's max tokens
                        model_max = self._get_model_max_tokens(str(self.model))
                        print(f"🎯 Model limit: {model_max:,} tokens")

                    # Best-effort recovery: pin the provider limit (when available) and compact+retry once.
                    # Keeps a hard 80% safety cap when estimates are high; avoids stuck jobs when
                    # pricing heuristics overestimate the true context window (e.g. alias models).
                    try:
                        inferred_max = locals().get("max_tokens", None)
                        inferred_used = locals().get("used_tokens", None)
                        if isinstance(inferred_max, int) and inferred_max > 0:
                            os.environ["CAI_MODEL_MAX_INPUT_TOKENS"] = str(inferred_max)
                        if not getattr(self, "_context_compact_retry", False):
                            self._context_compact_retry = True
                            # Force compaction attempt (estimated_tokens must exceed threshold).
                            force_est = int(inferred_used or inferred_max or estimated_input_tokens or 0)
                            force_est = max(force_est, 1)
                            _in = input
                            _sys = system_instructions
                            _in, _sys, compacted = await self._auto_compact_if_needed(
                                force_est,
                                _in,
                                _sys,
                            )
                            if compacted:
                                rebuilt = self._messages_for_token_count_after_history_mutation(
                                    system_instructions=_sys,
                                    input=_in,
                                )
                                kwargs["messages"] = rebuilt
                                return await self._fetch_response_litellm_openai(
                                    kwargs, model_settings, tool_choice, stream, parallel_tool_calls
                                )
                    except Exception:
                        pass
                    
                    print("\n💡 Quick fixes:")
                    print("  • /flush - Clear conversation history")
                    print("  • /compact - Manually compact context")
                    print("  • /model <larger-model> - Switch to model with more context")
                    
                    raise
            else:
                raise e

    # ------------------------------------------------------------------
    # Direct httpx completion — bypasses LiteLLM for alias models [N]
    # ------------------------------------------------------------------
    async def _direct_httpx_completion(
        self,
        kwargs: dict,
        model_settings: ModelSettings,
        tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven,
        stream: bool,
        parallel_tool_calls: bool,
    ):
        """Delegate to chatcompletions.httpx_client.direct_httpx_completion."""
        return await _direct_httpx_completion_impl(
            kwargs=kwargs,
            model_settings=model_settings,
            tool_choice=tool_choice,
            stream=stream,
            parallel_tool_calls=parallel_tool_calls,
            model_name=str(self.model),
            user_agent=_USER_AGENT,
        )

    async def _fetch_response_litellm_openai(
        self,
        kwargs: dict,
        model_settings: ModelSettings,
        tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven,
        stream: bool,
        parallel_tool_calls: bool,
    ) -> ChatCompletion | tuple[Response, AsyncStream[ChatCompletionChunk]]:
        """Delegate to chatcompletions.litellm_adapter.fetch_response_litellm_openai."""
        return await _fetch_litellm_openai_impl(
            kwargs=kwargs,
            model_name=str(self.model),
            model_settings=model_settings,
            tool_choice=tool_choice,
            stream=stream,
            parallel_tool_calls=parallel_tool_calls,
        )

    async def _fetch_response_litellm_ollama(
        self,
        kwargs: dict,
        model_settings: ModelSettings,
        tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven,
        stream: bool,
        parallel_tool_calls: bool,
    ) -> ChatCompletion | tuple[Response, AsyncStream[ChatCompletionChunk]]:
        """Delegate to chatcompletions.litellm_adapter.fetch_response_litellm_ollama."""
        return await _fetch_litellm_ollama_impl(
            kwargs=kwargs,
            model_name=str(self.model),
            model_settings=model_settings,
            tool_choice=tool_choice,
            stream=stream,
            parallel_tool_calls=parallel_tool_calls,
            )

    def _get_model_max_tokens(self, model_name: str) -> int:
        """Delegate to chatcompletions.auto_compactor.get_model_max_tokens."""
        return _get_model_max_tokens_impl(model_name)

    async def _auto_compact_if_needed(self, estimated_tokens: int, input: str | list[TResponseInputItem], system_instructions: str | None) -> tuple[str | list[TResponseInputItem], str | None, bool]:
        """Delegate to chatcompletions.auto_compactor.auto_compact_if_needed."""
        global _compaction_in_progress

        def _set_flag(val: bool):
            global _compaction_in_progress
            _compaction_in_progress = val

        return await _auto_compact_if_needed_impl(
            estimated_tokens=estimated_tokens,
            input=input,
            system_instructions=system_instructions,
            model_name=str(self.model),
            agent_name=self.agent_name,
            message_history=self.message_history,
            converter=self._converter,
            compaction_in_progress_flag=_compaction_in_progress,
            set_compaction_flag=_set_flag,
        )

    def _intermediate_logs(self):
        """Intermediate logging if conditions are met."""
        if (
            self.logger
            and self.interaction_counter > 0
            and self.interaction_counter % self.INTERMEDIATE_LOG_INTERVAL == 0
        ):
            process_intermediate_logs(self.logger.filename, self.logger.session_id)

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = resolve_llm_openai_compatible_api_key(str(self.model))
            if not api_key:
                _c = get_config()
                raise UserError(
                    "Missing API key for selected model. "
                    "For alias-family models (alias*/cai*/csi*), set ALIAS_API_KEY. "
                    "For OpenAI models, set OPENAI_API_KEY. "
                    f"(CAI_MODEL={_c.model!r})"
                )
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    # Helper function to detect and format function calls from various models
    def _detect_and_format_function_calls(self, delta):
        """
        Helper to detect function calls in different formats and normalize them.
        Handles Qwen specifics where function calls may be formatted differently.

        Returns: List of normalized tool calls or None
        """
        # Standard OpenAI-style tool_calls format
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            return delta.tool_calls
        elif isinstance(delta, dict) and "tool_calls" in delta and delta["tool_calls"]:
            return delta["tool_calls"]

        # Qwen/Ollama function_call format
        if isinstance(delta, dict) and "function_call" in delta:
            function_call = delta["function_call"]
            if function_call is None:
                return None
            return [
                {
                    "index": 0,
                    "id": f"call_{time.time_ns()}",  # Generate a unique ID
                    "type": "function",
                    "function": {
                        "name": function_call.get("name", ""),
                        "arguments": function_call.get("arguments", ""),
                    },
                }
            ]

        if isinstance(delta, dict) and "content" in delta:
            content = delta["content"]
            # Try to detect if the content is a JSON string with function call format
            try:
                if isinstance(content, str) and "{" in content and "}" in content:
                    # Try to extract JSON from the content (it might be embedded in text)
                    json_start = content.find("{")
                    json_end = content.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        parsed = _safe_json_loads(json_str, "delta content function call")
                        if parsed and "name" in parsed and "arguments" in parsed:
                            # This looks like a function call in JSON format
                            return [
                                {
                                    "index": 0,
                                    "id": f"call_{time.time_ns()}",  # Generate a unique ID
                                    "type": "function",
                                    "function": {
                                        "name": parsed["name"],
                                        "arguments": json.dumps(parsed["arguments"])
                                        if isinstance(parsed["arguments"], dict)
                                        else parsed["arguments"],
                                    },
                                }
                            ]
            except Exception:
                # If JSON parsing fails, just continue with normal processing
                pass

        # Anthropic-style tool_use format
        if hasattr(delta, "tool_use") and delta.tool_use:
            tool_use = delta.tool_use
            return [
                {
                    "index": 0,
                    "id": tool_use.get("id", f"tool_{time.time_ns()}"),
                    "type": "function",
                    "function": {
                        "name": tool_use.get("name", ""),
                        "arguments": tool_use.get("input", "{}"),
                    },
                }
            ]
        elif isinstance(delta, dict) and "tool_use" in delta and delta["tool_use"]:
            tool_use = delta["tool_use"]
            return [
                {
                    "index": 0,
                    "id": tool_use.get("id", f"tool_{time.time_ns()}"),
                    "type": "function",
                    "function": {
                        "name": tool_use.get("name", ""),
                        "arguments": tool_use.get("input", "{}"),
                    },
                }
            ]

        return None


# _Converter is now defined in chatcompletions/message_builder.py
# Keep a local alias for backward compatibility within this file.
_Converter = _NewConverter


# _Converter and ToolConverter are now defined in chatcompletions/message_builder.py
# Keep local aliases for full backward compatibility.
_Converter = _NewConverter
# ToolConverter is already imported from .chatcompletions.message_builder above.
