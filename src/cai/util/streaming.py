"""
Streaming panel management, live display, and tool output rendering for CAI.

Compact REPL note (q3=b)
------------------------
In compact mode (default for CLI sessions, opt-out via ``CAI_COMPACT_REPL=0``),
the verbose tool-output renderers in this module short-circuit to no-ops so
the single-line :class:`CompactCLIHandler` is the only writer to the
scrollback for tool events. The TUI patches these symbols at import time via
:mod:`cai.tui.display.wrapper`, so the suppression has no effect on TUI mode.
"""

import atexit
import json
import os
import re
import signal
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from rich.console import Console, Group
from rich.padding import Padding
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from wasabi import color

from cai.util.terminal import (
    _sanitize_output_for_display,
    _format_tool_args,
    _create_tool_panel_content,
    _print_simple_tool_output,
    _get_timing_info,
    _create_token_info_display,
    console,
    format_time,
    get_language_from_code_block,
    parse_message_content,
    parse_message_tool_call,
)
from cai.util._worker_silence import worker_display_silenced
from cai.util.pricing import is_tool_streaming_enabled
from cai.util.session import is_parallel_session
from cai.util.tokens import (
    get_model_name,
    get_model_input_tokens,
    _create_token_display,
)
from cai.util.pricing import (
    COST_TRACKER,
    enrich_token_info_for_pricing,
    calculate_model_cost,
    get_model_pricing,
    calculate_cached_token_costs,
)
from cai.util.cli_palette import CAI_GREEN, FINAL_PANEL_BG, GREY_HINT, GREY_TEXT


def _compact_suppresses_verbose() -> bool:
    """Return ``True`` when the verbose tool renderers should no-op.

    Delegates to the single source of truth :func:`is_compact_enabled` (cached
    at startup) so the verbose gate and the subscriber wiring stay in sync.
    Cheap to call; safe in hot paths.
    """
    from cai.repl.ui.compact_wiring import is_compact_enabled

    return is_compact_enabled()


_LIVE_STREAMING_PANELS = {}

# Global lock for coordinating parallel panel updates
_PANEL_UPDATE_LOCK = threading.Lock()

# Guard for duplicate non-streaming tool renders in serial mode.
_TOOL_RENDER_GUARD: dict[str, float] = {}
_TOOL_RENDER_GUARD_LOCK = threading.Lock()
_TOOL_RENDER_GUARD_TTL_S = 5.0


_CaiAgentLiveCls = None


def _get_cai_agent_live_class():
    """Return a ``Live`` subclass whose ``stop()`` can skip Rich's trailing ``console.line()``.

    Stock ``Live.stop()`` always calls ``console.line()`` after the final refresh. CAI's
    ``finish_agent_streaming`` always sets ``_cai_suppress_stop_line`` so that extra
    ``NewLine`` is omitted: it was stacking with a trailing ``\\n`` on frozen pre-tool text
    (two blanks before ``● tool``) and with the panel / tool output boundaries after tools.
    """

    global _CaiAgentLiveCls
    if _CaiAgentLiveCls is not None:
        return _CaiAgentLiveCls

    from rich.live import Live as _RichLive

    class CaiAgentLive(_RichLive):
        """Sync ``stop`` body with ``rich.live.Live.stop`` when upgrading Rich."""

        _cai_suppress_stop_line: bool = False

        def stop(self) -> None:
            with self._lock:
                if not self._started:
                    return
                self.console.clear_live()
                self._started = False

                if self.auto_refresh and self._refresh_thread is not None:
                    self._refresh_thread.stop()
                    self._refresh_thread = None
                self.vertical_overflow = "visible"
                with self.console:
                    try:
                        if not self._alt_screen and not self.console.is_jupyter:
                            self.refresh()
                    finally:
                        self._disable_redirect_io()
                        self.console.pop_render_hook()
                        if (
                            not self._alt_screen
                            and self.console.is_terminal
                            and not getattr(self, "_cai_suppress_stop_line", False)
                        ):
                            self.console.line()
                        self.console.show_cursor(True)
                        if self._alt_screen:
                            self.console.set_alt_screen(False)

                        if self.transient and not self._alt_screen:
                            self.console.control(self._live_render.restore_cursor())
                        if self.ipy_widget is not None and self.transient:
                            self.ipy_widget.close()  # pragma: no cover

    _CaiAgentLiveCls = CaiAgentLive
    return CaiAgentLive


def _build_tool_render_guard_key(
    tool_name: str,
    args: Any,
    output: Any,
    call_id: Optional[str],
    *,
    is_session_command: bool,
    is_parallel_mode: bool,
) -> Optional[str]:
    """Return a short-lived dedup key for final non-streaming tool render."""
    # Session polling and parallel fan-out can legitimately repeat similar output.
    if is_session_command or is_parallel_mode:
        return None
    if call_id:
        return f"call:{call_id}"

    try:
        args_key = json.dumps(args, sort_keys=True, ensure_ascii=False)
    except Exception:
        args_key = str(args)

    output_str = str(output or "")
    head = output_str[:120]
    tail = output_str[-120:] if len(output_str) > 120 else ""
    return f"{tool_name}|{args_key[:300]}|{len(output_str)}|{head}|{tail}"


def _should_skip_tool_render(render_key: Optional[str]) -> bool:
    """Return True when an equivalent tool output was rendered very recently."""
    if not render_key:
        return False
    now = time.time()
    with _TOOL_RENDER_GUARD_LOCK:
        # Bounded cleanup to avoid unbounded growth.
        if len(_TOOL_RENDER_GUARD) > 300:
            cutoff = now - (_TOOL_RENDER_GUARD_TTL_S * 4)
            stale_keys = [k for k, seen_at in _TOOL_RENDER_GUARD.items() if seen_at < cutoff]
            for key in stale_keys:
                _TOOL_RENDER_GUARD.pop(key, None)

        last_seen = _TOOL_RENDER_GUARD.get(render_key, 0.0)
        if now - last_seen < _TOOL_RENDER_GUARD_TTL_S:
            return True
        _TOOL_RENDER_GUARD[render_key] = now
        return False

# ─── Brand color (canonical: cai.util.cli_palette) ─────────────────────────
_DOT = "●"

# ─── Green/white theme for final response Markdown rendering ────────────────
from rich.theme import Theme as _Theme
_CAI_MD_THEME = _Theme({
    "markdown.h1": f"bold {CAI_GREEN} underline",
    "markdown.h2": f"bold {CAI_GREEN}",
    "markdown.h3": f"bold {CAI_GREEN}",
    "markdown.h4": f"bold {CAI_GREEN}",
    "markdown.h5": f"bold {CAI_GREEN}",
    "markdown.h6": f"bold {CAI_GREEN}",
    "markdown.h7": f"dim {CAI_GREEN}",
    "markdown.strong": f"bold {CAI_GREEN}",
    "markdown.em": "italic white",
    "markdown.code": f"bold {CAI_GREEN} on #1a1a2e",
    "markdown.code_block": f"{CAI_GREEN} on #1a1a2e",
    "markdown.item.bullet": f"bold {CAI_GREEN}",
    "markdown.item.number": f"bold {CAI_GREEN}",
    "markdown.item": "white",
    "markdown.list": f"dim {CAI_GREEN}",
    "markdown.link": f"{CAI_GREEN} underline",
    "markdown.link_url": "dim",
    "markdown.block_quote": f"italic dim {CAI_GREEN}",
    "markdown.paragraph": "white",
    "markdown.text": "white",
    "markdown.hr": f"dim {CAI_GREEN}",
})


def _flat_agent_header(agent_name: str, counter: int, model: str = "",
                       provider: str = "") -> Text:
    """Build a one-line header: ● Agent Name (model) [+ Unrestricted badge]"""
    t = Text()
    t.append(f"{_DOT} ", style=f"bold {CAI_GREEN}")
    t.append(f"{agent_name}", style=f"bold {CAI_GREEN}")
    if model:
        suffix = f" ({model})" if not provider else f" ({model} • {provider})"
        t.append(suffix, style="dim")
    if os.getenv("CAI_UNRESTRICTED", "false").strip().lower() in ("true", "1", "yes"):
        t.append(
            Text.from_markup(
                "  [bold bright_red]Unrestricted Mode [/bold bright_red]"
                "[bold white on bright_red] BETA [/]"
            )
        )
    return t


def _flat_tool_header(tool_name: str, args_str: str, execution_info: dict = None,
                      token_info: dict = None) -> Text:
    """Build a one-line tool header: ● AgentName ─ tool(args) [timing] [status]"""
    t = Text()
    t.append(f"{_DOT} ", style=f"bold {CAI_GREEN}")

    # Agent name if available
    agent_name = ""
    if token_info and isinstance(token_info, dict):
        agent_name = token_info.get("agent_name", "")
    if agent_name:
        t.append(f"{agent_name}", style=f"bold {CAI_GREEN}")
        t.append(" ─ ", style="dim")

    # Tool name
    is_handoff = tool_name.startswith("transfer_to_")
    if is_handoff:
        raw = tool_name[len("transfer_to_"):]
        nice = " ".join(w.capitalize() for w in raw.split("_"))
        t.append(f"→ {nice}", style="bold yellow")
    else:
        t.append(tool_name, style=f"bold {CAI_GREEN}")
        t.append(f"({args_str})", style="dim")

    # Timing
    if execution_info:
        timing_info, _ = _get_timing_info(execution_info)
        if timing_info:
            t.append(f" [{' | '.join(timing_info)}]", style="dim white")
        # Environment
        env = execution_info.get("environment", "")
        host = execution_info.get("host", "")
        if env:
            label = f"{env}:{host}" if host else env
            t.append(f" [{label}]", style="dim white")
        # Status
        status = execution_info.get("status", "")
        if status == "completed":
            t.append(" [Completed]", style=CAI_GREEN)
        elif status == "error":
            t.append(" [Error]", style="bold red")
        elif status == "timeout":
            t.append(" [Timeout]", style="bold red")
        elif status == "running":
            t.append(" [Running]", style="yellow")

    return t


def _flat_tool_output_block(output: str, max_lines: int = 40) -> Text:
    """Render tool output with └ prefix and indentation, in gray."""
    t = Text()
    if not output or not output.strip():
        return t
    output = _sanitize_output_for_display(output)
    lines = output.split("\n")
    # Truncate long outputs
    if len(lines) > max_lines:
        head = lines[:max_lines // 2]
        tail = lines[-(max_lines // 2):]
        omitted = len(lines) - max_lines
        lines = head + [f"  ... ({omitted} lines omitted) ..."] + tail

    for i, line in enumerate(lines):
        prefix = "  └ " if i == 0 else "    "
        t.append(f"{prefix}{line}\n", style="#aaaaaa")
    return t


# ─── Sticky pricing footer (Option F with green separators) ──────────────────
# Wide terminals: 3 lines (sep + single pricing+bar row + sep) or 1 without frame.
# Narrow terminals: 4 lines (sep + pricing + bar + sep) or 2 without frame.
# Tool wait hints add 1 extra row above.
_PRICING_FOOTER_LINES = 4
_pricing_footer_printed = False
_last_printed_sticky_footer_lines = 4
# Spinner animation is handled by rich.spinner.Spinner inside Live panels

def _print_cli_gap_after_completed_tool(
    streaming: bool,
    execution_info: Optional[dict],
    call_id: Optional[str] = None,
) -> None:
    """One blank row after a completed tool so the next ``● …`` block is not flush."""
    if streaming:
        return
    try:
        console.print()
    except Exception:
        try:
            print(file=sys.stdout)
        except Exception:
            pass


def _rich_line_with_grey_bold_italic_segments(line: str) -> Text:
    """Split ``**segment**`` into bold+italic grey; rest italic white (body prose)."""
    t = Text()
    for part in re.split(r"(\*\*.+?\*\*)", line):
        if len(part) >= 4 and part.startswith("**") and part.endswith("**"):
            t.append(part[2:-2], style=f"bold italic {GREY_TEXT}")
        elif part:
            t.append(part, style="italic white")
    return t


def _md_table_split_cells(line: str) -> list[str]:
    """Split a markdown pipe row into cell strings."""
    s = line.strip().strip("|")
    if not s:
        return []
    return [c.strip() for c in s.split("|")]


def _line_looks_like_md_table_row(line: str) -> bool:
    s = line.strip()
    return "|" in s and s.count("|") >= 1


def _is_markdown_table_separator_line(line: str) -> bool:
    """Match GFM-style ``| --- | :---: |`` separator rows."""
    t = line.strip().strip("|")
    if not t or "|" not in line:
        return False
    parts = [p.strip() for p in t.split("|")]
    if len(parts) < 2:
        return False
    pat = re.compile(r"^:?-{3,}:?$")
    return all(pat.match(p) for p in parts)


def _render_intermediate_markdown_table(
    console, header_cells: list[str], body_lines: list[str]
) -> None:
    """Print a pipe table: no borders/background, alternating white / grey rows."""
    ncols = len(header_cells)
    if ncols < 2:
        return
    rows: list[list[str]] = []
    for ln in body_lines:
        cells = _md_table_split_cells(ln)
        if len(cells) < 2 and not any(cells):
            continue
        while len(cells) < ncols:
            cells.append("")
        cells = cells[:ncols]
        rows.append(cells)
    if not rows:
        return

    table = Table(
        show_header=True,
        box=None,
        pad_edge=False,
        padding=(0, 1),
        collapse_padding=True,
        header_style="bold white",
    )
    for h in header_cells:
        table.add_column(h, overflow="fold")

    for ri, row in enumerate(rows):
        row_style = "italic white" if ri % 2 == 0 else f"italic {GREY_TEXT}"
        table.add_row(*[Text(c, style=row_style) for c in row])

    console.print(Padding(table, (0, 0, 0, 2)))


def _consume_intermediate_markdown_table(console, lines: list[str], start: int) -> int:
    """If a GFM table starts at *start*, render it and return the index after it; else -1."""
    if start >= len(lines) or start + 2 > len(lines):
        return -1
    if not _line_looks_like_md_table_row(lines[start]):
        return -1
    if not _is_markdown_table_separator_line(lines[start + 1]):
        return -1
    header_cells = _md_table_split_cells(lines[start])
    if len(header_cells) < 2:
        return -1
    j = start + 2
    body: list[str] = []
    while j < len(lines):
        raw = lines[j]
        if _is_markdown_table_separator_line(raw):
            break
        if not _line_looks_like_md_table_row(raw):
            break
        body.append(raw)
        j += 1
    if not body:
        return -1
    _render_intermediate_markdown_table(console, header_cells, body)
    return j


def _print_intermediate_plain_assistant_body(console, raw: str) -> None:
    """Format non-panel assistant text (tool-call turns): headings, **bold**, bash fences.

    Drops empty lines inside the body; prints a single trailing blank line before
    the next block (tool panels / next header).
    """
    if not raw or not str(raw).strip():
        return
    text = str(raw)
    lines = [ln for ln in text.split("\n") if ln.strip() != ""]
    if not lines:
        return

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        tbl_end = _consume_intermediate_markdown_table(console, lines, i)
        if tbl_end != -1:
            i = tbl_end
            continue

        if re.match(r"^```\s*(bash|sh|shell)\s*$", stripped, re.IGNORECASE):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                console.print(Text(f"  >> {lines[i]}", style=GREY_TEXT))
                i += 1
            if i < len(lines) and lines[i].strip().startswith("```"):
                i += 1
            continue

        if re.match(r"^#\s+[^#]", stripped):
            body = re.sub(r"^#\s+", "", stripped).strip()
            console.print(Text(f"  {body}", style="bold white"))
            i += 1
            continue

        if re.match(r"^##\s+", stripped) and not stripped.startswith("###"):
            body = re.sub(r"^##\s+", "", stripped).strip()
            console.print(Text(f"  {body}", style=f"bold {GREY_TEXT}"))
            i += 1
            continue

        if stripped.startswith("###"):
            body = re.sub(r"^#+\s*", "", stripped).strip()
            console.print(Text(f"  {body}", style=f"bold {GREY_TEXT}"))
            i += 1
            continue

        console.print(Padding(_rich_line_with_grey_bold_italic_segments(line), (0, 0, 0, 2)))
        i += 1

    console.print()


def _collapse_rich_live_shrink_gap(rich_console, extra_lines: int) -> None:
    """Remove blank terminal rows left when a Rich ``Live`` final frame is shorter than the prior one.

    ``LiveRender.position_cursor`` erases the *previous* full height, then the shorter renderable
    is drawn on the first N rows only; the remaining cleared rows stay visible as empty lines.
    That showed up as *two* (or more) blank lines between streamed assistant text and the first
    ``● … tool`` line after we dropped footer/pricing from the pre-tool freeze frame.
    """
    if extra_lines <= 0:
        return
    try:
        if not getattr(rich_console, "is_terminal", False):
            return
        if getattr(rich_console, "is_jupyter", False) or getattr(
            rich_console, "is_dumb_terminal", False
        ):
            return
        f = rich_console.file
        # Cursor ends on the last row of the new (shorter) output, often without a trailing LF.
        # Step onto the first ghost row, then CSI M (delete line) pulls following rows up.
        f.write("\n")
        for _ in range(extra_lines):
            f.write("\033[M")
        f.flush()
    except Exception:
        pass


def _erase_pricing_footer():
    """Erase the pricing footer from the terminal using ANSI escape codes.

    Moves cursor up by the footer height, clears each line, and repositions
    the cursor so new content can be printed where the footer was.
    """
    global _pricing_footer_printed, _last_printed_sticky_footer_lines
    if not _pricing_footer_printed:
        return
    try:
        sys.stdout.flush()
        n = max(1, _last_printed_sticky_footer_lines or _PRICING_FOOTER_LINES)
        # Move cursor up N lines
        sys.stdout.write(f"\033[{n}A")
        # Clear each line and move down
        for i in range(n):
            sys.stdout.write("\033[2K")
            if i < n - 1:
                sys.stdout.write("\n")
        # Move cursor back to the first cleared line
        sys.stdout.write(f"\r\033[{n - 1}A")
        sys.stdout.flush()
        _pricing_footer_printed = False
        _last_printed_sticky_footer_lines = 4
    except Exception:
        _pricing_footer_printed = False
        _last_printed_sticky_footer_lines = 4


def pause_streaming_lives() -> None:
    """Tear down every legacy streaming Live so an interactive prompt owns the screen.

    Compact mode normally suppresses these panels at creation time, but the
    agent-streaming Live (``create_agent_streaming_context``) is intentionally
    kept alive for plain conversational responses, and an in-flight LLM stream
    can still overlap with a tool-driven sudo / sensitive-guard prompt.

    The function ``stop()``s and forgets each Live; resumption is "fresh"
    (per user choice): the next streaming chunk creates a new context. Safe
    to call from worker threads — every entry point is wrapped in
    ``try/except`` so a missing registry never raises into the caller.
    """
    # 1. Per-call_id Live panels (tool streaming).
    try:
        for call_id, panel in list(_LIVE_STREAMING_PANELS.items()):
            try:
                if hasattr(panel, "stop"):
                    panel.stop()
            except Exception:
                pass
        _LIVE_STREAMING_PANELS.clear()
    except Exception:
        pass

    # 2. Grouped tool Live panels (legacy "[ tool batch ]" boxes).
    try:
        with _GROUPED_TOOLS_LOCK:
            for group_id, group_info in list(_GROUPED_STREAMING_TOOLS.items()):
                live_panel = group_info.get("live_panel") if isinstance(group_info, dict) else None
                try:
                    if live_panel and hasattr(live_panel, "stop"):
                        live_panel.stop()
                except Exception:
                    pass
            _GROUPED_STREAMING_TOOLS.clear()
    except Exception:
        pass

    # 3. Claude / model "thinking" panels.
    try:
        for thinking_id, ctx in list(_CLAUDE_THINKING_PANELS.items()):
            try:
                live = ctx.get("live") if isinstance(ctx, dict) else None
                if live is not None and ctx.get("is_started") and hasattr(live, "stop"):
                    live.stop()
            except Exception:
                pass
        _CLAUDE_THINKING_PANELS.clear()
    except Exception:
        pass

    # 4. Active agent-streaming contexts (per (agent, counter)).
    try:
        active = getattr(create_agent_streaming_context, "_active_streaming", None)
        if isinstance(active, dict):
            for key, ctx in list(active.items()):
                try:
                    live = ctx.get("live") if isinstance(ctx, dict) else None
                    if live is not None and ctx.get("is_started") and hasattr(live, "stop"):
                        live.stop()
                except Exception:
                    pass
            active.clear()
    except Exception:
        pass


def refresh_tool_wait_displays() -> None:
    """Redraw grouped tool Live panels and/or sticky pricing footer (tool wait hint)."""
    has_group_live = False
    sessions = getattr(cli_print_tool_output, "_streaming_sessions", {})
    has_active_sessions = any(
        isinstance(info, dict) and not info.get("is_complete", False)
        for info in sessions.values()
    )
    has_wait_hint = _tool_wait_hint_rich() is not None
    with _GROUPED_TOOLS_LOCK:
        for group_info in list(_GROUPED_STREAMING_TOOLS.values()):
            live_panel = group_info.get("live_panel")
            if not live_panel:
                continue
            has_group_live = True
            try:
                panel_raw, _ = _build_grouped_panel_content(group_info)
                live_panel.update(_group_tool_body_with_pricing_footer(panel_raw))
            except Exception:
                pass
    if not has_group_live and _pricing_footer_printed:
        try:
            # Prevent sticky footer repaints between completed tool A and starting tool B.
            # Only keep refreshing when there is an active wait context.
            if has_active_sessions and has_wait_hint:
                _erase_pricing_footer()
                _print_pricing_footer(Console(), final=False, framed=False)
        except Exception:
            pass

    # Non-grouped tool Live panels (single-call streaming)
    with _PANEL_UPDATE_LOCK:
        for call_id, panel_info in list(_LIVE_STREAMING_PANELS.items()):
            if isinstance(panel_info, dict):
                continue
            sess = sessions.get(call_id)
            if not sess:
                continue
            try:
                _, content = _create_tool_panel_content(
                    sess.get("tool_name", "tool"),
                    sess.get("args", {}),
                    sess.get("buffer", ""),
                    {"status": "running"},
                    sess.get("token_info"),
                )
                panel = _group_tool_body_with_pricing_footer(content)
                panel_info.update(panel)
            except Exception:
                pass


def _build_pricing_footer_renderable(final=False, *, framed: bool = True):
    """Build the pricing footer as a Rich Group renderable.

    Returns ``(renderable, content_lines)`` where *content_lines* is the number
    of terminal rows the renderable occupies (needed by ``_erase_pricing_footer``).

    Layout adapts to terminal width:
    - **Wide terminal**: pricing + context bar on a single row.
    - **Narrow terminal**: stacked (pricing row + bar row, like before).

    When framed=True separator lines are added above and below (+2 rows).
    """
    import shutil as _sh
    from rich.spinner import Spinner
    from rich.table import Table

    session_cost = getattr(COST_TRACKER, "session_total_cost", 0.0)
    inp = getattr(COST_TRACKER, "interaction_input_tokens", 0)
    out = getattr(COST_TRACKER, "interaction_output_tokens", 0)
    last_cost = getattr(COST_TRACKER, "last_interaction_cost", 0.0)

    model = os.environ.get("CAI_MODEL", "")
    try:
        max_tokens = get_model_input_tokens(model)
        ctx_pct = (inp / max_tokens) * 100 if max_tokens > 0 else 0.0
    except Exception:
        ctx_pct = 0.0

    tw = _sh.get_terminal_size().columns

    sep = Text("─" * tw, style=f"dim {CAI_GREEN}")
    sep_bottom = Text("─" * tw, style=f"dim {CAI_GREEN}")

    # Build pricing text (the part after the icon) — Layout 1: green/white/grey
    pricing_text = Text()
    pricing_text.append(f"${last_cost:.4f}", style=f"bold {CAI_GREEN}")
    pricing_text.append("  │  ", style="dim white")
    pricing_text.append("In:", style=f"italic {GREY_TEXT}")
    pricing_text.append(f"{inp:,}", style="bold white")
    pricing_text.append(" ", style="")
    pricing_text.append("Out:", style=f"italic {GREY_TEXT}")
    pricing_text.append(f"{out:,}", style="bold white")
    pricing_text.append("  │  ", style="dim white")
    pricing_text.append("Session: ", style=f"italic {GREY_TEXT}")
    pricing_text.append(f"${session_cost:.4f}", style=f"bold {CAI_GREEN}")

    # Context bar pieces
    ctx_label = f" {ctx_pct:.1f}% context"
    bar_color = CAI_GREEN if ctx_pct < 50 else "yellow" if ctx_pct < 80 else "bold red"
    pct_style = f"italic {GREY_HINT}" if ctx_pct < 80 else "bold red"

    # Decide layout: single-line when the terminal is wide enough
    pricing_prefix_len = 4  # "  ● " or spinner equivalent
    pricing_line_len = pricing_prefix_len + len(pricing_text.plain)
    _BAR_SEP = "  │  "
    min_bar_width = 20
    single_line = tw >= pricing_line_len + len(_BAR_SEP) + min_bar_width + len(ctx_label)

    if single_line:
        bar_width = max(min_bar_width, min(tw - pricing_line_len - len(_BAR_SEP) - len(ctx_label), 50))
    else:
        bar_width = 40

    filled = max(0, min(bar_width, int(ctx_pct / 100 * bar_width)))
    if inp > 0 and filled == 0:
        filled = 1
    empty = bar_width - filled

    def _bar_text() -> Text:
        t = Text()
        if filled > 0:
            t.append("█" * filled, style=bar_color)
        t.append("░" * empty, style="dim")
        t.append(ctx_label, style=pct_style)
        return t

    if single_line:
        # --- wide: one combined row ---
        bar_seg = Text()
        bar_seg.append(_BAR_SEP, style="dim white")
        bar_seg.append_text(_bar_text())

        if final:
            combined = Text()
            combined.append("  ● ", style=f"bold {CAI_GREEN}")
            combined.append_text(pricing_text)
            combined.append_text(bar_seg)
        else:
            spinner = Spinner("dots", style=f"bold {CAI_GREEN}")
            combined = Table.grid(padding=0)
            combined.add_row(Text("  "), spinner, Text(" "), pricing_text, bar_seg)

        content_lines = 3 if framed else 1
        if framed:
            return Group(sep, combined, sep_bottom), content_lines
        return Group(combined), content_lines
    else:
        # --- narrow: stacked (original layout) ---
        if final:
            line1 = Text()
            line1.append("  ● ", style=f"bold {CAI_GREEN}")
            line1.append_text(pricing_text)
        else:
            spinner = Spinner("dots", style=f"bold {CAI_GREEN}")
            line1 = Table.grid(padding=0)
            line1.add_row(Text("  "), spinner, Text(" "), pricing_text)

        line2 = Text()
        line2.append("  ", style="")
        line2.append_text(_bar_text())

        content_lines = 4 if framed else 2
        if framed:
            return Group(sep, line1, line2, sep_bottom), content_lines
        return Group(line1, line2), content_lines


def _tool_wait_hint_rich():
    """Single-line Rich renderable for active tool wait hint, or None."""
    try:
        from cai.util.wait_hints import get_tool_wait_footer_renderable

        r = get_tool_wait_footer_renderable()
        if r is None:
            return None
        return Padding(r, (0, 0, 0, 2))
    except Exception:
        return None


def _group_tool_body_with_pricing_footer(panel_body):
    """Return tool body alone, or stack wait hint + pricing when CAI_TOOL_LIVE_SHOW_PRICING is set.

    Default is body-only so Live tool panels match the flat Layout 1 style without the
    sticky pricing row or "Preparing tool" line (redundant with ⋯ RUNNING / header pills).
    """
    if os.getenv("CAI_TOOL_LIVE_SHOW_PRICING", "").lower() in ("1", "true", "yes"):
        foot = _DynamicPricingFooter(final=False, framed=False)
        hint = _tool_wait_hint_rich()
        if hint is not None:
            return Group(panel_body, hint, foot)
        return Group(panel_body, foot)
    return panel_body


class _DynamicPricingFooter:
    """Rebuild the pricing footer on every Live render.

    A static ``Group`` from ``_build_pricing_footer_renderable()`` freezes the
    Rich ``Spinner`` and token counts: Live would not animate or refresh costs
    until the next full ``update()``.
    """

    __slots__ = ("_final", "_framed")

    def __init__(self, final: bool = False, *, framed: bool = True) -> None:
        self._final = final
        self._framed = framed

    def __rich_console__(self, console, options):
        try:
            built, _ = _build_pricing_footer_renderable(
                final=self._final, framed=self._framed
            )
        except Exception:
            built = Text("")
        yield from console.render(built, options=options)


def _print_pricing_footer(console=None, final=False, framed=False):
    """Print the sticky pricing footer to the terminal (for non-Live contexts).

    Uses _build_pricing_footer_renderable() and prints it via console.print().
    By default, keeps footer unframed to avoid orphan separators between interactions.
    When framed=False, omits full-width separator lines (less noise between tools / in logs).
    """
    global _pricing_footer_printed, _last_printed_sticky_footer_lines
    try:
        if console is None:
            console = Console()

        renderable, content_lines = _build_pricing_footer_renderable(final=final, framed=framed)
        hint = _tool_wait_hint_rich()
        if hint is not None:
            console.print(Group(hint, renderable))
            _last_printed_sticky_footer_lines = content_lines + 1
        else:
            console.print(renderable)
            _last_printed_sticky_footer_lines = content_lines

        # Flush to ensure output is written before any ANSI operations
        console.file.flush()
        _pricing_footer_printed = True
    except Exception:
        pass  # Never break execution for a display-only feature

# Grouped streaming tool calls - combines multiple concurrent tool calls into one panel
# Structure: { "group_id": { "call_ids": [call_id1, call_id2, ...], "tools": {...}, "start_time": float, "panel": Live/None } }
_GROUPED_STREAMING_TOOLS = {}
_GROUPED_TOOLS_LOCK = threading.Lock()

# Time window (seconds) to group tool calls together
_GROUP_WINDOW_SECONDS = 0.5


def close_all_streaming_panels():
    """
    Close ALL open streaming panels and groups.
    Called at the start of each inference cycle to ensure clean state.
    This handles cases where not all tools in a group completed before
    the model started a new inference.
    """
    import os as _debug_os
    import time

    with _GROUPED_TOOLS_LOCK:
        # Close all grouped streaming tools
        for group_id, group_info in list(_GROUPED_STREAMING_TOOLS.items()):
            live_panel = group_info.get("live_panel")
            if live_panel:
                try:
                    live_panel.stop()
                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        tool_count = len(group_info.get("tools", {}))
                        completed = sum(1 for t in group_info.get("tools", {}).values() if t.get("is_complete", False))
                        print(f"[DEBUG_TOOLS_VIZ] close_all_streaming_panels: Closed group {group_id} ({completed}/{tool_count} were complete)")
                except Exception as e:
                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        print(f"[DEBUG_TOOLS_VIZ] close_all_streaming_panels: Error closing group {group_id}: {e}")

        # Clear all groups
        _GROUPED_STREAMING_TOOLS.clear()

    # Also clean up individual Live panels
    with _PANEL_UPDATE_LOCK:
        for call_id, panel_info in list(_LIVE_STREAMING_PANELS.items()):
            if not isinstance(panel_info, dict):
                try:
                    panel_info.stop()
                except Exception:
                    pass
        _LIVE_STREAMING_PANELS.clear()

    # Clear streaming sessions
    if hasattr(cli_print_tool_output, "_streaming_sessions"):
        cli_print_tool_output._streaming_sessions.clear()

    if hasattr(cli_print_tool_output, "_cli_gap_emitted_call_ids"):
        cli_print_tool_output._cli_gap_emitted_call_ids.clear()

    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
        print(f"[DEBUG_TOOLS_VIZ] close_all_streaming_panels: All panels closed, ready for new inference cycle")



def _finalize_live_panel(call_id, tool_name, args, output, execution_info, token_info):
    """
    Finalize an active Live panel by updating it with flat content and stopping it.
    """
    import os as _debug_os

    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
        print(f"[DEBUG_TOOLS_VIZ] _finalize_live_panel() called for call_id: {call_id}")

    if call_id not in _LIVE_STREAMING_PANELS:
        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
            print(f"[DEBUG_TOOLS_VIZ] _finalize_live_panel() - no Live panel found, skipping")
        return

    with _PANEL_UPDATE_LOCK:
        panel_info = _LIVE_STREAMING_PANELS.get(call_id)
        if panel_info is None or isinstance(panel_info, dict):
            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] _finalize_live_panel() - panel is static or None, skipping")
            return

        try:
            # Create flat content
            _, content = _create_tool_panel_content(
                tool_name, args, output, execution_info, token_info
            )

            # Update the Live panel with flat content
            panel_info.update(content)

            import time
            time.sleep(0.1)

            # Stop the Live panel (remains visible due to transient=False)
            panel_info.stop()
            _print_cli_gap_after_completed_tool(False, None, call_id)

            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] _finalize_live_panel() - Live panel finalized successfully")

        except Exception as e:
            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] _finalize_live_panel() - error: {e}")
            try:
                panel_info.stop()
                _print_cli_gap_after_completed_tool(False, None, call_id)
            except Exception:
                pass
        finally:
            if call_id in _LIVE_STREAMING_PANELS:
                del _LIVE_STREAMING_PANELS[call_id]



def _find_or_create_tool_group(call_id, tool_name, args, token_info):
    """
    Find an existing tool group to join, or create a new one.
    Tool calls started within _GROUP_WINDOW_SECONDS are grouped together.

    Returns: group_id (always returns a group_id, single tools are handled differently)
    """
    import os as _debug_os
    import time

    # NOTE: We don't check CAI_STREAM here because this function is only called
    # from the streaming path where streaming is already confirmed.

    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
        print(f"[DEBUG_TOOLS_VIZ] _find_or_create_tool_group() called for call_id: {call_id[:8]}")

    current_time = time.time()

    with _GROUPED_TOOLS_LOCK:
        # Look for an existing group that's still accepting new tools
        for group_id, group_info in list(_GROUPED_STREAMING_TOOLS.items()):
            time_since_start = current_time - group_info["start_time"]
            # Only join if within time window and group is still active
            if time_since_start < _GROUP_WINDOW_SECONDS and not group_info.get("finalized", False):
                # Add this tool to the group
                group_info["call_ids"].append(call_id)
                group_info["tools"][call_id] = {
                    "tool_name": tool_name,
                    "args": args,
                    "output": "",
                    "is_complete": False,
                    "token_info": token_info,
                    "start_time": current_time,
                }
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    print(f"[DEBUG_TOOLS_VIZ] Tool {call_id[:8]} JOINED existing group {group_id} (now {len(group_info['tools'])} tools)")
                return group_id

        # No suitable group found, create a new one
        group_id = f"group_{current_time}_{call_id[:8]}"
        _GROUPED_STREAMING_TOOLS[group_id] = {
            "call_ids": [call_id],
            "tools": {
                call_id: {
                    "tool_name": tool_name,
                    "args": args,
                    "output": "",
                    "is_complete": False,
                    "token_info": token_info,
                    "start_time": current_time,
                }
            },
            "start_time": current_time,
            "panel": None,
            "finalized": False,
        }
        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
            print(f"[DEBUG_TOOLS_VIZ] Tool {call_id[:8]} CREATED new group {group_id}")
        return group_id



def _build_grouped_panel_content(group_info):
    """
    Build combined content for a group of tools using Layout 1 (● header, >> command, Result rail).

    Same visual language as the final flat print after the group completes, including
    RUNNING/COMPLETED pills while streaming.
    Returns (renderable, all_complete) tuple.
    """
    import time as _time

    tools = group_info.get("tools") or {}
    if not tools:
        return Text(""), True

    now = _time.time()
    contents = []
    for i, tool_data in enumerate(tools.values()):
        is_done = tool_data.get("is_complete", False)
        exec_info = dict(tool_data.get("execution_info") or {})
        if not exec_info.get("status"):
            exec_info["status"] = "completed" if is_done else "running"
        if exec_info.get("tool_time") is None:
            try:
                exec_info["tool_time"] = float(now) - float(tool_data.get("start_time", now))
            except (TypeError, ValueError):
                exec_info["tool_time"] = 0.0

        _, content = _create_tool_panel_content(
            tool_data["tool_name"],
            tool_data["args"],
            tool_data.get("output", ""),
            exec_info,
            tool_data.get("token_info"),
            include_tool_wait_hint=(i == 0),
        )
        contents.append(content)

    merged = Group(*contents) if len(contents) > 1 else contents[0]
    all_complete = all(t.get("is_complete", False) for t in tools.values())
    return merged, all_complete


def _update_tool_group(group_id, call_id, output, execution_info=None, token_info=None, args=None):
    """
    Update a tool's output within a group and refresh the combined Live panel.
    Uses a single Live panel for all tools in the group.
    """
    import os as _debug_os
    from rich.console import Console
    from rich.live import Live

    if group_id not in _GROUPED_STREAMING_TOOLS:
        return False

    with _GROUPED_TOOLS_LOCK:
        group_info = _GROUPED_STREAMING_TOOLS.get(group_id)
        if not group_info:
            return False

        # Update this tool's output
        if call_id in group_info["tools"]:
            tool_data = group_info["tools"][call_id]
            tool_data["output"] = output
            # Update args to refresh countdown display
            if args:
                tool_data["args"] = args
            if execution_info:
                tool_data["execution_info"] = execution_info
                if execution_info.get("is_final", False):
                    tool_data["is_complete"] = True
            if token_info:
                tool_data["token_info"] = token_info

        # Build the combined panel, with pricing footer embedded for Live display
        panel_raw, all_complete = _build_grouped_panel_content(group_info)
        try:
            panel = _group_tool_body_with_pricing_footer(panel_raw)
        except Exception:
            panel = panel_raw

        # Check if we're in parallel mode
        is_parallel = is_parallel_session()

        if is_parallel:
            # In parallel mode, just update tracking info
            # We'll print final panels in _finalize_tool_group
            group_info["last_panel"] = panel
            return True

        # In single-agent mode, use Live panel
        live_panel = group_info.get("live_panel")

        if live_panel is None:
            # Before creating grouped panel, stop any existing individual panels for tools in this group
            for cid in group_info["call_ids"]:
                if cid in _LIVE_STREAMING_PANELS:
                    indiv_panel = _LIVE_STREAMING_PANELS[cid]
                    if not isinstance(indiv_panel, dict):
                        try:
                            indiv_panel.stop()
                            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                print(f"[DEBUG_TOOLS_VIZ] Stopped individual panel {cid} for group transition")
                        except Exception:
                            pass
                    del _LIVE_STREAMING_PANELS[cid]

            # Create a new Live panel for this group
            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] Creating grouped Live panel for group: {group_id}")
            try:
                # Erase sticky footer before grouped tool Live takes over
                _erase_pricing_footer()
                console = Console()
                live_panel = Live(
                    panel, console=console, refresh_per_second=4, auto_refresh=True,
                    transient=False
                )
                live_panel.start()
                group_info["live_panel"] = live_panel
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    print(f"[DEBUG_TOOLS_VIZ] Grouped Live panel started successfully")
            except Exception as e:
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    print(f"[DEBUG_TOOLS_VIZ] Grouped Live panel FAILED: {e}")
                # Fall back to static print
                console = Console()
                console.print(panel)
                return True
        else:
            # Update existing Live panel
            try:
                live_panel.update(panel)
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    completed = sum(1 for t in group_info["tools"].values() if t.get("is_complete", False))
                    total = len(group_info["tools"])
                    print(f"[DEBUG_TOOLS_VIZ] Grouped Live panel UPDATED ({completed}/{total} complete)")
            except Exception as e:
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    print(f"[DEBUG_TOOLS_VIZ] Grouped Live panel update FAILED: {e}")

        return True


def _finalize_tool_group(group_id):
    """
    When all tools in a group complete, stop the Live panel and print flat output.
    """
    import os as _debug_os
    import time
    from rich.console import Console

    if group_id not in _GROUPED_STREAMING_TOOLS:
        return

    with _GROUPED_TOOLS_LOCK:
        group_info = _GROUPED_STREAMING_TOOLS.get(group_id)
        if not group_info or group_info.get("finalized", False):
            return

        group_info["finalized"] = True

        if not all(t.get("is_complete", False) for t in group_info["tools"].values()):
            return

        tool_count = len(group_info["tools"])
        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
            print(f"[DEBUG_TOOLS_VIZ] Finalizing tool group: {group_id} with {tool_count} tools")

        live_panel = group_info.get("live_panel")

        # Helper: enrich token info from COST_TRACKER
        def _enrich(tool_data):
            raw = tool_data.get("token_info") or {}
            if not raw.get("model"):
                raw["model"] = os.environ.get("CAI_MODEL", "")
            if not raw.get("interaction_input_tokens"):
                raw["interaction_input_tokens"] = getattr(COST_TRACKER, "interaction_input_tokens", 0)
                raw["interaction_output_tokens"] = getattr(COST_TRACKER, "interaction_output_tokens", 0)
                raw["interaction_reasoning_tokens"] = getattr(COST_TRACKER, "interaction_reasoning_tokens", 0)
                raw["interaction_cost"] = getattr(COST_TRACKER, "last_interaction_cost", 0.0)
                raw["total_cost"] = getattr(COST_TRACKER, "last_total_cost", 0.0)
                raw["total_input_tokens"] = getattr(COST_TRACKER, "current_agent_input_tokens", 0)
                raw["total_output_tokens"] = getattr(COST_TRACKER, "current_agent_output_tokens", 0)
            if not raw.get("cache_read_tokens"):
                raw["cache_read_tokens"] = getattr(COST_TRACKER, "cache_read_tokens", 0)
            if not raw.get("cache_creation_tokens"):
                raw["cache_creation_tokens"] = getattr(COST_TRACKER, "cache_creation_tokens", 0)
            return enrich_token_info_for_pricing(raw)

        # One canonical final render (● Agent ─ tool …) matching cli_print_tool_output flat style.
        # Previously: Live froze a ✓-style block, then we printed this again → duplicate blocks.
        from rich.console import Group as _RichGroup

        contents_to_show = []
        for call_id, tool_data in group_info["tools"].items():
            enriched = _enrich(tool_data)
            _, content = _create_tool_panel_content(
                tool_data["tool_name"],
                tool_data["args"],
                tool_data.get("output", ""),
                tool_data.get("execution_info"),
                enriched,
            )
            contents_to_show.append(content)

        merged_final = (
            _RichGroup(*contents_to_show)
            if len(contents_to_show) > 1
            else contents_to_show[0]
        )

        used_live_for_final = False
        if live_panel:
            try:
                live_panel.update(merged_final)
                time.sleep(0.1)
                live_panel.stop()
                used_live_for_final = True
            except Exception:
                pass

        _console = Console()

        # Erase sticky footer before printing new tool content
        _erase_pricing_footer()

        # If Live already left the final render on screen, do not print again.
        if not used_live_for_final:
            for i, _c in enumerate(contents_to_show):
                _console.print(_c)
                if i < len(contents_to_show) - 1:
                    _console.print()
        _print_cli_gap_after_completed_tool(False, None, f"group:{group_id}")

        for call_id in group_info["tools"]:
            if not hasattr(cli_print_tool_output, "_displayed_call_ids"):
                cli_print_tool_output._displayed_call_ids = set()
            cli_print_tool_output._displayed_call_ids.add(call_id)

        # Do not re-print sticky pricing here — it duplicated rows between tools in logs.
        # Costs/tokens appear on the next assistant turn (streaming end or final panel).

        del _GROUPED_STREAMING_TOOLS[group_id]


def _get_group_for_call_id(call_id):
    """Find the group that contains a given call_id, if any."""
    with _GROUPED_TOOLS_LOCK:
        for group_id, group_info in _GROUPED_STREAMING_TOOLS.items():
            if call_id in group_info["call_ids"]:
                return group_id
    return None


def _check_and_finalize_group(call_id):
    """
    Check if all tools in a call_id's group are complete, and finalize if so.
    """
    group_id = _get_group_for_call_id(call_id)
    if not group_id:
        return False

    # Check completion status within lock, but call finalize outside to avoid deadlock
    should_finalize = False
    with _GROUPED_TOOLS_LOCK:
        group_info = _GROUPED_STREAMING_TOOLS.get(group_id)
        if group_info and not group_info.get("finalized", False):
            # Check if all tools are complete
            if all(t["is_complete"] for t in group_info["tools"].values()):
                should_finalize = True

    # Call finalize outside the lock (it will acquire its own lock)
    if should_finalize:
        _finalize_tool_group(group_id)
        return True

    return False


# Track parallel execution state
_PARALLEL_EXECUTION_STATE = {
    "active": False,
    "panel_groups": {},  # Group panels by execution batch
    "current_batch_id": None,
}

# ======================== CLAUDE THINKING STREAMING FUNCTIONS ========================

# Global tracker for Claude thinking streaming panels
_CLAUDE_THINKING_PANELS = {}

# Global flag to track if cleanup is in progress
_cleanup_in_progress = False
_cleanup_lock = threading.Lock()

# Rich ``Live`` used only for context-compaction UI (not tool panels).  If SIGINT
# fires while it is active, it must be stopped or the TTY can stay half-updated.
_COMPACTION_LIVE_LOCK = threading.Lock()
_registered_compaction_lives: list = []


def register_compaction_live(live) -> None:
    """Register a compaction ``Live`` so SIGINT / cleanup can ``stop()`` it."""
    if live is None:
        return
    with _COMPACTION_LIVE_LOCK:
        if live not in _registered_compaction_lives:
            _registered_compaction_lives.append(live)


def unregister_compaction_live(live) -> None:
    if live is None:
        return
    with _COMPACTION_LIVE_LOCK:
        try:
            _registered_compaction_lives.remove(live)
        except ValueError:
            pass


def _stop_registered_compaction_lives() -> None:
    with _COMPACTION_LIVE_LOCK:
        lives = list(_registered_compaction_lives)
        _registered_compaction_lives.clear()
    for lv in lives:
        try:
            if lv is not None and hasattr(lv, "stop"):
                lv.stop()
        except Exception:
            pass


def _reset_controlling_tty_sane() -> None:
    """If a child process left the controlling TTY raw or with echo off, ANSI alone is not enough."""
    if not sys.stdin.isatty():
        return
    try:
        import subprocess

        subprocess.run(
            ["stty", "sane"],
            stdin=sys.stdin,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
    except Exception:
        pass


def restore_terminal_state(
    *,
    leave_alternate_screen: bool = True,
    emit_trailing_newline: bool = True,
) -> None:
    """Show cursor, reset SGR; helps after Rich Live or prompt_toolkit + SIGINT.

    We intentionally do **not** emit \\033[?1049l (leave alternate screen). Rich Live uses
    screen=False by default, so CAI normally never enters the xterm alternate buffer; sending
    1049l anyway makes many terminals swap to the main buffer and redraw a stale bash prompt
    in the middle of CAI output while Python is still running. The leave_alternate_screen name
    is kept only for call-site compatibility with cleanup_all_streaming_resources().

    If emit_trailing_newline is False, do not append \\n after the escape sequence (cleanup
    can run twice on Ctrl+C; trailing newlines were stacking as blank lines before the exit
    summary).
    """
    esc = "\033[?25h\033[0m"  # DECTCEM show cursor + SGR reset
    suffix = "\n" if emit_trailing_newline else ""
    # Only stdout gets the trailing newline: when both attach to the same TTY, writing \n to
    # stderr as well stacks two blank lines before the shell redraws the prompt.
    try:
        sys.stdout.write(esc + suffix)
        sys.stdout.flush()
    except Exception:
        pass
    try:
        sys.stderr.write(esc)
        sys.stderr.flush()
    except Exception:
        pass
    try:
        from rich.console import Console

        Console().show_cursor(True)
    except Exception:
        pass
    _reset_controlling_tty_sane()


def cleanup_all_streaming_resources(
    *,
    leave_alternate_screen: bool = True,
    emit_trailing_newline: Optional[bool] = None,
):
    """
    Clean up all active streaming resources.
    This is called when the program is interrupted or exits.
    """
    global _cleanup_in_progress

    if emit_trailing_newline is None:
        emit_trailing_newline = leave_alternate_screen

    # Use non-blocking lock to avoid deadlocks during signal handling.
    # Hold the lock for the *entire* cleanup: releasing early allowed a second
    # SIGINT to return without restore_terminal_state(), leaving the TTY stuck
    # (hidden cursor, raw mode, etc.).
    if not _cleanup_lock.acquire(blocking=False):
        # Another cleanup holds the lock — still force-stop and restore the TTY.
        _stop_registered_compaction_lives()
        _force_stop_all_panels(
            leave_alternate_screen=leave_alternate_screen,
            emit_trailing_newline=emit_trailing_newline,
        )
        restore_terminal_state(
            leave_alternate_screen=leave_alternate_screen,
            emit_trailing_newline=emit_trailing_newline,
        )
        return

    try:
        if _cleanup_in_progress:
            # Defensive: should not happen while we hold the lock; still restore TTY.
            restore_terminal_state(
                leave_alternate_screen=leave_alternate_screen,
                emit_trailing_newline=emit_trailing_newline,
            )
            return
        _cleanup_in_progress = True
        try:
            _stop_registered_compaction_lives()

            # Clean up all active Live streaming panels
            for call_id, live in list(_LIVE_STREAMING_PANELS.items()):
                try:
                    if hasattr(live, "stop"):
                        live.stop()
                except Exception:
                    pass
            _LIVE_STREAMING_PANELS.clear()

            # Clean up all grouped streaming tools and their live panels
            for group_id, group_info in list(_GROUPED_STREAMING_TOOLS.items()):
                try:
                    live_panel = group_info.get("live_panel")
                    if live_panel and hasattr(live_panel, "stop"):
                        live_panel.stop()
                except Exception:
                    pass
            _GROUPED_STREAMING_TOOLS.clear()

            # Clean up all Claude thinking panels
            for thinking_id, context in list(_CLAUDE_THINKING_PANELS.items()):
                try:
                    if context and context.get("live") and context.get("is_started"):
                        context["live"].stop()
                except Exception:
                    pass
            _CLAUDE_THINKING_PANELS.clear()

            # Clean up active streaming contexts from create_agent_streaming_context
            if hasattr(create_agent_streaming_context, "_active_streaming"):
                for context_key, context in list(
                    create_agent_streaming_context._active_streaming.items()
                ):
                    try:
                        if context and context.get("live") and context.get("is_started"):
                            context["live"].stop()
                    except Exception:
                        pass
                create_agent_streaming_context._active_streaming.clear()

            # Reset any streaming session states
            if hasattr(cli_print_tool_output, "_streaming_sessions"):
                cli_print_tool_output._streaming_sessions.clear()

            # Clean up parallel execute_code tracking
            if hasattr(start_tool_streaming, "_parallel_execute_code_agents"):
                start_tool_streaming._parallel_execute_code_agents.clear()

            # Clean up recent commands tracking
            if hasattr(start_tool_streaming, "_recent_commands"):
                start_tool_streaming._recent_commands.clear()

            # Reset parallel execution state
            global _PARALLEL_EXECUTION_STATE
            _PARALLEL_EXECUTION_STATE = {
                "active": False,
                "panel_groups": {},
                "current_batch_id": None,
            }

            restore_terminal_state(
                leave_alternate_screen=leave_alternate_screen,
                emit_trailing_newline=emit_trailing_newline,
            )

        except Exception as e:
            print(f"\nError during streaming cleanup: {e}", file=sys.stderr)
            restore_terminal_state(
                leave_alternate_screen=leave_alternate_screen,
                emit_trailing_newline=emit_trailing_newline,
            )
        finally:
            _cleanup_in_progress = False
    finally:
        _cleanup_lock.release()



def _force_stop_all_panels(
    *,
    leave_alternate_screen: bool = True,
    emit_trailing_newline: bool = True,
):
    """
    Force stop all Live panels without acquiring locks.
    Used as a fallback when locks can't be acquired during signal handling.
    """
    _stop_registered_compaction_lives()

    # Stop individual live panels
    for call_id, live in list(_LIVE_STREAMING_PANELS.items()):
        try:
            if hasattr(live, "stop"):
                live.stop()
        except Exception:
            pass

    # Stop grouped live panels
    for group_id, group_info in list(_GROUPED_STREAMING_TOOLS.items()):
        try:
            live_panel = group_info.get("live_panel")
            if live_panel and hasattr(live_panel, "stop"):
                live_panel.stop()
        except Exception:
            pass

    # Stop Claude thinking panels
    for thinking_id, context in list(_CLAUDE_THINKING_PANELS.items()):
        try:
            if context and context.get("live") and context.get("is_started"):
                context["live"].stop()
        except Exception:
            pass

    restore_terminal_state(
        leave_alternate_screen=leave_alternate_screen,
        emit_trailing_newline=emit_trailing_newline,
    )


def cleanup_agent_streaming_resources(agent_name):
    """
    Clean up streaming resources for a specific agent.

    Args:
        agent_name: Name of the agent whose streaming resources to clean up
    """
    if not hasattr(cli_print_tool_output, "_streaming_sessions"):
        return

    # Find and finish streaming sessions belonging to this agent
    sessions_to_cleanup = []
    for session_id, session_info in list(cli_print_tool_output._streaming_sessions.items()):
        # Check if this session belongs to the agent and is not complete
        if session_info.get("agent_name") == agent_name and not session_info.get(
            "is_complete", False
        ):
            sessions_to_cleanup.append((session_id, session_info))

    # Also clean up any Live panels for this agent
    global _LIVE_STREAMING_PANELS
    panels_to_cleanup = []
    for panel_id, panel_info in list(_LIVE_STREAMING_PANELS.items()):
        # Check if this is a static panel with matching agent
        if isinstance(panel_info, dict) and panel_info.get("type") == "static":
            # We don't store agent name in panel info, so we can't filter by agent
            # But we can clean up based on session completion
            if panel_id in [s[0] for s in sessions_to_cleanup]:
                panels_to_cleanup.append(panel_id)

    # Clean up panels first
    for panel_id in panels_to_cleanup:
        del _LIVE_STREAMING_PANELS[panel_id]

    # Clean up parallel execute_code agent tracking
    if hasattr(start_tool_streaming, "_parallel_execute_code_agents"):
        if agent_name in start_tool_streaming._parallel_execute_code_agents:
            start_tool_streaming._parallel_execute_code_agents.remove(agent_name)

    # Finish each session properly
    for session_id, session_info in sessions_to_cleanup:
        finish_tool_streaming(
            tool_name=session_info.get("tool_name", "unknown"),
            args=session_info.get("args", {}),
            output=session_info.get("current_output", "Execution completed"),
            call_id=session_id,
            execution_info={"status": "completed", "is_final": True},
            token_info={"agent_name": agent_name},  # Pass agent name for proper display
        )



def cli_print_tool_call(
    tool_name: str = "",
    args: object = "",
    output: object = "",
    prefix: str = "  ",
    # Newer alias parameters used by templates
    tool_args: object = None,
    tool_output: object = None,
    # Optional token/cost/debug metadata (accepted for compatibility; ignored here)
    interaction_input_tokens: int = None,
    interaction_output_tokens: int = None,
    interaction_reasoning_tokens: int = None,
    total_input_tokens: int = None,
    total_output_tokens: int = None,
    total_reasoning_tokens: int = None,
    model: str = None,
    debug: bool = None,
    **kwargs,
):
    """
    Print a tool call with pretty formatting.

    Accepts both legacy (args/output) and new (tool_args/tool_output) names.
    Extra keyword arguments are accepted for forward compatibility and ignored.
    """
    if not tool_name:
        return

    # Respect explicit debug flag: if provided and falsey, do not print
    if debug is not None and not debug:
        return

    # Compact REPL owns tool rendering in CLI mode.
    if _compact_suppresses_verbose():
        return

    # Coalesce aliases
    effective_args = tool_args if tool_args is not None else args
    effective_output = tool_output if tool_output is not None else output

    print(f"{prefix}{color('Tool Call:', fg='cyan')}")
    print(f"{prefix}{color('Name:', fg='cyan')} {tool_name}")
    if effective_args:
        print(f"{prefix}{color('Args:', fg='cyan')} {effective_args}")
    if effective_output:
        print(f"{prefix}{color('Output:', fg='cyan')} {effective_output}")


def _prepare_terminal_for_final_agent_output() -> None:
    """Remove transient wait UI before printing the final assistant markdown.

    Dismisses the transient compact live block (if any) BEFORE drawing the
    final Panel. Rich's ``Live`` uses absolute cursor positioning to repaint
    its area; if still active when ``console.print(Panel)`` writes the bordered
    box "above" it, the next live refresh tick can overwrite the Panel's
    borders, leaving the markdown body visible without a frame. Tearing the
    live area down first means the Panel goes straight into scrollback intact.
    """
    try:
        from cai.util.wait_hints import clear_wait_hints

        clear_wait_hints()
    except Exception:
        pass
    try:
        from cai.repl.ui.compact_renderer import get_compact_handler

        _ch = get_compact_handler()
        if _ch is not None:
            _ch.flush()
    except Exception:
        pass
    try:
        from cai.util.wait_hints import clear_wait_hints

        clear_wait_hints()
    except Exception:
        pass


def cli_print_agent_messages(
    agent_name,
    message,
    counter,
    model,
    debug,  # pylint: disable=too-many-arguments,too-many-locals,unused-argument # noqa: E501
    interaction_input_tokens=None,
    interaction_output_tokens=None,
    interaction_reasoning_tokens=None,
    total_input_tokens=None,
    total_output_tokens=None,
    total_reasoning_tokens=None,
    interaction_cost=None,
    interaction_input_cost=None,  # Individual input cost
    interaction_output_cost=None,  # Individual output cost
    total_cost=None,
    total_input_cost=None,  # Total input cost
    total_output_cost=None,  # Total output cost
    tool_output=None,  # New parameter for tool output
    suppress_empty=False,  # New parameter to suppress empty panels
    # Cache token info (new format with read/creation separation)
    cache_read_tokens=None,  # Tokens read from cache (savings)
    cache_creation_tokens=None,  # Tokens written to cache (extra cost)
    cache_read_savings=None,  # Amount saved from cache reads
    cache_creation_extra=None,  # Extra cost from cache writes
    # Legacy params (for backward compatibility)
    cached_tokens=None,
    cached_cost=None,
    cache_savings=None,
    # Provider metadata (for OpenRouter, etc.)
    provider=None,
):
    """Print agent messages/thoughts with enhanced visual formatting."""

    # Sub-agents invoked as tools by the orchestration agent must not paint
    # their final markdown panel into the user-facing transcript — only the
    # orchestrator's synthesis is ever shown to the user. See
    # :mod:`cai.util._worker_silence`.
    if worker_display_silenced():
        return

    # Check if we're in TUI mode and should use TUI display instead
    import os
    if os.getenv("CAI_TUI_MODE") == "true":
        try:
            from cai.tui.display.integration import display_agent_messages

            # Convert message to list format
            messages = []
            if hasattr(message, "content") or isinstance(message, dict):
                # Convert to dict format
                if hasattr(message, "content"):
                    msg_dict = {
                        "role": "assistant",
                        "content": message.content if hasattr(message, "content") else str(message)
                    }
                    if hasattr(message, "tool_calls"):
                        msg_dict["tool_calls"] = message.tool_calls
                else:
                    msg_dict = message
                messages = [msg_dict]

            # Build token info (include model to align TUI pricing with CLI)
            token_info = {
                "interaction_input_tokens": interaction_input_tokens or 0,
                "interaction_output_tokens": interaction_output_tokens or 0,
                "interaction_reasoning_tokens": interaction_reasoning_tokens or 0,
                "total_input_tokens": total_input_tokens or 0,
                "total_output_tokens": total_output_tokens or 0,
                "total_reasoning_tokens": total_reasoning_tokens or 0,
                "interaction_cost": interaction_cost or 0.0,
                "interaction_input_cost": interaction_input_cost or 0.0,
                "interaction_output_cost": interaction_output_cost or 0.0,
                "total_cost": total_cost or 0.0,
                "total_input_cost": total_input_cost or 0.0,
                "total_output_cost": total_output_cost or 0.0,
                "session_total_cost": COST_TRACKER.session_total_cost if COST_TRACKER else 0.0,
                # propagate model and agent_name so TUI can compute accurate pricing and attribution
                "model": model,
                "agent_name": agent_name,
                # Cache info (new format)
                "cache_read_tokens": cache_read_tokens or 0,
                "cache_creation_tokens": cache_creation_tokens or 0,
                "cache_read_savings": cache_read_savings or 0.0,
                "cache_creation_extra": cache_creation_extra or 0.0,
                # Legacy (for backward compatibility)
                "cached_tokens": cached_tokens or cache_read_tokens or 0,
                "cached_cost": cached_cost or 0.0,
                "cache_savings": cache_savings or cache_read_savings or 0.0,
            }

            # Add terminal/agent identifiers to avoid attribution collisions in TUI
            try:
                from cai.tui.display.integration import get_terminal_id as _get_tid
                _tid = _get_tid()
                if _tid:
                    token_info["terminal_id"] = _tid
                    # Derive agent_id from terminal when not present
                    if "agent_id" not in token_info and isinstance(_tid, str) and _tid.startswith("terminal-"):
                        _num = _tid.split("-", 1)[1]
                        if _num.isdigit():
                            token_info["agent_id"] = f"P{_num}"
            except Exception:
                pass

            # Call TUI display
            display_agent_messages(
                agent_name=agent_name,
                messages=messages,
                model=model,
                counter=counter,
                token_info=token_info
            )
            return  # Exit early for TUI mode
        except ImportError:
            # Fall back to CLI display if TUI not available
            pass

    # Compact REPL: when the assistant message also carries tool calls, the
    # live block already represents what's about to execute, so the verbose
    # panel is redundant. Plain conversational replies (no tool calls) stay
    # visible because they ARE the agent's answer to the user.
    if _compact_suppresses_verbose():
        _has_tool_calls = False
        try:
            if hasattr(message, "tool_calls") and getattr(message, "tool_calls"):
                _has_tool_calls = True
            elif isinstance(message, dict) and message.get("tool_calls"):
                _has_tool_calls = True
        except Exception:
            pass
        if _has_tool_calls:
            return

    # Debug prints to trace the function calls
    if debug:
        if isinstance(message, str):
            print(f"DEBUG cli_print_agent_messages: Received string message: {message[:50]}...")
        if tool_output:
            print(f"DEBUG cli_print_agent_messages: Received tool_output: {tool_output[:50]}...")

    # Don't override the model - use the agent's actual model

    timestamp = datetime.now().strftime("%H:%M:%S")

    # Create header
    text = Text()

    # Check if the message has tool calls
    has_tool_calls = False
    has_execute_code = False
    if hasattr(message, "tool_calls") and message.tool_calls:
        has_tool_calls = True
        # Check if this is an execute_code tool call
        for tool_call in message.tool_calls:
            if hasattr(tool_call, "function") and hasattr(tool_call.function, "name"):
                if tool_call.function.name == "execute_code":
                    has_execute_code = True
                    break
    elif isinstance(message, dict) and "tool_calls" in message and message["tool_calls"]:
        has_tool_calls = True
        # Check if this is an execute_code tool call
        for tool_call in message["tool_calls"]:
            if isinstance(tool_call, dict) and "function" in tool_call:
                if tool_call["function"].get("name") == "execute_code":
                    has_execute_code = True
                    break

    # Parse the message based on whether it has tool calls
    if has_tool_calls:
        parsed_message, tool_panels = parse_message_tool_call(message, tool_output)
    else:
        # Get raw content first
        raw_content = parse_message_content(message)

        # Always render as Markdown for better formatting
        from rich.markdown import Markdown
        if isinstance(raw_content, str) and raw_content and raw_content.strip():
            parsed_message = Markdown(raw_content)
        else:
            parsed_message = raw_content
        tool_panels = []

    # Tool output was already printed by streaming finalization — drop redundant └ panels.
    if tool_panels and has_tool_calls:
        disp = getattr(cli_print_tool_output, "_displayed_call_ids", None)
        if disp:
            tcalls = getattr(message, "tool_calls", None)
            if tcalls is None and isinstance(message, dict):
                tcalls = message.get("tool_calls")
            ids_in_msg = []
            if tcalls:
                for tc in tcalls:
                    cid = getattr(tc, "id", None) if not isinstance(tc, dict) else tc.get("id")
                    if cid:
                        ids_in_msg.append(cid)
            if ids_in_msg and all(cid in disp for cid in ids_in_msg):
                tool_panels = []

    # Check if this is the main agent displaying a parallel agent's execute_code output
    # This happens when parallel results are added to message history
    if (
        isinstance(parsed_message, str)
        and hasattr(start_tool_streaming, "_parallel_execute_code_agents")
        and any(
            parallel_agent in parsed_message
            for parallel_agent in start_tool_streaming._parallel_execute_code_agents
            if parallel_agent
        )
        and token_info
        and token_info.get("agent_name") not in start_tool_streaming._parallel_execute_code_agents
    ):
        # This is the main agent displaying output from a parallel agent that used execute_code
        # Check if it contains execute_code output patterns (code blocks)
        if "```" in parsed_message and any(
            pattern in parsed_message.lower()
            for pattern in ["package main", "def ", "function", "import ", "class "]
        ):
            # Replace the execute_code output with a brief message
            lines = parsed_message.split("\n")
            summary_lines = []
            for line in lines:
                if "```" in line:
                    break
                summary_lines.append(line)

            if summary_lines:
                parsed_message = (
                    "\n".join(summary_lines).strip()
                    + "\n\n[Execute code output already shown in panels above]"
                )
            else:
                parsed_message = "[Execute code output already shown in panels above]"

    # Special handling for async session messages
    if tool_output and ("Started async session" in tool_output or "session" in tool_output.lower()):
        # For async session creation, show the session message as the main content
        if not parsed_message or parsed_message == "null" or parsed_message == "":
            parsed_message = tool_output
        else:
            # If there's already content, append the session message
            parsed_message = f"{parsed_message}\n\n{tool_output}"

        # Clear tool_panels to avoid duplication since we're showing the session message as main content
        tool_panels = []

    # Skip empty panels - THIS IS THE KEY CHANGE
    # If suppress_empty is True and there's no parsed message and no tool panels,
    # don't create an empty panel to avoid cluttering during streaming
    if suppress_empty and not parsed_message and not tool_panels:
        return

    # Check if parsed_message is empty or "null"
    is_empty_message = (
        parsed_message == "null"
        or parsed_message == ""
        or (isinstance(parsed_message, str) and not parsed_message.strip())
    )

    # Also skip if the only message is "null" or empty
    if is_empty_message:
        if suppress_empty and not tool_panels:
            return

    # Import Group early to fix scope issue
    from rich.console import Group

    # Check if we have Markdown or Group content
    is_rich_content = False
    from rich.markdown import Markdown

    if isinstance(parsed_message, (Group, Markdown)):
        is_rich_content = True

    # ── Flat-style output (no panels/boxes) ──────────────────────────────
    # Erase sticky pricing footer before printing new agent content
    _erase_pricing_footer()

    # Final boxed response only when this assistant turn has no pending tool calls.
    # If tool_calls exist but tool_output is not ready yet, tool_panels is empty and
    # the old logic wrongly treated the turn as "final" and drew a green Panel.
    is_final_response = not has_tool_calls

    # Header: ● Agent Name (model)
    header = _flat_agent_header(agent_name, counter, model or "", provider or "")

    if is_final_response and parsed_message:
        _prepare_terminal_for_final_agent_output()
        # Final response: wrap body in a green bordered panel with header as title
        # Apply green/white markdown theme for consistent styling
        from rich import box
        from rich.panel import Panel
        from rich.markdown import Markdown as _Md

        # Re-render as Markdown with headings converted to bold (left-aligned)
        if isinstance(parsed_message, _Md):
            raw_text = parse_message_content(message)
            if isinstance(raw_text, str) and raw_text.strip():
                raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
                # Convert ## headings to **bold** to prevent Rich centering them
                raw_text = re.sub(r'^#{1,4}\s+(.+)$', r'**\1**', raw_text, flags=re.MULTILINE)
                body = _Md(raw_text)
            else:
                body = parsed_message
        elif isinstance(parsed_message, str) and parsed_message.strip():
            body = Text(parsed_message, style="white")
        elif is_rich_content:
            body = parsed_message
        else:
            body = Text("")

        # ``try/finally`` invariant: even if ``console.print`` raises (e.g.
        # broken pipe, Rich rendering bug) the markdown theme must be popped
        # off the Console's theme stack — otherwise it leaks into every
        # subsequent render in the session.
        console.push_theme(_CAI_MD_THEME)
        try:
            console.print(
                Panel(
                    body,
                    title=header,
                    title_align="left",
                    border_style=CAI_GREEN,
                    expand=True,
                    padding=(1, 2),
                    style=f"on {FINAL_PANEL_BG}",
                    box=box.ROUNDED,
                )
            )
        finally:
            console.pop_theme()
    else:
        # Intermediate response (has tool calls): flat output, no box
        console.print(header)

        # Body: message content (Markdown or plain text), indented
        if parsed_message:
            if is_rich_content:
                from rich.padding import Padding
                console.print(Padding(parsed_message, (0, 0, 0, 2)))
            elif isinstance(parsed_message, str) and parsed_message.strip():
                _print_intermediate_plain_assistant_body(console, parsed_message)

    # Sticky pricing footer — Option F style with green separators.
    # Only after a completed assistant text turn (no tool_calls). Printing it on every
    # "planning tools" message stacked duplicate ── blocks with tool-group footers.
    if (
        is_final_response
        and interaction_input_tokens is not None  # pylint: disable=R0916
        and interaction_output_tokens is not None
    ):
        _print_pricing_footer(console, final=True, framed=True)

    # Tool panels (printed flat, not in a box)
    if tool_panels:
        for tool_panel in tool_panels:
            console.print(tool_panel)
        # No bare console.print() here — it added an extra empty row; spacing before the next
        # block comes from Rich console.print(..., end="\\n") on the following output only.


def create_agent_streaming_context(agent_name, counter, model):
    """
    Create a streaming context object that maintains state for streaming agent output.

    Args:
        agent_name: The name of the agent to display
        counter: The interaction counter (turn number)
        model: The model name

    Returns:
        A dictionary with the streaming context
    """
    # Check if we're in TUI mode - create a simplified context for TUI
    if os.getenv("CAI_TUI_MODE") == "true":
        import uuid
        # Create a simplified streaming context for TUI mode
        # The TUI will handle the actual display, we just need the context
        context = {
            "agent_name": agent_name,
            "interaction_counter": counter,
            "model": model,
            "stream_id": f"stream_{uuid.uuid4().hex[:8]}",
            "is_tui": True,
            "content": "",  # Will accumulate content
            "is_started": False,
        }

        # Get terminal ID if available
        try:
            from cai.tui.display.integration import get_terminal_id
            terminal_id = get_terminal_id()
            if terminal_id:
                context["terminal_id"] = terminal_id
        except ImportError:
            pass

        return context

    # Add a static variable to track active streaming contexts and prevent duplicates
    if not hasattr(create_agent_streaming_context, "_active_streaming"):
        create_agent_streaming_context._active_streaming = {}

    # If there's already an active streaming context with the same counter, return it
    context_key = f"{agent_name}_{counter}"
    if context_key in create_agent_streaming_context._active_streaming:
        return create_agent_streaming_context._active_streaming[context_key]

    try:
        import shutil

        # Don't override the model - use the agent's actual model

        timestamp = datetime.now().strftime("%H:%M:%S")

        # Terminal size for better display
        terminal_width, _ = shutil.get_terminal_size((100, 24))
        panel_width = min(terminal_width - 4, 120)  # Keep some margin

        # Create flat header: ● AgentName (model) [+ Unrestricted badge]
        header = Text()
        header.append(f"{_DOT} ", style=f"bold {CAI_GREEN}")
        header.append(f"{agent_name}", style=f"bold {CAI_GREEN}")
        if model:
            header.append(f" ({model})", style="dim")
        if os.getenv("CAI_UNRESTRICTED", "false").strip().lower() in ("true", "1", "yes"):
            header.append(
                Text.from_markup(
                    "  [bold bright_red]Unrestricted Mode [/bold bright_red]"
                    "[bold white on bright_red] BETA [/]"
                )
            )
        # No trailing \\n — Group already stacks children; extra \\n doubled vertical gaps.

        # Create the content area for streaming text
        content = Text("")

        # Footer for token stats (starts empty)
        footer = Text()

        # Lazy-create Live display object only when first content arrives.
        # This keeps terminal sizing/Live allocation off the pre-first-token path.
        live = None

        import uuid

        context = {
            "live": live,
            "panel": live,
            "header": header,
            "content": content,
            "footer": footer,
            "timestamp": timestamp,
            "model": model,
            "agent_name": agent_name,
            "panel_width": panel_width,
            "is_started": False,  # Track if we've started the display
            "error": None,  # Track any errors
            "context_key": context_key,  # Store the key for cleanup
            "stream_id": f"stream_{uuid.uuid4().hex[:8]}",  # Add stream_id for TUI streaming
            "interaction_counter": counter,  # Add counter for TUI display
        }

        # Store the context for potential reuse
        create_agent_streaming_context._active_streaming[context_key] = context

        return context
    except Exception as e:
        # If rich display fails, return None and log the error
        import sys

        print(f"Error creating streaming context: {e}", file=sys.stderr)
        return None


def update_agent_streaming_content(context, text_delta, token_stats=None):
    """
    Update the streaming content with new text.

    Args:
        context: The streaming context created by create_agent_streaming_context
        text_delta: The new text to add
        token_stats: Optional token statistics to show with each update
    """
    if not context:
        return False

    # Check if we're in TUI mode - handle updates differently
    if context.get("is_tui"):
        # Accumulate content in the context for TUI
        if text_delta:
            # For TUI mode, don't parse - just accumulate raw content
            # The TUI will handle formatting when displaying
            context["content"] += text_delta

            # Now notify TUI display system if we have a terminal_id
            if context.get("terminal_id"):
                try:
                    # Try direct integration import first (avoids textual dependency)
                    from cai.tui.display.integration import update_agent_streaming_content as tui_update
                    tui_update(context, text_delta, token_stats)
                except ImportError:
                    # Fallback to manager if integration not available
                    try:
                        from cai.tui.display.manager import DisplayManager
                        display_manager = DisplayManager()
                        # Update the streaming display with the new content delta
                        display_manager.update_agent_streaming_content(
                            context, text_delta, token_stats
                        )
                    except ImportError:
                        pass  # Silent fail in production
        return True

    # Check if cleanup is in progress to avoid updating a context being cleaned up
    global _cleanup_in_progress
    if _cleanup_in_progress:
        return False

    # Compact REPL: never allocate a second Rich Live for token streaming.
    if _compact_suppresses_verbose():
        if text_delta:
            parsed_delta = parse_message_content(text_delta)
            if parsed_delta and parsed_delta.strip():
                content = context.get("content")
                if isinstance(content, Text):
                    content.append(parsed_delta)
                else:
                    context["content"] = (content or "") + parsed_delta
        return True

    try:
        # Footer reads COST_TRACKER; stream usage is often applied only after the call ends.
        if token_stats and COST_TRACKER is not None:
            try:
                _ti = int(token_stats.get("input_tokens", 0) or 0)
                _to = int(token_stats.get("output_tokens", 0) or 0)
                COST_TRACKER.interaction_input_tokens = _ti
                COST_TRACKER.interaction_output_tokens = _to
                _cst = float(token_stats.get("cost", 0.0) or 0.0)
                if _cst > 0:
                    COST_TRACKER.last_interaction_cost = _cst
                    COST_TRACKER.interaction_cost = _cst
            except Exception:
                pass

        # Only parse and add text if we have actual content to add
        # Skip when text_delta is empty and we're just updating token stats
        if text_delta:
            # Parse the text_delta to get just the content if needed
            parsed_delta = parse_message_content(text_delta)

            # Skip empty updates to avoid showing an empty panel
            if not parsed_delta or parsed_delta.strip() == "":
                # Update token stats if provided
                if token_stats:
                    # Just update the footer, not the content
                    pass
            else:
                # For parallel agents that used execute_code, suppress duplicate output
                agent_name = context.get("agent_name", "")
                if (
                    agent_name
                    and hasattr(start_tool_streaming, "_parallel_execute_code_agents")
                    and agent_name in start_tool_streaming._parallel_execute_code_agents
                ):
                    # This parallel agent used execute_code
                    # Simply add a marker that output was shown in panels
                    if not hasattr(context, "_execute_code_noted"):
                        context["_execute_code_noted"] = True
                        context["content"].append("[Execute code output shown in panels above]\n")
                    # Skip the actual execute_code narrative output
                    if any(
                        marker in parsed_delta.lower()
                        for marker in ["execute", "code", "output", "running", "```"]
                    ):
                        return True  # Suppress
                else:
                    # Normal agent, show content as usual (cap runaway newlines from the model)
                    to_add = parsed_delta
                    if isinstance(to_add, str):
                        # First visible tokens: drop leading \\n+ so Live does not print empty rows
                        # above the answer (and the final Panel does not inherit them in plain text).
                        _existing = (
                            context["content"].plain
                            if hasattr(context["content"], "plain")
                            else ""
                        )
                        if not _existing:
                            to_add = re.sub(r"^\n+", "", to_add)
                        to_add = re.sub(r"\n{3,}", "\n\n", to_add)
                        # Cap trailing newlines per delta to one (model often sends \\n\\n+ at chunk ends).
                        to_add = re.sub(r"\n{2,}\Z", "\n", to_add)
                    context["content"].append(to_add)
        # If no text_delta but we have token_stats, just update stats
        elif not token_stats:
            # No text and no stats - nothing to update
            return True

        # Update the footer with token stats if provided
        if token_stats:
            # Create token stats display

            footer_stats = Text()

            # Add timestamp and model info (no leading \\n — avoids a blank line above the stats row)
            footer_stats.append(f"[{context['timestamp']}", style="dim")
            if context["model"]:
                footer_stats.append(f" ({context['model']})", style="bold magenta")
            footer_stats.append("]", style="dim")

            # Add token stats
            input_tokens = token_stats.get("input_tokens", 0)
            output_tokens = token_stats.get("output_tokens", 0)
            interaction_cost = token_stats.get("cost", 0.0)

            # Get session total cost - either from token_stats or directly from COST_TRACKER
            session_total_cost = token_stats.get("total_cost", 0.0)
            if session_total_cost == 0.0 and hasattr(COST_TRACKER, "session_total_cost"):
                session_total_cost = COST_TRACKER.session_total_cost

            if input_tokens > 0:
                footer_stats.append(" | ", style="dim")
                footer_stats.append(f"I:{input_tokens} O:{output_tokens}", style="green")

                # Add cache read (CR) and cache write (CW) tokens if available
                cache_read = token_stats.get("cache_read_tokens", 0)
                cache_write = token_stats.get("cache_creation_tokens", 0)
                if cache_read > 0:
                    footer_stats.append(f" CR:{cache_read}", style="cyan")
                if cache_write > 0:
                    footer_stats.append(f" CW:{cache_write}", style="yellow")

                # Show both interaction cost and total session cost
                if interaction_cost > 0:
                    footer_stats.append(f" (${interaction_cost:.4f})", style="bold cyan")

                # Add the total cost information on the same line
                footer_stats.append(" | Session: ", style="dim")
                footer_stats.append(f"${session_total_cost:.4f}", style="bold magenta")

                # Add context usage indicator (current interaction input)
                model_name = context.get("model", os.environ.get("CAI_MODEL", "alias1"))
                try:
                    max_tokens = get_model_input_tokens(model_name)
                    context_pct = (input_tokens / max_tokens) * 100 if max_tokens > 0 else 0.0
                except Exception:
                    context_pct = 0.0
                if context_pct < 50:
                    indicator = "🟩"
                    color = "green"
                elif context_pct < 80:
                    indicator = "🟨"
                    color = "yellow"
                else:
                    indicator = "🟥"
                    color = "red"
                footer_stats.append(f" {indicator} {context_pct:.1f}%", style=f"bold {color}")

            # Update the footer
            context["footer"] = footer_stats

        # Build flat renderable for Live update, including the pricing footer
        # so it is always visible at the bottom of the streaming panel.
        from rich.console import Group
        try:
            pricing_footer = _DynamicPricingFooter(final=False, framed=False)
        except Exception:
            pricing_footer = Text("")
        updated_content = Group(
            context["header"], context["content"], context["footer"],
            pricing_footer,
        )

        # Check if we need to start the display
        if not context.get("is_started", False):
            try:
                # Erase sticky footer before agent streaming Live takes over
                _erase_pricing_footer()
                if context.get("live") is None:
                    _LiveCls = _get_cai_agent_live_class()
                    context["live"] = _LiveCls(
                        updated_content,
                        refresh_per_second=10,
                        console=console,
                        auto_refresh=True,
                        vertical_overflow="visible",
                        transient=False,
                    )
                # Avoid start(refresh=True): it paints one frame before update()+refresh(), which
                # stacked an extra blank row vs. the following first real frame (tool output → panel).
                context["live"].start(refresh=False)
                context["is_started"] = True
            except Exception as e:
                context["error"] = str(e)
                context_key = context.get("context_key")
                if context_key and hasattr(create_agent_streaming_context, "_active_streaming"):
                    create_agent_streaming_context._active_streaming.pop(context_key, None)
                return False

        # Update with the flat content only if started
        if context.get("is_started", False) and context.get("live"):
            context["live"].update(updated_content)
            try:
                context["live"].refresh()
            except Exception:
                pass
        return True
    except Exception as e:
        # If there's an error, set it in the context
        context["error"] = str(e)
        # Try to clean up the context
        context_key = context.get("context_key")
        if context_key and hasattr(create_agent_streaming_context, "_active_streaming"):
            create_agent_streaming_context._active_streaming.pop(context_key, None)
        return False


def finish_agent_streaming(context, final_stats=None):
    """
    Finish the streaming session and display final stats if available.

    Args:
        context: The streaming context to finish
        final_stats: Optional dictionary with token statistics and costs
    """
    if not context:
        return False

    # Check if we're in TUI mode - handle finish differently
    if context.get("is_tui"):
        # Notify TUI display system to finish if we have a terminal_id
        if context.get("terminal_id"):
            try:
                # Try direct integration import first
                from cai.tui.display.integration import finish_agent_streaming as tui_finish
                tui_finish(context, final_stats)
            except ImportError:
                # Fallback to manager
                try:
                    from cai.tui.display.manager import DisplayManager
                    display_manager = DisplayManager()
                    # Finish the streaming display
                    display_manager.finish_agent_streaming(context, final_stats)
                except ImportError:
                    pass  # Silent fail in production
        return True

    # Check if cleanup is in progress
    global _cleanup_in_progress
    if _cleanup_in_progress:
        return False

    # Clean up tracking of this context
    context_key = context.get("context_key")
    if context_key and hasattr(create_agent_streaming_context, "_active_streaming"):
        create_agent_streaming_context._active_streaming.pop(context_key, None)

    try:
        # Check if there's actual content to display - don't show empty panels
        if not context["content"] or context["content"].plain == "":
            # If the display was never started, nothing to do
            if not context.get("is_started", False):
                return True
            # Otherwise, stop the display without showing final panel
            try:
                context["live"].stop()
            except Exception:
                pass
            return True

        # Determine if this is the final response (no more tool calls).
        # final_stats is None when streaming is interrupted by tool calls — never final.
        is_final = (
            final_stats is not None
            and not final_stats.get("has_tool_calls", False)
        )
        if is_final:
            _prepare_terminal_for_final_agent_output()

        # Build final renderable — use green Panel for final response
        from rich.console import Group
        if is_final:
            from rich import box
            from rich.panel import Panel
            from rich.markdown import Markdown
            # Re-render streamed text as Markdown for proper green/white styling
            raw = context["content"].plain if hasattr(context["content"], "plain") else str(context["content"])
            if raw.strip():
                # Model deltas often start with \\n\\n; that became two empty terminal rows above the Panel.
                raw = re.sub(r"^\n+", "", raw)
                # Cap runs of 3+ newlines so Markdown/Panels do not render huge vertical gaps
                raw = re.sub(r"\n{3,}", "\n\n", raw)
                # Convert ## headings to **bold** to prevent Rich centering them
                raw = re.sub(r'^#{1,4}\s+(.+)$', r'**\1**', raw, flags=re.MULTILINE)
                body = Markdown(raw)
            else:
                body = context["content"]
            # Apply green/white markdown theme for the final panel. The matching
            # ``pop_theme`` runs in a ``try/except`` further down (~2575) only
            # under ``if is_final:``; the wrap below keeps the invariant intact
            # even if the renderable construction below raises before reaching
            # the ``Live.update`` call.
            console.push_theme(_CAI_MD_THEME)
            final_content = Panel(
                body,
                title=context["header"],
                title_align="left",
                border_style=CAI_GREEN,
                expand=True,
                padding=(1, 2),
                style=f"on {FINAL_PANEL_BG}",
                box=box.ROUNDED,
            )
        else:
            # Frozen text before tools: normalize body only — strip *all* trailing newlines so Rich
            # does not paint an empty row after the last sentence. Do not include ``footer`` (token
            # stats row) in this final frame: it sat below that trailing ``\\n``, so the layout read
            # as (paragraph)(blank)(stats)(blank) before the first ``● … tool`` line.
            _ct = context["content"]
            if hasattr(_ct, "plain") and _ct.plain:
                _trim = _ct.plain.rstrip()
                if _trim:
                    _trim = re.sub(r"\n{3,}", "\n\n", _trim)
                    _trim = re.sub(r"\n+\Z", "", _trim)
                if _trim != _ct.plain:
                    context["content"] = Text(_trim, style="white")
            final_content = Group(
                context["header"],
                context["content"],
            )

        # Compact REPL: streaming text is accumulated without starting agent Live
        # (see update_agent_streaming_content). Flush the final frame to scrollback.
        if _compact_suppresses_verbose() and not context.get("is_started", False):
            try:
                console.print(final_content)
            except Exception as e:
                context["error"] = str(e)
            if is_final:
                try:
                    console.pop_theme()
                except Exception:
                    pass
            if final_stats is not None:
                _print_pricing_footer(final=is_final, framed=is_final)
            return True

        # Update one last time and stop the live display
        if context.get("is_started", False):
            try:
                _live = context["live"]
                _lr = getattr(_live, "_live_render", None)
                _old_shape = getattr(_lr, "_shape", None) if _lr is not None else None
                _old_h = (
                    _old_shape[1]
                    if _old_shape is not None and len(_old_shape) >= 2
                    else None
                )
                if hasattr(_live, "_cai_suppress_stop_line"):
                    # Always omit Rich Live.stop()'s trailing console.line() for agent finish: it stacked
                    # with the frozen line ending / panel render and produced two blank rows before tools
                    # or before the sticky pricing footer after the final panel.
                    _live._cai_suppress_stop_line = True
                _live.update(final_content)
                time.sleep(0.1)
                _live.stop()
                if hasattr(_live, "_cai_suppress_stop_line"):
                    _live._cai_suppress_stop_line = False
                # Shorter final frame leaves erased-but-still-visible rows below the new draw.
                if _old_h is not None:
                    _lr_after = getattr(_live, "_live_render", None)
                    _ns = getattr(_lr_after, "_shape", None) if _lr_after is not None else None
                    _new_h = (
                        _ns[1]
                        if _ns is not None and len(_ns) >= 2
                        else None
                    )
                    if _new_h is not None and _old_h > _new_h:
                        _collapse_rich_live_shrink_gap(_live.console, _old_h - _new_h)
            except Exception as e:
                context["error"] = str(e)
                try:
                    _live2 = context["live"]
                    if hasattr(_live2, "_cai_suppress_stop_line"):
                        _live2._cai_suppress_stop_line = False
                    _live2.stop()
                except Exception:
                    pass

        # Pop the markdown theme if we pushed it for the final panel
        if is_final:
            try:
                console.pop_theme()
            except Exception:
                pass

        # Sticky pricing after tool interrupts printed two extra rows here; the next UI
        # (tool stream / cli_print_agent_messages) redraws immediately and erases it anyway.
        if final_stats is not None:
            _print_pricing_footer(final=is_final, framed=is_final)

        return True
    except Exception as e:
        # If there's an error, print it if the context hasn't already tracked one
        if not context.get("error"):
            context["error"] = str(e)

        # Try to stop the live display even if there was an error
        try:
            if context.get("is_started", False) and context.get("live"):
                context["live"].stop()
        except Exception:
            pass

        return False


def cli_print_tool_output(
    tool_name="",
    args="",
    output="",
    call_id=None,
    execution_info=None,
    token_info=None,
    streaming=False,
):
    """
    Print a tool call output to the command line.
    Tool calls always use non-streaming panels for consistent display.
    Similar to cli_print_tool_call but for the output of the tool.

    Args:
        tool_name: Name of the tool
        args: Arguments passed to the tool
        output: The output of the tool
        call_id: Optional call ID for streaming updates
        execution_info: Optional execution information
        token_info: Optional token information with keys:
            - interaction_input_tokens, interaction_output_tokens, interaction_reasoning_tokens
            - total_input_tokens, total_output_tokens, total_reasoning_tokens
            - model: model name string
            - interaction_cost, total_cost: optional cost values
        streaming: Flag indicating if this is part of a streaming output
    """
    import time

    # Compact REPL owns tool rendering in CLI mode.
    if _compact_suppresses_verbose():
        return

    if token_info is not None:
        token_info = enrich_token_info_for_pricing(token_info)

    # If it's an empty output, don't print anything except for streaming sessions
    if not output and not call_id and not streaming:
        return

    # Skip internal setup commands used by execute_code
    if tool_name and tool_name.startswith("_internal_"):
        # These are internal setup commands that should not be displayed
        return

    # Normalize common wrapped text formats, e.g. {"type": "text", "text": "..."}
    # so that we only display the human-readable text portion.
    if isinstance(output, str):
        try:
            parsed_output = json.loads(output)
        except Exception:
            parsed_output = None

        # Single wrapped text item
        if isinstance(parsed_output, dict) and parsed_output.get("type") == "text":
            text_value = parsed_output.get("text")
            if isinstance(text_value, str):
                output = text_value
        # List of wrapped text items
        elif isinstance(parsed_output, list):
            text_items: list[str] = []
            for item in parsed_output:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(
                    item.get("text"), str
                ):
                    text_items.append(item["text"])
            if text_items:
                output = "\n\n".join(text_items)

    # If running in TUI mode, route tool output through DisplayManager to the correct terminal
    # and return early to avoid duplicating output in the CLI console.
    try:
        import os as _os
        if _os.getenv("CAI_TUI_MODE") == "true":
            # Resolve terminal_id from token_info or current TUI context
            terminal_id = None
            if isinstance(token_info, dict):
                terminal_id = token_info.get("terminal_id")
                if not terminal_id and token_info.get("terminal_number"):
                    terminal_id = f"terminal-{token_info['terminal_number']}"
                if not terminal_id:
                    agent_id = token_info.get("agent_id", "")
                    if isinstance(agent_id, str) and agent_id.startswith("P") and agent_id[1:].isdigit():
                        terminal_id = f"terminal-{int(agent_id[1:])}"
            if not terminal_id:
                try:
                    from cai.tui.core.terminal_tracking import get_current_terminal_id as _get_tid
                    from cai.tui.core.execution_context import get_terminal_id_context as _get_tid_ctx
                    terminal_id = _get_tid() or _get_tid_ctx()
                except Exception:
                    terminal_id = None

            if terminal_id:
                try:
                    from cai.tui.display.manager import DisplayManager as _TuiDisplayManager
                    _dm = _TuiDisplayManager()
                    _dm.display_tool_output(
                        terminal_id=terminal_id,
                        tool_name=tool_name,
                        args=args,
                        output=output,
                        execution_info=execution_info,
                        token_info=token_info,
                        streaming=streaming,
                        call_id=call_id,
                    )
                    return
                except Exception:
                    # Fall through to default CLI rendering on any TUI routing error
                    pass
    except Exception:
        pass

    # Keep the original streaming flag - panels should work the same regardless
    # streaming = False  # REMOVED - panels now work consistently

    # DEBUG: CLI tool output visualization
    import os as _debug_os
    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
        print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() CLI MODE:")
        print(f"  tool_name: {tool_name}")
        print(f"  call_id: {call_id}")
        print(f"  output_len: {len(output) if output else 0}")
        print(f"  streaming: {streaming}")

    # ===== CHECK FOR ACTIVE LIVE PANEL TO FINALIZE =====
    # If there's an active Live panel for this call_id and this is a non-streaming call,
    # finalize the Live panel (update to "Completed" and stop it)
    if call_id and not streaming and call_id in _LIVE_STREAMING_PANELS:
        panel_info = _LIVE_STREAMING_PANELS[call_id]
        # Check if it's a Live panel (not a static dict)
        if not isinstance(panel_info, dict):
            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() call_id '{call_id}' has active Live panel - finalizing")
            _finalize_live_panel(call_id, tool_name, args, output, execution_info, token_info)
            return

    # ===== PRIMARY DEDUPLICATION: call_id =====
    # If we have a call_id, use it as absolute deduplication key
    # Once a tool call with this call_id is displayed, NEVER display again
    # Track if this is a new call_id (for multi-tool call support)
    is_new_call_id = False

    # Check if this is a session-related command that should ALWAYS be displayed
    # Detection based ONLY on tool parameters (no regex, no command parsing):
    # - session_id parameter has a real value -> interacting with existing session
    # - interactive parameter is True -> starting new interactive session
    is_session_command = False
    if args and isinstance(args, dict):
        session_id_arg = args.get("session_id")
        interactive_arg = args.get("interactive")

        # session_id has a real value (not None, not empty, not string "None")
        if session_id_arg is not None and session_id_arg != "" and session_id_arg != "None":
            is_session_command = True
        # interactive is explicitly True
        elif interactive_arg is True:
            is_session_command = True

    if is_session_command and _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
        print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() session command detected, skipping deduplication")

    if call_id and not streaming and not is_session_command:
        if not hasattr(cli_print_tool_output, "_displayed_call_ids"):
            cli_print_tool_output._displayed_call_ids = set()

        if call_id in cli_print_tool_output._displayed_call_ids:
            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() SKIP: call_id '{call_id}' already displayed")
            return

        # This is a NEW call_id - mark it for later checks (multi-tool call support)
        is_new_call_id = True

        # Mark as displayed now (before any other checks)
        cli_print_tool_output._displayed_call_ids.add(call_id)

        # Periodic cleanup to prevent unbounded growth
        if len(cli_print_tool_output._displayed_call_ids) > 200:
            # Keep only the most recent 100 call_ids
            cli_print_tool_output._displayed_call_ids = set(list(cli_print_tool_output._displayed_call_ids)[-100:])

        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
            print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() call_id '{call_id}' is NEW, proceeding")

    # Check if we're in parallel mode
    is_parallel_mode = False
    if token_info and isinstance(token_info, dict):
        agent_id = token_info.get("agent_id", "")
        if agent_id and agent_id.startswith("P") and agent_id[1:].isdigit():
            is_parallel_mode = True

    # Special suppression for cat commands that create code files from execute_code
    # We don't want to show the cat command that creates the file
    if (
        tool_name == "cat_command"
        and isinstance(args, dict)
        and not streaming
        and "<< 'EOF'" in args.get("args", "")
    ):
        # This is likely a file creation command from execute_code, suppress it
        return

    # Note: We no longer skip execute_code in non-streaming mode
    # We want to show both code and output panels for all execute_code calls

    # Check if cleanup is in progress
    global _cleanup_in_progress
    if _cleanup_in_progress:
        return

    # Set up global tracker for streaming sessions
    if not hasattr(cli_print_tool_output, "_streaming_sessions"):
        cli_print_tool_output._streaming_sessions = {}

    # NOTE: _seen_calls was removed - duplicate prevention is now handled at the source
    # (openai_chatcompletions.py skips display when streaming is enabled)

    # Track all displayed commands to prevent duplicates with cleanup
    if not hasattr(cli_print_tool_output, "_displayed_commands"):
        cli_print_tool_output._displayed_commands = set()
        cli_print_tool_output._last_cleanup = time.time()

    # Periodic cleanup to prevent memory growth
    current_time = time.time()
    if current_time - cli_print_tool_output._last_cleanup > 300:  # Cleanup every 5 minutes
        # Clear the displayed commands set periodically
        cli_print_tool_output._displayed_commands.clear()
        cli_print_tool_output._last_cleanup = current_time

    # --- Consistent Command Key Generation ---
    # Include agent context from the start to prevent cross-agent duplicates
    agent_context = ""
    if token_info and isinstance(token_info, dict):
        agent_name = token_info.get("agent_name", "")
        agent_id = token_info.get("agent_id", "")
        interaction_counter = token_info.get("interaction_counter", 0)

        # Create agent-specific context
        if agent_id and agent_id.startswith("P"):
            # In parallel mode, use agent_id for uniqueness
            agent_context = f"agent_{agent_id}"
        elif agent_name:
            # In single agent mode, use agent name
            agent_context = f"agent_{agent_name.replace(' ', '_')}"

        # Add interaction counter if available
        if interaction_counter > 0:
            agent_context += f"_turn_{interaction_counter}"

    effective_command_args_str = ""
    if isinstance(args, dict):
        # If args is a dictionary, create a string representation of key arguments
        # First try specific fields that are commonly used
        if "args" in args:
            # For tools that have an 'args' field (like cat_command)
            effective_command_args_str = args.get("args", "")
        elif "command" in args:
# For tools that have a 'command' field (like generic_linux_command)
            effective_command_args_str = args.get("command", "")
        elif "query" in args:
            # For search tools (like shodan_search, make_google_search)
            effective_command_args_str = args.get("query", "")
        else:
            # For other tools, create a JSON representation of all args
            # This ensures each unique call gets a unique key
            effective_command_args_str = json.dumps(args, sort_keys=True)

        # For session commands, also include the session_id to make it unique
        if "command" in args and args.get("session_id"):
            # For async session commands, include the full command to differentiate
            effective_command_args_str = f"{args.get('command', '')}:{effective_command_args_str}"
            # Also include session_id to make it unique per session
            effective_command_args_str += f":session_{args.get('session_id', '')}"
    elif isinstance(args, str):
        # If args is a string, it might be a JSON representation or a plain string.
        try:
            parsed_json_args = json.loads(args)
            if isinstance(parsed_json_args, dict):
                # Parsed as JSON dict, apply same logic as above
                if "args" in parsed_json_args:
                    effective_command_args_str = parsed_json_args.get("args", "")
                elif "command" in parsed_json_args:
                    effective_command_args_str = parsed_json_args.get("command", "")
                elif "query" in parsed_json_args:
                    effective_command_args_str = parsed_json_args.get("query", "")
                else:
                    effective_command_args_str = json.dumps(parsed_json_args, sort_keys=True)

                # For session commands, also include the actual command
                if "command" in parsed_json_args and parsed_json_args.get("session_id"):
                    effective_command_args_str = (
                        f"{parsed_json_args.get('command', '')}:{effective_command_args_str}"
                    )
                    # Also include session_id to make it unique per session
                    effective_command_args_str += (
                        f":session_{parsed_json_args.get('session_id', '')}"
                    )
            else:
                # Parsed as JSON, but not a dict (e.g., a JSON string literal).
                effective_command_args_str = (
                    parsed_json_args if isinstance(parsed_json_args, str) else args
                )
        except json.JSONDecodeError:
            # Not a JSON string, treat 'args' as a plain string.
            effective_command_args_str = args

    # Build command key with agent context
    if agent_context:
        command_key = f"{agent_context}:{tool_name}:{effective_command_args_str}"
    else:
        command_key = f"{tool_name}:{effective_command_args_str}"

    # If args contain a call_counter, append it to make the key unique
    # This allows commands with counters to always display
    if isinstance(args, dict) and "call_counter" in args:
        call_counter = args["call_counter"]
        command_key += f":counter_{call_counter}"

    # For async session inputs, add timestamp to ensure uniqueness
    # This prevents duplicate detection for different commands sent to the same session
    if isinstance(args, dict) and args.get("session_id") and args.get("input_to_session"):
        # Add a timestamp component to make each session input unique
        import time

        command_key += f":ts_{int(time.time() * 1000)}"

    # Special handling for auto_output commands - they should always display
    # even if a similar command was shown before
    if isinstance(args, dict) and args.get("auto_output"):
        # Add auto_output flag to the key to differentiate from manual commands
        command_key += ":auto_output"

    # Note: interaction counter is now included in agent_context above

    # --- End of Command Key Generation ---

    # DEBUG: Show generated command key
    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
        print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() command_key:")
        print(f"  key: {command_key[:150]}{'...' if len(command_key) > 150 else ''}")
        print(f"  agent_context: {agent_context}")

    # NOTE: call_id-based duplicate detection was removed because common.py and
    # openai_chatcompletions.py use DIFFERENT call_ids (common.py generates its own).
    # Duplicate prevention is now handled at the source: openai_chatcompletions.py
    # skips display when streaming is enabled (common.py handles streaming display).

    current_time = time.time()

    # ===== DUPLICATE DETECTION: Output fingerprint =====
    # Secondary check based on normalized output content
    # SKIP for session commands - they should always display even with same output
    if output and not is_session_command:
        # Initialize output hash tracker if not exists
        if not hasattr(cli_print_tool_output, "_output_hashes"):
            cli_print_tool_output._output_hashes = {}

        # Normalize output to remove variable parts like timestamps
        output_str = str(output)
        # Remove common timestamp patterns from HTTP responses
        import re
        normalized_output = re.sub(
            r'Date: [A-Za-z]{3}, \d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} GMT',
            'Date: TIMESTAMP',
            output_str
        )
        # Remove other timestamp patterns
        normalized_output = re.sub(
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
            'TIMESTAMP',
            normalized_output
        )

        # Create fingerprint from normalized output
        output_fingerprint = f"{tool_name}:{len(normalized_output)}:{normalized_output[:100]}:{normalized_output[-100:] if len(normalized_output) > 100 else ''}"

        if output_fingerprint in cli_print_tool_output._output_hashes:
            last_time = cli_print_tool_output._output_hashes[output_fingerprint]
            # If same output was shown in last 3 seconds, it's likely a duplicate
            if current_time - last_time < 3.0:
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() SKIP: output fingerprint duplicate (time_since={current_time - last_time:.2f}s)")
                return

        cli_print_tool_output._output_hashes[output_fingerprint] = current_time

        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
            print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() output fingerprint NEW, proceeding")

        # Periodic cleanup of old hashes (keep only recent ones)
        if len(cli_print_tool_output._output_hashes) > 100:
            # Remove entries older than 30 seconds
            cli_print_tool_output._output_hashes = {
                k: v for k, v in cli_print_tool_output._output_hashes.items()
                if current_time - v < 30.0
            }

    # Check for duplicate display conditions
    if streaming:
        # For streaming updates, track and update the single streaming session
        if call_id:
            # Check if we're in parallel mode first
            is_parallel = is_parallel_session()

            # DEBUG: Streaming path
            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                is_final = execution_info.get("is_final", False) if execution_info else False
                in_panels = call_id in _LIVE_STREAMING_PANELS
                in_sessions = hasattr(cli_print_tool_output, "_streaming_sessions") and call_id in cli_print_tool_output._streaming_sessions
                print(f"[DEBUG_TOOLS_VIZ] STREAMING PATH:")
                print(f"  call_id: {call_id}")
                print(f"  is_parallel: {is_parallel}")
                print(f"  is_final: {is_final}")
                print(f"  in _LIVE_STREAMING_PANELS: {in_panels}")
                print(f"  in _streaming_sessions: {in_sessions}")

            # If this is a new streaming session, record it
            if call_id not in cli_print_tool_output._streaming_sessions:
                # Check if this tool should be grouped with others (non-parallel streaming mode)
                group_id = None
                if not is_parallel:
                    group_id = _find_or_create_tool_group(call_id, tool_name, args, token_info)
                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        if group_id:
                            group_info = _GROUPED_STREAMING_TOOLS.get(group_id, {})
                            tool_count = len(group_info.get("tools", {}))
                            print(f"[DEBUG_TOOLS_VIZ] Tool {call_id} joined group {group_id} (now {tool_count} tools)")

                cli_print_tool_output._streaming_sessions[call_id] = {
                    "tool_name": tool_name,
                    "args": args,  # Store original args for display formatting
                    "buffer": output if output else "",
                    "start_time": time.time(),
                    "last_update": time.time(),
                    "command_key": command_key,  # Store the generated key
                    "is_complete": False,
                    "agent_name": token_info.get("agent_name") if token_info else None,
                    "current_output": output if output else "",  # Track current output for cleanup
                    "group_id": group_id,  # Track group membership
                }
                # Add the command key to displayed commands
                if command_key not in cli_print_tool_output._displayed_commands:
                    cli_print_tool_output._displayed_commands.add(command_key)

                # Special case: If this is execute_code in normal streaming mode with "Executing code..." message,
                # skip showing the panel since we already showed the code panel
                if (
                    tool_name == "execute_code"
                    and not is_parallel
                    and isinstance(args, dict)
                    and "code" in args
                    and output == "Executing code..."
                ):
                    return

                # If we're in a group, defer ALL panel display until completion
                # Multiple tools in same turn = no panels until all complete
                if group_id:
                    group_info = _GROUPED_STREAMING_TOOLS.get(group_id, {})
                    tool_count = len(group_info.get("tools", {}))
                    is_final = execution_info and execution_info.get("is_final", False)

                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        print(f"[DEBUG_TOOLS_VIZ] Tool {call_id[:8]} in group with {tool_count} tools (is_final={is_final})")

                    # Update the tool's output in the group
                    if call_id in group_info.get("tools", {}):
                        group_info["tools"][call_id]["output"] = output
                        # Update args to refresh countdown display
                        if args:
                            group_info["tools"][call_id]["args"] = args
                        if execution_info:
                            group_info["tools"][call_id]["execution_info"] = execution_info
                            if is_final:
                                group_info["tools"][call_id]["is_complete"] = True
                        if token_info:
                            group_info["tools"][call_id]["token_info"] = token_info

                    # On is_final, check if all tools in group are done
                    if is_final:
                        all_complete = all(t.get("is_complete", False) for t in group_info["tools"].values())
                        if all_complete:
                            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                print(f"[DEBUG_TOOLS_VIZ] All {len(group_info['tools'])} tools complete - printing individual panels")
                            _finalize_tool_group(group_id)
                            return
                        else:
                            # Not all complete yet - still update the panel to show progress
                            _update_tool_group(group_id, call_id, output, execution_info, token_info, args)
                            return

                    # Show combined Live panel for all tools in group while running
                    _update_tool_group(group_id, call_id, output, execution_info, token_info, args)
                    return
            else:
                # Update the existing session
                session = cli_print_tool_output._streaming_sessions[call_id]
                # Always replace buffer with latest output for consistency
                session["buffer"] = output
                session["current_output"] = output  # Update current output for cleanup
                session["last_update"] = time.time()
                is_final = execution_info and execution_info.get("is_final", False)
                if is_final:
                    session["is_complete"] = True

                # Check if this tool is part of a group
                group_id = session.get("group_id")
                if group_id:
                    group_info = _GROUPED_STREAMING_TOOLS.get(group_id, {})
                    if group_info:
                        # Update the tool's output in the group
                        if call_id in group_info.get("tools", {}):
                            group_info["tools"][call_id]["output"] = output
                            # Update args to refresh countdown display
                            if args:
                                group_info["tools"][call_id]["args"] = args
                            if execution_info:
                                group_info["tools"][call_id]["execution_info"] = execution_info
                                if is_final:
                                    group_info["tools"][call_id]["is_complete"] = True
                            if token_info:
                                group_info["tools"][call_id]["token_info"] = token_info

                        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                            complete_count = sum(1 for t in group_info["tools"].values() if t.get("is_complete"))
                            print(f"[DEBUG_TOOLS_VIZ] Tool {call_id[:8]} update - {complete_count}/{len(group_info['tools'])} complete, is_final={is_final}")

                        # On is_final, check if all tools in group are done
                        if is_final:
                            all_complete = all(t.get("is_complete", False) for t in group_info["tools"].values())
                            if all_complete:
                                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                    print(f"[DEBUG_TOOLS_VIZ] All {len(group_info['tools'])} tools complete - printing individual panels")
                                # All tools complete - finalize the group (prints individual green panels)
                                _finalize_tool_group(group_id)
                                return
                            else:
                                # Not all complete yet - still update the panel to show progress
                                _update_tool_group(group_id, call_id, output, execution_info, token_info, args)
                                return

                        # Show combined Live panel for all tools while running
                        _update_tool_group(group_id, call_id, output, execution_info, token_info, args)
                        return

                # In parallel mode, if we already have a static panel, don't continue
                # This prevents duplicate panels from being created on updates
                if is_parallel and call_id in _LIVE_STREAMING_PANELS:
                    panel_info = _LIVE_STREAMING_PANELS[call_id]
                    if isinstance(panel_info, dict) and panel_info.get("type") == "static":
                        # Update stored info but don't print anything
                        panel_info["last_output"] = output
                        panel_info["last_update"] = time.time()
                        return

            # For streaming outputs, we'll use Rich Live panel if available
            try:
                from rich.console import Console
                from rich.live import Live
                from rich.text import Text

                # Create flat content for streaming display
                current_args_for_display = cli_print_tool_output._streaming_sessions[call_id][
                    "args"
                ]
                header, content = _create_tool_panel_content(
                    tool_name,
                    current_args_for_display,
                    cli_print_tool_output._streaming_sessions[call_id]["buffer"],
                    execution_info,
                    token_info,
                )

                # Flat tool body + optional [CAI] wait line + pricing footer inside Live.
                try:
                    panel = _group_tool_body_with_pricing_footer(content)
                except Exception:
                    panel = content

                # Check if we're in parallel execution mode
                is_parallel = is_parallel_session()

                # Check if we're in a container environment
                is_container = bool(os.getenv("CAI_ACTIVE_CONTAINER", ""))

                # If we already have a live panel for this call_id, update it
                if call_id in _LIVE_STREAMING_PANELS:
                    with _PANEL_UPDATE_LOCK:
                        panel_info = _LIVE_STREAMING_PANELS[call_id]

                        # Handle static panels in parallel mode or container mode
                        # In parallel mode or containers, we DON'T refresh static panels to avoid duplicates
                        # The panel was already printed when first created, and refreshing
                        # causes duplicate panels because cursor movement doesn't work reliably
                        if isinstance(panel_info, dict) and panel_info.get("type") == "static":
                            # Update stored info for tracking
                            panel_info["last_output"] = output
                            panel_info["last_update"] = time.time()
                            panel_info["updates_suppressed"] = (
                                panel_info.get("updates_suppressed", 0) + 1
                            )

                            # For parallel mode or container mode, only update if this is the final update with different content
                            if execution_info and execution_info.get("is_final", False):
                                # Debug output
                                if os.getenv("CAI_DEBUG_STREAMING"):
                                    print(f"\n[DEBUG] Final update check:")
                                    print(f"  output: {repr(output[:50])}...")
                                    print(
                                        f"  initial_output: {repr(panel_info.get('initial_output', '')[:50])}..."
                                    )
                                    print(
                                        f"  outputs_equal: {output == panel_info.get('initial_output', '')}"
                                    )
                                    print(f"  final_shown: {panel_info.get('final_shown', False)}")

                                # Check if we've already shown the final panel
                                if panel_info.get("final_shown", False):
                                    # Already shown final, don't duplicate
                                    return

                                # Mark that we've processed the final update
                                panel_info["final_shown"] = True
                                panel_info["is_complete"] = True
                                if call_id in cli_print_tool_output._streaming_sessions:
                                    cli_print_tool_output._streaming_sessions[call_id][
                                        "is_complete"
                                    ] = True

                                # Create a final GREEN panel to show completion
                                # Enrich token_info with COST_TRACKER values if needed
                                enriched_token_info = token_info or {}
                                if not enriched_token_info.get("model"):
                                    enriched_token_info["model"] = os.environ.get("CAI_MODEL", "")
                                if not enriched_token_info.get("interaction_input_tokens"):
                                    enriched_token_info["interaction_input_tokens"] = getattr(COST_TRACKER, "interaction_input_tokens", 0)
                                    enriched_token_info["interaction_output_tokens"] = getattr(COST_TRACKER, "interaction_output_tokens", 0)
                                    enriched_token_info["interaction_reasoning_tokens"] = getattr(COST_TRACKER, "interaction_reasoning_tokens", 0)
                                    enriched_token_info["cache_read_tokens"] = getattr(COST_TRACKER, "cache_read_tokens", 0)
                                    enriched_token_info["cache_creation_tokens"] = getattr(COST_TRACKER, "cache_creation_tokens", 0)
                                    enriched_token_info["interaction_cost"] = getattr(COST_TRACKER, "last_interaction_cost", 0.0)
                                    enriched_token_info["total_cost"] = getattr(COST_TRACKER, "last_total_cost", 0.0)
                                    enriched_token_info["total_input_tokens"] = getattr(COST_TRACKER, "current_agent_input_tokens", 0)
                                    enriched_token_info["total_output_tokens"] = getattr(COST_TRACKER, "current_agent_output_tokens", 0)
                                enriched_token_info = enrich_token_info_for_pricing(enriched_token_info)

                                # Create final flat content
                                final_header, final_content = _create_tool_panel_content(
                                    tool_name, args, output, execution_info, enriched_token_info
                                )

                                # Print flat content (no Panel box) — use shared CLI console
                                console.print(final_content)
                                console.print()
                                _print_cli_gap_after_completed_tool(True, execution_info, call_id)

                                # Clean up the panel tracking
                                del _LIVE_STREAMING_PANELS[call_id]
                                return

                            # Always return early for static panels - no further processing needed
                            return
                        else:
                            # Handle Live panels (non-parallel mode)
                            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                print(f"[DEBUG_TOOLS_VIZ] Updating Live panel (non-parallel)")
                            try:
                                panel_info.update(panel)
                            except Exception as e:
                                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                    print(f"[DEBUG_TOOLS_VIZ] Live panel update FAILED: {e}")
                                # If update fails, try to clean up
                                try:
                                    panel_info.stop()
                                except Exception:
                                    pass
                                del _LIVE_STREAMING_PANELS[call_id]

                    # If this is the final update, handle cleanup based on panel type
                    if execution_info and execution_info.get("is_final", False):
                        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                            print(f"[DEBUG_TOOLS_VIZ] FINAL UPDATE - handling cleanup")
                            print(f"  call_id in _LIVE_STREAMING_PANELS: {call_id in _LIVE_STREAMING_PANELS}")
                        with _PANEL_UPDATE_LOCK:
                            if call_id in _LIVE_STREAMING_PANELS:
                                panel_info = _LIVE_STREAMING_PANELS[call_id]
                                is_static = isinstance(panel_info, dict) and panel_info.get("type") == "static"
                                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                    print(f"  panel type: {'static' if is_static else 'Live'}")
                                if is_static:
                                    # For static panels in parallel mode:
                                    # 1. The initial panel was already printed when created
                                    # 2. We've been suppressing updates throughout
                                    # 3. Just clean up tracking without printing

                                    # Clean up tracking entry
                                    del _LIVE_STREAMING_PANELS[call_id]

                                    # Mark session as complete
                                    if call_id in cli_print_tool_output._streaming_sessions:
                                        cli_print_tool_output._streaming_sessions[call_id][
                                            "is_complete"
                                        ] = True

                                    _print_cli_gap_after_completed_tool(True, execution_info, call_id)
                                    # Always return early for static panels
                                    return
                                else:
                                    # For Live panels, update with final panel and stop
                                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                        print(f"[DEBUG_TOOLS_VIZ] Stopping Live panel with final update")
                                    try:
                                        # Update the live display with the final panel
                                        panel_info.update(panel)

                                        # Give a brief moment for the update to render
                                        time.sleep(0.1)

                                        # Stop the live display - with transient=False it will persist.
                                        # No extra console.print() gap here: Live.stop() already leaves the
                                        # cursor on a new line; adding _print_cli_gap stacked a second blank row.
                                        panel_info.stop()
                                        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                            print(f"[DEBUG_TOOLS_VIZ] Live panel stopped successfully")
                                    except Exception as e:
                                        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                            print(f"[DEBUG_TOOLS_VIZ] Live panel stop FAILED: {e}")
                                    del _LIVE_STREAMING_PANELS[call_id]
                            else:
                                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                    print(f"[DEBUG_TOOLS_VIZ] WARNING: is_final but call_id NOT in _LIVE_STREAMING_PANELS")
                else:
                    # Create a new live panel with parallel execution awareness
                    with _PANEL_UPDATE_LOCK:
                        # Check if we're in parallel execution mode
                        is_parallel = is_parallel_session()

                        # Check if we're in a container environment
                        is_container = bool(os.getenv("CAI_ACTIVE_CONTAINER", ""))

                        # In parallel mode, use static panels
                        # For container mode, use Live panels to allow real-time updates
                        if is_parallel:
                            # In parallel mode, use static panels to avoid Live context conflicts
                            # Check if we already printed this panel (shouldn't happen but be safe)
                            if call_id not in _LIVE_STREAMING_PANELS:
                                # If the tool already has final output on the first chunk (typical for fast
                                # local commands), print once. Otherwise we would print "running" then
                                # print again on is_final — stacking extra blank lines between tool blocks.
                                if execution_info and execution_info.get("is_final", False):
                                    # Final snapshot: body only (no embedded pricing footer) — avoids
                                    # two extra lines + another implicit newline before the next block.
                                    console.print(content)
                                    _print_cli_gap_after_completed_tool(True, execution_info, call_id)
                                    _LIVE_STREAMING_PANELS[call_id] = {
                                        "type": "static",
                                        "displayed": True,
                                        "last_update": time.time(),
                                        "last_output": output,
                                        "initial_output": output,
                                        "initial_panel_printed": True,
                                        "tool_name": tool_name,
                                        "command_key": command_key,
                                        "is_container": is_container,
                                        "final_shown": True,
                                        "is_complete": True,
                                    }
                                else:
                                    # Show the initial panel (still running)
                                    console.print(panel)
                                    _LIVE_STREAMING_PANELS[call_id] = {
                                        "type": "static",
                                        "displayed": True,
                                        "last_update": time.time(),
                                        "last_output": output,
                                        "initial_output": output,
                                        "initial_panel_printed": True,
                                        "tool_name": tool_name,
                                        "command_key": command_key,
                                        "is_container": is_container,
                                        "final_shown": False,
                                    }
                        else:
                            # In single agent mode without container, use Live panel
                            # First check if we already have a panel for this call_id
                            if call_id in _LIVE_STREAMING_PANELS:
                                panel_info = _LIVE_STREAMING_PANELS[call_id]
                                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                    panel_type = panel_info.get("type", "Live") if isinstance(panel_info, dict) else "Live"
                                    print(f"[DEBUG_TOOLS_VIZ] Panel already exists for call_id {call_id}, type: {panel_type}")
                                # Handle existing panels
                                if isinstance(panel_info, dict):
                                    # Static or fallback panel - skip
                                    pass
                                else:
                                    # Live panel - update it
                                    try:
                                        panel_info.update(panel)
                                    except Exception as e:
                                        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                            print(f"[DEBUG_TOOLS_VIZ] Live panel update failed: {e}")
                            else:
                                # Check if there's already an active Live panel (not static)
                                # Rich can't handle multiple Live contexts simultaneously
                                has_active_live = any(
                                    not isinstance(p, dict) for p in _LIVE_STREAMING_PANELS.values()
                                )

                                if has_active_live:
                                    # Another Live panel is active - use static panel to avoid corruption
                                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                        print(f"[DEBUG_TOOLS_VIZ] Another Live panel active - using static panel for call_id: {call_id}")
                                    console.print(panel)
                                    _LIVE_STREAMING_PANELS[call_id] = {
                                        "type": "static",
                                        "displayed": True,
                                        "last_update": time.time(),
                                        "last_output": output,
                                        "initial_output": output,
                                        "initial_panel_printed": True,
                                        "tool_name": tool_name,
                                        "command_key": command_key,
                                    }
                                else:
                                    # Single-chunk completion (typical for local commands): skip Live entirely.
                                    # Live.start/stop was adding an extra vertical gap vs one static print + gap.
                                    if execution_info and execution_info.get("is_final", False):
                                        _erase_pricing_footer()
                                        console.print(content)
                                        _print_cli_gap_after_completed_tool(True, execution_info, call_id)
                                        _LIVE_STREAMING_PANELS[call_id] = {
                                            "type": "static",
                                            "displayed": True,
                                            "last_update": time.time(),
                                            "last_output": output,
                                            "initial_output": output,
                                            "initial_panel_printed": True,
                                            "tool_name": tool_name,
                                            "command_key": command_key,
                                            "is_container": False,
                                            "final_shown": True,
                                            "is_complete": True,
                                        }
                                    else:
                                        # Create new Live panel (multi-chunk / long-running tool output)
                                        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                            print(f"[DEBUG_TOOLS_VIZ] Creating NEW Live panel for call_id: {call_id}")
                                        # Dedicated Rich console for this Live (do not shadow module `console`)
                                        _live_tool_console = Console()
                                        live = Live(
                                            panel, console=_live_tool_console, refresh_per_second=4, auto_refresh=True,
                                            transient=False  # Keep panel visible after stopping
                                        )
                                        # Start and store the live panel
                                        try:
                                            # Erase sticky footer before tool streaming Live takes over
                                            _erase_pricing_footer()
                                            live.start()
                                            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                                print(f"[DEBUG_TOOLS_VIZ] Live panel started successfully")
                                            _LIVE_STREAMING_PANELS[call_id] = live
                                        except Exception as e:
                                            # If we can't start the live panel, fall back to simple output
                                            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                                                import traceback
                                                print(f"[DEBUG_TOOLS_VIZ] Live panel FAILED to start: {type(e).__name__}: {e}")
                                                print(f"[DEBUG_TOOLS_VIZ] Full traceback:")
                                                traceback.print_exc()
                                            # Mark as a static fallback panel to prevent repeated attempts
                                            _LIVE_STREAMING_PANELS[call_id] = {
                                                "type": "static_fallback",
                                                "displayed": True,
                                                "last_update": time.time(),
                                                "last_output": output,
                                            }
                                            _print_simple_tool_output(
                                                tool_name, args, output, execution_info, token_info
                                            )
                                            _print_cli_gap_after_completed_tool(True, execution_info, call_id)

                # Return early for streaming updates
                return

            except (ImportError, Exception) as outer_e:
                # Fall back to simple updates without Rich
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    import traceback
                    print(f"[DEBUG_TOOLS_VIZ] OUTER EXCEPTION caught: {type(outer_e).__name__}: {outer_e}")
                    print(f"[DEBUG_TOOLS_VIZ] Full traceback:")
                    traceback.print_exc()

                # If we had a live panel, try to clean it up
                if call_id in _LIVE_STREAMING_PANELS:
                    try:
                        _LIVE_STREAMING_PANELS[call_id].stop()
                    except Exception:
                        pass
                    del _LIVE_STREAMING_PANELS[call_id]

                # Use simple output
                _print_simple_tool_output(tool_name, args, output, execution_info, token_info)
                _print_cli_gap_after_completed_tool(streaming, execution_info, call_id)
                return

    # Initialize is_first_display for later use
    is_first_display = False

    # Define streaming_enabled at function scope to avoid NameError
    streaming_enabled = is_tool_streaming_enabled()

    if not streaming:

        # Initialize command display times tracker if not exists
        if not hasattr(cli_print_tool_output, "_command_display_times"):
            cli_print_tool_output._command_display_times = {}

        # Check if this command has been displayed before
        if command_key in cli_print_tool_output._displayed_commands:
            # Get the last display time for this command
            last_display = cli_print_tool_output._command_display_times.get(command_key, 0)
            current_time = time.time()

            if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() command_key already displayed:")
                print(f"  time_since_last: {current_time - last_display:.2f}s")

            # In non-streaming mode, we need stricter duplicate detection
            # If the same command was displayed less than 0.5 seconds ago, it's a duplicate
            # BUT: If this is a new call_id (multi-tool call), don't skip - each tool call is unique
            # BUT: Session commands should NEVER be skipped - they need to show updated output
            if not streaming_enabled and current_time - last_display < 0.5:
                if is_session_command:
                    # Session commands always display - they poll for new output
                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() NOT skipping: is_session_command=True")
                elif is_new_call_id:
                    # This is a new unique tool call (multi-tool call scenario)
                    # Don't skip based on command_key timing
                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() NOT skipping: is_new_call_id=True (multi-tool call)")
                else:
                    if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                        print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() SKIP: command_key duplicate (time < 0.5s)")
                    return

            # Only skip if the exact same panel was already shown
            # Don't skip based on CAI_STREAM setting alone
            # This ensures panels always appear regardless of streaming mode
            pass  # Don't skip any panels based on streaming status

            # For empty output, always skip
            if not output:
                return

        # Check if this is first time display before adding to displayed commands
        is_first_display = command_key not in cli_print_tool_output._displayed_commands

        # Add to displayed commands since we're going to show it
        cli_print_tool_output._displayed_commands.add(command_key)

    # NOTE: Duplicate prevention for streaming vs non-streaming is now handled at the source
    # (openai_chatcompletions.py skips display when streaming is enabled for command tools)

    # Check if execute_code already showed special output in streaming
    if tool_name == "execute_code" and call_id and not streaming:
        # Check if special output was already shown during streaming
        if (
            hasattr(cli_print_tool_output, "_streaming_sessions")
            and call_id in cli_print_tool_output._streaming_sessions
            and cli_print_tool_output._streaming_sessions[call_id].get(
                "special_output_shown", False
            )
        ):
            # Special output was already shown, skip duplicate display
            return

    # Special handling for execute_code in non-streaming mode (both parallel and normal)
    if tool_name == "execute_code" and not streaming and isinstance(args, dict):
        # Don't show panels here for execute_code in non-streaming mode
        # The code panel is already shown in start_tool_streaming
        # The output panel will be shown in finish_tool_streaming
        # This prevents duplicate panels
        pass

    # ── Flat-style tool output (no panels/boxes) ───────────────────────
    try:
        from rich.text import Text

        # Clean args for display (remove internal counters and flags)
        display_args = args
        if isinstance(args, dict):
            display_args = {
                k: v for k, v in args.items() if k not in ["call_counter", "input_to_session"]
            }

        # Build flat header+body via _create_tool_panel_content
        header, content = _create_tool_panel_content(
            tool_name, display_args, output, execution_info, token_info
        )

        # Debug
        if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
            print(f"[DEBUG_TOOLS_VIZ] cli_print_tool_output() PRINTING FLAT:")
            print(f"  tool_name: {tool_name}")
            print(f"  is_first_display: {is_first_display}")
            print(f"  streaming: {streaming}")

        # Erase sticky footer before printing new tool content
        if not streaming:
            _erase_pricing_footer()

        if not streaming:
            render_guard_key = _build_tool_render_guard_key(
                tool_name,
                display_args,
                output,
                call_id,
                is_session_command=is_session_command,
                is_parallel_mode=is_parallel_mode,
            )
            if _should_skip_tool_render(render_guard_key):
                if _debug_os.getenv("CAI_DEBUG_TOOLS_VIZ") == "true":
                    print("[DEBUG_TOOLS_VIZ] cli_print_tool_output() SKIP: render guard duplicate")
                return

        # Print the flat content (header + indented output + token info)
        console.print(content)
        _print_cli_gap_after_completed_tool(streaming, execution_info, call_id)

        # No footer here — only agent messages print the footer to keep
        # the output clean between tools.

        # Track display time
        if not streaming and command_key:
            cli_print_tool_output._command_display_times[command_key] = time.time()

    except (ImportError, Exception):
        _print_simple_tool_output(tool_name, args, output, execution_info, token_info)
        _print_cli_gap_after_completed_tool(streaming, execution_info, call_id)
        if not streaming and command_key:
            cli_print_tool_output._command_display_times[command_key] = time.time()


def start_tool_streaming(tool_name, args, call_id=None, token_info=None):
    """
    Start a streaming tool execution session.
    This allows for progressive updates during tool execution.

    Args:
        tool_name: Name of the tool being executed
        args: Arguments to the tool (dictionary or string)
        call_id: Optional call ID for this execution. If not provided, one will be generated.

    Returns:
        call_id: The call ID for this streaming session (can be used for updates)
    """
    import time

    # Skip internal setup commands used by execute_code
    if tool_name and tool_name.startswith("_internal_"):
        # These are internal setup commands that should not be displayed
        # Just return a dummy call_id
        return f"internal_{str(uuid.uuid4())[:8]}"

    # Special handling for file creation commands from execute_code
    if tool_name == "_internal_file_creation":
        return f"file_create_{str(uuid.uuid4())[:8]}"

    # Compact REPL owns tool rendering in CLI mode. Still return a stable
    # call_id so downstream update_/finish_tool_streaming wiring stays valid.
    if _compact_suppresses_verbose():
        return call_id or f"compact_{uuid.uuid4().hex[:8]}"

    # Check if we're in parallel mode by looking at agent_id
    is_parallel = False
    if token_info and isinstance(token_info, dict):
        agent_id = token_info.get("agent_id", "")
        # In parallel mode, agent_id has format P1, P2, etc.
        if agent_id and agent_id.startswith("P") and agent_id[1:].isdigit():
            is_parallel = True

    # Special handling for execute_code in parallel mode - show code panel first
    if tool_name == "execute_code" and is_parallel and isinstance(args, dict) and "code" in args:
        # For execute_code in parallel mode, show the code panel first
        if not call_id:
            call_id = f"exec_{str(uuid.uuid4())[:8]}"

        # Track that execute_code was used by this parallel agent
        # This helps suppress duplicate output in the agent's response
        if token_info and isinstance(token_info, dict):
            agent_name = token_info.get("agent_name", "")
            if agent_name:
                if not hasattr(start_tool_streaming, "_parallel_execute_code_agents"):
                    start_tool_streaming._parallel_execute_code_agents = set()
                start_tool_streaming._parallel_execute_code_agents.add(agent_name)

        # Show code output in flat style (parallel mode)
        from rich.console import Console, Group
        from rich.syntax import Syntax
        from rich.text import Text

        console = Console()

        # Get agent name from token_info
        agent_name = token_info.get("agent_name", "Agent") if token_info else "Agent"

        # Extract code and language
        code = args.get("code", "")
        language = args.get("language", "python")
        filename = args.get("filename", "exploit")

        # Determine file extension based on language
        extensions = {
            "python": "py", "php": "php", "bash": "sh", "shell": "sh",
            "ruby": "rb", "perl": "pl", "golang": "go", "go": "go",
            "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
            "rust": "rs", "csharp": "cs", "cs": "cs", "java": "java",
            "kotlin": "kt", "c": "c", "cpp": "cpp", "c++": "cpp",
        }
        ext = extensions.get(language, "txt")

        # Get workspace directory
        workspace = args.get("workspace", "")
        environment = args.get("environment", "")

        # Build full path
        import os

        if environment == "Container" and workspace:
            full_path = f"{workspace}/{filename}.{ext}"
        elif workspace:
            cwd = os.getcwd()
            if workspace == os.path.basename(cwd):
                full_path = os.path.join(cwd, f"{filename}.{ext}")
            else:
                full_path = f"{workspace}/{filename}.{ext}"
        else:
            full_path = os.path.join(os.getcwd(), f"{filename}.{ext}")

        # Flat code output
        code_syntax = Syntax(
            code, language, theme="monokai", line_numbers=True,
            background_color="#272822", indent_guides=True, word_wrap=True,
        )
        code_header = Text()
        code_header.append("• ", style=CAI_GREEN)
        code_header.append(f"{agent_name}", style=f"bold {CAI_GREEN}")
        code_header.append(f" - Code saved to: ", style="dim")
        code_header.append(f"{full_path}", style="yellow")
        console.print(Group(code_header, code_syntax))

        # Mark that code panel was shown
        if not hasattr(cli_print_tool_output, "_streaming_sessions"):
            cli_print_tool_output._streaming_sessions = {}
        if call_id not in cli_print_tool_output._streaming_sessions:
            cli_print_tool_output._streaming_sessions[call_id] = {}
        cli_print_tool_output._streaming_sessions[call_id]["code_panel_shown"] = True

        # Don't show additional panel - the code panel is enough

        return call_id

    # Generate a command key to check for duplicates - match format used in cli_print_tool_output
    # Include agent context from the start for consistency
    agent_context = ""
    if token_info and isinstance(token_info, dict):
        agent_name = token_info.get("agent_name", "")
        agent_id = token_info.get("agent_id", "")
        interaction_counter = token_info.get("interaction_counter", 0)

        if agent_id and agent_id.startswith("P"):
            agent_context = f"agent_{agent_id}"
        elif agent_name:
            agent_context = f"agent_{agent_name.replace(' ', '_')}"

        if interaction_counter > 0:
            agent_context += f"_turn_{interaction_counter}"

    # Build command key consistently with cli_print_tool_output
    if isinstance(args, dict):
        cmd = args.get("command", "")
        cmd_args = args.get("args", "")
        effective_args = cmd_args
    else:
        effective_args = str(args)

    if agent_context:
        command_key = f"{agent_context}:{tool_name}:{effective_args}"
    else:
        command_key = f"{tool_name}:{effective_args}"

    # Check if we've already seen this exact command recently
    if not hasattr(start_tool_streaming, "_recent_commands"):
        start_tool_streaming._recent_commands = {}

    # If we have an existing active streaming session for this command, reuse its call_id
    # This prevents duplicate panels when the same command runs multiple times
    for existing_call_id, info in list(start_tool_streaming._recent_commands.items()):
        # Only consider recent commands (last 10 seconds)
        timestamp = info.get("timestamp", 0)
        if time.time() - timestamp < 10.0:
            existing_command_key = info.get("command_key", "")
            # Get the existing session info if available
            if (
                hasattr(cli_print_tool_output, "_streaming_sessions")
                and existing_call_id in cli_print_tool_output._streaming_sessions
            ):
                session = cli_print_tool_output._streaming_sessions[existing_call_id]
                # If this is the same command and not complete, reuse the call_id
                if existing_command_key == command_key and not session.get("is_complete", False):
                    return existing_call_id

    # Generate a call_id if not provided
    if not call_id:
        cmd_part = ""
        if isinstance(args, dict) and "command" in args:
            cmd_part = f"{args['command']}_"
        call_id = f"cmd_{cmd_part}{str(uuid.uuid4())[:8]}"

    # Track this call_id with command key for better duplicate detection
    start_tool_streaming._recent_commands[call_id] = {
        "timestamp": time.time(),
        "command_key": command_key,
    }

    # Cleanup old entries to prevent memory growth
    current_time = time.time()
    start_tool_streaming._recent_commands = {
        k: v
        for k, v in start_tool_streaming._recent_commands.items()
        if current_time - v.get("timestamp", 0) < 30  # Keep entries from last 30 seconds
    }

    # Special handling for execute_code - show code output immediately
    if tool_name == "execute_code" and isinstance(args, dict) and "code" in args:
        from rich.console import Console, Group
        from rich.syntax import Syntax
        from rich.text import Text

        console = Console()

        # Get agent name from token_info
        agent_name = token_info.get("agent_name", "Agent") if token_info else "Agent"

        # Extract code and language
        code = args.get("code", "")
        language = args.get("language", "python")
        filename = args.get("filename", "exploit")

        # Determine file extension based on language
        extensions = {
            "python": "py", "php": "php", "bash": "sh", "shell": "sh",
            "ruby": "rb", "perl": "pl", "golang": "go", "go": "go",
            "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
            "rust": "rs", "csharp": "cs", "cs": "cs", "java": "java",
            "kotlin": "kt", "c": "c", "cpp": "cpp", "c++": "cpp",
        }
        ext = extensions.get(language, "txt")

        # Get workspace directory
        workspace = args.get("workspace", "")
        environment = args.get("environment", "")

        # Build full path
        import os

        if environment == "Container" and workspace:
            full_path = f"{workspace}/{filename}.{ext}"
        elif workspace:
            cwd = os.getcwd()
            if workspace == os.path.basename(cwd):
                full_path = os.path.join(cwd, f"{filename}.{ext}")
            else:
                full_path = f"{workspace}/{filename}.{ext}"
        else:
            full_path = os.path.join(os.getcwd(), f"{filename}.{ext}")

        # Flat code output
        code_syntax = Syntax(
            code, language, theme="monokai", line_numbers=True,
            background_color="#272822", indent_guides=True, word_wrap=True,
        )
        code_header = Text()
        code_header.append("• ", style=CAI_GREEN)
        code_header.append(f"{agent_name}", style=f"bold {CAI_GREEN}")
        code_header.append(f" - Code saved to: ", style="dim")
        code_header.append(f"{full_path}", style="yellow")
        console.print(Group(code_header, code_syntax))

        # Mark that code panel was shown
        if not hasattr(cli_print_tool_output, "_streaming_sessions"):
            cli_print_tool_output._streaming_sessions = {}
        if call_id not in cli_print_tool_output._streaming_sessions:
            cli_print_tool_output._streaming_sessions[call_id] = {}
        cli_print_tool_output._streaming_sessions[call_id]["code_panel_shown"] = True

        # Don't show additional panel - the code panel is enough
    else:
        # Show initial message with "Starting..." output
        # In parallel mode, customize the initial message
        initial_message = "Starting tool execution..."
        if is_parallel and tool_name == "generic_linux_command" and isinstance(args, dict):
            command = args.get("command", "")
            cmd_args = args.get("args", "")
            if command:
                initial_message = f"Executing: {command} {cmd_args}".strip()

        cli_print_tool_output(
            tool_name=tool_name,
            args=args,
            output=initial_message,
            call_id=call_id,
            execution_info={"status": "running", "start_time": time.time()},
            token_info=token_info,
            streaming=True,
        )

    return call_id


# Add a function to update a streaming tool execution
def update_tool_streaming(tool_name, args, output, call_id, token_info=None):
    """
    Update a streaming tool execution with new output.

    Args:
        tool_name: Name of the tool being executed
        args: Arguments to the tool (dictionary or string)
        output: New output to display
        call_id: The call ID for this streaming session

    Returns:
        None
    """
    # Compact REPL owns tool rendering in CLI mode.
    if _compact_suppresses_verbose():
        return

    # Skip internal setup commands used by execute_code
    if tool_name and tool_name.startswith("_internal_"):
        # These are internal setup commands that should not be displayed
        return

    # Check if we're in parallel mode by looking at agent_id
    is_parallel = False
    if token_info and isinstance(token_info, dict):
        agent_id = token_info.get("agent_id", "")
        # In parallel mode, agent_id has format P1, P2, etc.
        if agent_id and agent_id.startswith("P") and agent_id[1:].isdigit():
            is_parallel = True

    # Special handling for execute_code in parallel mode - don't update during execution
    if tool_name == "execute_code" and is_parallel:
        # In parallel mode, we collect all output and show it at once in finish_tool_streaming
        # Store the output in the session for later use
        if (
            hasattr(cli_print_tool_output, "_streaming_sessions")
            and call_id in cli_print_tool_output._streaming_sessions
        ):
            cli_print_tool_output._streaming_sessions[call_id]["buffer"] = output
            cli_print_tool_output._streaming_sessions[call_id]["current_output"] = output
        return

    # Update the streaming output
    cli_print_tool_output(
        tool_name=tool_name,
        args=args,
        output=output,
        call_id=call_id,
        execution_info={"status": "running", "replace_buffer": True},
        token_info=token_info,
        streaming=True,
    )


def finish_tool_streaming(tool_name, args, output, call_id, execution_info=None, token_info=None):
    """
    Complete a streaming tool execution.

    Args:
        tool_name: Name of the tool being executed
        args: Arguments to the tool (dictionary or string)
        output: Final output to display
        call_id: The call ID for this streaming session
        execution_info: Optional execution information
        token_info: Optional token information

    Returns:
        None
    """
    # Compact REPL owns tool rendering in CLI mode.
    if _compact_suppresses_verbose():
        return
    import time

    # Skip internal setup commands used by execute_code
    if tool_name and tool_name.startswith("_internal_"):
        # These are internal setup commands that should not be displayed
        return

    # Check if we're in parallel mode by looking at agent_id
    is_parallel = False
    if token_info and isinstance(token_info, dict):
        agent_id = token_info.get("agent_id", "")
        # In parallel mode, agent_id has format P1, P2, etc.
        if agent_id and agent_id.startswith("P") and agent_id[1:].isdigit():
            is_parallel = True

    # Special handling for execute_code in streaming mode (both parallel and normal)
    if tool_name == "execute_code" and isinstance(args, dict) and "code" in args:
        from rich.console import Console, Group
        from rich.syntax import Syntax
        from rich.text import Text

        console = Console()

        # Get agent name from token_info
        agent_name = token_info.get("agent_name", "Agent") if token_info else "Agent"

        # In finish_tool_streaming, we only show the output
        # The code was already shown in start_tool_streaming
        output_syntax = Syntax(
            output or "No output", "text", theme="monokai",
            background_color="#272822", word_wrap=True,
        )

        # Flat output header
        status = execution_info.get("status", "completed") if execution_info else "completed"
        out_header = Text()
        out_header.append("• ", style=CAI_GREEN)
        out_header.append(f"{agent_name}", style=f"bold {CAI_GREEN}")
        if status == "completed":
            out_header.append(" - Output", style="dim")
        else:
            out_header.append(" - Output (Error)", style="bold red")
        _erase_pricing_footer()
        console.print(Group(out_header, output_syntax))
        # Print pricing footer after execute_code output
        _print_pricing_footer(console, final=False, framed=False)
        _print_cli_gap_after_completed_tool(False, None, call_id)

        # Mark the streaming session as complete and that we've shown special output
        if (
            hasattr(cli_print_tool_output, "_streaming_sessions")
            and call_id in cli_print_tool_output._streaming_sessions
        ):
            cli_print_tool_output._streaming_sessions[call_id]["is_complete"] = True
            cli_print_tool_output._streaming_sessions[call_id]["special_output_shown"] = True

        # Add to displayed commands to prevent duplicate display
        if hasattr(cli_print_tool_output, "_displayed_commands"):
            # Generate a command key for deduplication
            command_key = (
                f"execute_code:{args.get('filename', 'code')}:{args.get('language', 'unknown')}"
            )
            cli_print_tool_output._displayed_commands.add(command_key)

        return

    # Normal handling for other tools
    # Prepare execution info with completion status
    if execution_info is None:
        execution_info = {}

    # Add completion markers
    execution_info["status"] = execution_info.get("status", "completed")
    execution_info["is_final"] = True
    execution_info["replace_buffer"] = True

    # Calculate execution time if start_time is in the streaming session
    if (
        hasattr(cli_print_tool_output, "_streaming_sessions")
        and call_id in cli_print_tool_output._streaming_sessions
    ):
        session = cli_print_tool_output._streaming_sessions[call_id]
        if "start_time" in session and "tool_time" not in execution_info:
            execution_info["tool_time"] = time.time() - session["start_time"]

    # Pricing suppressed from individual tool outputs — shown only in agent messages

    # Show the final output
    # Note: In parallel mode with static panels, this call will be intercepted
    # and return early to avoid duplicate panels. The initial panel already shows
    # the output, so we don't need to print it again.
    cli_print_tool_output(
        tool_name=tool_name,
        args=args,
        output=output,
        call_id=call_id,
        execution_info=execution_info,
        token_info=token_info,
        streaming=True,
    )

    # Mark the streaming session as complete
    if (
        hasattr(cli_print_tool_output, "_streaming_sessions")
        and call_id in cli_print_tool_output._streaming_sessions
    ):
        cli_print_tool_output._streaming_sessions[call_id]["is_complete"] = True



def create_claude_thinking_context(agent_name, counter, model):
    """
    Create a streaming context for AI thinking/reasoning display.
    This creates a dedicated panel that shows the model's internal reasoning process.

    Args:
        agent_name: The name of the agent
        counter: The interaction counter
        model: The model name

    Returns:
        A dictionary with the streaming context for thinking display
    """
    import shutil
    import uuid

    from rich.console import Group
    from rich.live import Live
    from rich.text import Text

    # Generate unique thinking context ID
    thinking_id = f"thinking_{agent_name}_{counter}_{str(uuid.uuid4())[:8]}"

    # Check if we already have an active thinking panel
    if thinking_id in _CLAUDE_THINKING_PANELS:
        return _CLAUDE_THINKING_PANELS[thinking_id]

    try:
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Terminal size for better display
        terminal_width, _ = shutil.get_terminal_size((100, 24))
        panel_width = min(terminal_width - 4, 120)

        # Determine model type for display
        model_str = str(model).lower()
        if "claude" in model_str:
            model_display = "Claude"
        elif "deepseek" in model_str:
            model_display = "DeepSeek"
        else:
            model_display = "AI"

        # Create the thinking panel header
        header = Text()
        header.append("🧠 ", style="bold yellow")
        header.append(f"{model_display} Reasoning [{counter}]", style="bold yellow")
        header.append(f" | {agent_name}", style="bold cyan")
        header.append(f" | {timestamp}", style="dim")

        # Initial thinking content
        thinking_content = Text("Thinking...", style="italic dim")

        # Flat renderable (no Panel box)
        flat_content = Group(header, Text("\n"), thinking_content)

        # Create Live display object
        live = Live(flat_content, refresh_per_second=8, console=console, auto_refresh=True,
                   transient=False)

        context = {
            "thinking_id": thinking_id,
            "live": live,
            "panel": None,
            "header": header,
            "thinking_content": thinking_content,
            "timestamp": timestamp,
            "model": model,
            "model_display": model_display,
            "agent_name": agent_name,
            "panel_width": panel_width,
            "is_started": False,
            "accumulated_thinking": "",
        }

        # Store in global tracker
        _CLAUDE_THINKING_PANELS[thinking_id] = context

        return context

    except Exception as e:
        print(f"Error creating {model_display} thinking context: {e}")
        return None


def update_claude_thinking_content(context, thinking_delta):
    """
    Update the AI thinking content with new reasoning text.

    Args:
        context: The thinking context created by create_claude_thinking_context
        thinking_delta: The new thinking text to add
    """
    if not context:
        return False

    try:
        # Accumulate the thinking text
        context["accumulated_thinking"] += thinking_delta

        # Create syntax highlighted thinking content
        from rich.console import Group
        from rich.syntax import Syntax
        from rich.text import Text

        # Try to format as markdown-like reasoning
        thinking_text = context["accumulated_thinking"]

        # Create formatted thinking display
        if len(thinking_text) > 500:
            # For long thinking, use syntax highlighting
            thinking_display = Syntax(
                thinking_text,
                "markdown",
                theme="monokai",
                background_color="#2E2E2E",
                word_wrap=True,
                line_numbers=False,
            )
        else:
            # For short thinking, use regular text with styling
            thinking_display = Text(thinking_text, style="white")

        # Get model display name from context
        model_display = context.get("model_display", "AI")

        # Flat renderable for thinking update
        updated_content = Group(context["header"], Text("\n"), thinking_display)

        # Start the display if not already started
        if not context.get("is_started", False):
            try:
                context["live"].start(refresh=True)
                context["is_started"] = True
            except Exception as e:
                model_display = context.get("model_display", "AI")
                print(f"Error starting {model_display} thinking display: {e}")
                return False

        # Update the live display with flat content
        context["live"].update(updated_content)

        return True

    except Exception as e:
        model_display = context.get("model_display", "AI")
        print(f"Error updating {model_display} thinking content: {e}")
        return False


def finish_claude_thinking_display(context):
    """
    Finish the AI thinking display session.

    Args:
        context: The thinking context to finish
    """
    if not context:
        return False

    # Clean up from global tracker
    thinking_id = context.get("thinking_id")
    if thinking_id and thinking_id in _CLAUDE_THINKING_PANELS:
        del _CLAUDE_THINKING_PANELS[thinking_id]

    try:
        # Import required classes
        from rich.console import Group
        from rich.syntax import Syntax
        from rich.text import Text

        # Get model display name
        model_display = context.get("model_display", "AI")

        # Add final formatting to show completion
        final_header = Text()
        final_header.append("🧠 ", style="bold green")
        final_header.append(f"{model_display} Reasoning Complete", style="bold green")
        final_header.append(f" | {context['agent_name']}", style="bold cyan")
        final_header.append(f" | {context['timestamp']}", style="dim")

        thinking_text = context["accumulated_thinking"]

        if thinking_text.strip():
            # Create final formatted display
            final_thinking_display = Syntax(
                thinking_text,
                "markdown",
                theme="monokai",
                background_color="#2E2E2E",
                word_wrap=True,
                line_numbers=False,
            )
        else:
            final_thinking_display = Text("No reasoning captured", style="dim italic")

        # Create final flat content
        final_content = Group(final_header, Text("\n"), final_thinking_display)

        # Update one last time and stop the live display
        if context.get("is_started", False):
            context["live"].update(final_content)
            time.sleep(0.1)
            context["live"].stop()

        return True

    except Exception as e:
        model_display = context.get("model_display", "AI")
        print(f"Error finishing {model_display} thinking display: {e}")
        return False


def _raw_reasoning_display_enabled() -> bool:
    """Return whether raw provider reasoning text should be displayed.

    DeepSeek-compatible gateways often stream ``reasoning_content`` in tiny
    deltas. Rendering those deltas by default floods the terminal and can leak
    model-internal scratch text. Keep it opt-in for DeepSeek via
    ``CAI_SHOW_REASONING=true`` (or ``CAI_SHOW_THINKING=true`` for older local
    configs).
    """
    raw = os.getenv("CAI_SHOW_REASONING")
    if raw is None:
        raw = os.getenv("CAI_SHOW_THINKING")
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def detect_claude_thinking_in_stream(model_name):
    """
    Detect if a model should show thinking/reasoning display.

    Claude keeps the historical default. DeepSeek raw reasoning is opt-in
    because providers commonly stream it token-by-token as ``reasoning_content``.

    Args:
        model_name: The model name to check

    Returns:
        bool: True if thinking display should be shown
    """
    if not model_name:
        return False

    model_str = str(model_name).lower()

    # Check for Claude models with reasoning capability
    # Claude 4 models (like claude-sonnet-4-20250514) support reasoning
    # Also check for explicit "thinking" in model name
    has_claude_reasoning = "claude" in model_str and (
        # Claude 4 models (sonnet-4, haiku-4, opus-4)
        "-4-" in model_str
        or "sonnet-4" in model_str
        or "haiku-4" in model_str
        or "opus-4" in model_str
        or
        # Legacy support for 3.7 and explicit thinking models
        "3.7" in model_str
        or "thinking" in model_str
    )

    # DeepSeek reasoning display is intentionally opt-in. The text is still
    # accumulated internally by the model stream handler so empty-response
    # detection and accounting keep working; it is just not printed by default.
    has_deepseek_reasoning = "deepseek" in model_str and _raw_reasoning_display_enabled()

    return has_claude_reasoning or has_deepseek_reasoning


def print_claude_reasoning_simple(reasoning_content, agent_name, model_name):
    """
    Print AI reasoning content in simple mode (no Rich panels).
    Used when CAI_STREAM=False.

    Args:
        reasoning_content: The reasoning/thinking text
        agent_name: The agent name
        model_name: The model name
    """
    if not reasoning_content or not reasoning_content.strip():
        return

    # Determine model type for display
    model_str = str(model_name).lower()
    if "claude" in model_str:
        model_display = "Claude"
    elif "deepseek" in model_str:
        model_display = "DeepSeek"
    else:
        model_display = "AI"

    # Simple text output without Rich formatting
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n🧠 {model_display} Reasoning | {agent_name} | {model_name} | {timestamp}")
    print("=" * 60)
    print(reasoning_content)
    print("=" * 60 + "\n")


def start_claude_thinking_if_applicable(model_name, agent_name, counter):
    """
    Start AI thinking display if the model supports it AND streaming is enabled.
    Supports Claude and DeepSeek models with reasoning capabilities.

    Args:
        model_name: The model name
        agent_name: The agent name
        counter: The interaction counter

    Returns:
        The thinking context if created, None otherwise
    """
    # Only show thinking in streaming mode
    streaming_enabled = is_tool_streaming_enabled()

    if streaming_enabled and detect_claude_thinking_in_stream(model_name):
        return create_claude_thinking_context(agent_name, counter, model_name)
    return None


# Re-export from pricing for backward compatibility
from cai.util.pricing import set_pending_cache_info, get_and_clear_pending_cache_info

# Register signal handler for CTRL+C
from cai.util.interaction import signal_handler
signal.signal(signal.SIGINT, signal_handler)

# Register cleanup at exit
atexit.register(cleanup_all_streaming_resources)
