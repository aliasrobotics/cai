"""Round-robin rotation for NVIDIA NIM API keys.

Reads ``NVIDIA_NIM_API_KEY_1``, ``NVIDIA_NIM_API_KEY_2``, … from the
environment and cycles through them on every call to ``get_next_nim_key()``.

Set ``NVIDIA_NIM_API_KEY_1``, ``NVIDIA_NIM_API_KEY_2``, ``NVIDIA_NIM_API_KEY_3``
with your NIM keys. Each request gets the next key in sequence, spreading
the load so no single key exceeds the NIM rate limit (40 req/min).
"""

from __future__ import annotations

import itertools
import os
import sys

_NIM_CYCLE: itertools.cycle[str] | None = None


def _ensure_cycle() -> itertools.cycle[str] | None:
    global _NIM_CYCLE
    if _NIM_CYCLE is not None:
        return _NIM_CYCLE
    keys: list[str] = []
    for i in itertools.count(1):
        raw = os.getenv(f"NVIDIA_NIM_API_KEY_{i}")
        if raw:
            keys.append(raw.strip())
        else:
            break
    if keys:
        _NIM_CYCLE = itertools.cycle(keys)
        n = len(keys)
        print(
            f"[NIM] Round-robin active ({n} key{'s' if n != 1 else ''})",
            file=sys.stderr,
        )
    return _NIM_CYCLE


def is_nim_rotation_configured() -> bool:
    return _ensure_cycle() is not None


def get_next_nim_key() -> str | None:
    cycle = _ensure_cycle()
    if cycle is None:
        return None
    return next(cycle)
