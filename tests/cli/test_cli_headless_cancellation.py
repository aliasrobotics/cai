import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import litellm

from cai import cli_headless
from cai import parallel_worker
from cai.errors import LLMProviderUnavailable


def test_non_streamed_cancelled_error_uses_interrupt_flow(monkeypatch):
    async def cancelled_run(*_args, **_kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(cli_headless.Runner, "run", cancelled_run)

    with pytest.raises(KeyboardInterrupt):
        cli_headless._run_non_streamed(
            SimpleNamespace(model=SimpleNamespace(message_history=[])),
            "input",
            Mock(),
            False,
            None,
        )


def test_streamed_cancelled_error_uses_interrupt_flow(monkeypatch):
    def cancelled_asyncio_run(*_args, **_kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(cli_headless.asyncio, "run", cancelled_asyncio_run)

    with pytest.raises(KeyboardInterrupt):
        cli_headless._run_streamed(
            SimpleNamespace(model=SimpleNamespace(message_history=[])),
            "input",
            Mock(),
            False,
            None,
        )


def test_streamed_provider_disconnect_raises_typed_provider_error(monkeypatch):
    class DummyResult:
        async def stream_events(self):
            raise litellm.exceptions.InternalServerError(
                message="DeepseekException - Server disconnected",
                llm_provider="deepseek",
                model="deepseek/deepseek-v4-pro",
            )
            yield  # pragma: no cover

        def _cleanup_tasks(self):
            pass

    monkeypatch.setattr(
        cli_headless.Runner, "run_streamed", lambda *_args, **_kwargs: DummyResult()
    )

    with pytest.raises(LLMProviderUnavailable, match="Server disconnected"):
        cli_headless._run_streamed(
            SimpleNamespace(model=SimpleNamespace(message_history=[])),
            "input",
            Mock(),
            False,
            None,
        )


def test_simple_parallel_cancelled_error_uses_interrupt_flow(monkeypatch):
    dummy_agent = SimpleNamespace(model=SimpleNamespace(model="test-model", message_history=[]))

    async def cancelled_run(*_args, **_kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(cli_headless.Runner, "run", cancelled_run)
    monkeypatch.setattr("cai.agents.get_available_agents", lambda: {})
    monkeypatch.setattr("cai.agents.get_agent_by_name", lambda *_args, **_kwargs: dummy_agent)

    with pytest.raises(KeyboardInterrupt):
        cli_headless._run_simple_parallel(
            dummy_agent,
            "input",
            1,
            "test_agent",
            Mock(),
            lambda *_args, **_kwargs: None,
        )


def test_parallel_worker_writes_cancelled_payload(monkeypatch, tmp_path):
    result_file = tmp_path / "worker-result.json"
    args = parallel_worker.WorkerArgs(
        agent="test_agent",
        agent_id="P1",
        model="test-model",
        prompt="input",
        result_file=str(result_file),
    )

    async def cancelled_run(_args):
        raise asyncio.CancelledError()

    monkeypatch.setattr(parallel_worker, "_parse_args", lambda: args)
    monkeypatch.setattr(parallel_worker, "_run", cancelled_run)

    assert parallel_worker.main() == 0
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["status"] == "cancelled"
    assert payload["agent_id"] == "P1"
