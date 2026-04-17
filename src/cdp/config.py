"""Read and write ~/.config/cdp/config.toml using tomlkit to preserve comments."""
from __future__ import annotations

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
        entries = []
        for tbl in doc.get("project", []):
            entries.append(
                ConfigEntry(
                    path=str(tbl["path"]),
                    alias=str(tbl["alias"]) if "alias" in tbl else None,
                    pinned=bool(tbl.get("pinned", False)),
                    hidden=bool(tbl.get("hidden", False)),
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
        self._path.write_text(tomlkit.dumps(self._doc))

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
