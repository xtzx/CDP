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
