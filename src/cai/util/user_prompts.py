"""User prompts: terminal-owner coordination, sudo handling, sensitive-command guard.

Three closely related responsibilities live here, all of them blocking
interactions with the user. They were originally split across three files
(``cai/util/interactive_prompt.py``, ``cai/tools/sudo.py``,
``cai/tools/sensitive_command_guard.py``); merging them eliminates a layer
of cross-imports and keeps "what happens when CAI needs the human's
attention" in a single discoverable module.

Layout
------
1. **Terminal owners** — :func:`pause_terminal_owners` /
   :func:`resume_terminal_owners` / :func:`paused_terminal_owners` /
   :func:`with_paused_terminal_owners`. Used by every interactive section
   below to silence the compact REPL live block and the legacy wait hints
   while a prompt is on screen.
2. **Sudo handler** — :func:`ensure_sudo_credentials`,
   :func:`prompt_sudo_elevation` and friends. Validates credentials before
   the executor spawns the subprocess; passwords live only in process
   memory and are never logged.
3. **Sensitive command guard** — :func:`prompt_user_for_sensitive_command`,
   :func:`detect_sensitive_command`, :func:`avoid_sudo_command_blocked`.
   Detects risky shell commands (sudo, recon tools, reverse shells, …) and
   asks the user how to proceed.

Public API expected by the rest of the codebase:

* Pause/resume helpers: ``pause_terminal_owners``,
  ``resume_terminal_owners``, ``paused_terminal_owners``,
  ``with_paused_terminal_owners``.
* Sudo: ``is_sudo_command``, ``output_needs_sudo``,
  ``ensure_sudo_credentials``, ``prompt_sudo_elevation``,
  ``clear_cached_password``, ``run_sudo_command`` (alias).
* Guard: ``detect_sensitive_command``,
  ``prompt_user_for_sensitive_command``, ``avoid_sudo_command_blocked``,
  ``clear_allowed_commands``.

Security notes
--------------
* Passwords are never logged, persisted, or echoed in output strings.
* The sudo cache (``_cached_password``) is a process-local sentinel — no
  shared state, no disk persistence.
* The session allowlist (``_allowed_commands``) only suppresses
  ``recon_tool`` matches; sudo, destructive, reverse-shell and pipe-to-shell
  patterns are checked unconditionally.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import getpass
import os
import re
import shlex
import signal
import subprocess
from typing import Any, Callable, Iterator, Tuple

import questionary
from rich.text import Text

# NOTE: ``custom_style`` is imported lazily inside ``prompt_user_for_sensitive_command``
# because importing it at module load time would trigger a circular import:
# ``cai.tools.common`` re-exports the sudo helpers from this module, and the settings
# package transitively pulls ``cai.tools.common`` back in.
from cai.util.cli_palette import CAI_GREEN, GREY_TEXT, YELLOW_ON, YELLOW_WARN
from cai.util.terminal import console as _console


# ============================================================================
# Section 1 — Terminal-owner coordination
# ============================================================================
# Any UI element that captures user input (sudo password prompt, sensitive
# command questionary, future questionaries) must take exclusive ownership
# of stdout/stderr while showing. Otherwise the compact REPL live block or
# the legacy wait hints redraw on top of the prompt and overwrite it
# between refresh ticks.


def pause_terminal_owners() -> None:
    """Pause every UI element that could repaint over an interactive prompt.

    Three families to silence, in order:
      1. Wait hints (Rich Status loops) — they may also write through stderr.
      2. Legacy streaming Live panels — defense in depth: in compact mode
         most are suppressed at creation, but ``create_agent_streaming_context``
         keeps a Live for plain conversational responses that can race with a
         tool-driven sudo / questionary prompt.
      3. Compact REPL live block.

    Each call is wrapped in ``try/except`` so a missing optional dependency
    or a teardown race never raises into the caller's interactive flow.
    """
    try:
        from cai.util.wait_hints import pause_all_wait_hints

        pause_all_wait_hints()
    except Exception:
        pass
    try:
        from cai.util.streaming import pause_streaming_lives

        pause_streaming_lives()
    except Exception:
        pass
    try:
        from cai.repl.ui.compact_renderer import pause_compact_live

        pause_compact_live()
    except Exception:
        pass


def resume_terminal_owners() -> None:
    """Restore rendering torn down by :func:`pause_terminal_owners`.

    Reverse order: compact live first (re-asserts ownership flag), then wait
    hints (which check the compact-live flag before re-spawning their Rich
    Status). Streaming Lives need no resume — registries are emptied on
    pause and the next chunk recreates the contexts it needs.
    """
    try:
        from cai.repl.ui.compact_renderer import resume_compact_live

        resume_compact_live()
    except Exception:
        pass
    try:
        from cai.util.wait_hints import resume_all_wait_hints

        resume_all_wait_hints()
    except Exception:
        pass


@contextlib.contextmanager
def paused_terminal_owners() -> Iterator[None]:
    """Context manager that pauses + always resumes around a block."""
    pause_terminal_owners()
    try:
        yield
    finally:
        resume_terminal_owners()


def _query_cursor_row() -> int | None:
    """Ask the terminal for the absolute cursor row via DSR-CPR.

    Sends the ``\\033[6n`` query and reads the ``\\033[<row>;<col>R``
    response from stdin (briefly switched to cbreak mode). Returns the
    1-based row number, or ``None`` if anything fails (non-TTY, terminal
    that doesn't speak DSR, timeout, …).

    Mainstream emulators (xterm/iTerm2/alacritty/kitty/gnome-terminal/
    Windows Terminal/tmux/screen) all support DSR-CPR.
    """
    import os as _os
    import re as _re
    import select
    import sys
    import termios
    import time
    import tty

    out = sys.stdout
    try:
        if not out.isatty():
            return None
        in_fd = sys.stdin.fileno()
        if not _os.isatty(in_fd):
            return None
        old_attrs = termios.tcgetattr(in_fd)
    except Exception:
        return None

    try:
        try:
            tty.setcbreak(in_fd, termios.TCSANOW)
        except termios.error:
            return None
        try:
            out.write("\033[6n")
            out.flush()
        except Exception:
            return None
        buf: list[str] = []
        deadline = time.monotonic() + 0.3  # DSR response is typically <10ms
        while True:
            rem = deadline - time.monotonic()
            if rem <= 0:
                break
            try:
                ready, _, _ = select.select([in_fd], [], [], rem)
            except Exception:
                break
            if not ready:
                break
            try:
                ch = _os.read(in_fd, 64).decode("utf-8", errors="ignore")
            except Exception:
                break
            buf.append(ch)
            if "R" in ch:
                break
        # Drain any trailing bytes still in the buffer so a late DSR
        # tail doesn't leak into the next reader (questionary, getpass).
        try:
            while True:
                ready, _, _ = select.select([in_fd], [], [], 0.0)
                if not ready:
                    break
                _os.read(in_fd, 1024)
        except Exception:
            pass
        m = _re.search(r"\033\[(\d+);\d+R", "".join(buf))
        if m:
            return int(m.group(1))
        return None
    finally:
        try:
            termios.tcsetattr(in_fd, termios.TCSANOW, old_attrs)
        except Exception:
            pass


# Best-effort viewport erase for residual auth status lines (cancelled /
# no-response / 3-fails). When one of those helpers prints, it records the
# absolute row of the printed line and the cursor row right after; the next
# :func:`_transient_prompt_block` to open inspects this state and, if the
# residual is still inside the visible viewport (no terminal scroll has
# pushed it into history), erases that single line. Otherwise the message
# stays in scrollback as a record of what happened.
_pending_residual_row: int | None = None
_pending_residual_row_after_print: int | None = None


def _track_residual_after_print() -> None:
    """Capture the absolute row of the line just printed above the cursor.

    Must be called immediately after the residual line is flushed to
    stdout. Uses DSR-CPR (``\\033[6n``) so it only works on real TTYs;
    in non-TTY contexts it silently no-ops.
    """
    global _pending_residual_row, _pending_residual_row_after_print
    row_after = _query_cursor_row()
    if row_after is None or row_after <= 1:
        return
    _pending_residual_row = row_after - 1
    _pending_residual_row_after_print = row_after


def _erase_pending_residual_if_safe() -> None:
    """Try to erase the previously printed residual auth status line.

    Conservative: only erases when we can prove no terminal scroll has
    moved the residual out of the viewport since it was printed. If the
    cursor has advanced fewer rows than there were visible rows below the
    residual at print time, the line is still where we left it and can be
    cleared with a single ``\\033[<row>;1H\\033[2K`` sandwich. Otherwise we
    do nothing and the message stays in scrollback.
    """
    global _pending_residual_row, _pending_residual_row_after_print
    target_row = _pending_residual_row
    saved_row_after = _pending_residual_row_after_print
    _pending_residual_row = None
    _pending_residual_row_after_print = None
    if target_row is None or saved_row_after is None:
        return

    import sys
    out = sys.stdout
    try:
        if not out.isatty():
            return
    except Exception:
        return

    current_row = _query_cursor_row()
    if current_row is None or current_row < saved_row_after:
        return

    try:
        terminal_height = os.get_terminal_size().lines
    except Exception:
        terminal_height = 24

    # Rows available below the residual at print time. As long as the
    # cursor has not advanced more than this, no \n caused a scroll and
    # ``target_row`` still points at the residual line.
    visible_room_below = terminal_height - saved_row_after
    if current_row - saved_row_after >= visible_room_below:
        # Cursor reached (or could have reached) the bottom; we cannot
        # rule out a scroll. Leave the residual in scrollback.
        return

    try:
        # \033[s/\033[u (DEC save/restore) is enough here: nothing else
        # in the prompt flow uses them concurrently.
        out.write(f"\033[s\033[{target_row};1H\033[2K\033[u")
        out.flush()
    except Exception:
        pass


@contextlib.contextmanager
def _transient_prompt_block(reserve_lines: int = 12) -> Iterator[None]:
    """Erase every line printed inside the block when leaving it.

    Same UX as ``rich.live.Live(transient=True)``, but compatible with
    the interactive widgets we use for prompts (``questionary`` /
    ``prompt_toolkit``, ``getpass``).

    Strategy
    --------
    1. **Pre-allocate vertical headroom**: write ``reserve_lines`` blank
       lines and bring the cursor back up. Any terminal scroll caused by
       the prompt block (banner + questionary picker, typically 6-9
       rows) is forced to happen *here*, before we record the reference
       row. From this point on the block fits without further scroll.
    2. **Anchor the cursor** via DSR-CPR (``\\033[6n``) — the terminal
       reports the absolute row where the prompt block will start.
    3. **On exit**: jump back to that row with ``\\033[<row>;1H`` and
       erase to end of screen (``\\033[0J``).

    Why pre-allocate? DSR alone fails when the cursor sits near the
    bottom of the terminal: subsequent prints scroll the content up,
    and the saved row no longer points to the banner's top. Pre-
    allocation moves the scroll out of the critical region, so the
    saved row stays valid for the lifetime of the block.

    Why not ``\\033[s``/``\\033[u``? ``prompt_toolkit``'s renderer uses
    those sequences internally and clobbers them before we can restore.

    Falls back to a no-op when DSR is unavailable (non-TTY, exotic
    terminal, timeout) so behavior on CI / piped output is unchanged.
    """
    import sys

    out = sys.stdout
    try:
        if not out.isatty():
            yield
            return
    except Exception:
        yield
        return

    # Step 0: best-effort cleanup of any pending residual auth status line
    # left by ``_show_auth_cancelled`` / ``_show_auth_no_response`` /
    # ``_show_auth_failed_final``. Must happen *before* the pre-allocate
    # below, since writing newlines can scroll the residual out of the
    # viewport and invalidate the saved row.
    _erase_pending_residual_if_safe()

    # Step 1: pre-allocate. The \r before the up-arrow guards against
    # leftover columns from any non-newline write that preceded us.
    try:
        out.write("\n" * reserve_lines)
        out.write(f"\r\033[{reserve_lines}A")
        out.flush()
    except Exception:
        yield
        return

    # Step 2: anchor.
    saved_row = _query_cursor_row()
    if saved_row is None:
        yield
        return

    # Step 3: yield + restore.
    try:
        yield
    finally:
        try:
            out.write(f"\033[{saved_row};1H\033[0J")
            out.flush()
        except Exception:
            pass


def with_paused_terminal_owners(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that pauses owners around ``func``.

    Detects ``async def`` automatically so both blocking and coroutine
    callers can share the same wrapper. Used by
    :func:`prompt_user_for_sensitive_command` (async) and
    :func:`ensure_sudo_credentials` (sync).
    """
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            pause_terminal_owners()
            try:
                return await func(*args, **kwargs)
            finally:
                resume_terminal_owners()

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        pause_terminal_owners()
        try:
            return func(*args, **kwargs)
        finally:
            resume_terminal_owners()

    return sync_wrapper


# ============================================================================
# Section 2 — Sudo password handler
# ============================================================================
# Validates sudo credentials BEFORE the executor creates a subprocess. Once
# validated, OS-level sudo caching (``sudo -v``) keeps credentials active so
# the normal streaming execution path works without blocking.
#
# This module NEVER executes the user's actual command — it only validates
# the password and returns control to the executor.


def _restore_tty_for_prompt() -> None:
    """Show cursor / sane TTY after Rich Live or prompt_toolkit before interactive I/O."""
    try:
        from cai.util.streaming import restore_terminal_state

        restore_terminal_state(emit_trailing_newline=False)
    except Exception:
        pass


_DOT = "\u25cf"  # ● (failure / elevation titles still use bullet where needed)
_CHECK = "\u2611"  # ☑ ballot box with check


def _continuous_ops_no_sudo() -> bool:
    """True when the continuous-ops worker was started without privileged execution."""
    return os.getenv("CAI_CONTINUOUS_OPS_NO_SUDO", "").strip().lower() in ("1", "true", "yes")


def _continuous_ops_loop_child() -> bool:
    """True inside the headless loop child (set only by the generated worker script)."""
    return os.getenv("CAI_CONTINUOUS_OPS_LOOP_CHILD", "").strip().lower() in ("1", "true", "yes")


# Shared alias used by the sensitive guard timeout heuristic.
_continuous_ops_worker = _continuous_ops_loop_child


def _privileged_continuous_ops_worker() -> bool:
    """Privileged continuous-ops tick (loop child, operator granted sudo in the wizard)."""
    return _continuous_ops_loop_child() and not _continuous_ops_no_sudo()


class _SudoPasswordTimeout(Exception):
    """SIGALRM fired while waiting at the sudo password prompt (privileged worker only)."""


class _SudoPasswordIdleTimeout(Exception):
    """The interactive prompt received no input for ``_SUDO_IDLE_TIMEOUT_SECONDS``."""


# Hard idle timeout for the interactive sudo password prompt. If the user
# does not press any key for this many seconds we abandon the prompt and
# tell the agent to retry without sudo. The wait-hint warning starts
# ``_SUDO_WARN_REMAINING_SECONDS`` seconds before the deadline.
_SUDO_IDLE_TIMEOUT_SECONDS = 120.0
_SUDO_WARN_REMAINING_SECONDS = 30.0


def _privileged_worker_sudo_prompt_timeout() -> float | None:
    """Wall-clock limit for one sudo password attempt in the privileged worker."""
    if not _privileged_continuous_ops_worker():
        return None
    try:
        tick = float(os.getenv("CAI_CONTINUOUS_OPS_TICK_SECONDS", "60"))
    except ValueError:
        tick = 60.0
    return max(5.0, tick / 3.0)


def _effective_idle_timeout() -> float:
    """Return the idle timeout the interactive prompt should use right now.

    Coexists with :func:`_privileged_worker_sudo_prompt_timeout`: when the
    process runs as a privileged continuous-ops worker, use the smaller of
    the two values so we never block the worker tick longer than its share
    of the cycle. Otherwise the default 120s idle limit applies.
    """
    worker_timeout = _privileged_worker_sudo_prompt_timeout()
    if worker_timeout is None:
        return _SUDO_IDLE_TIMEOUT_SECONDS
    return min(_SUDO_IDLE_TIMEOUT_SECONDS, worker_timeout)


def _show_timeout_warning(seconds_left: int) -> None:
    """Draw ``⏳ sudo — timing out in {N}s…`` one line below the cursor.

    Uses DEC save/restore (``\\033[s`` / ``\\033[u``) so the visible prompt
    line is not disturbed. The line is rewritten on every tick from the
    interruptible reader to render a live countdown.
    """
    try:
        import sys
        sys.stdout.write(
            f"\033[s\n\033[2K\033[33m\u23f3 sudo \u2500 timing out in {seconds_left}s\u2026\033[0m\033[u"
        )
        sys.stdout.flush()
    except Exception:
        pass


def _clear_timeout_warning() -> None:
    """Erase the timeout warning line (if any) without moving the visible cursor."""
    try:
        import sys
        sys.stdout.write("\033[s\n\033[2K\033[u")
        sys.stdout.flush()
    except Exception:
        pass


def _read_sudo_password_interruptible(
    idle_timeout_seconds: float = _SUDO_IDLE_TIMEOUT_SECONDS,
) -> str | None:
    """Read a password from stdin one byte at a time, polling the abort flag.

    Two reasons to leave the timer inside this function:

    * Ctrl+C in MainThread sets ``_PROMPT_ABORT_REQUESTED``; checking it
      between polls keeps the cancel path snappy (≤100 ms).
    * The idle deadline is reset on every keystroke, so it has to be
      maintained where the bytes are actually consumed.

    Raises :class:`_SudoPasswordIdleTimeout` if no input arrives for
    ``idle_timeout_seconds`` seconds. Returns ``None`` on Ctrl+C / EOF, or
    the typed password on Enter.
    """
    import sys
    import os as _os
    import select
    import termios
    import time as _time

    from cai.util.interaction import is_prompt_abort_requested

    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        return None

    chars: list[str] = []
    last_activity = _time.monotonic()
    last_warn_second: int | None = None
    try:
        new_settings = termios.tcgetattr(fd)
        # lflag is index 3 in the termios attr list.
        new_settings[3] = new_settings[3] & ~(termios.ICANON | termios.ECHO)
        # Keep ISIG enabled so Ctrl+C reaches signal_handler normally.
        new_settings[3] = new_settings[3] | termios.ISIG
        # VMIN=1 / VTIME=0: read returns as soon as 1 byte is available.
        new_settings[6][termios.VMIN] = 1
        new_settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, new_settings)

        while True:
            if is_prompt_abort_requested():
                if last_warn_second is not None:
                    _clear_timeout_warning()
                return None

            elapsed_idle = _time.monotonic() - last_activity
            remaining = idle_timeout_seconds - elapsed_idle
            if remaining <= 0:
                if last_warn_second is not None:
                    _clear_timeout_warning()
                raise _SudoPasswordIdleTimeout()
            if remaining <= _SUDO_WARN_REMAINING_SECONDS:
                # Show a live countdown (whole seconds, rounded up so the
                # user sees e.g. 30, 29, ... 1 with each tick).
                current_second = int(remaining) + 1
                if current_second != last_warn_second:
                    _show_timeout_warning(current_second)
                    last_warn_second = current_second
            elif last_warn_second is not None:
                _clear_timeout_warning()
                last_warn_second = None

            try:
                r, _, _ = select.select([fd], [], [], 0.1)
            except (OSError, ValueError):
                # EINTR from SIGINT: loop re-checks the abort flag next pass.
                continue
            if not r:
                continue
            try:
                byte = _os.read(fd, 1)
            except OSError:
                continue
            if not byte:
                if last_warn_second is not None:
                    _clear_timeout_warning()
                return None

            # Any keypress resets the idle deadline and dismisses the warning.
            last_activity = _time.monotonic()
            if last_warn_second is not None:
                _clear_timeout_warning()
                last_warn_second = None

            ch = byte.decode("utf-8", errors="ignore")
            if ch in ("\r", "\n"):
                break
            if ch == "\x04":  # Ctrl+D / EOF
                return None
            if ch in ("\x7f", "\b"):
                if chars:
                    chars.pop()
                continue
            if ord(ch) < 0x20:
                # Discard other control characters silently.
                continue
            chars.append(ch)
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except termios.error:
            pass
        try:
            sys.stdout.write("\r\n")
            sys.stdout.flush()
        except Exception:
            pass
    return "".join(chars)


def _read_sudo_password() -> str | None:
    """Prompt like ``sudo password:`` with ``sudo`` on white background.

    Wipes the current line with ``\\r\\033[2K`` and flushes both stdout and
    stderr before printing the label so that any residual frame from a
    just-stopped Rich Live cannot bleed onto the prompt while the user
    types.

    Returns ``None`` when the user aborts with Ctrl+C (handled by the
    interruptible reader); ``""`` when the user just pressed Enter.
    """
    import sys

    _restore_tty_for_prompt()

    # Wipe the line on both streams: Rich Live writes to the same TTY as
    # stdout, the wait-hint Status writes to stderr.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.write("\r\033[2K")
            stream.flush()
        except Exception:
            pass

    label = Text()
    label.append("sudo", style="black on white")
    label.append(" password: ", style="white")
    _console.print(label, end="")
    try:
        sys.stdout.flush()
    except Exception:
        pass

    # Interruptible reader on real TTYs (REPL + TUI); fall back to
    # getpass when stdin is not a TTY (CI, pipes, redirected input).
    try:
        if sys.stdin.isatty():
            return _read_sudo_password_interruptible(_effective_idle_timeout())
    except _SudoPasswordIdleTimeout:
        # Idle deadline expired: propagate to ensure_sudo_credentials /
        # prompt_sudo_elevation so they can show the timeout notice and
        # return the "retrying without privileges" fallback. Without this
        # branch the generic except below would silently swallow it and
        # we'd fall through to getpass.getpass(), which blocks forever.
        raise
    except (KeyboardInterrupt, EOFError):
        # User-driven cancels are handled by the callers; do not mask them
        # behind getpass either.
        raise
    except Exception:
        pass
    return getpass.getpass("")


def _read_sudo_password_maybe_timed() -> str | None:
    """Return password, or ``None`` if the privileged-worker prompt timed out (SIGALRM)."""
    timeout = _privileged_worker_sudo_prompt_timeout()
    if timeout is None or os.name == "nt" or not hasattr(signal, "SIGALRM"):
        return _read_sudo_password()

    def _handler(_signum, _frame):
        raise _SudoPasswordTimeout

    old_handler = signal.signal(signal.SIGALRM, _handler)
    try:
        signal.setitimer(signal.ITIMER_REAL, float(timeout))
        try:
            return _read_sudo_password()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
    except _SudoPasswordTimeout:
        _console.print()
        try:
            _console.print(
                Text(
                    "sudo password prompt timed out (continuous-ops worker); "
                    "treating as declined for this command.",
                    style=f"bold {YELLOW_WARN}",
                )
            )
        except Exception:
            pass
        return None
    finally:
        signal.signal(signal.SIGALRM, old_handler)


# Session-scoped password cache — NEVER logged or persisted.
_cached_password: str | None = None


def clear_cached_password() -> None:
    """Invalidate the cached sudo password."""
    global _cached_password
    _cached_password = None


# --- Detection helpers ------------------------------------------------------

def is_sudo_command(command: str) -> bool:
    """Return *True* if *command* requires sudo authentication."""
    cmd = command.strip()
    if cmd.startswith("sudo ") or cmd == "sudo":
        return True
    if " | sudo " in cmd or " |sudo " in cmd:
        return True
    return False


_PERMISSION_DENIED_PATTERNS = (
    "permission denied",
    "operation not permitted",
    "requires root",
    "root privileges",
    "must be root",
    "must be run as root",
    "run as root",
    "need to be root",
    "needs root",
    "insufficient privileges",
    "eacces",
    "you must be root",
    "cap_net_raw",
    "packet socket failed",
    "permission to perform this capture",
    "couldn't run dumpcap",
)


def output_needs_sudo(output: str) -> bool:
    """Return *True* if *output* indicates the command failed due to
    missing root/sudo privileges."""
    if not output:
        return False
    lower = output.lower()
    return any(p in lower for p in _PERMISSION_DENIED_PATTERNS)


# Regex that matches  sudo [-flags [arg]] … <actual_command>
# Flags that take an argument: -u, -g, -C, -D, -R, -T
_SUDO_PREFIX_RE = re.compile(
    r"^sudo\s+"                          # literal sudo
    r"(?:"
    r"  -[ugCDRT]\s+\S+\s+"             # flag WITH argument (-u user, -g group)
    r"| -[A-Za-z]+\s+"                  # flag WITHOUT argument (-E, -n, -S)
    r"| --\S+\s+"                        # long flags (--preserve-env)
    r"| \S+=\S+\s+"                      # env assignments (HOME=/root)
    r")*",
    re.VERBOSE,
)


def _strip_sudo(command: str) -> str:
    """Remove the ``sudo [flags]`` prefix, returning the inner command."""
    cmd = command.strip()
    if not cmd.startswith("sudo"):
        return cmd
    m = _SUDO_PREFIX_RE.match(cmd)
    if m and m.end() < len(cmd):
        return cmd[m.end():]
    if cmd.startswith("sudo "):
        return cmd[5:].lstrip()
    return cmd


# --- Credential validation (never run the actual command) -------------------

def _validate_cached_creds(cwd: str, timeout: int = 5) -> bool:
    """Check if sudo credentials are already cached at OS level.

    Uses ``sudo -n -v`` which validates without running any command
    and without prompting.  Returns *True* if credentials are valid.
    """
    try:
        proc = subprocess.run(
            "sudo -n -v", shell=True, capture_output=True,  # nosec B602
            text=True, timeout=timeout, cwd=cwd,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _validate_with_password(
    password: str, cwd: str, timeout: int = 10,
) -> Tuple[bool, bool]:
    """Validate a password by running ``sudo -S -v``.

    ``sudo -v`` refreshes the OS credential cache without executing
    any command.  Returns ``(success, auth_failed)``.
    """
    try:
        proc = subprocess.Popen(
            "sudo -S -v", shell=True, stdin=subprocess.PIPE,  # nosec B602
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=cwd,
        )
        _, stderr = proc.communicate(
            input=password + "\n", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return False, False
    except Exception:
        return False, False

    if proc.returncode == 0:
        return True, False

    stderr_lower = (stderr or "").lower()
    auth_failed = any(kw in stderr_lower for kw in (
        "incorrect password",
        "sorry, try again",
        "authentication failure",
        "no password was provided",
    ))
    return False, auth_failed


# --- Flat-style display (matches util/streaming.py visual language) --------

def _show_auth_header(command: str) -> None:
    """Display auth-required header: ! sudo ─ … (yellow/brown like sensitive guard)."""
    inner_cmd = _strip_sudo(command)
    t = Text()
    t.append("!", style=YELLOW_ON)
    t.append(" ", style="")
    t.append("sudo", style=YELLOW_WARN)
    t.append(" ─ ", style="dim white")
    t.append("Authentication Required", style=YELLOW_WARN)
    _console.print(t)
    c = Text()
    c.append("  Command: ", style=f"dim {GREY_TEXT}")
    c.append(inner_cmd, style="bold white")
    _console.print(c)


# --- Inline replacement: ``sudo password:`` → live-style auth dot --------
# After ``getpass`` returns we erase the prompt line and render a one-row
# ``● sudo — authenticating…`` (orange while the validation runs), which
# then mutates in place to ``✓ sudo — ok`` (green) or ``✗ sudo — failed``
# (red). The whole sudo block is wrapped in :func:`_transient_prompt_block`,
# so this final row also disappears as soon as ``ensure_sudo_credentials``
# returns — leaving only the compact REPL row in scrollback.

def _erase_previous_line() -> None:
    """Move cursor up one line and erase it (no-op if stdout is not a TTY)."""
    import sys
    try:
        if not sys.stdout.isatty():
            return
        sys.stdout.write("\033[1A\033[2K\r")
        sys.stdout.flush()
    except Exception:
        pass


def _show_auth_dot(label: str, style: str) -> None:
    """Render a single ``● sudo — <label>`` row in the given style colour."""
    t = Text()
    t.append(f"{_DOT} ", style=f"bold {style}")
    t.append("sudo", style=f"bold {style}")
    t.append(" ─ ", style="dim white")
    t.append(label, style=style)
    _console.print(t)


def _show_authenticating() -> None:
    """Replace the ``sudo password:`` line with ``● sudo — authenticating…`` (orange)."""
    _erase_previous_line()
    _show_auth_dot("authenticating…", YELLOW_WARN)


def _show_auth_ok() -> None:
    """Replace ``authenticating…`` with ``✓ sudo — ok`` (green)."""
    _erase_previous_line()
    t = Text()
    t.append(f"{_CHECK} ", style=f"bold {CAI_GREEN}")
    t.append("sudo", style=f"bold {CAI_GREEN}")
    t.append(" ─ ", style="dim white")
    t.append("ok", style=CAI_GREEN)
    _console.print(t)


def _show_auth_failed() -> None:
    """Replace ``authenticating…`` with ``✗ sudo — failed`` (red)."""
    _erase_previous_line()
    t = Text()
    t.append("\u2717 ", style="bold red")
    t.append("sudo", style="bold red")
    t.append(" ─ ", style="dim white")
    t.append("failed", style="red")
    _console.print(t)


def _show_auth_cancelled() -> None:
    """Render ``! sudo — cancelled by user`` (yellow) outside the transient block.

    Mirrors the visual language of the sensitive-command guard's cancel
    path (yellow warning) and the ``UserCancelledCommand`` wording used in
    ``cai.sdk.agents.exceptions``.
    """
    t = Text()
    t.append("!", style=YELLOW_ON)
    t.append(" ", style="")
    t.append("sudo", style=YELLOW_WARN)
    t.append(" ─ ", style="dim white")
    t.append("cancelled by user", style=YELLOW_WARN)
    _console.print(t)
    _track_residual_after_print()


def _show_auth_no_response() -> None:
    """Render ``! sudo — no response, continuing without privileges`` (yellow).

    Shown when the interactive prompt idled past the timeout. Same yellow
    palette as the cancel notice; phrased to make it clear the action was
    not a user decision but a wait-out.
    """
    t = Text()
    t.append("!", style=YELLOW_ON)
    t.append(" ", style="")
    t.append("sudo", style=YELLOW_WARN)
    t.append(" ─ ", style="dim white")
    t.append("no response, continuing without privileges", style=YELLOW_WARN)
    _console.print(t)
    _track_residual_after_print()


def _show_auth_failed_final() -> None:
    """Render ``! sudo — authentication failed, continuing without privileges``.

    Shown when the user exhausted all attempts (3 wrong passwords or 3
    empty enters). Same yellow palette as the cancel / no-response
    notices; tracked as a residual so the next prompt can erase it.
    """
    t = Text()
    t.append("!", style=YELLOW_ON)
    t.append(" ", style="")
    t.append("sudo", style=YELLOW_WARN)
    t.append(" ─ ", style="dim white")
    t.append("authentication failed, continuing without privileges", style=YELLOW_WARN)
    _console.print(t)
    _track_residual_after_print()


def _show_elevation_prompt(command: str) -> None:
    """Display a prompt offering to retry the command with sudo."""
    t = Text()
    t.append("!", style=YELLOW_ON)
    t.append(" ", style="")
    t.append("sudo", style=YELLOW_WARN)
    t.append(" ─ ", style="dim white")
    t.append("Command requires elevated privileges", style=YELLOW_WARN)
    _console.print(t)
    c = Text()
    c.append("  Command: ", style=f"dim {GREY_TEXT}")
    c.append(command, style="bold white")
    _console.print(c)


# --- Main entry points ------------------------------------------------------

_VALIDATED = None  # Sentinel: credentials OK, proceed with normal execution


@with_paused_terminal_owners
def ensure_sudo_credentials(
    command: str,
    workspace_dir: str,
    timeout: int = 100,
    tool_name: str | None = None,
    token_info: dict | None = None,
    max_attempts: int = 3,
) -> str | None:
    """Ensure sudo credentials are available for *command*.

    Returns
    -------
    ``None``
        Credentials are valid — the caller should execute *command*
        through the normal streaming path (sudo creds are OS-cached).
    ``str``
        A fallback result string — the caller should return this
        directly instead of executing the command.

    Flow
    ----
    1. Try session-cached password via ``sudo -S -v``.
    2. Try OS-cached credentials via ``sudo -n -v``.
    3. Prompt user with ``getpass`` → up to *max_attempts*.
       If the terminal is unavailable (TUI), ``getpass`` raises
       ``OSError`` and we strip sudo for a non-privileged fallback.
    4. On success → cache password, return ``None`` (proceed).
    5. On total failure → return fallback output string.

    The whole interactive section (auth-required banner, attempt counter,
    ``sudo password:`` prompt and ``authenticating…`` row) is rendered
    inside a :func:`_transient_prompt_block`; once the function returns,
    the entire block disappears from scrollback.
    """
    global _cached_password

    if _continuous_ops_no_sudo():
        stripped = _strip_sudo(command)
        return (
            "[CAI_CONTINUOUS_OPS_NO_SUDO] This worker was started with sudo-style privileges "
            "declined. The command was not executed with elevation. On the next tick, use only "
            "read-only or user-accessible probes; never use sudo, su, doas, or pkexec.\n"
            f"Inner command (without sudo prefix): {stripped}"
        )

    # --- 1. Try session-cached password (no UI) ------------------------
    if _cached_password is not None:
        ok, auth_failed = _validate_with_password(
            _cached_password, workspace_dir,
        )
        if ok:
            return _VALIDATED
        if auth_failed:
            _cached_password = None  # stale

    # --- 2. Try OS-cached credentials, also no UI ---------------------
    if _validate_cached_creds(workspace_dir):
        return _VALIDATED

    # Reset the user-abort flag so a previous (now-handled) Ctrl+C does
    # not leak into this fresh prompt block. ``signal_handler`` will set
    # it again on the next SIGINT.
    from cai.util.interaction import (
        clear_prompt_abort_request,
        is_prompt_abort_requested,
    )
    clear_prompt_abort_request()

    # --- 3. Interactive password prompt (transient on screen) ----------
    cancelled = False
    timed_out = False
    result: str | None = None
    with _transient_prompt_block():
        _restore_tty_for_prompt()
        _show_auth_header(command)

        for attempt in range(1, max_attempts + 1):
            try:
                if max_attempts > 1:
                    _console.print(
                        Text(
                            f"Attempt {attempt}/{max_attempts}",
                            style=f"bold {CAI_GREEN}",
                        )
                    )
                password = _read_sudo_password_maybe_timed()
            except _SudoPasswordIdleTimeout:
                timed_out = True
                break
            except (EOFError, KeyboardInterrupt, OSError):
                # OSError: terminal not available (e.g. TUI owns /dev/tty)
                cancelled = True
                break

            # The interruptible reader returns None when Ctrl+C set the
            # abort flag while it was polling. Treat that as user cancel.
            if is_prompt_abort_requested() or password is None:
                clear_prompt_abort_request()
                cancelled = True
                break
            if not password:
                # Pressing Enter on an empty prompt is treated as a failed
                # attempt (matching real sudo's behavior). We skip the
                # actual ``sudo -S -v`` round-trip to avoid noise in
                # /var/log/auth.log and to keep the UX snappy, but still
                # consume one of the retry slots.
                _show_auth_failed()
                continue

            _show_authenticating()
            ok, auth_failed = _validate_with_password(password, workspace_dir)
            if ok:
                _cached_password = password
                _show_auth_ok()
                result = _VALIDATED
                break

            _show_auth_failed()
            if auth_failed and attempt < max_attempts:
                continue

    # ``_transient_prompt_block`` has now erased everything it drew. Any
    # message printed below stays in scrollback.
    if cancelled:
        _show_auth_cancelled()
        return f"Command cancelled by user: {command}"
    if timed_out:
        _show_auth_no_response()
        stripped = _strip_sudo(command)
        return (
            "Sudo verification failed, retrying without privileges. "
            f"Command changed to: {stripped}"
        )
    if result is None:
        # All attempts exhausted without a successful validation. Surface
        # the same "retrying without privileges" wording the timeout uses
        # so the agent reacts consistently regardless of the failure mode.
        _show_auth_failed_final()
        stripped = _strip_sudo(command)
        return (
            "Sudo verification failed, retrying without privileges. "
            f"Command changed to: {stripped}"
        )
    return result


@with_paused_terminal_owners
def prompt_sudo_elevation(
    command: str,
    workspace_dir: str,
    max_attempts: int = 3,
) -> str | None:
    """Called after a command fails with a permission error.

    Offers the user to retry with sudo.  If credentials are validated
    (or already cached), returns ``"sudo <command>"`` so the caller
    can re-execute.  Returns ``None`` if the user declines or auth fails.

    The interactive banner + password attempts are wrapped in a
    :func:`_transient_prompt_block` and erased on return.
    """
    global _cached_password

    if _continuous_ops_no_sudo():
        return None

    # --- 1. Cached creds? Validate silently. ---------------------------
    if _cached_password is not None:
        ok, _ = _validate_with_password(_cached_password, workspace_dir)
        if ok:
            return f"sudo {command}"

    if _validate_cached_creds(workspace_dir):
        return f"sudo {command}"

    # Reset abort flag so a previous Ctrl+C does not leak into this block.
    from cai.util.interaction import (
        clear_prompt_abort_request,
        is_prompt_abort_requested,
    )
    clear_prompt_abort_request()

    # --- 2. Interactive prompt -----------------------------------------
    cancelled = False
    timed_out = False
    result: str | None = None
    with _transient_prompt_block():
        _restore_tty_for_prompt()
        _show_elevation_prompt(command)

        for attempt in range(1, max_attempts + 1):
            try:
                if max_attempts > 1:
                    _console.print(
                        Text(
                            f"Attempt {attempt}/{max_attempts}",
                            style=f"bold {CAI_GREEN}",
                        )
                    )
                password = _read_sudo_password_maybe_timed()
            except _SudoPasswordIdleTimeout:
                timed_out = True
                break
            except (EOFError, KeyboardInterrupt, OSError):
                cancelled = True
                break

            if is_prompt_abort_requested() or password is None:
                clear_prompt_abort_request()
                cancelled = True
                break
            if not password:
                # Empty Enter counts as a failed attempt (see notes in
                # ``ensure_sudo_credentials``); we skip the validator
                # round-trip and just consume the retry slot.
                _show_auth_failed()
                continue

            _show_authenticating()
            ok, auth_failed = _validate_with_password(password, workspace_dir)
            if ok:
                _cached_password = password
                _show_auth_ok()
                result = f"sudo {command}"
                break

            _show_auth_failed()
            if auth_failed and attempt < max_attempts:
                continue

    if cancelled:
        _show_auth_cancelled()
    elif timed_out:
        _show_auth_no_response()
    elif result is None:
        # All attempts exhausted without success: same visual notice as
        # ``ensure_sudo_credentials`` so both sudo flows look identical.
        _show_auth_failed_final()
    return result


# Backward-compatible alias
run_sudo_command = ensure_sudo_credentials


# ============================================================================
# Section 3 — Sensitive command guard
# ============================================================================
# Detects commands requiring elevated privileges or performing dangerous
# operations and prompts the user for confirmation before execution.
#
# Sudo password handling is delegated to Section 2 above (credential
# caching, ``sudo -S -v`` validation, post-execution elevation). The guard
# only decides whether the command should proceed, be retried differently,
# or be cancelled.
#
# An allowlist cache lets users permanently authorise a binary for the
# current session (e.g. ``nmap``).  Choosing "Always allow" adds the binary
# to the cache so the guard won't prompt again.  ``/flush all`` clears it.
#
# Controlled by CAI_SENSITIVE_GUARD env var (default: "true").
# CAI_YOLO=1 (or CLI ``--yolo``) disables this guard entirely.
# CAI_AVOID_SUDO=true rejects sudo/su/pkexec/doas regardless of YOLO.
#
# Only active in CLI headless mode (CAI_TUI_MODE != "true").
#
# Interactive choice uses questionary's blocking ``.ask()`` from a worker
# thread (``asyncio.to_thread``) so a second prompt after sudo/getpass does
# not trip prompt_toolkit/asyncio nesting issues that ``ask_async()`` can
# hit mid-run.

_SENSITIVE_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, human-readable reason, category)

    # sudo / su — password handling delegated to Section 2
    (r"\bsudo\b", "Command requires superuser privileges (sudo)", "sudo"),
    (r"^\s*su\s+", "Command switches user (su)", "sudo"),
    (r"^\s*su\s*$", "Command switches to root (su)", "sudo"),
    (r"\bpkexec\b", "Command uses PolicyKit privilege escalation", "sudo"),
    (r"\bdoas\b", "Command uses doas privilege escalation", "sudo"),

    # destructive
    # (catastrophic ``rm`` is detected by _is_catastrophic_rm() below -- a regex
    # here would be filtered out by the "destructive" binary post-check anyway)
    (r"\bmkfs\.", "Command formats a filesystem", "destructive"),
    (r"\bdd\b.*\bof=/dev/", "Direct write to block device (dd)", "destructive"),
    (r"\bwipefs\b", "Command wipes filesystem signatures", "destructive"),
    (r"\bfdisk\b", "Command modifies partition table", "destructive"),
    (r"\bparted\b", "Command modifies partition table", "destructive"),
    (r"\bshred\b", "Command securely erases files", "destructive"),

    # reconnaissance tools — may trigger IDS/IPS or violate scope
    (r"\bnmap\b", "Network scanner (nmap)", "recon_tool"),
    (r"\bmasscan\b", "Mass port scanner (masscan)", "recon_tool"),
    (r"\bnikto\b", "Web vulnerability scanner (nikto)", "recon_tool"),
    (r"\bgobuster\b", "Directory/DNS brute-forcer (gobuster)", "recon_tool"),
    (r"\bdirsearch\b", "Web path scanner (dirsearch)", "recon_tool"),
    (r"\bsqlmap\b", "SQL injection tool (sqlmap)", "recon_tool"),
    (r"\bhydra\b", "Brute-force tool (hydra)", "recon_tool"),
    (r"\bmsfconsole\b|\bmsfvenom\b|\bmetasploit\b", "Metasploit framework", "recon_tool"),

    # reverse shells
    (r"nc\s+[\d\.]+\s+\d+.*(-e\s|/bin/)", "Netcat reverse shell", "reverse_shell"),
    (r"ncat\s+.*(-e\s|--exec)", "Ncat reverse shell", "reverse_shell"),
    (r"bash\s+.*-i\s+.*>&.*/dev/tcp/", "Bash reverse shell via /dev/tcp", "reverse_shell"),
    (r"/dev/tcp/[\d\.]+/\d+", "Bash network redirection (/dev/tcp)", "reverse_shell"),
    (r"socat\s+.*TCP:.*EXEC", "Socat reverse shell", "reverse_shell"),

    # pipe to shell
    (r"curl\s+.*\|\s*(ba)?sh", "Download piped to shell (curl|sh)", "pipe_to_shell"),
    (r"wget\s+.*\|\s*(ba)?sh", "Download piped to shell (wget|sh)", "pipe_to_shell"),
    (r"curl\s+.*\|\s*python", "Download piped to python (curl|python)", "pipe_to_shell"),
    (r"wget\s+.*\|\s*python", "Download piped to python (wget|python)", "pipe_to_shell"),

    # exfiltration
    (r"curl\s+.*-d\s+.*\$\(env\)", "Exfiltration of environment variables via curl", "exfiltration"),
    (r"curl\s+.*-d\s+.*`env`", "Exfiltration of environment variables via curl", "exfiltration"),
]

# Session-scoped allowlist of binaries the user has permanently authorised.
_allowed_commands: set[str] = set()

_GREP_LIKE = re.compile(r"^(?:grep|egrep|fgrep|rg)\b", re.IGNORECASE)


def _split_pipe_segments(cmd: str) -> list[str]:
    """Split *cmd* on a single ``|`` pipeline boundary.

    Ignores ``|`` inside single/double-quoted spans (so ``grep -E '(a|b)'`` does not
    fragment) and treats ``||`` as logical OR, not a pipeline delimiter.
    """
    segments: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(cmd)
    in_single = False
    in_double = False

    def _flush() -> None:
        t = "".join(buf).strip()
        if t:
            segments.append(t)
        buf.clear()

    while i < n:
        c = cmd[i]
        if in_single:
            buf.append(c)
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
                buf.append(c)
                buf.append(cmd[i + 1])
                i += 2
                continue
            buf.append(c)
            if c == '"':
                in_double = False
            i += 1
            continue
        if c == "'":
            in_single = True
            buf.append(c)
            i += 1
            continue
        if c == '"':
            in_double = True
            buf.append(c)
            i += 1
            continue
        if c == "|":
            j = i + 1
            while j < n and cmd[j].isspace():
                j += 1
            if j < n and cmd[j] == "|":
                buf.append("|")
                buf.append("|")
                i = j + 1
                continue
            _flush()
            i = j
            continue
        buf.append(c)
        i += 1
    _flush()
    return segments


def _mask_quoted_regions(cmd: str) -> str:
    """Replace quoted spans with spaces so token scans ignore literal tool names in strings."""
    out: list[str] = []
    i = 0
    n = len(cmd)
    in_single = False
    in_double = False
    while i < n:
        c = cmd[i]
        if in_single:
            out.append(" ")
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\" and i + 1 < n:
                out.append(" ")
                out.append(" ")
                i += 2
                continue
            out.append(" ")
            if c == '"':
                in_double = False
            i += 1
            continue
        if c == "'":
            in_single = True
            out.append(" ")
            i += 1
            continue
        if c == '"':
            in_double = True
            out.append(" ")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _command_has_shell_level_sudo(cmd: str) -> bool:
    """True only if ``sudo`` appears as a real shell token, not inside a ``grep -E '...'`` pattern."""
    for raw_seg in _split_pipe_segments(cmd):
        seg = raw_seg.strip()
        if not seg:
            continue
        if _GREP_LIKE.match(seg):
            continue
        if re.search(r"(?:^|[;&]\s*)sudo\b", seg, re.IGNORECASE):
            return True
    return False


def clear_allowed_commands() -> None:
    """Reset the session allowlist (called by ``/flush all``)."""
    _allowed_commands.clear()


_COMMAND_PREFIXES = frozenset({
    "sudo", "env", "nice", "nohup", "time", "strace", "ltrace",
    "ionice", "taskset", "chrt",
})


def _extract_all_binaries(command: str) -> set[str]:
    """Extract the actual binary names from all sub-commands in a pipeline/chain.

    Splits on ``|``, ``&&``, ``||``, and ``;``, then for each sub-command
    skips common prefixes (sudo, env, ...) and env-var assignments
    (``FOO=bar``) to find the real binary being executed.

    Returns basenames so ``/usr/bin/nmap`` yields ``"nmap"``.
    """
    parts = re.split(r"\s*(?:\|\||&&|[|;])\s*", command)
    binaries: set[str] = set()
    for part in parts:
        tokens = part.strip().split()
        for token in tokens:
            if "=" in token and not token.startswith("-"):
                continue
            if token.startswith("-"):
                continue
            basename = os.path.basename(token)
            if basename in _COMMAND_PREFIXES:
                continue
            binaries.add(basename)
            break
    return binaries


_RECON_TOOL_NAMES: set[str] = {
    "nmap", "masscan", "nikto", "gobuster", "dirsearch",
    "sqlmap", "hydra", "msfconsole", "msfvenom", "metasploit",
}
_DESTRUCTIVE_TOOL_NAMES: set[str] = {
    "mkfs", "wipefs", "fdisk", "parted", "shred",
}
_BINARY_CHECK_CATEGORIES: dict[str, set[str]] = {
    "recon_tool": _RECON_TOOL_NAMES,
    "destructive": _DESTRUCTIVE_TOOL_NAMES,
}


def _recon_tool_tokens(command: str) -> set[str]:
    """Recon binaries named anywhere in *command* (e.g. ``which nmap``, paths to ``nmap``).

    ``_extract_all_binaries`` only keeps the invoked binary per shell segment, so ``which nmap``
    would otherwise miss ``nmap`` and break "Always allow" for the tool the user cares about.
    """
    found: set[str] = set()
    scan = _mask_quoted_regions(command)
    for raw in re.findall(r"\S+", scan):
        tok = raw.strip("`'\";|&()")
        if not tok or tok.startswith("#"):
            continue
        if tok.startswith("-") and "=" not in tok:
            continue
        if re.match(r"^[\d.:]+$", tok):
            continue
        base = os.path.basename(tok)
        if base in _RECON_TOOL_NAMES:
            found.add(base)
    return found


def _recon_hits_for_command(command: str) -> set[str]:
    """Recon tools invoked or referenced in *command* (used for prompts + allowlist)."""
    return (_extract_all_binaries(command) | _recon_tool_tokens(command)) & _RECON_TOOL_NAMES


def _yolo_enabled() -> bool:
    return os.getenv("CAI_YOLO", "").strip().lower() in ("1", "true", "yes")


def _avoid_sudo_enabled() -> bool:
    """Operator policy: reject privilege-escalation shell commands (see module docstring)."""
    return os.getenv("CAI_AVOID_SUDO", "").strip().lower() in ("1", "true", "yes", "on")


def avoid_sudo_command_blocked(command: str) -> tuple[bool, str]:
    """If ``CAI_AVOID_SUDO`` is on, block ``sudo``/``su``/``pkexec``/``doas`` regardless of YOLO.

    Returns:
        ``(True, reason)`` when the command must not run, else ``(False, "")``.
    """
    if not _avoid_sudo_enabled():
        return (False, "")
    if _command_has_shell_level_sudo(command):
        return (
            True,
            "Command uses sudo; CAI_AVOID_SUDO is enabled — use non-privileged alternatives "
            "(no sudo/su/pkexec/doas).",
        )
    if re.search(r"\bpkexec\b", command, re.IGNORECASE):
        return (True, "Command uses pkexec; CAI_AVOID_SUDO is enabled.")
    if re.search(r"\bdoas\b", command, re.IGNORECASE):
        return (True, "Command uses doas; CAI_AVOID_SUDO is enabled.")
    if re.search(r"(?:^|[;&|]\s*)\bsu\b(?:\s+|$)", command, re.IGNORECASE):
        return (True, "Command uses su; CAI_AVOID_SUDO is enabled.")
    return (False, "")


def _is_guard_enabled() -> bool:
    if os.getenv("CAI_TUI_MODE", "").lower() == "true":
        return False
    if _yolo_enabled():
        return False
    return os.getenv("CAI_SENSITIVE_GUARD", "true").lower() != "false"


# --- Catastrophic ``rm`` detection (issue #470) ------------------------------
# The guard prompts before dangerous operations, but its original ``rm`` regex
# required the target to contain ``/``, so ``rm -rf .``, ``rm -rf ~`` and
# ``rm -rf *`` -- the ordinary ways to wipe a working tree or a home directory
# -- were never detected (a user reported CAI running ``rm -rf .`` and deleting
# their home directory). This predicate replaces that regex.
#
# It is a heuristic for an *interactive confirmation*, not a sandbox. Deliberately
# obfuscated forms are intentionally out of scope and left to other guards / the
# model's judgement: command substitution (``$(pwd)``, backticks), wrapper
# binaries (``env``/``xargs``/``nice`` ...), and non-``rm`` tree deleters
# (``find ... -delete``).
_CATASTROPHIC_RM_TARGETS: frozenset[str] = frozenset(
    {"/", "/*", ".", "..", "~", "*", "$HOME", "$PWD"}
)
_CRITICAL_SYSTEM_DIRS: frozenset[str] = frozenset({
    "/etc", "/home", "/usr", "/var", "/bin", "/sbin", "/lib", "/lib64",
    "/boot", "/root", "/opt", "/dev", "/proc", "/sys", "/srv", "/mnt", "/media",
})
_RM_SEGMENT_SEPARATORS: frozenset[str] = frozenset(
    {"&&", "||", ";", ";;", "|", "&", "(", ")", "\n"}
)
_RM_GLOB_LEAVES: frozenset[str] = frozenset({"*", ".*", ".[!.]*"})


def _rm_command_segments(command: str) -> list[list[str]]:
    """Tokenize *command* and split it into simple-command token lists on shell
    control operators, quote-aware.

    So ``rm -rf ./build && cd ~`` becomes two segments and the ``~`` from
    ``cd ~`` is never misread as an ``rm`` target, while a file literally named
    ``a && b`` stays a single token.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        try:
            tokens = shlex.split(command)
        except ValueError:
            return []
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _RM_SEGMENT_SEPARATORS:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _rm_target_is_catastrophic(target: str) -> bool:
    """True if a single ``rm`` argument denotes a catastrophic location."""
    norm = target.replace("${HOME}", "$HOME").replace("${PWD}", "$PWD")
    norm = norm.rstrip("/") or "/"
    # Peel one trailing glob leaf: ``~/*`` -> ``~``, ``/home/*`` -> ``/home``.
    if "/" in norm:
        head, _, leaf = norm.rpartition("/")
        if head and leaf in _RM_GLOB_LEAVES:
            norm = head
    return norm in _CATASTROPHIC_RM_TARGETS or norm in _CRITICAL_SYSTEM_DIRS


def _segment_is_catastrophic_rm(tokens: list[str]) -> bool:
    if not tokens:
        return False
    index = 0
    # Skip leading VAR=value assignments, e.g. ``FOO=bar rm -rf .``.
    while (
        index < len(tokens)
        and "=" in tokens[index]
        and not tokens[index].startswith("-")
    ):
        index += 1
    if index >= len(tokens) or os.path.basename(tokens[index]) != "rm":
        return False
    recursive = False
    targets: list[str] = []
    for token in tokens[index + 1:]:
        if token == "--":
            continue
        if token.startswith("--"):
            if token == "--recursive":
                recursive = True
            continue
        if token.startswith("-") and len(token) > 1:
            if "r" in token or "R" in token:
                recursive = True
            continue
        targets.append(token)
    if not recursive:
        return False
    return any(_rm_target_is_catastrophic(t) for t in targets)


def _is_catastrophic_rm(command: str) -> bool:
    """True if *command* runs an ``rm`` that recursively/forcibly removes a
    catastrophic target -- the root filesystem, a top-level system directory,
    the home directory, the current/parent directory, or a glob of their
    contents (``rm -rf .`` / ``~`` / ``*`` / ``~/*`` / ``/etc`` ...).

    Deliberately obfuscated forms are out of scope (see the module note above);
    this only has to catch the ordinary spellings the old regex missed.
    """
    return any(
        _segment_is_catastrophic_rm(segment)
        for segment in _rm_command_segments(command)
    )


def detect_sensitive_command(command: str) -> tuple[bool, str, str]:
    """Check whether *command* matches any sensitive pattern.

    The allowlist only suppresses ``recon_tool`` matches.  Privilege-
    escalation (``sudo``), ``destructive``, ``reverse_shell``,
    ``pipe_to_shell``, and ``exfiltration`` patterns are **always**
    checked — even when the leading binary is in the allowlist.

    Returns:
        (is_sensitive, reason, category)
        When *is_sensitive* is False, *reason* and *category* are empty strings.
    """
    if not _is_guard_enabled():
        return (False, "", "")

    for pattern, reason, category in _SENSITIVE_PATTERNS:
        if not re.search(pattern, command, re.IGNORECASE):
            continue
        if category == "sudo" and not _command_has_shell_level_sudo(command):
            continue

        tool_names = _BINARY_CHECK_CATEGORIES.get(category)
        relevant = _extract_all_binaries(command)
        if category == "recon_tool":
            relevant |= _recon_tool_tokens(command)
        if tool_names is not None:
            if not (relevant & tool_names):
                continue

        # Session allowlist: skip only when every recon tool in this command is allowed
        # (covers ``sudo nmap`` after allowing ``nmap``, and ``which nmap`` vs first-token ``which``).
        if category == "recon_tool":
            hits = relevant & _RECON_TOOL_NAMES
            if hits and hits.issubset(_allowed_commands):
                return (False, "", "")

        return (True, reason, category)

    # Catastrophic ``rm`` (issue #470): the patterns above only match targets
    # containing ``/``, so ``rm -rf .`` / ``~`` / ``*`` slip through. Check for
    # them here, after the loop, so the ``sudo`` pattern still wins for
    # ``sudo rm -rf /`` (it matches earlier and returns "sudo").
    if _is_catastrophic_rm(command):
        return (
            True,
            "Recursive/forced removal of a catastrophic target (the root "
            "filesystem, a system directory, home, the working directory, or a "
            "glob of their contents)",
            "destructive",
        )

    return (False, "", "")


def _continuous_ops_sensitive_wait_seconds() -> float:
    """Max seconds to wait on the sensitive-command menu inside the continuous-ops worker."""
    try:
        tick = float(os.getenv("CAI_CONTINUOUS_OPS_TICK_SECONDS", "60"))
    except ValueError:
        tick = 60.0
    return max(5.0, tick / 3.0)


def _sensitive_menu_timeout_seconds() -> float:
    """Idle limit on the sensitive-command menu (questionary / plain fallback).

    Continuous-ops ticks use ``tick/3`` so unattended loops do not stall. All other
    headless contexts use three minutes, then default to reject (same as declining).
    """
    if _continuous_ops_worker():
        return _continuous_ops_sensitive_wait_seconds()
    return 180.0


def _map_sensitive_answer(answer: str | None) -> str:
    if answer is None or answer.startswith("Cancel"):
        return "cancel"
    if answer.startswith("Reject"):
        return "reject"
    return "allow"


@with_paused_terminal_owners
async def prompt_user_for_sensitive_command(
    command: str,
    reason: str,
    category: str,
) -> str:
    """Show an interactive selector asking the user what to do.

    Returns:
        ``"allow"``        – proceed with execution once
        ``"allow_always"`` – proceed and remember the binary for the session
        ``"reject"``       – abort and tell the LLM to try another way
        ``"cancel"``       – return control to user for new instructions

    The whole banner + questionary block is rendered inside a
    :func:`_transient_prompt_block` so it disappears from the screen as
    soon as the user picks an answer; the only visible record stays in
    the compact REPL live block (``✓ COMPLETED`` / ``✗ ERROR`` rows).
    """
    if (
        os.getenv("CAI_CONTINUOUS_OPS_NO_SUDO", "").strip().lower() in ("1", "true", "yes")
        and category == "sudo"
    ):
        return "reject"

    if _avoid_sudo_enabled() and category == "sudo":
        return "reject"

    with _transient_prompt_block():
        return await _prompt_user_for_sensitive_command_body(command, reason, category)


async def _prompt_user_for_sensitive_command_body(
    command: str,
    reason: str,
    category: str,
) -> str:
    """Body of :func:`prompt_user_for_sensitive_command` (transient erase happens in the wrapper)."""

    # Restore cursor / TTY before any prompt text so the banner and questionary stay visible
    # after Rich Live (frozen agent) or prompt_toolkit.
    try:
        from cai.util.streaming import restore_terminal_state

        restore_terminal_state(emit_trailing_newline=False)
    except Exception:
        pass

    # No leading \\n — the frozen agent Live block already ends with a newline; extra
    # newlines here stacked 2–3 blank rows before this prompt (photo 4 in CLI UX reports).
    try:
        from rich.console import Group

        # Only "!" is on yellow; following space is unstyled (no yellow band before text).
        warn = Text()
        warn.append("!", style=YELLOW_ON)
        warn.append(" ", style="")
        warn.append("Sensitive command detected", style=YELLOW_WARN)
        cmd_ln = Text()
        cmd_ln.append("   Command : ", style="dim yellow")
        cmd_ln.append(command, style=YELLOW_WARN)
        reason_ln = Text()
        reason_ln.append("   Reason  : ", style="dim yellow")
        reason_ln.append(reason, style=YELLOW_WARN)
        _console.print(Group(warn, cmd_ln, reason_ln))
    except Exception:
        header = (
            f"⚠  Sensitive command detected\n"
            f"   Command : {command}\n"
            f"   Reason  : {reason}\n"
        )
        print(header, flush=True)

    choices = ["Authorize execution"]
    if category == "recon_tool":
        hits = sorted(_recon_hits_for_command(command))
        if hits:
            if len(hits) == 1:
                choices.append(f"Always allow '{hits[0]}' this session")
            else:
                choices.append(f"Always allow ({', '.join(hits)}) this session")
    choices.append("Reject — try another way")
    choices.append("Cancel — abort and return to prompt")

    # Lazy import to avoid the cai.tools.common <-> cai.util.user_prompts cycle
    # (see module-level comment).
    from cai.repl.commands.settings.general import custom_style

    def _sync_questionary_select() -> str | None:
        """Run questionary select; returns None only on user Ctrl+C.

        Real errors (terminal incompatibility, broken pipe, etc.) propagate
        so the caller can fall back to the plain text menu.
        """
        try:
            return questionary.select(
                "What do you want to do?",
                choices=choices,
                style=custom_style,
            ).ask()
        except KeyboardInterrupt:
            return None
        except EOFError:
            return None

    def _sync_plain_fallback() -> str:
        print("What do you want to do?")
        print("  [1] Authorize execution")
        try:
            if category == "recon_tool":
                _h = sorted(_recon_hits_for_command(command))
                if _h:
                    _al = f"'{_h[0]}'" if len(_h) == 1 else f"({', '.join(_h)})"
                    print(f"  [2] Always allow {_al} this session")
                    print("  [3] Reject \u2014 try another way")
                    print("  [4] Cancel \u2014 abort and return to prompt")
                    raw = input("Choice [1-4, default 4]: ").strip().lower()
                    if raw in ("1", "a", "authorize", "y", "yes"):
                        return choices[0]
                    if raw in ("2",):
                        return choices[1]
                    if raw in ("3", "r", "reject", "n", "no"):
                        return choices[2]
                    return choices[3]
                print("  [2] Reject \u2014 try another way")
                print("  [3] Cancel \u2014 abort and return to prompt")
                raw = input("Choice [1-3, default 3]: ").strip().lower()
                if raw in ("1", "a", "authorize", "y", "yes"):
                    return choices[0]
                if raw in ("2", "r", "reject", "n", "no"):
                    return choices[1]
                return choices[2]
            else:
                print("  [2] Reject \u2014 try another way")
                print("  [3] Cancel \u2014 abort and return to prompt")
                raw = input("Choice [1-3, default 3]: ").strip().lower()
                if raw in ("1", "a", "authorize", "y", "yes"):
                    return choices[0]
                if raw in ("2", "r", "reject", "n", "no"):
                    return choices[1]
                return choices[2]
        except (EOFError, KeyboardInterrupt):
            return choices[-1]

    answer: str | None = None
    questionary_failed = False
    timeout_sec = _sensitive_menu_timeout_seconds()
    try:
        answer = await asyncio.wait_for(
            asyncio.to_thread(_sync_questionary_select),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        try:
            if _continuous_ops_worker():
                _console.print(
                    "[bold yellow]Sensitive-command prompt timed out (1/3 of tick interval). "
                    "Defaulting to reject.[/bold yellow]"
                )
            else:
                _console.print(
                    "[bold yellow]Sensitive-command prompt timed out (3 minutes). "
                    "Defaulting to reject.[/bold yellow]"
                )
        except Exception:
            pass
        return "reject"
    except Exception:
        questionary_failed = True

    if answer is None and not questionary_failed:
        if _continuous_ops_worker():
            try:
                _console.print(
                    "[bold yellow]Sensitive-command prompt closed with no selection; "
                    "defaulting to reject for unattended continuous-ops iteration.[/bold yellow]"
                )
            except Exception:
                pass
            return "reject"
        try:
            from cai.util.streaming import restore_terminal_state as _restore
            _restore(emit_trailing_newline=False)
        except Exception:
            pass
        return "cancel"

    if answer is None:
        try:
            answer = await asyncio.wait_for(
                asyncio.to_thread(_sync_plain_fallback),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            try:
                _console.print(
                    "[bold yellow]Sensitive-command plain menu timed out — defaulting to reject.[/bold yellow]"
                )
            except Exception:
                pass
            return "reject"
        except (EOFError, KeyboardInterrupt, OSError):
            return "cancel"

    mapped = _map_sensitive_answer(answer)
    if mapped == "allow" and answer and answer.startswith("Always allow"):
        if category == "recon_tool":
            for b in _recon_hits_for_command(command):
                _allowed_commands.add(b)

    # No trailing blank line: the surrounding ``_transient_prompt_block``
    # erases the entire banner + questionary on context exit, so any
    # spacing here would be wiped anyway.
    return mapped


__all__ = [
    # Section 1 — terminal owners
    "pause_terminal_owners",
    "paused_terminal_owners",
    "resume_terminal_owners",
    "with_paused_terminal_owners",
    # Section 2 — sudo
    "clear_cached_password",
    "ensure_sudo_credentials",
    "is_sudo_command",
    "output_needs_sudo",
    "prompt_sudo_elevation",
    "run_sudo_command",
    # Section 3 — sensitive command guard
    "avoid_sudo_command_blocked",
    "clear_allowed_commands",
    "detect_sensitive_command",
    "prompt_user_for_sensitive_command",
]
