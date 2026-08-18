"""Tests for catastrophic ``rm`` detection in the sensitive-command guard (#470).

CAI's guard prompts before dangerous shell commands, but its original ``rm``
regex only matched targets containing ``/`` -- so ``rm -rf .`` / ``~`` / ``*``
(the ordinary ways to wipe a working tree or a home directory) slipped through,
and one such command was reported to have deleted a user's home directory. These
tests pin the fix: those forms are now detected and prompt, while legitimate
recursive removals of named sub-paths are left alone.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from cai.util.user_prompts import _is_catastrophic_rm, detect_sensitive_command


@pytest.fixture(autouse=True)
def _guard_enabled():
    """Ensure the guard is always enabled during tests."""
    with patch.dict("os.environ", {"CAI_SENSITIVE_GUARD": "true", "CAI_TUI_MODE": "false"}):
        yield


# Commands that must be treated as catastrophic (the guard should prompt).
CATASTROPHIC = [
    "rm -rf .", "rm -rf ./", "rm -rf ..", "rm -rf ~", "rm -rf ~/",
    "rm -rf $HOME", 'rm -rf "$HOME"', "rm -rf ${HOME}", "rm -rf *",
    "rm -rf /", "rm -rf /*", "rm -fr .", "rm -Rf .", "rm -r -f .",
    "rm --recursive --force ~", "rm -rf -- .", "FOO=bar rm -rf .",
    "rm -rf . 2>/dev/null",
    # top-level system directories
    "rm -rf /etc", "rm -rf /home", "rm -rf /usr/",
    # a glob of a catastrophic root's contents
    "rm -rf ~/*", "rm -rf ./*", "rm -rf /home/*", "rm -rf $HOME/*",
    # the destructive rm hidden after a leading command in a compound line
    "cd /tmp && rm -rf ~",
]

# Legitimate recursive removals that must NOT be flagged.
LEGIT = [
    "rm file.txt", "rm -f stale.log", "rm -r mydir", "rm -rf ./build",
    "rm -rf node_modules", "rm -rf target/debug", "rm -rf /tmp/cai-scratch",
    "rm -rf /tmp", "rm -rf ~/proj/node_modules", "rm -rf ~/.cache/foo",
    "rm -rf ./out/", "rm -rf /home/kali/proj/build",
    # a benign command chained after a legit rm must not be misread as a target
    "rm -rf ./build && cd ~", "rm -rf ./out; cd /",
    # not the rm binary
    "git rm -rf .", "docker rm -f ctr",
]


class TestIsCatastrophicRm:
    @pytest.mark.parametrize("command", CATASTROPHIC)
    def test_catastrophic(self, command):
        assert _is_catastrophic_rm(command) is True

    @pytest.mark.parametrize("command", LEGIT)
    def test_legit(self, command):
        assert _is_catastrophic_rm(command) is False


class TestDetectSensitiveCommand:
    @pytest.mark.parametrize("command", CATASTROPHIC)
    def test_catastrophic_prompts_as_destructive(self, command):
        is_sensitive, _reason, category = detect_sensitive_command(command)
        assert is_sensitive
        assert category == "destructive"

    @pytest.mark.parametrize("command", LEGIT)
    def test_legit_not_flagged(self, command):
        is_sensitive, _reason, _category = detect_sensitive_command(command)
        assert not is_sensitive

    def test_sudo_rm_rf_still_categorised_as_sudo(self):
        # ``sudo`` is matched earlier in the pattern loop, so it wins and the
        # command is reported as "sudo" (still prompted), not "destructive".
        is_sensitive, _reason, category = detect_sensitive_command("sudo rm -rf /")
        assert is_sensitive
        assert category == "sudo"

    def test_respects_disabled_guard(self):
        # When the guard is disabled the catastrophic check must not fire either.
        with patch.dict("os.environ", {"CAI_SENSITIVE_GUARD": "false"}):
            is_sensitive, _reason, _category = detect_sensitive_command("rm -rf ~")
            assert not is_sensitive
