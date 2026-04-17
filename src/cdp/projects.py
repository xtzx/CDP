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


@dataclass(frozen=True)
class DiscoveredProject:
    """A project auto-discovered from ~/.claude/projects/. No pin/alias yet."""
    path: str
    mtime: float


def scan_recent_projects(claude_projects_dir: Path) -> list[DiscoveredProject]:
    """Scan Claude Code's projects dir. Skip records whose decoded path is gone.

    Returns list sorted by mtime descending (most recent session first).
    """
    if not claude_projects_dir.is_dir():
        return []

    results: list[DiscoveredProject] = []
    for entry in claude_projects_dir.iterdir():
        if not entry.is_dir():
            continue
        decoded = decode_encoded_path(entry.name)
        if not os.path.isdir(decoded):
            continue
        mtime = _max_jsonl_mtime(entry)
        results.append(DiscoveredProject(path=decoded, mtime=mtime))

    results.sort(key=lambda p: p.mtime, reverse=True)
    return results


def _max_jsonl_mtime(proj_dir: Path) -> float:
    """Return the max mtime of .jsonl files inside proj_dir, or 0.0 if none/errors."""
    best = 0.0
    try:
        for f in proj_dir.iterdir():
            if f.suffix != ".jsonl":
                continue
            try:
                m = f.stat().st_mtime
                if m > best:
                    best = m
            except OSError:
                continue
    except OSError:
        return 0.0
    return best
