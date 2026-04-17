"""Merge auto-discovered projects with user config to produce the display list."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cdp.config import Config, ConfigEntry
from cdp.projects import DiscoveredProject


@dataclass(frozen=True)
class Project:
    path: str
    mtime: float
    display_name: str
    pinned: bool
    alias: str | None


def get_display_projects(
    discovered: list[DiscoveredProject],
    cfg: Config,
) -> list[Project]:
    """Return projects in final display order: pinned (config order) + rest (mtime desc).

    Hidden projects are filtered out. Projects whose directories no longer
    exist are filtered out. Config-only projects (user pinned/aliased but
    never opened with claude) are included when the dir exists.
    """
    # Build a lookup: path -> ConfigEntry
    by_path: dict[str, ConfigEntry] = {e.path: e for e in cfg.entries}

    # Union of all paths from discovered + config
    seen: set[str] = set()
    union_paths: list[tuple[str, float]] = []  # (path, mtime from discovered, or 0.0)
    for d in discovered:
        if d.path in seen:
            continue
        seen.add(d.path)
        union_paths.append((d.path, d.mtime))
    for e in cfg.entries:
        if e.path in seen:
            continue
        seen.add(e.path)
        union_paths.append((e.path, 0.0))

    # Build Project objects, applying filters
    projects: list[Project] = []
    for path, mtime in union_paths:
        e = by_path.get(path)
        if e is not None and e.hidden:
            continue
        if not os.path.isdir(path):
            continue
        alias = e.alias if e is not None else None
        pinned = e.pinned if e is not None else False
        display_name = alias if alias is not None else os.path.basename(path)
        projects.append(
            Project(
                path=path,
                mtime=mtime,
                display_name=display_name,
                pinned=pinned,
                alias=alias,
            )
        )

    # Split pinned vs rest, order pinned by config declaration order
    pin_order: dict[str, int] = {
        e.path: i for i, e in enumerate(cfg.entries) if e.pinned
    }
    pinned = sorted(
        (p for p in projects if p.pinned),
        key=lambda p: pin_order.get(p.path, 10**9),
    )
    rest = sorted(
        (p for p in projects if not p.pinned),
        key=lambda p: p.mtime,
        reverse=True,
    )
    return pinned + rest
