"""Scan Claude Code project records and decode their paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def decode_encoded_path(encoded: str) -> str:
    """Decode a Claude Code project dir name back to a filesystem path.

    Claude encodes paths by replacing '/' with '-'. Since real dir names may
    contain '-', we walk from root and at each depth try progressively longer
    segments, checking isdir. If no valid segmentation is found, fall back to
    naive '-' → '/' replacement.
    """
    if not encoded.startswith("-"):
        return encoded
    parts = encoded[1:].split("-")

    resolved = _walk(parts, "/")
    if resolved is not None:
        return resolved
    return "/" + "/".join(parts)


def _walk(remaining: list[str], current: str) -> str | None:
    if not remaining:
        return current
    for n in range(1, len(remaining) + 1):
        segment = "-".join(remaining[:n])
        candidate = os.path.join(current, segment)
        if os.path.isdir(candidate):
            result = _walk(remaining[n:], candidate)
            if result is not None:
                return result
    return None
