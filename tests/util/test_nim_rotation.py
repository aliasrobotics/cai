"""Tests for NVIDIA NIM API key round-robin rotation."""

from __future__ import annotations

import cai.util.nim_rotation as nim_rotation


def _reset() -> None:
    nim_rotation._NIM_CYCLE = None


def test_no_keys_configured_returns_none(monkeypatch):
    _reset()
    for i in range(1, 5):
        monkeypatch.delenv(f"NVIDIA_NIM_API_KEY_{i}", raising=False)
    assert nim_rotation.is_nim_rotation_configured() is False
    assert nim_rotation.get_next_nim_key() is None


def test_rotates_through_all_keys(monkeypatch, capsys):
    _reset()
    monkeypatch.setenv("NVIDIA_NIM_API_KEY_1", "key-one")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY_2", "key-two")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY_3", "key-three")
    monkeypatch.delenv("NVIDIA_NIM_API_KEY_4", raising=False)

    assert nim_rotation.is_nim_rotation_configured() is True
    seen = [
        nim_rotation.get_next_nim_key(),
        nim_rotation.get_next_nim_key(),
        nim_rotation.get_next_nim_key(),
        nim_rotation.get_next_nim_key(),
    ]
    assert seen == ["key-one", "key-two", "key-three", "key-one"]

    err = capsys.readouterr().err
    assert "Round-robin active (3 keys)" in err


def test_single_key_never_moves(monkeypatch):
    _reset()
    monkeypatch.setenv("NVIDIA_NIM_API_KEY_1", "only-key")
    monkeypatch.delenv("NVIDIA_NIM_API_KEY_2", raising=False)
    assert nim_rotation.get_next_nim_key() == "only-key"
    assert nim_rotation.get_next_nim_key() == "only-key"
