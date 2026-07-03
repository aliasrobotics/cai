from cai.util import streaming


def test_create_claude_thinking_context_for_deepseek_does_not_reference_missing_panel(capsys):
    streaming._CLAUDE_THINKING_PANELS.clear()

    context = streaming.create_claude_thinking_context(
        "Web App Pentester",
        1,
        "deepseek/deepseek-v4-pro",
    )

    captured = capsys.readouterr()
    assert context is not None
    assert "Error creating DeepSeek thinking context" not in captured.out
    assert context["model_display"] == "DeepSeek"
    assert context["accumulated_thinking"] == ""
    assert context["is_started"] is False

    thinking_id = context["thinking_id"]
    assert streaming._CLAUDE_THINKING_PANELS[thinking_id] is context
    streaming._CLAUDE_THINKING_PANELS.clear()


def test_deepseek_reasoning_display_is_opt_in(monkeypatch):
    monkeypatch.delenv("CAI_SHOW_REASONING", raising=False)
    monkeypatch.delenv("CAI_SHOW_THINKING", raising=False)

    assert streaming.detect_claude_thinking_in_stream("deepseek/deepseek-v4-pro") is False

    monkeypatch.setenv("CAI_SHOW_REASONING", "true")
    assert streaming.detect_claude_thinking_in_stream("deepseek/deepseek-v4-pro") is True


def test_claude_reasoning_display_keeps_historical_default(monkeypatch):
    monkeypatch.delenv("CAI_SHOW_REASONING", raising=False)
    monkeypatch.delenv("CAI_SHOW_THINKING", raising=False)

    assert streaming.detect_claude_thinking_in_stream("claude-sonnet-4-20250514") is True
