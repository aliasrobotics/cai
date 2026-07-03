"""Headless (non-TUI) REPL loop and supporting helpers.

Extracted from cli.py to keep the main module a thin orchestrator.
Contains:
  - update_agent_models_recursively()
  - run_cai_cli()  -- the interactive conversation loop
"""

import asyncio
import contextlib
import io
import json
import logging
import os
import re
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cai import is_pentestperf_available
from cai.internal.components.metrics import process_metrics
from cai.repl.commands import get_fuzzy_completer, handle_command as commands_handle_command
import cai.repl.commands.exit as _repl_exit_cmd
from cai.repl.commands.parallel import (
    PARALLEL_CONFIGS,
    ParallelConfig,
    PARALLEL_AGENT_INSTANCES,
)
from cai.repl.ui.banner import display_banner
from cai.repl.ui.startup_hints import StartupHints, mask_key_for_hint
from cai.repl.ui.keybindings import create_key_bindings
from cai.repl.ui.logging import setup_session_logging
from cai.repl.ui.prompt import consume_repl_stdin_exhausted, get_user_input
from cai.repl.ui.toolbar import get_toolbar_with_refresh
from cai.sdk.agents import Runner, set_tracing_disabled
from cai.sdk.agents.items import ToolCallOutputItem
from cai.sdk.agents.exceptions import (
    OutputGuardrailTripwireTriggered,
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    PriceLimitExceeded,
    UserCancelledCommand,
)
from cai.sdk.agents.run_to_jsonl import get_session_recorder
from cai.sdk.agents.global_usage_tracker import GLOBAL_USAGE_TRACKER
from cai.sdk.agents.stream_events import RunItemStreamEvent
from wasabi import color
from cai.util.hint_renderables import build_cai_markup_line, build_startup_hint_renderable
from cai.util import (
    reset_interaction_counter,
    check_interaction_limit,
    MaxInteractionsExceeded,
    start_active_timer,
    start_idle_timer,
    stop_active_timer,
    stop_idle_timer,
    check_flag,
    setup_ctf,
)
from cai.config import DEFAULT_AGENT_TYPE, get_config as _get_config
from cai.errors import (
    LLMContextOverflow,
    LLMEmptyAssistantError,
    LLMProviderUnavailable,
    LLMRateLimited,
    LLMTimeout,
)
from cai.sdk.agents.models.chatcompletions.httpx_client import verbose_http_retries
from cai.sdk.agents.models.chatcompletions.litellm_adapter import (
    is_transient_litellm_provider_error,
    provider_error_summary,
)
from cai.continuation import generate_continuation_advice, should_continue_automatically
from litellm.exceptions import RateLimitError, Timeout

import cai.cli_setup as _setup  # access CTF globals

try:
    from cai.caibench.ctf import CTFSetupError as _CTFSetupError

    _CTF_HOTSWAP_FAILURE_EXCEPTIONS = (ValueError, _CTFSetupError)
except ImportError:
    _CTF_HOTSWAP_FAILURE_EXCEPTIONS = (ValueError,)


def _ctf_hotswap_failure_extra_hints(err: BaseException) -> str:
    """Rich markup (Spanish): cómo resolver fallos de registry / pull de imágenes CAIBench."""
    msg = str(err).lower()
    if type(err).__name__ != "CTFSetupError" and not any(
        k in msg
        for k in ("registry", "gitlab", "credential", "authenticate", "pull image", "docker login")
    ):
        return ""
    return (
        "\n\n[bold #00ff9d]Cómo solucionarlo[/bold #00ff9d]\n"
        "• Define [bold]CAIBENCH_IMG_REGISTRY_TOKEN[/bold] en tu [dim].env[/dim] o con "
        "[bold]export[/bold] antes de lanzar CAI: debe ser un [bold]token de GitLab[/bold] "
        "con permiso de lectura del registry ([dim]read_registry[/dim]) para "
        "[dim]registry.gitlab.com[/dim].\n"
        "• CAIBench usa usuario [dim]gitlab[/dim] y ese token como contraseña al hacer "
        "[dim]docker login[/dim] y [dim]docker pull[/dim] de la imagen del CTF.\n"
        "• Prueba el login a mano: "
        "[bold]echo \"$CAIBENCH_IMG_REGISTRY_TOKEN\" | docker login registry.gitlab.com "
        "-u gitlab --password-stdin[/bold]\n"
        "• Si la imagen ya está en local ([bold]docker images[/bold]), el arranque puede "
        "reutilizarla sin volver a descargarla.\n"
        "• Si sigue fallando: token caducado o revocado, Docker sin servicio, o la imagen "
        "no existe en ese registry."
    )


def __getattr__(name: str):
    """Lazy ``START_TIME`` from :mod:`cai.util.cli_session_clock` (no import-time side effects)."""
    if name == "START_TIME":
        import cai.util.cli_session_clock as _clk

        return _clk.START_TIME
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _line_is_cli_command_line(line: str) -> bool:
    """Return True if ``line`` should be routed to the CLI command dispatcher.

    Recognised forms: ``/cmd``, ``$shellcmd`` and bare ``?`` (REPL shortcuts).
    """
    s = line.strip()
    if not s:
        return False
    return s.startswith("/") or s.startswith("$") or s == "?"


def _user_input_is_cli_command_block(raw: str) -> bool:
    """Detect single-line or pasted multi-line CLI command blocks."""
    if "\n" in raw:
        return any(_line_is_cli_command_line(ln) for ln in raw.splitlines())
    return _line_is_cli_command_line(raw)


# Parallel execution summary table (CLI): horizontal rule only, CAI green; columns alternate fg
_PARALLEL_SUMMARY_GREEN = "#00ff9d"
_PARALLEL_SUMMARY_MUTED = "#9aa0a6"
_PARALLEL_SUMMARY_COL_LIGHT = "white"
_PARALLEL_SUMMARY_COL_DIM = "#9aa0a6"
# Alternating row *foreground* only (no row backgrounds): non-green columns cycle these.
_PARALLEL_ROW_FG_EVEN = "bright_white"
_PARALLEL_ROW_FG_ODD = "#9aa0a6"


def _parallel_summary_row_fg(row_index: int) -> str:
    return _PARALLEL_ROW_FG_EVEN if row_index % 2 == 0 else _PARALLEL_ROW_FG_ODD


def _strip_parallel_preview_emojis_and_rules(text: str) -> str:
    """Remove emoji, HR lines, decorative rules; flatten markdown headings to bold lines."""
    if not text:
        return ""
    s = text.replace("\r\n", "\n")
    s = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF\uFE0F\u200d]+",
        "",
        s,
    )
    out_lines: list[str] = []
    for raw in s.split("\n"):
        t = raw.strip()
        if not t:
            continue
        if re.fullmatch(r"[-=*_·\u2013\u2014\s]{3,}", t):
            continue
        if re.fullmatch(r"[\u2500-\u257F\u2550-\u257F\s]{2,}", t):
            continue
        hm = re.match(r"^#{1,6}\s+(.+)$", t)
        if hm:
            t = f"**{hm.group(1).strip()}**"
        out_lines.append(t)
    return "\n".join(out_lines)


def _parallel_preview_repair_pipe_row_boundaries(text: str) -> str:
    """Turn flattened `| col | | next row` into real newlines so markdown tables render."""
    if not text or text.count("|") < 4:
        return text
    # Common corruption: row boundary appears as space/pipe/space/pipe between cells.
    return re.sub(r"\|\s+\|\s+", "|\n|", text)


def _parallel_preview_is_markdown_separator_row(row: str) -> bool:
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    if len(cells) < 2:
        return False
    return all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c)


def _split_md_table_row(ln: str) -> list[str]:
    """Split one markdown table row into cell strings (outer pipes optional)."""
    s = ln.strip()
    if not s.startswith("|"):
        s = "|" + s
    if not s.endswith("|"):
        s = s + "|"
    inner = s.strip("|")
    return [c.strip() for c in inner.split("|")]


def _parallel_preview_table_block_to_bullets(block: str) -> str:
    """Convert GFM-style pipe tables to bullet lines (Rich Markdown nested tables break badly)."""
    raw_lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip() and "|" in ln]
    if len(raw_lines) < 2:
        return block.strip()
    rows: list[list[str]] = []
    for ln in raw_lines:
        if _parallel_preview_is_markdown_separator_row(ln):
            continue
        rows.append(_split_md_table_row(ln))
    if len(rows) < 2:
        if rows:
            return " · ".join(x for x in rows[0] if x)
        return block.strip()
    headers = rows[0]
    nh = len(headers)
    out_lines: list[str] = []
    for data in rows[1:]:
        dc = list(data)
        if len(dc) < nh:
            dc.extend([""] * (nh - len(dc)))
        elif len(dc) > nh:
            dc = dc[: nh - 1] + [" ".join(dc[nh - 1 :]).strip()]
        parts: list[str] = []
        for h, v in zip(headers, dc):
            hs = (h or "").strip()
            vs = (v or "").strip()
            if not hs and not vs:
                continue
            if hs:
                parts.append(f"{hs}: {vs}".strip() if vs else hs)
            else:
                parts.append(vs)
        if parts:
            out_lines.append(" · ".join(parts))
    if not out_lines:
        return block.strip()
    # Use middle-dot lines (not markdown "- " lists) so Rich won't paint bullets brown.
    return "\n".join(f"\u00b7 {line}" for line in out_lines)


def _parallel_preview_fenced_code_to_gtgt(text: str) -> str:
    """Replace ``` fences with plain ``>> command`` lines (no ``**`` — reserved for real bold)."""

    def _fmt_body(body: str) -> str:
        one = " ".join(body.strip().split())
        if not one:
            return ""
        return f">> {one}"

    out = re.sub(
        r"```[\w+-]*\s*\n?(.*?)```",
        lambda m: "\n" + _fmt_body(m.group(1)) + "\n\n",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return out


def _collapse_parallel_preview_paragraphs(text: str) -> str:
    """Join non-table lines into compact prose; keep markdown tables as tight blocks."""
    if not text:
        return ""
    lines = text.split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith(">>"):
            chunk_gt: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">>"):
                chunk_gt.append(re.sub(r"\s+", " ", lines[i].strip()))
                i += 1
            blocks.append("\n".join(chunk_gt))
            while i < len(lines) and not lines[i].strip():
                i += 1
            continue
        if "|" in line and line.count("|") >= 2 and not stripped.startswith(">>"):
            tbl: list[str] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row = lines[i].strip()
                if row.startswith(">>"):
                    break
                if not re.match(r"^[\s|\-_:]+$", row):
                    tbl.append(row)
                i += 1
            if tbl:
                blocks.append(
                    _parallel_preview_table_block_to_bullets("\n".join(tbl))
                )
            continue
        chunk: list[str] = []
        while i < len(lines) and lines[i].strip():
            rs = lines[i].strip()
            if rs.startswith(">>"):
                break
            if "|" in lines[i] and lines[i].count("|") >= 2:
                break
            chunk.append(re.sub(r"\s+", " ", rs))
            i += 1
        if chunk:
            # Single newlines between lines (no blank runs); not one mashed paragraph.
            blocks.append("\n".join(chunk))
        while i < len(lines) and not lines[i].strip():
            i += 1
    return "\n".join(blocks)


def _parallel_preview_strip_links_and_inline_code(text: str) -> str:
    """Avoid default Markdown link/code colors (blue etc.) in the summary preview."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def _parallel_preview_avoid_md_list_syntax(text: str) -> str:
    """Turn '- ' / '* ' line starters into middle-dot lines (plain text, row-colored)."""
    out: list[str] = []
    for ln in text.split("\n"):
        m = re.match(r"^(\s*)[-*]\s+(.*)$", ln)
        if m:
            out.append(f"{m.group(1)}\u00b7 {m.group(2)}")
        else:
            out.append(ln)
    return "\n".join(out)


def _parallel_preview_strip_blockquote_prefixes(text: str) -> str:
    """Remove markdown blockquote markers (Rich would render purple bars otherwise)."""
    out: list[str] = []
    for ln in text.split("\n"):
        t = ln.lstrip()
        while t.startswith(">"):
            t = t[1:].lstrip()
        out.append(t)
    return "\n".join(out)


def _parallel_preview_strip_gt_command_prefix(text: str) -> str:
    """Normalize >> lines from fenced-code conversion to plain text."""
    lines: list[str] = []
    for ln in text.split("\n"):
        t = ln.lstrip()
        if t.startswith(">>"):
            t = t[2:].lstrip()
        lines.append(t)
    return "\n".join(lines)


def _parallel_preview_strip_underline_emphasis(text: str) -> str:
    """Strip ``__underline__`` only; ``**bold**`` is kept for Rich Text rendering."""
    return re.sub(r"__([^_]+)__", r"\1", text)


def _parallel_preview_text_with_inline_bold(body: str, row_fg: str) -> Text:
    """Render ``**segment**`` as bold using the same base color as the row."""
    if not body:
        return Text("", style=row_fg)
    if "**" not in body:
        return Text(body, style=row_fg)
    bold_style = f"bold {row_fg}"
    out = Text()
    pos = 0
    for m in re.finditer(r"\*\*([^*]+)\*\*", body):
        if m.start() > pos:
            out.append(body[pos : m.start()], style=row_fg)
        out.append(m.group(1), style=bold_style)
        pos = m.end()
    if pos < len(body):
        out.append(body[pos:], style=row_fg)
    return out


def _parallel_preview_format_numbered_step_breaks(text: str) -> str:
    """Break 'Step N: … 1) …' and '… 2) Plan …' into separate lines (no blank lines)."""
    t = text.replace("\r\n", "\n")
    t = re.sub(
        r"(Step\s+\d+:\s*[^\n]+?)\s+(\d+\))",
        r"\1\n\2",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r" (\d+\) )", r"\n\1", t)
    t = re.sub(r" (\d+\))(\s*$)", r"\n\1\2", t, flags=re.MULTILINE)
    return t


def _parallel_preview_expand_dot_subclauses(text: str) -> str:
    """Split '1) Title · Goal: … · Assumptions: …' into indented · lines."""
    out_lines: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in re.split(r"\s+·\s+", line) if p.strip()]
        if len(parts) > 1 and re.match(r"^\d+\)", parts[0]):
            out_lines.append(parts[0])
            for p in parts[1:]:
                out_lines.append(f"   · {p}")
        elif line.startswith("·") or line.startswith("\u00b7"):
            out_lines.append(line if line.startswith("   ") else f"   {line}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def _sanitize_parallel_preview_for_table(
    text: str, max_chars: int = 1200
) -> tuple[str, bool]:
    """Normalize parallel worker preview text; ``**bold**`` survives for table rendering.

    Returns:
        (text_with_optional_bold_markers, truncated)
    """
    s = text.replace("\r\n", "\n")
    s = _parallel_preview_fenced_code_to_gtgt(s)
    # Fold indent-wrapped lines only (keep blank lines so >> / paragraphs stay separated).
    s = re.sub(r"\n[ \t]+", " ", s)
    s = _strip_parallel_preview_emojis_and_rules(s)
    # Join broken "|\n  cell" fragments common in model output.
    s = re.sub(r"\|\s*\n\s*", "| ", s)
    s = re.sub(r"\n\s+\|", "\n|", s)
    s = _parallel_preview_repair_pipe_row_boundaries(s)
    # Avoid merging a table row with a following >> command on the same physical line.
    s = re.sub(r"(\|)\s*(>>)", r"\1\n\2", s)
    s = _collapse_parallel_preview_paragraphs(s)
    s = _parallel_preview_strip_links_and_inline_code(s)
    s = _parallel_preview_strip_blockquote_prefixes(s)
    s = _parallel_preview_strip_gt_command_prefix(s)
    s = _parallel_preview_strip_underline_emphasis(s)
    s = _parallel_preview_format_numbered_step_breaks(s)
    s = _parallel_preview_expand_dot_subclauses(s)
    s = _parallel_preview_avoid_md_list_syntax(s)
    s = _parallel_preview_strip_underline_emphasis(s)
    # Single newlines only (no blank runs between sections).
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    truncated = False
    if len(s) > max_chars:
        s = s[: max_chars - 1].rstrip()
        truncated = True
    return s, truncated


def _parallel_summary_preview_renderable(body: str, truncated: bool, *, row_fg: str):
    """Preview cell: *row_fg* for body, ``**...**`` segments as bold (no full Markdown)."""
    main = _parallel_preview_text_with_inline_bold(body, row_fg)
    if not truncated:
        return main
    return Text.assemble(main, Text("…", style=row_fg))


def _new_parallel_execution_summary_table() -> Table:
    """Horizontal rule under header (CAI green); no row backgrounds (zebra is text color only)."""
    return Table(
        title="Parallel Execution Summary",
        title_style=f"bold {_PARALLEL_SUMMARY_MUTED}",
        box=box.HORIZONTALS,
        show_edge=False,
        show_lines=False,
        pad_edge=True,
        header_style=f"bold {_PARALLEL_SUMMARY_GREEN}",
        border_style=_PARALLEL_SUMMARY_GREEN,
    )


def _add_parallel_summary_columns(t: Table, preview_max_width: int = 88) -> None:
    t.add_column(
        "Agent",
        style=f"bold {_PARALLEL_SUMMARY_GREEN}",
        no_wrap=False,
        overflow="fold",
        vertical="top",
    )
    # Model / Prompt / Preview colors come from per-row Text (white vs grey).
    t.add_column("Model", no_wrap=True, vertical="top")
    t.add_column("Prompt Source", no_wrap=True, vertical="top")
    t.add_column("Status", no_wrap=True, vertical="top")
    t.add_column(
        "Preview",
        max_width=preview_max_width,
        overflow="fold",
        vertical="top",
    )

def _resolve_parallel_model_name(config_model: str | None) -> str:
    """Resolve parallel model name, enforcing alias-family models for consistency."""
    env_model = (os.getenv("CAI_MODEL", "alias1") or "alias1").strip()
    candidate = (config_model or env_model).strip()
    if candidate.lower().startswith("alias"):
        return candidate
    if env_model.lower().startswith("alias"):
        return env_model
    return "alias1"


def _print_session_log_target(
    console: Console, filepath: str, *, trailing_blankline: bool = True
) -> None:
    """Print session JSONL path (Layout 1: italic grey path:/file: lines).

    If ``trailing_blankline`` is True, print one blank row after path/file so the
    next ``● …`` block is not flush. Set False when the following output already
    ends with its own blank line.
    """
    from cai.util.cli_palette import GREY_TEXT

    log_style = f"italic {GREY_TEXT}"
    expanded = os.path.expanduser(filepath)
    full_line = f"path: {expanded}"
    cols = max(40, shutil.get_terminal_size((80, 24)).columns)

    if len(full_line) <= cols:
        console.print(Text(full_line, style=log_style))
        if trailing_blankline:
            console.print()
        return

    p = Path(expanded)
    try:
        rp = p.resolve()
    except OSError:
        rp = p
    parent_str = str(rp.parent)
    if not parent_str.endswith(os.sep):
        parent_disp = parent_str + os.sep
    else:
        parent_disp = parent_str
    console.print(Text(f"path: {parent_disp}", style=log_style))
    console.print(Text(f"file: {rp.name}", style=log_style))
    if trailing_blankline:
        console.print()


# ---------------------------------------------------------------------------
# Agent model updater
# ---------------------------------------------------------------------------

def update_agent_models_recursively(agent, new_model, visited=None):
    """Recursively update the model for an agent and all agents in its handoffs."""
    if visited is None:
        visited = set()

    if agent.name in visited:
        return
    visited.add(agent.name)

    if hasattr(agent, "model") and hasattr(agent.model, "model"):
        agent.model.model = new_model
        if hasattr(agent.model, "agent_name"):
            agent.model.agent_name = agent.name
        if hasattr(agent.model, "_client"):
            agent.model._client = None
        if hasattr(agent.model, "_converter"):
            if hasattr(agent.model._converter, "recent_tool_calls"):
                agent.model._converter.recent_tool_calls.clear()
            if hasattr(agent.model._converter, "tool_outputs"):
                agent.model._converter.tool_outputs.clear()

    if hasattr(agent, "handoffs"):
        for handoff_item in agent.handoffs:
            if hasattr(handoff_item, "on_invoke_handoff"):
                try:
                    if (
                        hasattr(handoff_item.on_invoke_handoff, "__closure__")
                        and handoff_item.on_invoke_handoff.__closure__
                    ):
                        for cell in handoff_item.on_invoke_handoff.__closure__:
                            if hasattr(cell.cell_contents, "model") and hasattr(cell.cell_contents, "name"):
                                update_agent_models_recursively(cell.cell_contents, new_model, visited)
                                break
                except Exception:
                    pass
            elif hasattr(handoff_item, "model"):
                update_agent_models_recursively(handoff_item, new_model, visited)


# ---------------------------------------------------------------------------
# Headless REPL
# ---------------------------------------------------------------------------

def run_cai_cli(
    starting_agent,
    context_variables=None,
    max_turns=float("inf"),
    force_until_flag=False,
    initial_prompt=None,
    continue_mode=False,
    *,
    console=None,
    skip_startup_banner: bool = False,
):
    """Run the interactive headless CLI loop for CAI.

    This is the non-TUI conversation loop.  The function returns when the
    user presses Ctrl-C at the input prompt or force-mode criteria are met.
    """
    from cai.util.cli_session_clock import reset_session_clock

    reset_session_clock()
    set_tracing_disabled(True)

    if console is None:
        console = Console()
    _startup_cfg = _get_config()
    last_model = _startup_cfg.model
    last_agent_type = _startup_cfg.agent_type
    parallel_count = _startup_cfg.parallel
    use_initial_prompt = initial_prompt is not None
    starting_agent_name = getattr(starting_agent, "name", last_agent_type)

    if not skip_startup_banner:
        display_banner(
            console,
            model=_startup_cfg.model,
            agent_type=starting_agent_name,
        )
        console.print()

    session_hints = StartupHints(console)
    session_hints.start(
        f"Connecting to model server ({_startup_cfg.model})...",
        leading_blank=False,
    )

    # Initialize CTF at runtime
    _setup.initialize_ctf_if_needed()

    agent = starting_agent
    turn_count = 0
    idle_time = 0

    # Reset cost tracking
    from cai.util import COST_TRACKER
    COST_TRACKER.reset_agent_costs()
    reset_interaction_counter()

    # Reset agent manager
    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
    AGENT_MANAGER.reset_registry()
    AGENT_MANAGER.clear_session_context()

    AGENT_MANAGER.switch_to_single_agent(starting_agent, starting_agent_name)
    try:
        from cai.continuous_ops.loop_tick_epilogue import maybe_import_snapshot_before_cli_loop

        maybe_import_snapshot_before_cli_loop(agent, starting_agent_name)
    except Exception:
        pass

    # Completer, key bindings, session logging
    FuzzyCommandCompleter = get_fuzzy_completer()
    command_completer = FuzzyCommandCompleter()
    current_text = [""]
    kb = create_key_bindings(current_text)
    history_file = setup_session_logging()
    session_logger = get_session_recorder()

    GLOBAL_USAGE_TRACKER.start_session(
        session_id=session_logger.session_id,
        agent_name=None,
    )

    queue_file = _startup_cfg.queue_file
    auto_run_queue = False

    # Continue mode after restoring history (e.g. user ran /resume before first prompt)
    _has_history = bool(
        getattr(agent, "model", None)
        and getattr(agent.model, "message_history", None)
        and len(agent.model.message_history) > 0
    )
    if continue_mode and _has_history:
        session_hints.stop()
        from cai.repl.commands.queue import add_to_queue
        try:
            if hasattr(agent, "model") and hasattr(agent.model, "message_history") and agent.model.message_history:
                continuation_prompt = asyncio.run(generate_continuation_advice(
                    agent_name=getattr(agent, "name", "Agent"),
                    message_history=agent.model.message_history,
                    console=console
                ))
                add_to_queue(continuation_prompt)
                auto_run_queue = True
                console.print(
                    build_cai_markup_line(
                        "\n[#9aa0a6]Continue mode: resuming automatically from previous session.[/]"
                    )
                )
        except Exception:
            add_to_queue("Continue working on the task based on your previous findings.")
            auto_run_queue = True
            console.print(
                build_cai_markup_line(
                    "\n[#9aa0a6]Continue mode: resuming automatically from previous session.[/]"
                )
            )

    if queue_file:
        from cai.repl.commands.queue import load_queue_from_file
        queue_file = os.path.expanduser(queue_file)
        if os.path.exists(queue_file):
            session_hints.set_message("Loading prompt queue from disk...")
            loaded = load_queue_from_file(queue_file)
            if loaded > 0:
                session_hints.stop()
                console.print(
                    build_cai_markup_line(
                        f"\n[#9aa0a6]Auto-loaded [/][bold #00ff9d]{loaded}[/bold #00ff9d]"
                        f"[#9aa0a6] prompts from [/][bold white]{queue_file}[/bold white][#9aa0a6].[/]"
                    )
                )
                console.print(f"[green]Starting automatic queue processing...[/green]\n")
                auto_run_queue = True

    def get_agent_short_name(agent):
        return getattr(agent, "name", "Agent")

    # Configure model streaming flags
    if hasattr(agent, "model"):
        if hasattr(agent.model, "disable_rich_streaming"):
            agent.model.disable_rich_streaming = False
        if hasattr(agent.model, "suppress_final_output"):
            agent.model.suppress_final_output = False
        if hasattr(agent.model, "set_agent_name"):
            agent.model.set_agent_name(get_agent_short_name(agent))

    prev_max_turns = max_turns
    turn_limit_reached = False
    interaction_limit_reached = False

    # Initial system check (second startup phase: license / API reachability)
    session_hints.set_message(
        f"Verifying license and API key ({mask_key_for_hint(os.getenv('ALIAS_API_KEY', ''))})..."
    )
    try:
        from cai.util_ext import _chk
        if not _chk():
            session_hints.stop()
            Console(stderr=True).print(
                Panel(
                    "[bold red]ALIAS_API_KEY is invalid or not set[/bold red]\n\n"
                    "Please set a valid ALIAS_API_KEY in your .env file or environment.",
                    title="[red]Authentication Error[/red]",
                    border_style="red",
                )
            )
            return
    except Exception:
        pass

    session_hints.stop()

    def _single_shot_cli_active() -> bool:
        return os.getenv("CAI_SINGLE_SHOT_CLI", "").lower() in ("1", "true", "yes")

    def _bundled_stdin_prompt_text() -> str:
        path = (os.getenv("CAI_SINGLE_SHOT_STDIN_PROMPT_FILE") or "").strip()
        if path:
            try:
                return Path(path).expanduser().resolve().read_text(encoding="utf-8")
            except OSError:
                pass
        return (os.getenv("CAI_SINGLE_SHOT_STDIN_PROMPT", "") or "").strip()

    def _interactive_cli_input() -> str | None:
        """Return user line, or ``None`` if the REPL must exit (fatal single-shot without TTY)."""
        prompt_file_set = bool((os.getenv("CAI_SINGLE_SHOT_STDIN_PROMPT_FILE") or "").strip())
        loop_child = os.getenv("CAI_CONTINUOUS_OPS_LOOP_CHILD", "").lower() in ("1", "true", "yes")
        fb = _bundled_stdin_prompt_text().strip() or (initial_prompt or "").strip()
        # Single-shot ticks (e.g. continuous_ops in tmux) often have a real TTY; still must not
        # block on prompt_toolkit when a bundled prompt is configured or this is the loop worker.
        if _single_shot_cli_active() and fb and (not sys.stdin.isatty() or prompt_file_set or loop_child):
            console.print("[dim]Single-shot: using bundled tick prompt (no interactive stdin).[/dim]")
            return fb
        if _single_shot_cli_active() and not sys.stdin.isatty():
            console.print(
                "[bold red]Single-shot CLI cannot open prompt_toolkit: stdin is not a TTY and no "
                "CAI_SINGLE_SHOT_STDIN_PROMPT_FILE / CAI_SINGLE_SHOT_STDIN_PROMPT / --prompt text is available. Exiting.[/bold red]"
            )
            return None
        return get_user_input(
            command_completer, kb, history_file, get_toolbar_with_refresh, current_text,
        )

    while True:
        # ---- CTF hotswap ----
        if _setup.previous_ctf_name != os.getenv("CTF_NAME", None):
            if is_pentestperf_available():
                if _setup.ctf_global:
                    _setup.ctf_global.stop_ctf()
                old_prev = _setup.previous_ctf_name
                try:
                    ctf, _setup.messages_ctf = setup_ctf()
                except _CTF_HOTSWAP_FAILURE_EXCEPTIONS as err:
                    console.print(
                        Panel(
                            f"[bold red]CTF setup failed[/bold red]\n\n{err}\n\n"
                            "[yellow]Se revirtió [bold]CTF_NAME[/bold] al valor anterior para que CAI "
                            "siga respondiendo. Si el nombre era incorrecto, usa un id del catálogo "
                            "CAIBench; si el fallo es de red o credenciales, corrígelo y vuelve a "
                            "ejecutar [bold]/env set CTF_NAME …[/bold].[/yellow]"
                            f"{_ctf_hotswap_failure_extra_hints(err)}",
                            title="[red]CTF error[/red]",
                            border_style="red",
                        )
                    )
                    if old_prev is not None:
                        os.environ["CTF_NAME"] = old_prev
                    else:
                        os.environ.pop("CTF_NAME", None)
                    _setup.previous_ctf_name = old_prev
                    _setup.ctf_global = None
                    _setup.ctf_init = 1
                    _setup.first_ctf_time = False
                    _setup.messages_ctf = ""
                    continue
                _setup.ctf_global = ctf
                _setup.previous_ctf_name = os.getenv("CTF_NAME", None)
                _setup.ctf_init = 0
                _setup.first_ctf_time = True

        # ---- max-turns check ----
        current_max_turns = os.getenv("CAI_MAX_TURNS", "inf")
        if current_max_turns != str(prev_max_turns):
            max_turns = float(current_max_turns)
            prev_max_turns = max_turns
            if turn_limit_reached and turn_count < max_turns:
                turn_limit_reached = False
                console.print("[green]Turn limit increased. You can now continue using CAI.[/green]")

        if turn_count >= max_turns and max_turns != float("inf"):
            if not turn_limit_reached:
                turn_limit_reached = True
                console.print(f"[bold red]Error: Maximum turn limit ({int(max_turns)}) reached.[/bold red]")
                console.print("[yellow]You must increase the limit using: /env set CAI_MAX_TURNS <new_value>[/yellow]")
                console.print("[yellow]Only CLI commands (starting with '/') will be processed until the limit is increased.[/yellow]")
            if force_until_flag:
                return

        # ---- interaction limit check ----
        current_max_interactions = os.getenv("CAI_MAX_INTERACTIONS", "inf")
        try:
            check_interaction_limit()
            interaction_limit_reached = False
        except MaxInteractionsExceeded:
            if not interaction_limit_reached:
                interaction_limit_reached = True
                console.print(f"[bold red]Error: Maximum interaction limit ({current_max_interactions}) reached.[/bold red]")
                console.print("[yellow]You must increase the limit using: /env set CAI_MAX_INTERACTIONS <new_value>[/yellow]")
                console.print("[yellow]Only CLI commands (starting with '/') will be processed until the limit is increased.[/yellow]")
            if force_until_flag:
                return

        if interaction_limit_reached:
            console.print("[bold red]Error: Interaction limit reached. Only CLI commands are allowed.[/bold red]")
            console.print("[yellow]Please use /env to increase CAI_MAX_INTERACTIONS limit.[/yellow]")

        # ---- price limit check ----
        current_price_limit = os.getenv("CAI_PRICE_LIMIT", "inf")
        try:
            price_limit_reached = False
            from cai.util import COST_TRACKER
            try:
                price_limit = float(current_price_limit) if current_price_limit != "inf" else float("inf")
            except ValueError:
                price_limit = float("inf")

            if price_limit != float("inf") and COST_TRACKER.session_total_cost >= price_limit:
                price_limit_reached = True
                if not hasattr(run_cai_cli, '_price_limit_warning_shown'):
                    run_cai_cli._price_limit_warning_shown = True
                    console.print(f"[bold red]Error: Maximum price limit (${price_limit:.4f}) reached. Current cost: ${COST_TRACKER.session_total_cost:.4f}[/bold red]")
                    console.print("[yellow]You must increase the limit using: /env set CAI_PRICE_LIMIT <new_value>[/yellow]")
                    console.print("[yellow]Only CLI commands (starting with '/') will be processed until the limit is increased.[/yellow]")
                if force_until_flag:
                    return
        except Exception:
            price_limit_reached = False

        if price_limit_reached:
            console.print("[bold red]Error: Price limit reached. Only CLI commands are allowed.[/bold red]")
            console.print("[yellow]Please use /env to increase CAI_PRICE_LIMIT limit.[/yellow]")

        try:
            # Idle time measurement
            start_idle_timer()
            idle_start_time = time.time()

            # Model hotswap
            current_model = os.getenv("CAI_MODEL", "alias1")
            agent_specific_model = os.getenv(f"CAI_{last_agent_type.upper()}_MODEL")
            if agent_specific_model:
                current_model = agent_specific_model
            if current_model != last_model and hasattr(agent, "model"):
                update_agent_models_recursively(agent, current_model)
                last_model = current_model

            # Agent type hotswap
            current_agent_type = os.getenv("CAI_AGENT_TYPE", DEFAULT_AGENT_TYPE)
            parallel_count = int(os.getenv("CAI_PARALLEL", "1"))

            # Check the handled flag independently of agent type comparison
            # so that /agent called with the same type (e.g. to pick up MCP
            # tools) still updates the local agent variable.
            if os.environ.get("CAI_AGENT_SWITCH_HANDLED") == "1":
                os.environ["CAI_AGENT_SWITCH_HANDLED"] = "0"
                from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                if hasattr(AGENT_MANAGER, '_current_agent_strong_ref'):
                    agent = AGENT_MANAGER._current_agent_strong_ref
                    delattr(AGENT_MANAGER, '_current_agent_strong_ref')
                else:
                    agent = AGENT_MANAGER.get_active_agent()
                if agent:
                    last_agent_type = current_agent_type
                    if current_agent_type == "continuous_ops_agent":
                        os.environ.pop("CAI_CONTINUOUS_OPS_SETUP_DONE", None)
                else:
                    from cai.agents import get_agent_by_name
                    from cai.sdk.agents.simple_agent_manager import DEFAULT_SESSION_AGENT_ID

                    agent = get_agent_by_name(current_agent_type, agent_id=DEFAULT_SESSION_AGENT_ID)
                    last_agent_type = current_agent_type
                    if current_agent_type == "continuous_ops_agent":
                        os.environ.pop("CAI_CONTINUOUS_OPS_SETUP_DONE", None)
                    agent_name = agent.name if hasattr(agent, "name") else current_agent_type
                    AGENT_MANAGER.set_active_agent(agent, agent_name, DEFAULT_SESSION_AGENT_ID)
                # Force next user turn to be treated as a fresh task after explicit agent switch.
                os.environ["CAI_TASK_RESET_PENDING"] = "1"
                continue

            if current_agent_type != last_agent_type:
                try:
                    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                    if hasattr(agent, "name"):
                        current_agent_name = agent.name
                        current_history = AGENT_MANAGER.get_message_history(current_agent_name)
                        if current_history:
                            AGENT_MANAGER._pending_history_transfer = list(current_history)
                            try:
                                from cai.util.session_compact import prepare_agent_handoff

                                si = getattr(agent.model, "system_instructions", None) if hasattr(agent, "model") else None
                                prepare_agent_handoff(
                                    current_agent_name,
                                    current_history,
                                    si,
                                    to_agent_name=current_agent_type,
                                )
                            except Exception:
                                pass

                    from cai.agents import get_agent_by_name
                    from cai.sdk.agents.simple_agent_manager import DEFAULT_SESSION_AGENT_ID

                    agent = get_agent_by_name(current_agent_type, agent_id=DEFAULT_SESSION_AGENT_ID)
                    last_agent_type = current_agent_type
                    if current_agent_type == "continuous_ops_agent":
                        os.environ.pop("CAI_CONTINUOUS_OPS_SETUP_DONE", None)

                    from cai.util import COST_TRACKER
                    COST_TRACKER.reset_agent_costs()

                    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
                    agent_name = getattr(agent, "name", current_agent_type)
                    AGENT_MANAGER.switch_to_single_agent(agent, agent_name)

                    if hasattr(agent, "model") and hasattr(agent.model, "message_history"):
                        agent_history = AGENT_MANAGER.get_message_history(agent_name)
                        agent.model.message_history.clear()
                        if agent_history:
                            agent.model.message_history.extend(agent_history)
                    # Agent changed: next prompt should prioritize new task over unfinished prior one.
                    os.environ["CAI_TASK_RESET_PENDING"] = "1"

                    if hasattr(agent, "model"):
                        if hasattr(agent.model, "disable_rich_streaming"):
                            agent.model.disable_rich_streaming = False
                        if hasattr(agent.model, "suppress_final_output"):
                            agent.model.suppress_final_output = False
                        agent_specific_model = os.getenv(f"CAI_{current_agent_type.upper()}_MODEL")
                        model_to_apply = agent_specific_model if agent_specific_model else current_model
                        update_agent_models_recursively(agent, model_to_apply)
                        last_model = model_to_apply
                        if hasattr(agent.model, "set_agent_name"):
                            agent.model.set_agent_name(get_agent_short_name(agent))
                        try:
                            all_tasks = asyncio.all_tasks() if hasattr(asyncio, "all_tasks") else asyncio.Task.all_tasks()
                            current_task = asyncio.current_task() if hasattr(asyncio, "current_task") else asyncio.Task.current_task()
                            for task in all_tasks:
                                if task != current_task and not task.done():
                                    task.cancel()
                        except RuntimeError:
                            pass
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error switching agent: {str(e)}")
                    if _get_config().debug == 2:
                        console.print(f"[red]Error switching agent: {str(e)}[/red]")

            # ---- Get user input ----
            if not force_until_flag and _setup.ctf_init != 0:
                if use_initial_prompt and turn_count == 0:
                    user_input = initial_prompt
                    if not (user_input or "").strip():
                        console.print("[bold red]Initial --prompt is empty; cannot run. Exiting.[/bold red]")
                        return
                    console.print(f"[dim white]Processing initial prompt:[/dim white] {user_input}")
                    # Defer clearing until a successful turn unless the queue will drive subsequent prompts
                    # (otherwise a failed first turn leaves turn_count==0 and forces interactive input).
                    if os.getenv("CAI_AUTO_RUN_QUEUE") == "1":
                        auto_run_queue = True
                        use_initial_prompt = False
                elif auto_run_queue:
                    from cai.repl.commands.queue import get_queue, get_next_prompt
                    queue_items = get_queue()
                    if queue_items:
                        next_item = get_next_prompt()
                        if next_item:
                            if isinstance(next_item, dict):
                                user_input = next_item.get("prompt", "")
                                item_agent = next_item.get("agent")
                                if item_agent:
                                    from cai.agents import get_available_agents as _get_agents
                                    _avail = _get_agents()
                                    if item_agent in _avail:
                                        agent = _avail[item_agent]
                                        console.print(
                                            f"[dim white]Queue: switching to "
                                            f"[bold]{item_agent}[/bold][/dim white]"
                                        )
                            else:
                                user_input = str(next_item)
                            console.print(
                                f"[dim white]Processing from queue:[/dim white] {user_input}"
                            )
                        else:
                            auto_run_queue = False
                            u = _interactive_cli_input()
                            if u is None:
                                return
                            user_input = u
                    else:
                        auto_run_queue = False
                        u = _interactive_cli_input()
                        if u is None:
                            return
                        user_input = u
                else:
                    if turn_count == 0 and os.getenv("CAI_AUTO_RUN_PARALLEL") == "1" and PARALLEL_CONFIGS:
                        user_input = ""
                        console.print(f"[dim white]Auto-running parallel agents with configured prompts...[/dim white]")
                        os.environ.pop("CAI_AUTO_RUN_PARALLEL", None)
                    else:
                        u = _interactive_cli_input()
                        if u is None:
                            return
                        user_input = u
            else:  # CTF mode
                if not force_until_flag and _setup.first_ctf_time is False:
                    u = _interactive_cli_input()
                    if u is None:
                        return
                    user_input = u
                else:
                    if _setup.first_ctf_time:
                        user_input = _setup.messages_ctf
                        _setup.first_ctf_time = False
                    else:
                        user_input = "Continue working on the CTF challenge based on previous output."

            idle_time += time.time() - idle_start_time
            stop_idle_timer()
            start_active_timer()

            _try_refresh_info_bars()

            if consume_repl_stdin_exhausted():
                _handle_exit_interrupt(
                    agent, console, session_logger, idle_time, idle_start_time, force_until_flag,
                    PARALLEL_CONFIGS, PARALLEL_AGENT_INSTANCES,
                )
                break

            if not user_input.strip():
                stop_active_timer()
                continue

            # Semicolon command chaining
            if user_input and ';' in user_input and not user_input.startswith('/load '):
                commands = [cmd.strip() for cmd in user_input.split(';')]
                if len(commands) > 1:
                    user_input = commands[0]
                    from cai.repl.commands.queue import add_to_queue
                    for cmd in commands[1:]:
                        if cmd:
                            add_to_queue(cmd)
                    auto_run_queue = True

        except KeyboardInterrupt:
            _handle_exit_interrupt(
                agent, console, session_logger, idle_time, idle_start_time, force_until_flag,
                PARALLEL_CONFIGS, PARALLEL_AGENT_INSTANCES,
            )
            break

        try:
            # Turn/price limit enforcement on non-command input
            if turn_limit_reached and not _user_input_is_cli_command_block(user_input):
                console.print("[bold red]Error: Turn limit reached. Only CLI commands are allowed.[/bold red]")
                console.print("[yellow]Please use /env to increase CAI_MAX_TURNS limit.[/yellow]")
                stop_active_timer()
                start_idle_timer()
                _try_refresh_info_bars()
                continue

            if price_limit_reached and not _user_input_is_cli_command_block(user_input):
                console.print("[bold red]Error: Price limit reached. Only CLI commands are allowed.[/bold red]")
                console.print("[yellow]Please use /env to increase CAI_PRICE_LIMIT limit.[/yellow]")
                stop_active_timer()
                start_idle_timer()
                continue

            # ---- Parallel execution path ----
            if PARALLEL_CONFIGS and not _user_input_is_cli_command_block(user_input):
                exec_mode = os.getenv("CAI_PARALLEL_EXEC_MODE", "external").strip().lower()
                if exec_mode == "external":
                    console.print(
                        build_cai_markup_line(
                            "[#9aa0a6]Parallel mode is active (external terminals). "
                            "Use [/][bold #00ff9d]/parallel run[/bold #00ff9d][#9aa0a6] to launch workers, "
                            "[/][bold #00ff9d]/parallel clear[/bold #00ff9d][#9aa0a6] to exit parallel mode.[/]"
                        )
                    )
                    continue
                _run_parallel_turn(
                    agent, user_input, console, PARALLEL_CONFIGS, PARALLEL_AGENT_INSTANCES,
                    last_agent_type, update_agent_models_recursively,
                )
                turn_count += 1
                use_initial_prompt = False
                stop_active_timer()
                start_idle_timer()
                _try_refresh_info_bars()
                continue

            # ---- Continuous ops agent (CLI onboarding + worker launch) ----
            if (
                os.environ.get("CAI_TUI_MODE", "").lower() != "true"
                and not PARALLEL_CONFIGS
                and last_agent_type == "continuous_ops_agent"
                and not user_input.startswith("$")
            ):
                from cai.continuous_ops.wizard import maybe_intercept_continuous_ops_turn

                if maybe_intercept_continuous_ops_turn(user_input, console):
                    turn_count += 1
                    use_initial_prompt = False
                    stop_active_timer()
                    start_idle_timer()
                    _try_refresh_info_bars()
                    continue

            # ---- Slash/dollar / bare ? (CLI shortcuts) ----
            if _user_input_is_cli_command_block(user_input):
                # Support pasted multiline command batches:
                # each non-empty line is treated as an independent command.
                command_lines = [user_input]
                if "\n" in user_input:
                    command_lines = [
                        line.strip() for line in user_input.splitlines() if line.strip()
                    ]

                from cai.repl.commands import handle_command_with_autocorrect

                for line in command_lines:
                    parts = line.split()
                    if not parts:
                        continue
                    command = parts[0]
                    args = parts[1:] if len(parts) > 1 else None

                    handled, suggested = handle_command_with_autocorrect(command, args)
                    if handled:
                        # Check /parallel run trigger
                        import cai.repl.commands._parallel_monolith as _par_mod
                        if _par_mod._TRIGGER_PARALLEL_RUN:
                            _par_mod._TRIGGER_PARALLEL_RUN = False
                            _run_parallel_turn(
                                agent,
                                "",
                                console,
                                PARALLEL_CONFIGS,
                                PARALLEL_AGENT_INSTANCES,
                                last_agent_type,
                                update_agent_models_recursively,
                            )
                            turn_count += 1
                            use_initial_prompt = False
                            stop_active_timer()
                            start_idle_timer()
                            _try_refresh_info_bars()

                        # Check /queue run trigger
                        import cai.repl.commands.queue as _queue_mod
                        if _queue_mod._TRIGGER_QUEUE_RUN:
                            _queue_mod._TRIGGER_QUEUE_RUN = False
                            auto_run_queue = True

                        if _repl_exit_cmd.REPL_EXIT_REQUESTED:
                            break
                        continue

                    # Commands print their own usage/errors. Avoid generic fallback noise
                    # here, which can duplicate messages for valid commands.

                if _repl_exit_cmd.REPL_EXIT_REQUESTED:
                    _repl_exit_cmd.REPL_EXIT_REQUESTED = False
                    _handle_exit_interrupt(
                        agent, console, session_logger, idle_time, idle_start_time, force_until_flag,
                        PARALLEL_CONFIGS, PARALLEL_AGENT_INSTANCES,
                    )
                    break

                continue

            # ---- Agent execution ----
            _lf = session_logger.filename
            _print_session_log_target(console, _lf)

            # Build history context
            history_context = _build_history_context(agent)
            try:
                from cai.util import sanitize_message_list as fix_message_list
                history_context = fix_message_list(history_context)
            except Exception:
                pass

            # CTF flag check
            if is_pentestperf_available() and _setup.ctf_init == 0 and force_until_flag:
                found_flag, flag = check_flag(str(history_context), _setup.ctf_global)
                if found_flag:
                    console.print(Text(f"Correct flag submitted: {flag}! Stopping CTF.", style="bold green"))
                    _setup.messages_ctf = ""
                    _setup.ctf_init = 1
                    if _setup.ctf_global:
                        _setup.ctf_global.stop_ctf()
                    os.environ["CTF_FLAG_FOUND"] = str(flag)
                    return
                else:
                    console.print(Text("Incorrect flag! Try again.", style="bold red"))

            # Pass only the new user message — history lives in model.message_history
            # and get_response() already prepends it. Passing it here too caused
            # the entire conversation to be sent TWICE on every API call.
            if history_context:
                conversation_input = user_input
            else:
                # First turn: no history yet; prepend CTF context if applicable
                if user_input == _setup.messages_ctf:
                    conversation_input = user_input
                else:
                    conversation_input = _setup.messages_ctf + user_input

            # After Ctrl+C or agent switch, force one-turn task reset so the model
            # prioritizes the current user request unless resume is explicit.
            if os.getenv("CAI_TASK_RESET_PENDING") == "1":
                from cai.util.session_compact import consume_agent_handoff

                handoff = consume_agent_handoff()
                if handoff:
                    reset_note = (
                        "SYSTEM CONTEXT NOTE: The active agent changed. Continue the same engagement "
                        "using the handoff below (compacted context + recent findings). "
                        "Do not claim there is no prior history.\n\n"
                        f"{handoff}\n\n"
                    )
                else:
                    reset_note = (
                        "SYSTEM CONTEXT NOTE: The previous task was interrupted or the active agent changed. "
                        "Treat the user's current request as the active task and do not continue prior unfinished work "
                        "unless the user explicitly asks to resume it.\n\n"
                    )
                conversation_input = reset_note + conversation_input
                os.environ["CAI_TASK_RESET_PENDING"] = "0"

            # Parallel count execution (simple, non-configured)
            if parallel_count > 1:
                _run_simple_parallel(
                    agent, conversation_input, parallel_count,
                    last_agent_type, console, update_agent_models_recursively,
                )
            else:
                _run_single_agent(
                    agent, conversation_input, console,
                    force_until_flag, _setup.ctf_global,
                )

            turn_count += 1
            use_initial_prompt = False
            stop_active_timer()
            start_idle_timer()
            _try_refresh_info_bars()
            if os.getenv("CAI_SINGLE_SHOT_CLI", "").lower() in ("1", "true", "yes"):
                if os.getenv("CAI_CONTINUOUS_OPS_LOOP_CHILD", "").lower() in ("1", "true", "yes"):
                    try:
                        from cai.continuous_ops.loop_tick_epilogue import (
                            export_loop_child_snapshot,
                            run_continuous_ops_extra_turns,
                        )

                        run_continuous_ops_extra_turns(
                            agent, console, force_until_flag, _setup.ctf_global,
                        )
                    except Exception:
                        pass
                    try:
                        export_loop_child_snapshot(agent)
                    except Exception:
                        pass
                return

            # Automatic continuation
            current_continue_mode = continue_mode
            try:
                import importlib
                continue_module = importlib.import_module('cai.repl.commands.continue')
                current_continue_mode = continue_module.get_continue_mode() or continue_mode
            except ImportError:
                pass

            if current_continue_mode and not force_until_flag:
                if hasattr(agent, "model") and hasattr(agent.model, "message_history"):
                    if should_continue_automatically(agent.model.message_history, force_continue=True):
                        try:
                            continuation_prompt = asyncio.run(generate_continuation_advice(
                                agent_name=getattr(agent, "name", "Agent"),
                                message_history=agent.model.message_history,
                                console=console,
                            ))
                        except Exception:
                            continuation_prompt = "Continue working on the task based on your previous findings."
                            console.print(f"\n[dim white]Auto-continuing with:[/dim white] {continuation_prompt}")
                        from cai.repl.commands.queue import add_to_queue
                        add_to_queue(continuation_prompt)
                        auto_run_queue = True

        except KeyboardInterrupt:
            _handle_inner_interrupt(agent, console)
        except Exception as e:
            _handle_loop_exception(e, agent, console, force_until_flag)
            _try_refresh_info_bars()
            if (
                os.getenv("CAI_SINGLE_SHOT_CLI", "").lower() in ("1", "true", "yes")
                and os.getenv("CAI_CONTINUOUS_OPS_LOOP_CHILD", "").lower() in ("1", "true", "yes")
            ):
                raise SystemExit(1) from e


# ---------------------------------------------------------------------------
# Helper: build conversation history from agent model
# ---------------------------------------------------------------------------

def _build_history_context(agent):
    history_context = []
    if not (hasattr(agent, "model") and hasattr(agent.model, "message_history")):
        return history_context

    for msg in agent.model.message_history:
        role = msg.get("role")
        content = msg.get("content")
        tool_calls = msg.get("tool_calls")

        if role == "user":
            history_context.append({"role": "user", "content": content or ""})
        elif role == "system":
            history_context.append({"role": "system", "content": content or ""})
        elif role == "assistant":
            if tool_calls:
                history_context.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            elif content is not None:
                history_context.append({"role": "assistant", "content": content})
            else:
                history_context.append({"role": "assistant", "content": None})
        elif role == "tool":
            history_context.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id"),
                "content": msg.get("content"),
            })
    return history_context


# ---------------------------------------------------------------------------
# Helper: single agent execution (streamed / non-streamed)
# ---------------------------------------------------------------------------

def _run_single_agent(agent, conversation_input, console, force_until_flag, ctf_global):
    stream = _get_config().stream  # [S] centralised config

    # Compact REPL: wrap the entire turn with TurnStart/TurnSummary events so
    # the live block is guaranteed to collapse between turns. No-op when
    # compact mode is disabled (CAI_COMPACT_REPL=0) or in TUI mode.
    from cai.repl.ui.compact_wiring import turn_lifecycle

    with turn_lifecycle(user_input=str(conversation_input or "")):
        if stream:
            _run_streamed(agent, conversation_input, console, force_until_flag, ctf_global)
        else:
            _run_non_streamed(agent, conversation_input, console, force_until_flag, ctf_global)


def _run_streamed(agent, conversation_input, console, force_until_flag, ctf_global):
    async def process_streamed_response(agent, conversation_input):
        tool_calls_seen = {}
        tool_results_seen = set()
        result = None
        stream_iterator = None
        try:
            result = Runner.run_streamed(agent, conversation_input)
            stream_iterator = result.stream_events()
            async for event in stream_iterator:
                if isinstance(event, RunItemStreamEvent):
                    if event.name == "tool_called":
                        if hasattr(event.item, "raw_item"):
                            call_id = getattr(event.item.raw_item, "call_id", None)
                            if call_id:
                                tool_calls_seen[call_id] = event.item
                    elif event.name == "tool_output":
                        if isinstance(event.item, ToolCallOutputItem):
                            call_id = event.item.raw_item["call_id"]
                            tool_results_seen.add(call_id)
                            agent.model.add_to_message_history({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "content": event.item.output,
                            })
            return result
        except (KeyboardInterrupt, asyncio.CancelledError) as e:
            if stream_iterator is not None:
                try:
                    await stream_iterator.aclose()
                except Exception:
                    pass
            if result is not None and hasattr(result, "_cleanup_tasks"):
                try:
                    result._cleanup_tasks()
                except Exception:
                    pass
            try:
                for call_id, tool_item in tool_calls_seen.items():
                    if call_id not in tool_results_seen:
                        agent.model.add_to_message_history({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": "Tool execution interrupted",
                        })
            except Exception:
                pass
            raise e
        except MaxTurnsExceeded as e:
            if force_until_flag and ctf_global:
                return
            raise e
        except UserCancelledCommand:
            if stream_iterator is not None:
                try:
                    await stream_iterator.aclose()
                except Exception:
                    pass
            if result is not None and hasattr(result, "_cleanup_tasks"):
                try:
                    result._cleanup_tasks()
                except Exception:
                    pass
            raise
        except Exception as e:
            if stream_iterator is not None:
                try:
                    await stream_iterator.aclose()
                except Exception:
                    pass
            if result is not None and hasattr(result, "_cleanup_tasks"):
                try:
                    result._cleanup_tasks()
                except Exception:
                    pass
            logger = logging.getLogger(__name__)
            if isinstance(e, (LLMProviderUnavailable, LLMTimeout, LLMRateLimited)):
                raise
            if is_transient_litellm_provider_error(e):
                summary = provider_error_summary(e)
                logger.warning("Streaming provider error: %s", summary)
                raise LLMProviderUnavailable(
                    f"Model provider disconnected during streaming: {summary}"
                ) from e
            logger.error(f"Error occurred during streaming: {str(e)}", exc_info=True)
            if _get_config().debug == 2:
                import traceback
                print(f"\n[Error occurred during streaming: {str(e)}]\nLocation: {traceback.format_exc()}")
            return None

    try:
        asyncio.run(process_streamed_response(agent, conversation_input))
    except asyncio.CancelledError as e:
        raise KeyboardInterrupt from e
    except MaxTurnsExceeded as e:
        if force_until_flag and ctf_global:
            return
        raise e
    except UserCancelledCommand:
        raise
    except OutputGuardrailTripwireTriggered as e:
        _print_guardrail_warning(e)
    except KeyboardInterrupt:
        raise
    except RuntimeError as e:
        if "This event loop is already running" in str(e) or "Cannot close a running event loop" in str(e):
            import sys
            if sys.platform.startswith("win"):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            else:
                asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(process_streamed_response(agent, conversation_input))
            except OutputGuardrailTripwireTriggered as e2:
                _print_guardrail_warning(e2)
                new_loop.close()
                return
            finally:
                if not new_loop.is_closed():
                    new_loop.close()
        else:
            raise


def _run_non_streamed(agent, conversation_input, console, force_until_flag, ctf_global):
    max_retries = 5
    last_input = conversation_input
    response = None

    for attempt in range(max_retries):
        try:
            response = asyncio.run(Runner.run(agent, last_input))
            break
        except asyncio.CancelledError as e:
            raise KeyboardInterrupt from e
        except (Timeout, RateLimitError, ConnectionError) as e:
            if attempt < max_retries - 1:
                import random
                _base, _cap = 5.0, 60.0
                delay = min(_base * (2 ** attempt), _cap) + random.uniform(0, 2.0)
                _log = logging.getLogger(__name__)
                if verbose_http_retries():
                    print(
                        f"{type(e).__name__} on attempt {attempt + 1}/{max_retries}, "
                        f"retrying in {delay:.0f}s..."
                    )
                else:
                    _log.warning(
                        "Runner %s attempt %s/%s, sleeping %.0fs",
                        type(e).__name__,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                import time; time.sleep(delay)
                # Clean retry: re-send the SAME input — don't inject "continue"
                # into message history as it pollutes context [F]
            else:
                print("Max retries reached")
                raise
        except MaxTurnsExceeded as e:
            if force_until_flag and ctf_global:
                return
            raise e
        except InputGuardrailTripwireTriggered as e:
            _print_input_guardrail_warning(e)
            break
        except OutputGuardrailTripwireTriggered as e:
            _print_guardrail_warning(e)
            break
    else:
        pass

    if response is None:
        return

    for item in response.new_items:
        if isinstance(item, ToolCallOutputItem):
            tool_call_id = item.raw_item["call_id"]
            tool_msg_exists = any(
                msg.get("role") == "tool" and msg.get("tool_call_id") == tool_call_id
                for msg in agent.model.message_history
            )
            if not tool_msg_exists:
                agent.model.add_to_message_history({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": item.output,
                })

    try:
        from cai.util import sanitize_message_list as fix_message_list
        agent.model.message_history[:] = fix_message_list(agent.model.message_history)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helper: simple parallel (CAI_PARALLEL > 1)
# ---------------------------------------------------------------------------

def _run_simple_parallel(agent, conversation_input, parallel_count, last_agent_type, console, _update_fn):
    async def run_instance(instance_number, context):
        try:
            from cai.agents import get_available_agents, get_agent_by_name
            base_agent = get_available_agents().get(last_agent_type.lower())
            agent_display_name = base_agent.name if base_agent else last_agent_type
            custom_name = f"{agent_display_name} #{instance_number + 1}"
            instance_agent = get_agent_by_name(last_agent_type, custom_name=custom_name, agent_id=f"P{instance_number + 1}")

            if hasattr(instance_agent, "model") and hasattr(agent, "model"):
                if hasattr(instance_agent.model, "model") and hasattr(agent.model, "model"):
                    instance_specific = os.getenv(f"CAI_{last_agent_type.upper()}_{instance_number + 1}_MODEL")
                    agent_specific = os.getenv(f"CAI_{last_agent_type.upper()}_MODEL")
                    model_to_use = instance_specific or agent_specific or agent.model.model
                    _update_fn(instance_agent, model_to_use)

            result = await Runner.run(instance_agent, context)
            return (instance_number, result)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in instance {instance_number}: {str(e)}", exc_info=True)
            if _get_config().debug == 2:
                console.print(f"[bold red]Error in instance {instance_number}: {str(e)}[/bold red]")
            return (instance_number, None)

    async def process_all():
        tasks = [run_instance(i, conversation_input) for i in range(parallel_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for item in results:
            if isinstance(item, asyncio.CancelledError):
                raise item
        return [
            item for item in results
            if isinstance(item, tuple) and len(item) == 2 and item[1] is not None
        ]

    try:
        results = asyncio.run(process_all())
    except asyncio.CancelledError as e:
        raise KeyboardInterrupt from e
    for idx, result in results:
        if result and hasattr(result, "final_output") and result.final_output:
            agent.model.add_to_message_history({"role": "assistant", "content": f"{result.final_output}"})


# ---------------------------------------------------------------------------
# Helper: configured parallel execution (PARALLEL_CONFIGS)
# ---------------------------------------------------------------------------

def _run_parallel_turn(agent, user_input, console, configs, instances, last_agent_type, _update_fn):
    """Execute one turn with all configured parallel agents."""
    from cai.agents import get_available_agents, get_agent_by_name
    from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER

    # Default to external terminal fan-out (product expectation). If unavailable
    # on the host, _run_parallel_turn_external() emits guidance and falls back.
    exec_mode = os.getenv("CAI_PARALLEL_EXEC_MODE", "external").strip().lower()
    if exec_mode == "external":
        return _run_parallel_turn_external(console, configs, user_input)
    if os.environ.get("CAI_PARALLEL_MODE_HINT_SHOWN") != "1":
        console.print(
            build_cai_markup_line(
                "[#9aa0a6]Parallel mode is running in logical mode (single main terminal). "
                "Set [/][bold #00ff9d]CAI_PARALLEL_EXEC_MODE=external[/bold #00ff9d][#9aa0a6] to launch separate system terminals.[/]"
            )
        )
        os.environ["CAI_PARALLEL_MODE_HINT_SHOWN"] = "1"

    agent_ids = [c.id or f"P{i}" for i, c in enumerate(configs, 1)]

    # Transfer history to parallel isolation if needed
    already_has_histories = False
    if PARALLEL_ISOLATION.is_parallel_mode():
        for aid in agent_ids:
            if PARALLEL_ISOLATION.get_isolated_history(aid):
                already_has_histories = True
                break

    if not already_has_histories:
        current_history = []
        if hasattr(agent, "model") and hasattr(agent.model, "message_history"):
            current_history = agent.model.message_history
        elif hasattr(agent, "name"):
            current_history = AGENT_MANAGER.get_message_history(agent.name)

        pattern_description = os.getenv("CAI_PATTERN_DESCRIPTION", "")
        if "different contexts" in pattern_description.lower():
            PARALLEL_ISOLATION._parallel_mode = True
            if current_history and agent_ids:
                PARALLEL_ISOLATION.clear_all_histories()
                PARALLEL_ISOLATION.replace_isolated_history(agent_ids[0], current_history.copy())
                for aid in agent_ids[1:]:
                    PARALLEL_ISOLATION.replace_isolated_history(aid, [])
        else:
            PARALLEL_ISOLATION.transfer_to_parallel(current_history, len(configs), agent_ids)
    else:
        PARALLEL_ISOLATION._parallel_mode = True

    # Ensure agent instances exist
    for idx, config in enumerate(configs, 1):
        instance_key = (config.agent_name, idx)
        if instance_key not in instances:
            base = get_available_agents().get(config.agent_name.lower())
            if base:
                display_name = getattr(base, "name", config.agent_name)
                custom_name = f"{display_name} #{idx}"
                model_to_use = _resolve_parallel_model_name(config.model)
                slot_pid = config.id or f"P{idx}"
                inst = get_agent_by_name(
                    config.agent_name,
                    custom_name=custom_name,
                    model_override=model_to_use,
                    agent_id=slot_pid,
                )
                instances[instance_key] = inst

    async def run_agent_instance(config, input_text):
        instance_agent = None
        agent_id = None
        try:
            instance_number = configs.index(config) + 1
            agent_id = config.id or f"P{instance_number}"
            instance_key = (config.agent_name, instance_number)
            instance_agent = instances.get(instance_key)

            if not instance_agent:
                from cai.agents.patterns import get_pattern
                agent_display_name = None
                actual_agent_name = config.agent_name
                if config.agent_name.endswith("_pattern"):
                    pattern = get_pattern(config.agent_name)
                    if pattern and hasattr(pattern, "entry_agent"):
                        agent_display_name = getattr(pattern.entry_agent, "name", config.agent_name)
                else:
                    base = get_available_agents().get(config.agent_name.lower())
                    agent_display_name = base.name if base else config.agent_name
                if not config.agent_name.endswith("_pattern"):
                    custom_name = f"{agent_display_name} #{instance_number}"
                else:
                    custom_name = agent_display_name
                model_to_use = _resolve_parallel_model_name(config.model)
                instance_agent = get_agent_by_name(
                    actual_agent_name,
                    custom_name=custom_name,
                    model_override=model_to_use,
                    agent_id=agent_id,
                )
                instances[instance_key] = instance_agent

            agent_display_name = getattr(instance_agent, "name", config.agent_name)
            AGENT_MANAGER.set_parallel_agent(agent_id, instance_agent, agent_display_name)

            model_to_use = _resolve_parallel_model_name(config.model)
            if model_to_use:
                _update_fn(instance_agent, model_to_use)

            instance_input = config.prompt if config.prompt else input_text
            result = await Runner.run(instance_agent, instance_input)

            # Cleanup streaming resources
            try:
                from cai.util import finish_tool_streaming, cli_print_tool_output, _LIVE_STREAMING_PANELS
                if hasattr(cli_print_tool_output, "_streaming_sessions"):
                    for session_id, session_info in list(cli_print_tool_output._streaming_sessions.items()):
                        if session_info.get("agent_name") == agent_display_name and not session_info.get("is_complete", False):
                            finish_tool_streaming(
                                tool_name=session_info.get("tool_name", "unknown"),
                                args=session_info.get("args", {}),
                                output=session_info.get("current_output", "Tool execution completed"),
                                call_id=session_id,
                                execution_info={"status": "completed", "is_final": True},
                                token_info={"agent_name": agent_display_name, "agent_id": getattr(instance_agent.model, "agent_id", None) if hasattr(instance_agent, "model") else None},
                            )
            except Exception:
                pass

            if instance_agent and agent_id:
                if hasattr(instance_agent, "model") and hasattr(instance_agent.model, "message_history"):
                    PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)

            return (config, result)
        except asyncio.CancelledError:
            try:
                from cai.util import cleanup_agent_streaming_resources
                if instance_agent:
                    cleanup_agent_streaming_resources(getattr(instance_agent, "name", config.agent_name))
            except Exception:
                pass
            if instance_agent and agent_id:
                if hasattr(instance_agent, "model") and hasattr(instance_agent.model, "message_history"):
                    PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)
            raise
        except Exception as e:
            try:
                from cai.util import cleanup_agent_streaming_resources
                if instance_agent:
                    cleanup_agent_streaming_resources(getattr(instance_agent, "name", config.agent_name))
            except Exception:
                pass
            if instance_agent and agent_id:
                if hasattr(instance_agent, "model") and hasattr(instance_agent.model, "message_history"):
                    PARALLEL_ISOLATION.replace_isolated_history(agent_id, instance_agent.model.message_history)
            logger = logging.getLogger(__name__)
            logger.error(f"Error in {config.agent_name}: {str(e)}", exc_info=True)
            if _get_config().debug == 2:
                console.print(f"[bold red]Error in {config.agent_name}: {str(e)}[/bold red]")
            return (config, None)

    async def run_all():
        tasks = [run_agent_instance(c, c.prompt if c.prompt else user_input) for c in configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for item in results:
            if isinstance(item, asyncio.CancelledError):
                raise item
        return [item for item in results if isinstance(item, tuple) and len(item) == 2 and item[1] is not None]

    launched_names = []
    for config in configs:
        try:
            launched_names.append(_sync_parallel_display_name(config, configs, get_available_agents))
        except Exception:
            launched_names.append(config.agent_name)
    launched_preview = ", ".join(launched_names) if launched_names else "parallel agents"
    if len(launched_preview) > 100:
        launched_preview = launched_preview[:97] + "..."
    wait_msg = build_startup_hint_renderable(
        f"Launched agents {launched_preview} in parallel. Waiting for responses..."
    )

    results = []
    # Keep main terminal clean: suppress verbose per-agent streaming/tool panels
    # during parallel fan-out; main will show the aggregated summary only.
    old_stream = os.environ.get("CAI_STREAM")
    old_tool_stream = os.environ.get("CAI_TOOL_STREAM")
    os.environ["CAI_STREAM"] = "false"
    os.environ["CAI_TOOL_STREAM"] = "false"
    wait_console = Console(stderr=True, highlight=False)
    try:
        # Silence noisy per-agent rich/tool output in the main stdout while workers run.
        # Keep the waiting spinner visible on stderr.
        with wait_console.status(wait_msg, spinner="dots"):
            with contextlib.redirect_stdout(io.StringIO()):
                results = asyncio.run(run_all())
    except (KeyboardInterrupt, asyncio.CancelledError) as e:
        for idx, config in enumerate(configs, 1):
            instance_key = (config.agent_name, idx)
            if instance_key in instances:
                inst = instances[instance_key]
                if hasattr(inst, "model") and hasattr(inst.model, "message_history"):
                    aid = config.id or f"P{idx}"
                    PARALLEL_ISOLATION.replace_isolated_history(aid, inst.model.message_history)
                    disp = _sync_parallel_display_name(config, configs, get_available_agents)
                    AGENT_MANAGER.clear_history(disp)
                    for msg in inst.model.message_history:
                        AGENT_MANAGER.add_to_history(disp, msg)
        if isinstance(e, asyncio.CancelledError):
            raise KeyboardInterrupt from e
        raise
    finally:
        if old_stream is None:
            os.environ.pop("CAI_STREAM", None)
        else:
            os.environ["CAI_STREAM"] = old_stream
        if old_tool_stream is None:
            os.environ.pop("CAI_TOOL_STREAM", None)
        else:
            os.environ["CAI_TOOL_STREAM"] = old_tool_stream

    if not results:
        console.print(
            build_cai_markup_line(
                "[#9aa0a6]Parallel execution finished with no successful outputs.[/]"
            )
        )
        return

    # Show a compact comparison in the main terminal after all agents finish.
    summary_table = _new_parallel_execution_summary_table()
    _add_parallel_summary_columns(summary_table)

    for row_i, (config, result) in enumerate(results):
        row_fg = _parallel_summary_row_fg(row_i)
        prompt_src = "preset" if config.prompt else "main input"
        model_name = _resolve_parallel_model_name(config.model)
        final_output = getattr(result, "final_output", "")
        if final_output is None:
            final_output = ""
        preview_raw = str(final_output).strip()
        preview_clean, preview_trunc = _sanitize_parallel_preview_for_table(
            preview_raw, max_chars=900
        )
        if preview_clean:
            preview_renderable = _parallel_summary_preview_renderable(
                preview_clean, preview_trunc, row_fg=row_fg
            )
        else:
            preview_renderable = Text("(empty output)", style=row_fg)
        agent_name = _sync_parallel_display_name(config, configs, get_available_agents)
        status_text = Text("ok", style=f"bold {_PARALLEL_SUMMARY_GREEN}")
        summary_table.add_row(
            agent_name,
            Text(model_name, style=row_fg),
            Text(prompt_src, style=row_fg),
            status_text,
            preview_renderable,
        )

    # Print on a clean line after spinner teardown.
    console.print()
    console.print(summary_table)
    console.print(
        build_cai_markup_line(
            f"[{_PARALLEL_SUMMARY_MUTED}][italic]All parallel agents completed. "
            "Use /parallel merge to consolidate histories.[/italic][/]"
        )
    )


def _sync_parallel_display_name(config, configs, get_available_agents_fn):
    available = get_available_agents_fn()
    if config.agent_name in available:
        base = available[config.agent_name]
        name = getattr(base, "name", config.agent_name)
        total = sum(1 for c in configs if c.agent_name == config.agent_name)
        if total > 1:
            num = 0
            for c in configs:
                if c.agent_name == config.agent_name:
                    num += 1
                    if c.id == config.id:
                        break
            name = f"{name} #{num}"
        return name
    return config.agent_name


def _detect_external_terminal_backend() -> tuple[str | None, str]:
    """Return (backend, human_hint) for external terminal execution."""
    is_wsl = "microsoft" in platform.release().lower() or bool(os.getenv("WSL_DISTRO_NAME"))
    system = platform.system().lower()

    if system == "darwin":
        if shutil.which("osascript"):
            return "osascript", "macOS Terminal (via osascript)"
        return None, "Install/enable AppleScript CLI (osascript)"

    # Linux / WSL
    for candidate in ("gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
        if shutil.which(candidate):
            return candidate, candidate

    if is_wsl:
        return None, "Install one terminal launcher inside WSL/X11 (e.g. xterm)"
    return None, "Install one of: gnome-terminal, konsole, xfce4-terminal, xterm"


def _spawn_external_worker_terminal(backend: str, title: str, command: str) -> bool:
    """Spawn worker terminal window/tab for one agent."""
    try:
        if backend == "gnome-terminal":
            subprocess.Popen(
                [
                    "gnome-terminal",
                    "--title",
                    title,
                    "--",
                    "bash",
                    "-lc",
                    f"{command}; echo; echo '[CAI] Worker finished.'; read -r -p 'Press Enter to close...'",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if backend == "konsole":
            subprocess.Popen(
                [
                    "konsole",
                    "--new-tab",
                    "-p",
                    f"tabtitle={title}",
                    "-e",
                    "bash",
                    "-lc",
                    f"{command}; echo; echo '[CAI] Worker finished.'; read -r -p 'Press Enter to close...'",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if backend == "xfce4-terminal":
            subprocess.Popen(
                [
                    "xfce4-terminal",
                    "--title",
                    title,
                    "--hold",
                    "-e",
                    f"bash -lc {shlex.quote(command)}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if backend == "xterm":
            subprocess.Popen(
                [
                    "xterm",
                    "-T",
                    title,
                    "-hold",
                    "-e",
                    "bash",
                    "-lc",
                    command,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if backend == "osascript":
            osa_cmd = (
                'tell application "Terminal" to do script '
                + json.dumps(f"{command}; echo; echo '[CAI] Worker finished.'")
            )
            subprocess.Popen(
                ["osascript", "-e", osa_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    except Exception:
        return False
    return False


def _run_parallel_turn_external(console, configs, user_input: str) -> None:
    """Run parallel workers in external system terminals and summarize in main."""
    from cai.util.pricing import COST_TRACKER
    from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
    from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER

    main_session_before = float(getattr(COST_TRACKER, "session_total_cost", 0.0) or 0.0)
    backend, backend_hint = _detect_external_terminal_backend()
    if not backend:
        console.print(
            build_cai_markup_line(
                "[#9aa0a6]External parallel mode requested, but no supported terminal launcher was found.[/]"
            )
        )
        console.print(build_cai_markup_line(f"[#9aa0a6]{backend_hint}[/]"))
        console.print(
            build_cai_markup_line(
                "[#9aa0a6]Falling back to logical mode. "
                "Note: these are system-level requirements and are not installed via [/]"
                "[bold #00ff9d]pyproject.toml[/bold #00ff9d][#9aa0a6].[/]"
            )
        )
        old_mode = os.environ.get("CAI_PARALLEL_EXEC_MODE")
        os.environ["CAI_PARALLEL_EXEC_MODE"] = "logical"
        try:
            # Re-enter logical mode path
            from cai.agents import get_available_agents, get_agent_by_name
            from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER
            # Build a minimal fallback runner context from current active agent if available.
            current_agent = AGENT_MANAGER.get_active_agent()
            if current_agent is None:
                return
            return _run_parallel_turn(
                current_agent,
                user_input,
                console,
                configs,
                PARALLEL_AGENT_INSTANCES,
                getattr(current_agent, "name", "agent"),
                update_agent_models_recursively,
            )
        finally:
            if old_mode is None:
                os.environ.pop("CAI_PARALLEL_EXEC_MODE", None)
            else:
                os.environ["CAI_PARALLEL_EXEC_MODE"] = old_mode

    console.print(
        build_cai_markup_line(
            "[dim]External parallel mode uses system terminal launchers "
            f"({backend_hint}); this is not managed by pyproject dependencies.[/dim]"
        )
    )
    _pe_timeout = float(os.getenv("CAI_PARALLEL_EXTERNAL_TIMEOUT", "1800"))
    console.print(
        build_cai_markup_line(
            "[dim]External parallel: the main CLI waits up to "
            f"{int(_pe_timeout)}s for each worker result file "
            "(CAI_PARALLEL_EXTERNAL_TIMEOUT). Workers may keep running in their terminals after that. "
            "The cost footer sums metrics from workers that finished in time—it is not a single "
            "agent's token limit.[/dim]"
        )
    )

    worker_specs = []
    tmp_dir = tempfile.mkdtemp(prefix="cai_parallel_")
    mcp_bootstrap_path: str | None = None
    try:
        from cai.repl.commands.mcp import export_parallel_mcp_bootstrap_dict

        _mcp_spec = export_parallel_mcp_bootstrap_dict()
        if _mcp_spec:
            mcp_bootstrap_path = os.path.join(tmp_dir, "mcp_bootstrap.json")
            with open(mcp_bootstrap_path, "w", encoding="utf-8") as bf:
                json.dump(_mcp_spec, bf, ensure_ascii=False)
            console.print(
                build_cai_markup_line(
                    "[dim]Active MCP servers and /mcp associations are passed to each "
                    "external worker (re-connected in that process).[/dim]"
                )
            )
    except Exception:
        mcp_bootstrap_path = None
    used_agent_ids = set()
    for idx, config in enumerate(configs, 1):
        agent_id = config.id or f"P{idx}"
        if agent_id in used_agent_ids:
            agent_id = f"{agent_id}_{idx}"
        used_agent_ids.add(agent_id)
        agent_name = config.agent_name
        model = _resolve_parallel_model_name(config.model)
        prompt = config.prompt if config.prompt else user_input
        result_path = os.path.join(tmp_dir, f"{agent_id}.json")
        title = f"CAI Parallel {agent_id}"
        worker_py = (
            f"{shlex.quote(sys.executable)} -m cai.parallel_worker "
            f"--agent {shlex.quote(agent_name)} "
            f"--agent-id {shlex.quote(agent_id)} "
            f"--model {shlex.quote(model)} "
            f"--prompt {shlex.quote(prompt)} "
            f"--result-file {shlex.quote(result_path)}"
        )
        if mcp_bootstrap_path:
            cmd = (
                f"export CAI_PARALLEL_MCP_BOOTSTRAP={shlex.quote(mcp_bootstrap_path)} && "
                f"{worker_py}"
            )
        else:
            cmd = worker_py
        ok = _spawn_external_worker_terminal(backend, title, cmd)
        if ok:
            worker_specs.append(
                {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "model": model,
                    "prompt_source": "preset" if config.prompt else "main input",
                    "result_file": result_path,
                }
            )
        else:
            console.print(
                build_cai_markup_line(
                    f"[red]Failed to open terminal for {agent_id} ({agent_name}).[/red]"
                )
            )

    if not worker_specs:
        console.print(
            build_cai_markup_line(
                "[red]No external worker terminals could be launched.[/red]"
            )
        )
        return

    launched_preview = ", ".join([w["agent_id"] for w in worker_specs])
    wait_msg = build_startup_hint_renderable(
        f"Launched agents {launched_preview} in parallel (external terminals). "
        "Waiting for responses..."
    )

    timeout_s = float(os.getenv("CAI_PARALLEL_EXTERNAL_TIMEOUT", "1800"))
    start = time.time()
    pending = {w["result_file"]: w for w in worker_specs}
    completed = []

    wait_console = Console(stderr=True, highlight=False)
    with wait_console.status(wait_msg, spinner="dots"):
        while pending and (time.time() - start) < timeout_s:
            finished_paths = []
            for path, spec in pending.items():
                if os.path.exists(path):
                    try:
                        with open(path, encoding="utf-8") as f:
                            payload = json.load(f)
                        completed.append((spec, payload))
                        finished_paths.append(path)
                    except Exception:
                        # File may still be being written
                        continue
            for p in finished_paths:
                pending.pop(p, None)
            if pending:
                time.sleep(0.3)

    # Build summary on main
    summary_table = _new_parallel_execution_summary_table()
    _add_parallel_summary_columns(summary_table)

    payload_by_id = {spec["agent_id"]: (spec, payload) for spec, payload in completed}
    total_in_tokens = 0
    total_out_tokens = 0
    total_max_tokens = 0
    worker_session_cost_sum = 0.0
    total_last_interaction_cost = 0.0
    for row_i, spec in enumerate(worker_specs):
        row_fg = _parallel_summary_row_fg(row_i)
        agent_id = spec["agent_id"]
        status = "timeout"
        preview = "(no result file yet)"
        preview_renderable = Text(preview, style=row_fg)
        if agent_id in payload_by_id:
            _spec, payload = payload_by_id[agent_id]
            status = payload.get("status", "unknown")
            final_output = payload.get("final_output", "") or payload.get("error", "")
            preview_raw = str(final_output or "").strip()
            preview_clean, preview_trunc = _sanitize_parallel_preview_for_table(
                preview_raw, max_chars=1200
            )
            if preview_clean:
                preview_renderable = _parallel_summary_preview_renderable(
                    preview_clean, preview_trunc, row_fg=row_fg
                )
            else:
                one_line = " ".join(preview_raw.split())
                if len(one_line) > 120:
                    one_line = one_line[:117] + "\u2026"
                preview_renderable = _parallel_preview_text_with_inline_bold(
                    one_line or "(empty)", row_fg
                )
            usage = payload.get("usage", {}) or {}
            total_in_tokens += int(usage.get("input_tokens", 0) or 0)
            total_out_tokens += int(usage.get("output_tokens", 0) or 0)
            total_max_tokens += int(usage.get("max_input_tokens", 0) or 0)
            cost = payload.get("cost", {}) or {}
            worker_session_cost_sum += float(cost.get("session_total_cost", 0.0) or 0.0)
            total_last_interaction_cost += float(cost.get("last_interaction_cost", 0.0) or 0.0)
        st = str(status).lower()
        if st == "ok":
            status_style: str = f"bold {_PARALLEL_SUMMARY_GREEN}"
        else:
            status_style = row_fg
        status_renderable = Text(str(status), style=status_style)

        summary_table.add_row(
            f'{spec["agent_name"]} [{agent_id}]',
            Text(spec["model"], style=row_fg),
            Text(spec["prompt_source"], style=row_fg),
            status_renderable,
            preview_renderable,
        )

    # Persist worker histories so /merge can see all external parallel agents.
    for spec in worker_specs:
        agent_id = spec["agent_id"]
        if agent_id not in payload_by_id:
            continue
        _spec, payload = payload_by_id[agent_id]
        hist = payload.get("history", [])
        if not isinstance(hist, list) or not hist:
            continue
        try:
            # Keep isolation store in sync with external workers.
            PARALLEL_ISOLATION.replace_isolated_history(agent_id, hist)
            # Also mirror into manager history by id for merge/discovery paths.
            AGENT_MANAGER.clear_history(agent_id)
            for msg in hist:
                if isinstance(msg, dict):
                    AGENT_MANAGER.add_to_history(agent_id, msg)
        except Exception:
            pass

    console.print()
    console.print(summary_table)
    # Use the standard CAI pricing footer render (same style as normal flow),
    # but with aggregated metrics: existing main session + all worker sessions.
    aggregated_session_total = main_session_before + worker_session_cost_sum
    prev_last = float(getattr(COST_TRACKER, "last_interaction_cost", 0.0) or 0.0)
    prev_in = int(getattr(COST_TRACKER, "interaction_input_tokens", 0) or 0)
    prev_out = int(getattr(COST_TRACKER, "interaction_output_tokens", 0) or 0)
    prev_session = float(getattr(COST_TRACKER, "session_total_cost", 0.0) or 0.0)
    try:
        COST_TRACKER.last_interaction_cost = total_last_interaction_cost
        COST_TRACKER.interaction_input_tokens = total_in_tokens
        COST_TRACKER.interaction_output_tokens = total_out_tokens
        COST_TRACKER.session_total_cost = aggregated_session_total
        try:
            from cai.util.streaming import _print_pricing_footer
            _print_pricing_footer(console, final=False, framed=True)
        except Exception:
            # Fallback text if footer renderer fails for any reason.
            agg_context_pct = (
                (total_in_tokens / total_max_tokens) * 100.0 if total_max_tokens > 0 else 0.0
            )
            console.print(
                build_cai_markup_line(
                    f"[#9aa0a6]In:{total_in_tokens:,} Out:{total_out_tokens:,} "
                    f"Session:${aggregated_session_total:.4f} {agg_context_pct:.1f}% context[/]"
                )
            )
    finally:
        COST_TRACKER.last_interaction_cost = prev_last
        COST_TRACKER.interaction_input_tokens = prev_in
        COST_TRACKER.interaction_output_tokens = prev_out
        COST_TRACKER.session_total_cost = prev_session
    if pending:
        console.print(
            build_cai_markup_line(
                f"[#9aa0a6]{len(pending)} worker(s) timed out after {int(timeout_s)}s. "
                "Results may still complete in external terminals. "
                "Increase [/][bold #00ff9d]CAI_PARALLEL_EXTERNAL_TIMEOUT[/bold #00ff9d][#9aa0a6] if needed.[/]"
            )
        )
    console.print(
        build_cai_markup_line(
            f"[{_PARALLEL_SUMMARY_MUTED}][italic]External parallel run finished.[/italic][/]"
        )
    )
    console.print(
        build_cai_markup_line(
            f"[{_PARALLEL_SUMMARY_MUTED}]Next steps: "
            f"[/][bold #00ff9d]/merge[/bold #00ff9d][{_PARALLEL_SUMMARY_MUTED}] to consolidate results into the main context "
            f"and exit parallel mode automatically.[/]"
        )
    )
    console.print(
        build_cai_markup_line(
            f"[{_PARALLEL_SUMMARY_MUTED}]Or use [/][bold #00ff9d]/parallel clear[/bold #00ff9d]"
            f"[{_PARALLEL_SUMMARY_MUTED}] to leave parallel mode without merging—parallel agent histories are not "
            f"folded into the main conversation.[/]"
        )
    )


# ---------------------------------------------------------------------------
# Interrupt / exception handlers
# ---------------------------------------------------------------------------

def _handle_exit_interrupt(agent, console, session_logger, idle_time, idle_start_time,
                            force_until_flag, parallel_configs, parallel_instances):
    """Handle Ctrl-C at the input prompt (outer loop)."""
    try:
        from cai.util import cleanup_all_streaming_resources

        cleanup_all_streaming_resources(leave_alternate_screen=False)
    except Exception:
        pass

    def format_time(seconds):
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d}"

    import cai.util.cli_session_clock as _session_clock

    Total = (
        time.time() - _session_clock.START_TIME
        if _session_clock.START_TIME is not None
        else 0.0
    )
    idle_time += time.time() - idle_start_time

    # Save parallel agent histories
    try:
        from cai.sdk.agents.parallel_isolation import PARALLEL_ISOLATION
        from cai.sdk.agents.simple_agent_manager import AGENT_MANAGER

        if parallel_configs and PARALLEL_ISOLATION.is_parallel_mode():
            for idx, config in enumerate(parallel_configs, 1):
                instance_key = (config.agent_name, idx)
                if instance_key in parallel_instances:
                    inst = parallel_instances[instance_key]
                    if hasattr(inst, "model") and hasattr(inst.model, "message_history"):
                        aid = config.id or f"P{idx}"
                        if inst.model.message_history:
                            PARALLEL_ISOLATION.replace_isolated_history(aid, inst.model.message_history)
    except Exception:
        pass

    # Clean up pending tool calls
    try:
        if hasattr(agent.model, "_converter") and hasattr(agent.model._converter, "recent_tool_calls"):
            for call_id, call_info in list(agent.model._converter.recent_tool_calls.items()):
                tool_response_exists = any(
                    msg.get("role") == "tool" and msg.get("tool_call_id") == call_id
                    for msg in agent.model.message_history
                )
                if not tool_response_exists:
                    assistant_exists = any(
                        msg.get("role") == "assistant" and msg.get("tool_calls")
                        and any(tc.get("id") == call_id for tc in msg.get("tool_calls", []))
                        for msg in agent.model.message_history
                    )
                    if not assistant_exists:
                        tool_name = (call_info.get("name") or "").strip()
                        if tool_name:
                            agent.model.add_to_message_history({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": call_info.get("arguments", "{}"),
                                    },
                                }],
                            })
                    agent.model.add_to_message_history({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": "Operation interrupted by user (Keyboard Interrupt during shutdown)",
                    })
            try:
                from cai.util import sanitize_message_list as fix
                agent.model.message_history[:] = fix(agent.model.message_history)
            except Exception:
                pass
    except Exception:
        pass

    # Session summary
    try:
        from cai.util import COST_TRACKER, get_active_time_seconds, get_idle_time_seconds
        active_secs = get_active_time_seconds()
        idle_secs = get_idle_time_seconds()
        session_cost = COST_TRACKER.session_total_cost

        metrics = {
            "session_time": format_time(Total),
            "active_time": format_time(active_secs),
            "idle_time": format_time(idle_secs),
            "llm_percentage": round((active_secs / Total) * 100, 1) if Total > 0 else 0.0,
            "session_cost": f"${session_cost:.6f}",
        }
        logging_path = getattr(session_logger, "filename", None)

        from rich.box import ROUNDED
        from rich.console import Group

        from cai.repl.ui.banner import CAI_GREEN, session_summary_panel_title

        _body = "dim white"
        text_content = [
            Text(f"Session Time: {metrics['session_time']}", style=_body),
            Text(
                f"Active Time: {metrics['active_time']} ({metrics['llm_percentage']}%)",
                style=_body,
            ),
            Text(f"Idle Time: {metrics['idle_time']}", style=_body),
        ]
        cost_line = Text()
        cost_line.append("Total Session Cost:", style=_body)
        cost_line.append(" ", style=_body)
        cost_line.append(metrics["session_cost"], style=f"bold {CAI_GREEN}")
        text_content.append(cost_line)
        if logging_path:
            text_content.append(Text("Log available at:", style=_body))
            text_content.append(Text(logging_path, style=_body))

        # Suppress atexit log_final_cost — cost is already inside the session panel.
        os.environ["CAI_COST_DISPLAYED"] = "true"

        console.print(
            Panel(
                Group(*text_content),
                border_style=CAI_GREEN,
                box=ROUNDED,
                padding=(1, 1),
                title=session_summary_panel_title(),
                title_align="left",
            ),
        )

        # Telemetry
        telemetry_enabled = _startup_cfg.telemetry
        if telemetry_enabled and hasattr(session_logger, "session_id") and hasattr(session_logger, "filename"):
            process_metrics(session_logger.filename, sid=session_logger.session_id)

        if session_logger:
            session_logger.log_session_end()

        GLOBAL_USAGE_TRACKER.end_session(final_cost=COST_TRACKER.session_total_cost)

        if session_logger and hasattr(session_logger, "filename"):
            from cai.cli_setup import create_last_log_symlink
            create_last_log_symlink(session_logger.filename)

        # Clean up CTF container
        if is_pentestperf_available() and os.getenv("CTF_NAME", None):
            if _setup.ctf_global:
                try:
                    print(color("\nStopping CTF container...", fg="yellow"))
                    _setup.ctf_global.stop_ctf()
                    print(color("CTF container stopped successfully.", fg="green"))
                except Exception as e:
                    print(color(f"Warning: Failed to stop CTF container: {e}", fg="yellow"))

        try:
            from cai.util.streaming import restore_terminal_state

            # One trailing \\n comes from atexit cleanup (single stdout newline); avoid stacking
            # here so we do not get multiple blank lines before the shell prompt.
            restore_terminal_state(leave_alternate_screen=True, emit_trailing_newline=False)
        except Exception:
            pass

        try:
            from cai.repl.ui.terminal_title import restore_terminal_window_title

            restore_terminal_window_title()
        except Exception:
            pass
    except Exception:
        pass


def _handle_inner_interrupt(agent, console):
    """Handle Ctrl-C during agent execution (inner loop)."""
    os.environ["CAI_TASK_RESET_PENDING"] = "1"
    try:
        from cai.util import cleanup_all_streaming_resources
        cleanup_all_streaming_resources(leave_alternate_screen=False)
    except Exception:
        pass

    try:
        orphaned = []
        for msg in agent.model.message_history:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    cid = tc.get("id")
                    if cid:
                        has_result = any(
                            m.get("role") == "tool" and m.get("tool_call_id") == cid
                            for m in agent.model.message_history
                        )
                        if not has_result:
                            orphaned.append(cid)

        for cid in orphaned:
            agent.model.add_to_message_history({
                "role": "tool",
                "tool_call_id": cid,
                "content": "Tool execution interrupted",
            })
        if orphaned:
            try:
                from cai.util import sanitize_message_list as fix
                agent.model.message_history[:] = fix(agent.model.message_history)
            except Exception:
                pass
    except Exception:
        pass

    time.sleep(0.1)

    try:
        loop = asyncio.get_event_loop()
        if loop and loop.is_running():
            pending = asyncio.all_tasks(loop) if hasattr(asyncio, "all_tasks") else asyncio.Task.all_tasks(loop)
            for task in pending:
                task.cancel()
    except Exception:
        pass

    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception:
        pass


def _handle_loop_exception(e, agent, console, force_until_flag):
    """Handle non-interrupt exceptions in the main loop."""
    import sys
    import traceback

    try:
        from cai.util import close_all_streaming_panels

        close_all_streaming_panels()
    except Exception:
        pass

    stop_active_timer()
    start_idle_timer()

    if isinstance(e, UserCancelledCommand):
        console.print(
            f"[yellow]Command cancelled.[/yellow] [dim]Awaiting new instructions.[/dim]\n"
        )
        return

    if isinstance(e, MaxTurnsExceeded):
        max_turns_val = os.getenv("CAI_MAX_TURNS", "unlimited")
        console.print(f"[yellow]Maximum conversation turns reached ({max_turns_val} turns)[/yellow]")
        console.print("[dim]The agent has reached the configured turn limit for this conversation.[/dim]")
        console.print("[dim white]You can continue with a new conversation or adjust CAI_MAX_TURNS if needed.[/dim white]\n")
        return

    cfg = _get_config()
    if isinstance(e, LLMEmptyAssistantError):
        try:
            from cai.util.streaming import cleanup_all_streaming_resources

            cleanup_all_streaming_resources()
        except Exception:
            pass
        log = logging.getLogger(__name__)
        log.warning("Empty assistant completions: %s", e)
        from rich.panel import Panel
        from rich.text import Text

        from cai.util.cli_palette import CAI_GREEN, FINAL_PANEL_BG, GREY_TEXT, YELLOW_WARN

        n = 3
        det = getattr(e, "details", None) or {}
        if isinstance(det, dict) and "attempts" in det:
            try:
                n = int(det["attempts"])
            except (TypeError, ValueError):
                n = 3
        body = Text.assemble(
            (f"[bold {CAI_GREEN}]CAI[/bold {CAI_GREEN}]\n\n", ""),
            (
                f"The provider returned [bold]{n}[/bold] consecutive empty responses "
                "(no assistant text and no tool calls). This is usually a transient gateway issue.\n\n",
                GREY_TEXT,
            ),
            ("Try again in a moment, or switch model if it keeps happening.", YELLOW_WARN),
        )
        console.print(
            Panel.fit(
                body,
                title=Text("Provider error", style=f"bold {YELLOW_WARN}"),
                border_style=CAI_GREEN,
                style=f"on {FINAL_PANEL_BG}",
            )
        )
        console.print()
        return

    if isinstance(e, LLMContextOverflow):
        try:
            from cai.util.streaming import cleanup_all_streaming_resources

            cleanup_all_streaming_resources()
        except Exception:
            pass
        from rich.panel import Panel
        from rich.text import Text

        from cai.util.cli_palette import CAI_GREEN, FINAL_PANEL_BG, GREY_TEXT, YELLOW_WARN

        det = getattr(e, "details", None) or {}
        if not isinstance(det, dict):
            det = {}

        log = logging.getLogger(__name__)

        # Two origins share this typed error and need different copy + title.
        # Discrimination is by ``details["origin"]`` only (set explicitly by
        # both raise sites: ``client_rate_limiter`` in gateway_rate_limiter.py
        # and ``http_413`` in httpx_client.py:_build_413_details). Inferring
        # from other keys would be fragile.
        origin = det.get("origin")

        if origin == "client_rate_limiter":
            projected = det.get("projected_tokens")
            tpm_limit = det.get("tpm_limit")
            log.warning(
                "LLM context overflow (TPM budget %s, projected %s): %s",
                tpm_limit, projected, e,
            )
            panel_title = "Gateway rate budget exceeded"
            projected_str = f"{projected:,}" if isinstance(projected, int) else "?"
            tpm_str = f"{tpm_limit:,}" if isinstance(tpm_limit, int) else "?"
            body_text = Text.assemble(
                (f"[bold {CAI_GREEN}]CAI[/bold {CAI_GREEN}]\n\n", ""),
                (
                    f"This request projects [bold]{projected_str}[/bold] tokens, which alone "
                    f"exceeds the gateway's per-minute budget of [bold]{tpm_str}[/bold] "
                    "tokens. No amount of waiting will let it through — the body itself must "
                    "shrink before retrying.\n\n",
                    GREY_TEXT,
                ),
                (
                    "Use [bold]/compact[/bold] to summarize the conversation, or [bold]/flush[/bold] to "
                    "reset history. Tool outputs that returned large dumps (filesystem listings, packet "
                    "captures, full binaries) are the usual culprit — pipe to ``head`` / ``wc -l`` or "
                    "save to a file next time.",
                    YELLOW_WARN,
                ),
            )
        else:
            # Default branch covers ``origin == "http_413"`` and any future
            # variant whose details look 413-shaped.
            body_bytes = det.get("body_bytes")
            msg_count = det.get("body_message_count")
            body_kb = (
                f"{body_bytes / 1024:.0f} KB"
                if isinstance(body_bytes, int) else "unknown size"
            )
            log.warning("LLM context overflow (HTTP 413, %s): %s", body_kb, e)
            panel_title = "Request body too large"
            body_text = Text.assemble(
                (f"[bold {CAI_GREEN}]CAI[/bold {CAI_GREEN}]\n\n", ""),
                (
                    f"The request body ({body_kb}, {msg_count if msg_count is not None else '?'} messages) "
                    "exceeded the model gateway's POST size limit (HTTP 413). This usually means a tool "
                    "returned a very large output (binary dump, full filesystem listing, packet capture, "
                    "etc.) that ballooned the context.\n\n",
                    GREY_TEXT,
                ),
                (
                    "Use [bold]/compact[/bold] to summarize the conversation, or [bold]/flush[/bold] to "
                    "reset history before retrying. For one-off heavy commands, pipe to ``head`` / ``wc -l`` "
                    "or save the output to a file instead of returning it inline.",
                    YELLOW_WARN,
                ),
            )
        console.print(
            Panel.fit(
                body_text,
                title=Text(panel_title, style=f"bold {YELLOW_WARN}"),
                border_style=CAI_GREEN,
                style=f"on {FINAL_PANEL_BG}",
            )
        )
        console.print()
        return

    if isinstance(e, (LLMProviderUnavailable, LLMTimeout, LLMRateLimited)):
        try:
            from cai.util.streaming import cleanup_all_streaming_resources

            cleanup_all_streaming_resources()
        except Exception:
            pass
        log = logging.getLogger(__name__)
        log.warning("LLM call failed (%s): %s", type(e).__name__, e)
        if cfg.debug == 2:
            console.print(f"[bold red]{type(e).__name__}: {e}[/bold red]")
            traceback.print_exc()
        else:
            # User-facing copy only — no exception text or URLs (see CAI_DEBUG=2 for engineers).
            console.print(
                "\n[bold yellow]The model service and its proxy are under heavy load right now.[/bold yellow]"
            )
            console.print(
                "[dim]In busy periods, access with your current ALIAS_API_KEY plan is not prioritized, "
                "which makes complex requests more likely to fail or queue behind higher tiers. "
                "We recommend waiting a few minutes before trying again so the gateway may clear, "
                "or upgrading your plan if you need more consistent capacity during peak demand.[/dim]"
            )
            console.print(
                "[dim]Error details are not shown in the console; set CAI_DEBUG=2 only if you need a "
                "traceback for support.[/dim]\n"
            )
        return

    if isinstance(e, PriceLimitExceeded):
        logging.getLogger(__name__).error("Price limit: %s", e, exc_info=True)
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        if force_until_flag:
            console.print("[yellow]Price limit reached. Exiting due to force_until_flag=True.[/yellow]")
            raise SystemExit(0)
        console.print(
            "[yellow]You must increase the limit using: "
            "/env set CAI_PRICE_LIMIT <new_value>[/yellow]"
        )
        return

    if isinstance(e, OutputGuardrailTripwireTriggered):
        _print_guardrail_warning(e)
        return
    if isinstance(e, InputGuardrailTripwireTriggered):
        _print_input_guardrail_warning(e)
        return

    if (
        "context_length_exceeded" in str(e)
        or "prompt is too long" in str(e).lower()
        or "maximum context length" in str(e).lower()
        or ("max_tokens" in str(e) and "exceeded" in str(e).lower())
        or "too many tokens" in str(e).lower()
        or "token limit" in str(e).lower()
    ):
        if force_until_flag:
            print("Automatically running /compact to summarize the conversation...\n")
            from cai.repl.commands.base import handle_command as commands_handle_command

            commands_handle_command("/compact", ["--model", _get_config().model])
            return
        raise

    try:
        from cai.repl.exception_recovery import (
            is_recovery_enabled,
            should_skip_model_for_exception,
            try_recover_with_model,
        )

        if (
            is_recovery_enabled()
            and agent is not None
            and not should_skip_model_for_exception(e)
        ):
            logging.getLogger(__name__).error("Error in main loop: %s", e, exc_info=True)
            if cfg.debug == 2:
                console.print(f"[bold red]Error: {str(e)}[/bold red]")
                traceback.print_exc()

            def _recovery_agent_run(hint: str, brief: str) -> None:
                from cai.repl.exception_recovery import build_recovery_agent_user_message

                try:
                    umsg = build_recovery_agent_user_message(hint, brief)
                    _run_single_agent(
                        agent,
                        umsg,
                        console,
                        force_until_flag,
                        _setup.ctf_global,
                    )
                except Exception as run_exc:
                    logging.getLogger(__name__).exception(
                        "Recovery agent run failed: %s", run_exc
                    )
                    console.print(
                        f"[yellow]Recovery agent run stopped with an error: {run_exc}[/yellow]"
                    )

            try_recover_with_model(
                e,
                agent,
                console,
                cfg,
                recovery_agent_runner=_recovery_agent_run,
            )
            return
    except Exception:
        logging.getLogger(__name__).warning("exception_recovery path failed", exc_info=True)

    if cfg.debug == 2:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_info = traceback.extract_tb(exc_traceback)
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        console.print(f"[bold red]Traceback: {tb_info}[/bold red]")
    else:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in main loop: {str(e)}", exc_info=True)
        console.print(f"[yellow]Error occurred: {type(e).__name__}: {str(e)[:100]}[/yellow]")


# ---------------------------------------------------------------------------
# Guardrail warning printers
# ---------------------------------------------------------------------------

def _print_guardrail_warning(e):
    guardrail_name = e.guardrail_result.guardrail.get_name()
    reason = e.guardrail_result.output.output_info.get("reason", "Security policy violation")
    print(f"\n\033[91mSECURITY GUARDRAIL TRIGGERED\033[0m")
    print(f"\033[91mGuardrail: {guardrail_name}\033[0m")
    print(f"\033[91mReason: {reason}\033[0m")
    print(f"\033[93mThe agent's output was blocked for security reasons.\033[0m")
    print(f"\033[96mYou can continue the conversation with a different request.\033[0m\n")


def _print_input_guardrail_warning(e):
    reason = "Potential security threat detected in input"
    if hasattr(e, 'guardrail_result') and e.guardrail_result:
        if hasattr(e.guardrail_result, 'output') and e.guardrail_result.output:
            reason = e.guardrail_result.output.output_info.get("reason", reason)
    print(f"\n\033[91mINPUT SECURITY GUARDRAIL TRIGGERED\033[0m")
    print(f"\033[91mReason: {reason}\033[0m")
    print(f"\033[93mYour input was blocked for security reasons.\033[0m")
    if "base64" in reason.lower() or "pattern" in reason.lower():
        print(f"\n\033[96mThis may be due to malicious content in the conversation history.\033[0m")
        print(f"\033[96mOptions:\033[0m")
        print(f"  1. Type \033[92m/clear\033[0m to clear the conversation history")
        print(f"  2. Type \033[92m/env set CAI_GUARDRAILS false\033[0m to temporarily disable guardrails")
        print(f"  3. Type \033[92m/exit\033[0m to exit CAI")
    else:
        print(f"\033[96mPlease rephrase your request or try a different approach.\033[0m\n")


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

def _try_refresh_info_bars():
    try:
        from cai.tui.components.info_status_bar_updater import force_refresh_all_info_bars
        force_refresh_all_info_bars()
    except ImportError:
        pass
