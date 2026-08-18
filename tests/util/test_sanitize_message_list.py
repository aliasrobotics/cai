"""Regression tests for :func:`cai.util.terminal.sanitize_message_list`.

These lock in correct handling of assistant turns that issue two or more
(parallel) ``tool_calls``.

A released version (0.5.10) entered an unbounded reorder loop whenever an
assistant message carried multiple tool calls: the second-pass sequence
check in ``sanitize_message_list`` only compared a tool message against its
*immediate* predecessor, so the 2nd/3rd sibling tool response was treated as
out-of-order, moved, and re-examined forever. Any turn that issued 2+
``tool_calls`` at once hung CAI indefinitely (issues #469, #401, #410).

The second-pass loop now tracks already-processed positions so it always
makes forward progress. These tests keep that guard honest and assert the
resulting list stays valid for the OpenAI / LiteLLM chat-completions API.
They intentionally do **not** assert that an already-valid order is left
untouched -- only that every input terminates and yields a valid sequence.
"""

import copy

import pytest

from cai.util.terminal import fix_message_list, sanitize_message_list


def _assistant(*tool_call_ids):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tid,
                "type": "function",
                "function": {"name": "generic_linux_command", "arguments": "{}"},
            }
            for tid in tool_call_ids
        ],
    }


def _tool(tool_call_id, content="ok"):
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _user(content="hello"):
    return {"role": "user", "content": content}


def _assert_valid_tool_ordering(messages):
    """Each tool message, skipping sibling tool messages, must be immediately
    preceded by the assistant message that owns its ``tool_call_id`` -- the
    invariant the OpenAI / LiteLLM API enforces for parallel tool calls."""
    for i, msg in enumerate(messages):
        if msg.get("role") != "tool" or not msg.get("tool_call_id"):
            continue
        tid = msg["tool_call_id"]
        k = i - 1
        while k >= 0 and messages[k].get("role") == "tool":
            k -= 1
        assert k >= 0, f"tool {tid!r} at index {i} has no preceding assistant"
        owner = messages[k]
        assert owner.get("role") == "assistant", (
            f"tool {tid!r} at index {i}: nearest non-tool predecessor is "
            f"{owner.get('role')!r}, not an assistant"
        )
        assert any(tc.get("id") == tid for tc in owner.get("tool_calls", [])), (
            f"tool {tid!r} at index {i}: preceding assistant does not own it"
        )


# Assistant turns with >= 2 parallel tool_calls whose responses arrive in an
# order the pre-fix second pass could not reconcile without looping.
PARALLEL_CASES = {
    "in_order": [_user(), _assistant("a", "b"), _tool("a"), _tool("b")],
    "reversed": [_user(), _assistant("a", "b"), _tool("b"), _tool("a")],
    "three_scrambled": [
        _user(),
        _assistant("a", "b", "c"),
        _tool("c"),
        _tool("a"),
        _tool("b"),
    ],
    "two_assistants_interleaved": [
        _user(),
        _assistant("a", "b"),
        _tool("a"),
        _assistant("c", "d"),
        _tool("b"),
        _tool("c"),
        _tool("d"),
    ],
    # Mirrors the report in issue #469: two commands issued in one turn.
    "issue_469_two_calls_one_turn": [
        _user(),
        _assistant("call_1", "call_2"),
        _tool("call_1", "ls -la /tmp/"),
        _tool("call_2", "ls -la ~/challenge/"),
    ],
    # A repeated sibling response (same id twice) must not re-trigger the loop.
    "duplicate_sibling_response": [
        _user(),
        _assistant("a", "b"),
        _tool("a"),
        _tool("b"),
        _tool("a"),
    ],
}


@pytest.mark.timeout(5)
@pytest.mark.parametrize("name", sorted(PARALLEL_CASES))
def test_parallel_tool_calls_terminate_and_stay_valid(name):
    messages = copy.deepcopy(PARALLEL_CASES[name])
    original_tool_ids = sorted(
        m["tool_call_id"] for m in messages if m.get("role") == "tool"
    )

    # Pre-fix, this call never returned for any of these shapes.
    result = sanitize_message_list(messages)

    assert isinstance(result, list) and result
    _assert_valid_tool_ordering(result)

    # No tool response may be silently dropped.
    result_tool_ids = [m["tool_call_id"] for m in result if m.get("role") == "tool"]
    for tid in original_tool_ids:
        assert tid in result_tool_ids, f"tool response {tid!r} was dropped"


@pytest.mark.timeout(5)
def test_long_history_of_parallel_pairs_terminates():
    """A long history of reversed parallel pairs must still terminate; the
    pre-fix reorder loop degenerated into an unbounded ping-pong as history
    grew (``sanitize_message_list`` runs on every model request)."""
    messages = [_user()]
    for k in range(200):
        messages += [_assistant(f"a{k}", f"b{k}"), _tool(f"b{k}"), _tool(f"a{k}")]

    result = sanitize_message_list(messages)

    assert isinstance(result, list)
    _assert_valid_tool_ordering(result)
    result_tool_ids = {m["tool_call_id"] for m in result if m.get("role") == "tool"}
    for k in range(200):
        assert f"a{k}" in result_tool_ids and f"b{k}" in result_tool_ids


@pytest.mark.timeout(5)
def test_tool_message_without_owning_assistant_is_repaired():
    """A tool message whose owning assistant is missing (here, at index 0)
    must be repaired into a valid sequence rather than dropped or looped on."""
    result = sanitize_message_list([_tool("orphan"), _user("continue")])

    assert isinstance(result, list) and result
    _assert_valid_tool_ordering(result)


def test_fix_message_list_alias_is_preserved():
    """``fix_message_list`` stays importable as a backwards-compatible alias."""
    assert fix_message_list is sanitize_message_list

    from cai.util import fix_message_list as reexported

    assert reexported is sanitize_message_list
