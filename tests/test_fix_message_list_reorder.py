"""Tests for fix_message_list tool message reordering.

Verifies that fix_message_list correctly handles out-of-order tool messages
without entering an infinite loop. This is critical for agent-as-a-tool
architectures where concurrent sub-agents produce tool responses that arrive
in a different order than the tool_calls in the assistant message.
"""

from cai.util import fix_message_list


def _make_assistant_tool_calls(*call_ids):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": cid,
                "type": "function",
                "function": {"name": f"func_{cid}", "arguments": "{}"},
            }
            for cid in call_ids
        ],
    }


def _make_tool_response(call_id, content="ok"):
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": content,
    }


def _assert_tool_follows_assistant(result, tool_call_id):
    """Assert that a tool response appears after its matching assistant message."""
    tool_idx = next(
        i for i, m in enumerate(result)
        if m.get("role") == "tool" and m.get("tool_call_id") == tool_call_id
    )
    asst_idx = next(
        i for i, m in enumerate(result)
        if m.get("role") == "assistant"
        and m.get("tool_calls")
        and any(tc["id"] == tool_call_id for tc in m["tool_calls"])
    )
    assert tool_idx > asst_idx, (
        f"Tool {tool_call_id} at index {tool_idx} should follow assistant at index {asst_idx}"
    )


def test_two_tool_responses_reversed_order():
    """Simplest reproducer: two tool responses arrive in reverse order."""
    messages = [
        {"role": "user", "content": "Validate the security alert"},
        _make_assistant_tool_calls("call_1", "call_2"),
        _make_tool_response("call_2", "GitHub: Found PR #1234"),
        _make_tool_response("call_1", "Wiz: Resource is internet-facing"),
    ]

    result = fix_message_list(messages)

    assert sum(1 for m in result if m["role"] == "tool") == 2
    _assert_tool_follows_assistant(result, "call_1")
    _assert_tool_follows_assistant(result, "call_2")


def test_multi_assistant_reversed_tool_responses():
    """Two separate assistant messages with tool responses arriving reversed."""
    messages = [
        {"role": "user", "content": "Investigate Wiz alert and Bugcrowd submission"},
        _make_assistant_tool_calls("call_1"),
        _make_assistant_tool_calls("call_2"),
        _make_tool_response("call_2", "Bugcrowd: Submission details..."),
        _make_tool_response("call_1", "Wiz: Alert details..."),
    ]

    result = fix_message_list(messages)

    _assert_tool_follows_assistant(result, "call_1")
    _assert_tool_follows_assistant(result, "call_2")


def test_three_tool_calls_scrambled():
    """Three tool calls with responses arriving in fully scrambled order."""
    messages = [
        {"role": "user", "content": "Run analysis"},
        _make_assistant_tool_calls("call_a", "call_b", "call_c"),
        _make_tool_response("call_c", "result_c"),
        _make_tool_response("call_a", "result_a"),
        _make_tool_response("call_b", "result_b"),
    ]

    result = fix_message_list(messages)

    assert sum(1 for m in result if m["role"] == "tool") == 3
    _assert_tool_follows_assistant(result, "call_a")
    _assert_tool_follows_assistant(result, "call_b")
    _assert_tool_follows_assistant(result, "call_c")


def test_tool_responses_already_in_order():
    """Already-ordered tool responses should pass through without issues."""
    messages = [
        {"role": "user", "content": "Do stuff"},
        _make_assistant_tool_calls("call_1", "call_2"),
        _make_tool_response("call_1", "result_1"),
        _make_tool_response("call_2", "result_2"),
    ]

    result = fix_message_list(messages)

    tool_ids = [m["tool_call_id"] for m in result if m.get("role") == "tool"]
    assert "call_1" in tool_ids
    assert "call_2" in tool_ids


def test_nested_agent_interleaved_history():
    """Nested agent-as-tool: the faster sub-agent (call_yyy) returns first."""
    messages = [
        {"role": "user", "content": "Cross-validate evidence"},
        _make_assistant_tool_calls("call_xxx", "call_yyy"),
        _make_tool_response("call_yyy", "Wiz confirms exposure..."),
        _make_tool_response("call_xxx", "CVE-2024-3094 is NOT applicable..."),
    ]

    result = fix_message_list(messages)

    tool_ids = [m["tool_call_id"] for m in result if m.get("role") == "tool"]
    assert len(tool_ids) == 2
    _assert_tool_follows_assistant(result, "call_xxx")
    _assert_tool_follows_assistant(result, "call_yyy")


def test_mixed_correctly_and_incorrectly_ordered():
    """First assistant's tools are in order, second assistant's are reversed."""
    messages = [
        {"role": "user", "content": "Start"},
        _make_assistant_tool_calls("call_ok1", "call_ok2"),
        _make_tool_response("call_ok1", "ok1"),
        _make_tool_response("call_ok2", "ok2"),
        _make_assistant_tool_calls("call_rev1", "call_rev2"),
        _make_tool_response("call_rev2", "rev2"),
        _make_tool_response("call_rev1", "rev1"),
    ]

    result = fix_message_list(messages)

    for cid in ("call_ok1", "call_ok2", "call_rev1", "call_rev2"):
        _assert_tool_follows_assistant(result, cid)


def test_tool_response_separated_by_user_message():
    """Tool response separated from its assistant by a user message gets moved back."""
    messages = [
        {"role": "user", "content": "First request"},
        _make_assistant_tool_calls("call_x"),
        {"role": "user", "content": "Interruption"},
        _make_tool_response("call_x", "result_x"),
    ]

    result = fix_message_list(messages)

    asst_idx = next(
        i for i, m in enumerate(result)
        if m.get("role") == "assistant"
        and m.get("tool_calls")
        and any(tc["id"] == "call_x" for tc in m["tool_calls"])
    )
    tool_idx = next(
        i for i, m in enumerate(result)
        if m.get("role") == "tool" and m.get("tool_call_id") == "call_x"
    )
    assert tool_idx == asst_idx + 1


def test_does_not_modify_original_messages():
    """fix_message_list should not mutate the input list."""
    messages = [
        {"role": "user", "content": "Test"},
        _make_assistant_tool_calls("call_1", "call_2"),
        _make_tool_response("call_2", "result_2"),
        _make_tool_response("call_1", "result_1"),
    ]
    original_order = [m.get("tool_call_id") for m in messages if m.get("role") == "tool"]

    fix_message_list(messages)

    current_order = [m.get("tool_call_id") for m in messages if m.get("role") == "tool"]
    assert current_order == original_order


def test_single_tool_call_in_order():
    """Single tool call already in order should not change."""
    messages = [
        {"role": "user", "content": "Hello"},
        _make_assistant_tool_calls("call_solo"),
        _make_tool_response("call_solo", "done"),
        {"role": "user", "content": "Thanks"},
    ]

    result = fix_message_list(messages)

    tool_msgs = [m for m in result if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "call_solo"


def test_complex_multi_level_agent_scenario():
    """Three-level agent nesting with two rounds of reversed tool responses."""
    messages = [
        {"role": "user", "content": "Analyze security posture"},
        _make_assistant_tool_calls("call_validate_cve", "call_verify_wiz"),
        _make_tool_response("call_verify_wiz", "Wiz: exposure confirmed, no WAF"),
        _make_tool_response(
            "call_validate_cve",
            "CVE-2024-3094: NOT applicable - xz-utils version 5.4.1 is not affected",
        ),
        {"role": "assistant", "content": "Based on my analysis..."},
        {"role": "user", "content": "What about the network exposure?"},
        _make_assistant_tool_calls("call_deep_scan", "call_quick_check"),
        _make_tool_response("call_quick_check", "No additional exposure found"),
        _make_tool_response("call_deep_scan", "Deep scan: 3 open ports detected"),
    ]

    result = fix_message_list(messages)

    assert sum(1 for m in result if m["role"] == "tool") == 4
    for cid in ("call_validate_cve", "call_verify_wiz", "call_deep_scan", "call_quick_check"):
        _assert_tool_follows_assistant(result, cid)
