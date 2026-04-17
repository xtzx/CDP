"""Read and write ~/.config/cdp/config.toml using tomlkit to preserve comments."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import tomlkit
from tomlkit import TOMLDocument


@dataclass
class ConfigEntry:
    path: str
    alias: str | None = None
    pinned: bool = False
    hidden: bool = False


def _require_bool(value, field: str, file: Path) -> bool:
    # tomlkit's Bool is a subclass of `int` but NOT of `bool`, so check via its
    # class name. Built-in Python bools pass isinstance(value, bool).
    if isinstance(value, bool):
        return value
    type_name = type(value).__name__
    if type_name in ("Bool", "Boolean"):
        return bool(value)
    raise ValueError(
        f"invalid TOML at {file}: `{field}` must be a boolean (true/false), "
        f"got {type_name} ({value!r})"
    )


class Config:
    def __init__(self, path: Path, doc: TOMLDocument, entries: list[ConfigEntry]):
        self._path = path
        self._doc = doc
        self.entries = entries

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            return cls(path=path, doc=tomlkit.document(), entries=[])
        try:
            doc = tomlkit.parse(path.read_text())
        except Exception as e:
            raise ValueError(f"invalid TOML at {path}: {e}") from e

        raw_projects = doc.get("project", [])
        # Guard: `project` must be an array of tables, not a scalar or a plain
        # table. `list` catches plain lists; tomlkit's AoT subclasses `list` so
        # it passes this check too.
        if not isinstance(raw_projects, list):
            raise ValueError(
                f"invalid TOML at {path}: `project` must be an array of tables "
                f"([[project]]), got {type(raw_projects).__name__}"
            )

        entries = []
        for tbl in raw_projects:
            entries.append(
                ConfigEntry(
                    path=str(tbl["path"]),
                    alias=str(tbl["alias"]) if "alias" in tbl else None,
                    pinned=_require_bool(tbl.get("pinned", False), "pinned", path),
                    hidden=_require_bool(tbl.get("hidden", False), "hidden", path),
                )
            )
        return cls(path=path, doc=doc, entries=entries)

    def save(self) -> None:
        # Rebuild the `project` array of tables from self.entries while keeping
        # top-level comments / unrelated keys in the document.
        new_array = tomlkit.aot()
        for e in self.entries:
            t = tomlkit.table()
            t["path"] = e.path
            if e.alias is not None:
                t["alias"] = e.alias
            if e.pinned:
                t["pinned"] = True
            if e.hidden:
                t["hidden"] = True
            new_array.append(t)
        self._doc["project"] = new_array
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: stage to a sibling .tmp then rename. A process kill or
        # disk-full between the write and the rename leaves the original file
        # intact.
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(tomlkit.dumps(self._doc))
        os.replace(tmp, self._path)

    # --- Mutations -----------------------------------------------------------

    def _find(self, path: str) -> ConfigEntry | None:
        for e in self.entries:
            if e.path == path:
                return e
        return None

    def _ensure(self, path: str) -> ConfigEntry:
        existing = self._find(path)
        if existing is not None:
            return existing
        new = ConfigEntry(path=path)
        self.entries.append(new)
        return new

    def _gc(self, entry: ConfigEntry) -> None:
        """Drop an entry that has no interesting state left."""
        if entry.alias is None and not entry.pinned and not entry.hidden:
            self.entries.remove(entry)

    def pin(self, path: str) -> None:
        self._ensure(path).pinned = True

    def unpin(self, path: str) -> None:
        e = self._find(path)
        if e is None:
            return
        e.pinned = False
        self._gc(e)

    def hide(self, path: str) -> None:
        self._ensure(path).hidden = True

    def unhide(self, path: str) -> None:
        e = self._find(path)
        if e is None:
            return
        e.hidden = False
        self._gc(e)

    def set_alias(self, path: str, alias: str) -> None:
        self._ensure(path).alias = alias

    def clear_alias(self, path: str) -> None:
        e = self._find(path)
        if e is None:
            return
        e.alias = None
        self._gc(e)
