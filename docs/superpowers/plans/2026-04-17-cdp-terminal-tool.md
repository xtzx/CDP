# cdp Terminal Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zsh terminal tool `cdp` that lists recent Claude Code projects (auto-discovered from `~/.claude/projects/`), lets the user pick one via fzf, and runs `cd <path> && claude` in the current shell.

**Architecture:** Python package (`python -m cdp`) handles scanning, sorting, config I/O, and fzf invocation. A thin zsh wrapper function reads the Python's stdout and performs `cd` in the parent shell (which a child process cannot do). A TOML config file (`~/.config/cdp/config.toml`) holds user-declared pin/hide/alias state; `tomlkit` preserves comments during round-trip writes.

**Tech Stack:** Python 3.10+, `tomlkit` (sole runtime dep), `pytest` (test dep), `fzf` (external CLI), `claude` (external CLI), zsh.

**Spec:** `docs/superpowers/specs/2026-04-17-cdp-terminal-tool-design.md`

---

## File Structure

Each file has one responsibility:

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, `cdp` script not used (we use `python -m cdp`) |
| `src/cdp/__init__.py` | Empty (marks package) |
| `src/cdp/__main__.py` | `python -m cdp` entrypoint; calls `cli.main()` |
| `src/cdp/constants.py` | Paths (`CLAUDE_PROJECTS_DIR`, `CONFIG_PATH`), command name, display widths |
| `src/cdp/projects.py` | Scan `~/.claude/projects/`, decode encoded directory names, produce `Project` dataclass list sorted by mtime |
| `src/cdp/config.py` | Load/save `~/.config/cdp/config.toml` with tomlkit; mutation methods (pin/unpin/hide/unhide/alias/unalias) |
| `src/cdp/combine.py` | Merge auto-discovered projects with config data; apply hide filter, alias, pin ordering; return final display list |
| `src/cdp/picker.py` | Format projects for fzf input, invoke fzf via subprocess, parse selection; handle hotkey internal commands |
| `src/cdp/cli.py` | argparse dispatcher for all subcommands; glue between `combine`, `picker`, `config` |
| `shell/cdp.zsh` | zsh wrapper function `cdp()` |
| `install.sh` | venv bootstrap + `~/.zshrc` injection (idempotent via marker comments) |
| `tests/test_projects.py` | Unit tests for `projects.py` (decoding, scanning, sorting) |
| `tests/test_config.py` | Unit tests for `config.py` (roundtrip, mutations, comment preservation) |
| `tests/test_combine.py` | Unit tests for `combine.py` (pin ordering, hide filter, alias application) |
| `tests/test_cli.py` | Integration tests via `subprocess.run` for CLI subcommands |
| `README.md` | Install / usage / rename / uninstall instructions |

## Data Model

`Project` (returned by `combine.get_display_projects()` to picker/cli):

```python
@dataclass(frozen=True)
class Project:
    path: str              # absolute, existing directory
    mtime: float           # epoch seconds; 0.0 if unknown
    display_name: str      # alias if set else basename(path)
    pinned: bool           # True → goes to pin section
    alias: str | None      # raw alias from config, if any
```

`ConfigEntry` (stored in `config.py`):

```python
@dataclass
class ConfigEntry:
    path: str
    alias: str | None = None
    pinned: bool = False
    hidden: bool = False
```

---

## Task 1: Repo scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/cdp/__init__.py`
- Create: `src/cdp/__main__.py`
- Create: `src/cdp/constants.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cdp"
version = "0.1.0"
description = "Terminal picker for recent Claude Code projects"
requires-python = ">=3.10"
dependencies = [
    "tomlkit>=0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=7",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
```

- [ ] **Step 2: Create package files**

`src/cdp/__init__.py`:
```python
__version__ = "0.1.0"
```

`src/cdp/__main__.py`:
```python
from cdp.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `src/cdp/constants.py`**

```python
"""Central place for names and paths. Change COMMAND_NAME to rename the tool."""
import os
from pathlib import Path

COMMAND_NAME = "cdp"

HOME = Path.home()
CLAUDE_PROJECTS_DIR = HOME / ".claude" / "projects"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / COMMAND_NAME
CONFIG_PATH = CONFIG_DIR / "config.toml"

# Display widths (characters) for fzf rendering
NAME_COL_WIDTH = 18
PIN_ICON = "📌 "
NO_PIN_PREFIX = "   "  # 3 spaces to keep columns aligned with PIN_ICON width
```

- [ ] **Step 4: Create test infrastructure**

`tests/__init__.py`: (empty)

`tests/conftest.py`:
```python
"""Shared fixtures for all tests."""
import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect HOME to tmp_path so tests don't touch the real ~."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    # Reload constants so they pick up the new HOME
    import importlib
    import cdp.constants
    importlib.reload(cdp.constants)
    yield tmp_path
    importlib.reload(cdp.constants)
```

- [ ] **Step 5: Verify the package is importable**

Run:
```bash
cd /Users/bjhl/Documents/手写系列/cdp
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -c "import cdp; print(cdp.__version__)"
```
Expected: prints `0.1.0`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: repo scaffolding with package, tests, constants"
```

---

## Task 2: Path decoding (`projects.py::decode_encoded_path`)

Claude Code encodes `/Users/bjhl/Documents/gaokao` → `-Users-bjhl-Documents-gaokao` (every `/` becomes `-`). Problem: real paths may contain `-` (like `galaxy-client` → `-Users-bjhl-galaxy-client` which naively decodes to `/Users/bjhl/galaxy/client`). Fix: walk from root, at each depth try progressively longer segments and check `isdir`.

**Files:**
- Create: `src/cdp/projects.py`
- Create: `tests/test_projects.py`

- [ ] **Step 1: Write failing tests**

`tests/test_projects.py`:
```python
from pathlib import Path

from cdp.projects import decode_encoded_path


def test_simple_decode(tmp_path):
    # Create /tmp_path/Users/bjhl/Documents/gaokao
    target = tmp_path / "Users/bjhl/Documents/gaokao"
    target.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-Users-bjhl-Documents-gaokao"
    result = decode_encoded_path(encoded)
    assert result == str(target)


def test_decode_with_hyphen_in_dir_name(tmp_path):
    # Create /tmp_path/foo/galaxy-client
    target = tmp_path / "foo/galaxy-client"
    target.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-foo-galaxy-client"
    result = decode_encoded_path(encoded)
    assert result == str(target)


def test_decode_nonexistent_path_returns_naive_join(tmp_path):
    """If no segmentation works, return naive join (will be filtered elsewhere)."""
    encoded = "-nonexistent-xyz-abc"
    result = decode_encoded_path(encoded)
    assert result == "/nonexistent/xyz/abc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_projects.py -v`
Expected: FAIL with `ImportError: cannot import name 'decode_encoded_path'`.

- [ ] **Step 3: Implement `decode_encoded_path`**

Add to `src/cdp/projects.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_projects.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/projects.py tests/test_projects.py
git commit -m "feat(projects): decode encoded claude project paths with hyphen fallback"
```

---

## Task 3: Project scanner (`projects.py::scan_recent_projects`)

Walk `~/.claude/projects/*`, decode each, check the dir still exists, compute max mtime across all `.jsonl` files inside, return a list sorted mtime-descending.

**Files:**
- Modify: `src/cdp/projects.py`
- Modify: `tests/test_projects.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_projects.py`:
```python
from cdp.projects import Project, scan_recent_projects


def _make_claude_project(claude_projects_dir: Path, encoded: str, jsonl_mtimes: list[float]):
    proj_dir = claude_projects_dir / encoded
    proj_dir.mkdir(parents=True)
    for i, m in enumerate(jsonl_mtimes):
        f = proj_dir / f"session-{i}.jsonl"
        f.write_text("{}")
        os.utime(f, (m, m))


def test_scan_returns_empty_when_dir_missing(tmp_path):
    result = scan_recent_projects(tmp_path / "does-not-exist")
    assert result == []


def test_scan_decodes_and_filters_nonexistent_dirs(tmp_path):
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    # One real project on disk
    real = tmp_path / "Users/bjhl/gaokao"
    real.mkdir(parents=True)
    _make_claude_project(
        claude_projects,
        str(tmp_path).replace("/", "-") + "-Users-bjhl-gaokao",
        [1700000000.0],
    )
    # One "ghost" project — claude has a record but actual dir was deleted
    _make_claude_project(claude_projects, "-removed-project-path", [1700000500.0])

    result = scan_recent_projects(claude_projects)
    assert len(result) == 1
    assert result[0].path == str(real)


def test_scan_sorts_by_max_mtime_descending(tmp_path):
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)

    for name, mtimes in [
        ("a", [1700000000.0, 1700000001.0]),
        ("b", [1700000100.0]),
        ("c", [1700000050.0, 1699999000.0]),
    ]:
        (tmp_path / name).mkdir()
        _make_claude_project(claude_projects, str(tmp_path).replace("/", "-") + "-" + name, mtimes)

    result = scan_recent_projects(claude_projects)
    names_in_order = [Path(p.path).name for p in result]
    # b (mtime 1700000100) > c (1700000050) > a (1700000001)
    assert names_in_order == ["b", "c", "a"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_projects.py -v`
Expected: 3 tests fail with ImportError for `Project` / `scan_recent_projects`.

- [ ] **Step 3: Implement the scanner**

Append to `src/cdp/projects.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_projects.py -v`
Expected: 6 passed total.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/projects.py tests/test_projects.py
git commit -m "feat(projects): scan ~/.claude/projects/ sorted by max jsonl mtime"
```

---

## Task 4: Config load/save (`config.py`)

TOML round-trip with `tomlkit` to preserve user comments.

**Files:**
- Create: `src/cdp/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from cdp.config import Config, ConfigEntry


def test_load_missing_file_returns_empty(tmp_path):
    cfg = Config.load(tmp_path / "nope.toml")
    assert cfg.entries == []


def test_load_valid_file(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('''
# top-level comment

[[project]]
path = "/a"
pinned = true

[[project]]
path = "/b"
alias = "bee"

[[project]]
path = "/c"
hidden = true
''')
    cfg = Config.load(f)
    assert cfg.entries == [
        ConfigEntry(path="/a", pinned=True),
        ConfigEntry(path="/b", alias="bee"),
        ConfigEntry(path="/c", hidden=True),
    ]


def test_save_roundtrip_preserves_comments(tmp_path):
    f = tmp_path / "c.toml"
    original = '''# pin order comment
# another line

[[project]]
path = "/a"
pinned = true
'''
    f.write_text(original)
    cfg = Config.load(f)
    cfg.save()
    # Header comments and blank lines preserved
    assert "# pin order comment" in f.read_text()
    assert "# another line" in f.read_text()


def test_load_invalid_toml_raises(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('not a valid toml = = =')
    with pytest.raises(Exception) as exc_info:
        Config.load(f)
    # Any exception is fine; message should mention the file
    assert str(f) in str(exc_info.value) or "toml" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 4 tests fail with ImportError.

- [ ] **Step 3: Implement Config load/save**

`src/cdp/config.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/config.py tests/test_config.py
git commit -m "feat(config): load/save ~/.config/cdp/config.toml with tomlkit"
```

---

## Task 5: Config mutations (`Config.pin / unpin / hide / unhide / set_alias / clear_alias`)

**Files:**
- Modify: `src/cdp/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config.py`:
```python
def test_pin_adds_new_entry(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin("/a")
    assert cfg.entries == [ConfigEntry(path="/a", pinned=True)]


def test_pin_sets_flag_on_existing_entry(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[[project]]\npath = "/a"\nalias = "ay"\n')
    cfg = Config.load(f)
    cfg.pin("/a")
    assert cfg.entries == [ConfigEntry(path="/a", alias="ay", pinned=True)]


def test_unpin_clears_flag(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin("/a")
    cfg.unpin("/a")
    # Entry with no flags left is removed entirely
    assert cfg.entries == []


def test_unpin_keeps_entry_if_other_flags_present(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.set_alias("/a", "ay")
    cfg.pin("/a")
    cfg.unpin("/a")
    assert cfg.entries == [ConfigEntry(path="/a", alias="ay")]


def test_hide_and_unhide(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.hide("/a")
    assert cfg.entries == [ConfigEntry(path="/a", hidden=True)]
    cfg.unhide("/a")
    assert cfg.entries == []


def test_set_and_clear_alias(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.set_alias("/a", "ay")
    assert cfg.entries == [ConfigEntry(path="/a", alias="ay")]
    cfg.clear_alias("/a")
    assert cfg.entries == []


def test_pin_preserves_order_of_existing_pins(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin("/a")
    cfg.pin("/b")
    cfg.pin("/c")
    assert [e.path for e in cfg.entries if e.pinned] == ["/a", "/b", "/c"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 7 new tests fail with AttributeError (no pin/unpin/… methods yet).

- [ ] **Step 3: Implement mutations**

Append to `src/cdp/config.py` inside class `Config`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: 11 passed total.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/config.py tests/test_config.py
git commit -m "feat(config): pin/unpin/hide/unhide/alias mutation methods"
```

---

## Task 6: Merge projects + config (`combine.py`)

Produce the final list shown to the user: pinned entries first (in config order), then remaining auto-discovered sorted by mtime desc, with hidden filtered out and aliases applied. Also include config-only projects (user pinned/aliased a path that hasn't been opened with claude yet) when their dir exists.

**Files:**
- Create: `src/cdp/combine.py`
- Create: `tests/test_combine.py`

- [ ] **Step 1: Write failing tests**

`tests/test_combine.py`:
```python
import os
from pathlib import Path

from cdp.combine import Project, get_display_projects
from cdp.config import Config
from cdp.projects import DiscoveredProject


def _writable_dir(tmp_path: Path, name: str) -> str:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def test_empty_inputs(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    assert get_display_projects([], cfg) == []


def test_mtime_order_without_config(tmp_path):
    a = _writable_dir(tmp_path, "a")
    b = _writable_dir(tmp_path, "b")
    cfg = Config.load(tmp_path / "c.toml")
    discovered = [
        DiscoveredProject(path=a, mtime=100.0),
        DiscoveredProject(path=b, mtime=200.0),
    ]
    result = get_display_projects(discovered, cfg)
    assert [p.path for p in result] == [b, a]
    # display_name defaults to basename
    assert result[0].display_name == "b"


def test_pinned_go_first_in_config_order(tmp_path):
    a = _writable_dir(tmp_path, "a")
    b = _writable_dir(tmp_path, "b")
    c = _writable_dir(tmp_path, "c")

    cfg_path = tmp_path / "c.toml"
    cfg = Config.load(cfg_path)
    cfg.pin(c)  # pin c first
    cfg.pin(a)  # pin a second

    discovered = [
        DiscoveredProject(path=a, mtime=10.0),
        DiscoveredProject(path=b, mtime=999.0),
        DiscoveredProject(path=c, mtime=5.0),
    ]
    result = get_display_projects(discovered, cfg)
    assert [p.path for p in result] == [c, a, b]
    assert result[0].pinned is True
    assert result[2].pinned is False


def test_hidden_filtered(tmp_path):
    a = _writable_dir(tmp_path, "a")
    b = _writable_dir(tmp_path, "b")
    cfg_path = tmp_path / "c.toml"
    cfg = Config.load(cfg_path)
    cfg.hide(b)
    discovered = [
        DiscoveredProject(path=a, mtime=1.0),
        DiscoveredProject(path=b, mtime=2.0),
    ]
    result = get_display_projects(discovered, cfg)
    assert [p.path for p in result] == [a]


def test_alias_applied_to_display_name(tmp_path):
    a = _writable_dir(tmp_path, "a")
    cfg = Config.load(tmp_path / "c.toml")
    cfg.set_alias(a, "高考")
    discovered = [DiscoveredProject(path=a, mtime=1.0)]
    result = get_display_projects(discovered, cfg)
    assert result[0].display_name == "高考"
    assert result[0].alias == "高考"


def test_config_only_pinned_project_appears_if_dir_exists(tmp_path):
    a = _writable_dir(tmp_path, "a")
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin(a)
    # No discovered entry
    result = get_display_projects([], cfg)
    assert [p.path for p in result] == [a]


def test_config_only_project_skipped_if_dir_missing(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin(str(tmp_path / "does-not-exist"))
    result = get_display_projects([], cfg)
    assert result == []


def test_pinned_project_whose_dir_got_deleted_is_skipped(tmp_path):
    a = _writable_dir(tmp_path, "a")
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin(a)
    cfg.pin(str(tmp_path / "gone"))  # nonexistent
    discovered = [DiscoveredProject(path=a, mtime=1.0)]
    result = get_display_projects(discovered, cfg)
    assert [p.path for p in result] == [a]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_combine.py -v`
Expected: 8 tests fail with ImportError.

- [ ] **Step 3: Implement `combine.py`**

`src/cdp/combine.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_combine.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/combine.py tests/test_combine.py
git commit -m "feat(combine): merge discovered projects with config into display list"
```

---

## Task 7: CLI skeleton and `list` subcommand

**Files:**
- Create: `src/cdp/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

`tests/test_cli.py`:
```python
import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], env_home: Path, **kwargs) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(env_home)
    env["XDG_CONFIG_HOME"] = str(env_home / ".config")
    return subprocess.run(
        [sys.executable, "-m", "cdp", *args],
        capture_output=True,
        text=True,
        env=env,
        **kwargs,
    )


def test_help(tmp_path):
    r = _run(["--help"], tmp_path)
    assert r.returncode == 0
    assert "pin" in r.stdout
    assert "alias" in r.stdout


def test_list_empty(tmp_path):
    (tmp_path / ".claude" / "projects").mkdir(parents=True)
    r = _run(["list"], tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_list_with_one_project(tmp_path):
    proj = tmp_path / "Users/bjhl/gaokao"
    proj.mkdir(parents=True)
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-Users-bjhl-gaokao"
    (claude_projects / encoded).mkdir()
    (claude_projects / encoded / "s.jsonl").write_text("{}")

    r = _run(["list"], tmp_path)
    assert r.returncode == 0
    # Format: <path>\t<display_name>
    assert f"{proj}\tgaokao" in r.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 3 tests fail (module `cli` has no `main`, or argparse not set up).

- [ ] **Step 3: Implement minimal CLI with `list` subcommand**

`src/cdp/cli.py`:
```python
"""argparse-based CLI for cdp."""
from __future__ import annotations

import argparse
import sys

from cdp import combine, config as cfg_mod, constants, projects


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=constants.COMMAND_NAME,
        description="Terminal picker for recent Claude Code projects.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="print projects (path<TAB>display_name)")

    for name in ("pin", "unpin", "hide", "unhide"):
        sp = sub.add_parser(name, help=f"{name} a path (defaults to $PWD)")
        sp.add_argument("path", nargs="?", default=None)

    # `alias` takes 1 or 2 positional args:
    #   cdp alias <name>             → path=$PWD, name=<name>
    #   cdp alias <path> <name>      → explicit path and name
    # We use nargs="+" and post-process to avoid argparse's ambiguous
    # behavior with "optional followed by required" positionals.
    sp_alias = sub.add_parser("alias", help="set alias for a path")
    sp_alias.add_argument("args", nargs="+", help="[path] <name>")

    sp_unalias = sub.add_parser("unalias", help="remove alias for a path")
    sp_unalias.add_argument("path", nargs="?", default=None)

    # Direct path mode is captured as a positional arg outside of subparsers.
    # argparse doesn't natively mix subparsers and a leading positional, so we
    # fall back to argv inspection for that case.
    if argv is None:
        argv = sys.argv[1:]

    known_subcommands = {"list", "pin", "unpin", "hide", "unhide", "alias", "unalias"}
    if argv and argv[0] not in known_subcommands and not argv[0].startswith("-"):
        return _cmd_direct_path(argv[0])

    args = parser.parse_args(argv)
    if args.cmd == "list":
        return _cmd_list()
    if args.cmd is None:
        return _cmd_picker()
    if args.cmd in ("pin", "unpin", "hide", "unhide"):
        return _cmd_config_toggle(args.cmd, args.path)
    if args.cmd == "alias":
        return _cmd_alias(args.args)
    if args.cmd == "unalias":
        return _cmd_unalias(args.path)
    return 0


def _cmd_list() -> int:
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    discovered = projects.scan_recent_projects(constants.CLAUDE_PROJECTS_DIR)
    for p in combine.get_display_projects(discovered, cfg):
        print(f"{p.path}\t{p.display_name}")
    return 0


def _cmd_picker() -> int:
    # Implemented in a later task
    print("picker: not yet implemented", file=sys.stderr)
    return 2


def _cmd_direct_path(raw: str) -> int:
    # Implemented in a later task
    print(f"direct path mode: not yet implemented ({raw!r})", file=sys.stderr)
    return 2


def _cmd_config_toggle(cmd: str, path: str | None) -> int:
    # Implemented in a later task
    print(f"{cmd}: not yet implemented", file=sys.stderr)
    return 2


def _cmd_alias(args_list: list[str]) -> int:
    print("alias: not yet implemented", file=sys.stderr)
    return 2


def _cmd_unalias(path: str | None) -> int:
    print("unalias: not yet implemented", file=sys.stderr)
    return 2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/cli.py tests/test_cli.py
git commit -m "feat(cli): argparse skeleton with 'list' subcommand"
```

---

## Task 8: `pin` / `unpin` / `hide` / `unhide` subcommands

These four share identical shape so we implement them together.

**Files:**
- Modify: `src/cdp/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:
```python
def test_pin_uses_pwd_when_no_arg(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    # Run with cwd=proj so $PWD default resolves there
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    r = subprocess.run(
        [sys.executable, "-m", "cdp", "pin"],
        capture_output=True, text=True, env=env, cwd=str(proj),
    )
    assert r.returncode == 0
    toml_text = (tmp_path / ".config/cdp/config.toml").read_text()
    assert str(proj) in toml_text
    assert "pinned" in toml_text


def test_pin_explicit_path(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    r = _run(["pin", str(proj)], tmp_path)
    assert r.returncode == 0
    toml_text = (tmp_path / ".config/cdp/config.toml").read_text()
    assert str(proj) in toml_text


def test_pin_nonexistent_path_warns_but_succeeds(tmp_path):
    target = str(tmp_path / "does-not-exist")
    r = _run(["pin", target], tmp_path)
    assert r.returncode == 0
    assert "does not exist" in r.stderr
    # still recorded
    assert target in (tmp_path / ".config/cdp/config.toml").read_text()


def test_unpin_removes(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["pin", str(proj)], tmp_path)
    _run(["unpin", str(proj)], tmp_path)
    toml_text = (tmp_path / ".config/cdp/config.toml").read_text()
    assert "pinned" not in toml_text


def test_hide_and_unhide(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["hide", str(proj)], tmp_path)
    assert "hidden" in (tmp_path / ".config/cdp/config.toml").read_text()
    _run(["unhide", str(proj)], tmp_path)
    assert "hidden" not in (tmp_path / ".config/cdp/config.toml").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 5 new tests fail with "not yet implemented".

- [ ] **Step 3: Replace `_cmd_config_toggle` stub**

Replace the stub in `src/cdp/cli.py`:
```python
def _cmd_config_toggle(cmd: str, path: str | None) -> int:
    import os as _os
    target = _os.path.abspath(_os.path.expanduser(path)) if path else _os.getcwd()
    if not _os.path.isdir(target):
        print(f"warning: {target} does not exist, {cmd}ning anyway", file=sys.stderr)
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    getattr(cfg, cmd)(target)
    cfg.save()
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 8 passed total.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/cli.py tests/test_cli.py
git commit -m "feat(cli): pin/unpin/hide/unhide subcommands"
```

---

## Task 9: `alias` / `unalias` subcommands

**Files:**
- Modify: `src/cdp/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:
```python
def test_alias_set_and_show_in_list(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-p"
    (claude_projects / encoded).mkdir()
    (claude_projects / encoded / "s.jsonl").write_text("{}")

    r = _run(["alias", str(proj), "foobar"], tmp_path)
    assert r.returncode == 0
    r2 = _run(["list"], tmp_path)
    assert f"{proj}\tfoobar" in r2.stdout


def test_alias_pwd_default(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    r = subprocess.run(
        [sys.executable, "-m", "cdp", "alias", "myname"],
        capture_output=True, text=True, env=env, cwd=str(proj),
    )
    assert r.returncode == 0
    assert 'alias = "myname"' in (tmp_path / ".config/cdp/config.toml").read_text()


def test_unalias_removes(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["alias", str(proj), "x"], tmp_path)
    _run(["unalias", str(proj)], tmp_path)
    assert "alias" not in (tmp_path / ".config/cdp/config.toml").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 3 new tests fail.

- [ ] **Step 3: Replace `_cmd_alias` and `_cmd_unalias` stubs**

Replace stubs in `src/cdp/cli.py`:
```python
def _cmd_alias(args_list: list[str]) -> int:
    """Parse `cdp alias [path] <name>`. 1 arg = path defaults to $PWD."""
    import os as _os
    if len(args_list) == 1:
        path, name = None, args_list[0]
    elif len(args_list) == 2:
        path, name = args_list[0], args_list[1]
    else:
        print(f"usage: {constants.COMMAND_NAME} alias [path] <name>", file=sys.stderr)
        return 2
    target = _os.path.abspath(_os.path.expanduser(path)) if path else _os.getcwd()
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    cfg.set_alias(target, name)
    cfg.save()
    return 0


def _cmd_unalias(path: str | None) -> int:
    import os as _os
    target = _os.path.abspath(_os.path.expanduser(path)) if path else _os.getcwd()
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    cfg.clear_alias(target)
    cfg.save()
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 11 passed total.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/cli.py tests/test_cli.py
git commit -m "feat(cli): alias/unalias subcommands"
```

---

## Task 10: Direct path mode `cdp <path>`

`cdp /Users/bjhl/x` must print the absolute, `~`-expanded path to stdout so the shell wrapper can `cd` to it. Non-directory input is an error.

**Files:**
- Modify: `src/cdp/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:
```python
def test_direct_path_prints_absolute(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    r = _run([str(proj)], tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == str(proj)


def test_direct_path_expands_tilde(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    # HOME is tmp_path, so ~/p → tmp_path/p
    r = _run(["~/p"], tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == str(proj)


def test_direct_path_rejects_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    r = _run([str(f)], tmp_path)
    assert r.returncode != 0
    assert "not a directory" in r.stderr


def test_direct_path_rejects_missing(tmp_path):
    r = _run([str(tmp_path / "nope")], tmp_path)
    assert r.returncode != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 4 new tests fail.

- [ ] **Step 3: Implement `_cmd_direct_path`**

Replace stub in `src/cdp/cli.py`:
```python
def _cmd_direct_path(raw: str) -> int:
    import os as _os
    target = _os.path.abspath(_os.path.expanduser(raw))
    if not _os.path.isdir(target):
        print(f"error: {target} is not a directory", file=sys.stderr)
        return 1
    print(target)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 15 passed total.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/cli.py tests/test_cli.py
git commit -m "feat(cli): direct path mode prints absolute path to stdout"
```

---

## Task 11: fzf rendering (`picker.py::render_lines`)

Render the picker's input lines. Each line: `<prefix><name_col_padded>  <path>`. fzf reads them via stdin.

**Files:**
- Create: `src/cdp/picker.py`
- Create: `tests/test_picker.py`

- [ ] **Step 1: Write failing tests**

`tests/test_picker.py`:
```python
from cdp.combine import Project
from cdp.picker import render_lines


def _p(path, name, pinned=False):
    return Project(path=path, mtime=0.0, display_name=name, pinned=pinned, alias=None)


def test_render_empty():
    assert render_lines([]) == []


def test_render_alignment():
    lines = render_lines([
        _p("/a/gaokao", "gaokao", pinned=True),
        _p("/b/wxzs-website", "wxzs-website", pinned=False),
    ])
    # Pinned row prefixed with pin icon, non-pinned with 3 spaces
    assert lines[0].startswith("📌 ")
    assert lines[1].startswith("   ")
    # Paths present at end
    assert lines[0].endswith("/a/gaokao")
    assert lines[1].endswith("/b/wxzs-website")


def test_render_truncates_long_names():
    lines = render_lines([_p("/p", "a" * 30, pinned=False)])
    # Name column width is 18; should be truncated with ellipsis
    # (exact format can vary; assert that full 30-char name doesn't appear verbatim)
    assert ("a" * 30) not in lines[0]
    assert "/p" in lines[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_picker.py -v`
Expected: 3 tests fail with ImportError.

- [ ] **Step 3: Implement `render_lines`**

`src/cdp/picker.py`:
```python
"""fzf rendering and invocation."""
from __future__ import annotations

from cdp import constants
from cdp.combine import Project


def render_lines(projects: list[Project]) -> list[str]:
    """Format projects for fzf input.

    Line layout: <prefix><name_col_padded>  <path>
    - prefix: pin icon or 3 spaces
    - name_col_padded: display_name, truncated to NAME_COL_WIDTH with ellipsis, left-justified
    """
    out: list[str] = []
    for p in projects:
        prefix = constants.PIN_ICON if p.pinned else constants.NO_PIN_PREFIX
        name = _truncate(p.display_name, constants.NAME_COL_WIDTH)
        padded = name.ljust(constants.NAME_COL_WIDTH)
        out.append(f"{prefix}{padded}  {p.path}")
    return out


def _truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    return s[: width - 1] + "…"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_picker.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cdp/picker.py tests/test_picker.py
git commit -m "feat(picker): render_lines for fzf input with pin icon and padding"
```

---

## Task 12: fzf invocation + parse selection

Call `fzf` as subprocess, pipe rendered lines to stdin, read selected line from stdout, extract path from that line. Handle Esc (fzf exit 130) cleanly.

**Files:**
- Modify: `src/cdp/picker.py`
- Modify: `src/cdp/cli.py` (wire `_cmd_picker` to `picker.run`)
- Modify: `tests/test_picker.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_picker.py`:
```python
from unittest.mock import patch

from cdp.picker import parse_selection, run


def test_parse_selection_extracts_path():
    line = "📌 gaokao              /Users/bjhl/gaokao"
    assert parse_selection(line) == "/Users/bjhl/gaokao"


def test_parse_selection_handles_padding_and_ellipsis():
    line = "   web-capability…   /Users/bjhl/Documents/手写系列/web-capability-compiler"
    assert parse_selection(line) == "/Users/bjhl/Documents/手写系列/web-capability-compiler"


def test_parse_selection_empty_returns_none():
    assert parse_selection("") is None
    assert parse_selection("\n") is None


def test_run_fzf_missing_returns_error(monkeypatch):
    """If fzf isn't on PATH, run() should return None and print a helpful error."""
    import cdp.picker as mod
    monkeypatch.setattr(mod, "_fzf_available", lambda: False)
    result = run([_p_for_run()])
    assert result is None


def _p_for_run():
    from cdp.combine import Project
    return Project(path="/a", mtime=0.0, display_name="a", pinned=False, alias=None)


def test_run_returns_selected_path(monkeypatch):
    """When fzf returns 0 with a line, run() extracts and returns its path."""
    import cdp.picker as mod
    monkeypatch.setattr(mod, "_fzf_available", lambda: True)

    class FakeCompleted:
        returncode = 0
        stdout = "   a                  /a\n"

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: FakeCompleted())
    result = run([_p_for_run()])
    assert result == "/a"


def test_run_cancelled_returns_none(monkeypatch):
    """Esc in fzf yields exit 130; run() returns None."""
    import cdp.picker as mod
    monkeypatch.setattr(mod, "_fzf_available", lambda: True)

    class FakeCompleted:
        returncode = 130
        stdout = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: FakeCompleted())
    assert run([_p_for_run()]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_picker.py -v`
Expected: 6 new tests fail (ImportError for `parse_selection` and `run`).

- [ ] **Step 3: Implement `run` and `parse_selection`**

Append to `src/cdp/picker.py`:
```python
import shutil
import subprocess
import sys

from cdp import constants


def _fzf_available() -> bool:
    return shutil.which("fzf") is not None


def parse_selection(line: str) -> str | None:
    """Extract the path from a picker line. Path follows at least 2 spaces."""
    line = line.rstrip("\n")
    if not line.strip():
        return None
    # Path is everything after the last run of 2+ spaces
    # Simpler approach: the line format is "<prefix><name_padded>  <path>",
    # and path itself does not contain a double-space. So split on the LAST
    # occurrence of "  " (two spaces).
    idx = line.rfind("  ")
    if idx == -1:
        return line.strip() or None
    return line[idx + 2:].strip() or None


def run(projects: list) -> str | None:
    """Launch fzf for the user to pick a project. Return selected path or None.

    None means: fzf not installed, user cancelled, or empty selection.
    """
    if not _fzf_available():
        print(
            "error: fzf not found. Install via: brew install fzf",
            file=sys.stderr,
        )
        return None

    lines = render_lines(projects)
    stdin = "\n".join(lines)
    cmd = [
        "fzf",
        "--reverse",
        "--height=60%",
        "--prompt=project> ",
        "--no-sort",  # we already sorted
    ]
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return parse_selection(r.stdout)
```

- [ ] **Step 4: Wire `_cmd_picker` in cli.py**

Replace the `_cmd_picker` stub in `src/cdp/cli.py`:
```python
def _cmd_picker() -> int:
    from cdp import picker
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    discovered = projects.scan_recent_projects(constants.CLAUDE_PROJECTS_DIR)
    display = combine.get_display_projects(discovered, cfg)
    if not display:
        print(
            f"No recent projects. Use `{constants.COMMAND_NAME} <path>` to open one.",
            file=sys.stderr,
        )
        return 1
    selected = picker.run(display)
    if selected is None:
        return 130  # cancelled or error
    print(selected)
    return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest -v`
Expected: all tests pass. Approximate counts by file after this task: test_projects=6, test_config=11, test_combine=8, test_cli=15, test_picker=9 → ~49 total.

- [ ] **Step 6: Commit**

```bash
git add src/cdp/picker.py src/cdp/cli.py tests/test_picker.py
git commit -m "feat(picker): run fzf, parse selection, wire _cmd_picker"
```

---

## Task 13: fzf hotkeys (ctrl-p pin, ctrl-h hide, ctrl-o Finder)

fzf `--bind "ctrl-p:reload(<cmd>)+refresh-preview"` invokes a command when the key is pressed. We need an **internal command** that takes the currently-highlighted line's path, toggles the state in config, then re-renders the list.

Expose `cdp _toggle-pin <path>`, `cdp _toggle-hide <path>`, `cdp _render` (reprints the list for fzf to consume). Prefix with underscore so they don't show in `--help`.

**Files:**
- Modify: `src/cdp/cli.py`
- Modify: `src/cdp/picker.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:
```python
def test_internal_render_outputs_picker_lines(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-p"
    (claude_projects / encoded).mkdir()
    (claude_projects / encoded / "s.jsonl").write_text("{}")

    r = _run(["_render"], tmp_path)
    assert r.returncode == 0
    # output should contain a space-separated line with the path
    assert str(proj) in r.stdout


def test_internal_toggle_pin_flips_state(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    # Starts unpinned
    r1 = _run(["_toggle-pin", str(proj)], tmp_path)
    assert r1.returncode == 0
    assert "pinned" in (tmp_path / ".config/cdp/config.toml").read_text()
    # Second call unpins
    r2 = _run(["_toggle-pin", str(proj)], tmp_path)
    assert r2.returncode == 0
    assert "pinned" not in (tmp_path / ".config/cdp/config.toml").read_text()


def test_internal_toggle_hide_flips_state(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["_toggle-hide", str(proj)], tmp_path)
    assert "hidden" in (tmp_path / ".config/cdp/config.toml").read_text()
    _run(["_toggle-hide", str(proj)], tmp_path)
    assert "hidden" not in (tmp_path / ".config/cdp/config.toml").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 3 new tests fail.

- [ ] **Step 3: Add internal subcommands in cli.py**

In `src/cdp/cli.py`, extend the parser (inside `main`):
```python
    # Internal commands used by fzf --bind; underscore-prefixed to hide from help.
    # All of them receive the fzf-format line as argv; _render takes no arg.
    sub.add_parser("_render", help=argparse.SUPPRESS)

    sp_tp = sub.add_parser("_toggle-pin", help=argparse.SUPPRESS)
    sp_tp.add_argument("line")

    sp_th = sub.add_parser("_toggle-hide", help=argparse.SUPPRESS)
    sp_th.add_argument("line")

    sp_op = sub.add_parser("_open", help=argparse.SUPPRESS)
    sp_op.add_argument("line")
```

Extend the `known_subcommands` set to include `_render`, `_toggle-pin`, `_toggle-hide`, `_open`.

Extend the dispatch block:
```python
    if args.cmd == "_render":
        return _cmd_render()
    if args.cmd == "_toggle-pin":
        return _cmd_toggle("pin", args.line)
    if args.cmd == "_toggle-hide":
        return _cmd_toggle("hide", args.line)
    if args.cmd == "_open":
        return _cmd_open(args.line)
```

Add the handlers:
```python
def _cmd_render() -> int:
    from cdp import picker
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    discovered = projects.scan_recent_projects(constants.CLAUDE_PROJECTS_DIR)
    display = combine.get_display_projects(discovered, cfg)
    for line in picker.render_lines(display):
        print(line)
    return 0


def _cmd_toggle(kind: str, line: str) -> int:
    """kind is 'pin' or 'hide'. line may be a full fzf line or just a path."""
    from cdp import picker
    parsed = picker.parse_selection(line)
    path = parsed if parsed else line.strip()
    if not path:
        return 0
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    e = cfg._find(path)  # noqa: SLF001
    currently_on = (kind == "pin" and e is not None and e.pinned) or \
                   (kind == "hide" and e is not None and e.hidden)
    if currently_on:
        getattr(cfg, f"un{kind}")(path)
    else:
        getattr(cfg, kind)(path)
    cfg.save()
    return 0


def _cmd_open(line: str) -> int:
    """Open the highlighted path in Finder (via macOS `open`)."""
    import subprocess as _sp
    from cdp import picker
    parsed = picker.parse_selection(line)
    path = parsed if parsed else line.strip()
    if path:
        _sp.run(["open", path], check=False)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 18 passed total.

- [ ] **Step 5: Wire fzf `--bind` in `picker.run`**

Replace the `cmd = [...]` list in `src/cdp/picker.py::run`. All hotkeys route
through internal subcommands (not shell `awk`/`cut`) so paths with spaces work.

```python
    import os as _os
    python_exe = _os.environ.get("CDP_PYTHON") or sys.executable
    prog = f"{python_exe} -m cdp"
    cmd = [
        "fzf",
        "--reverse",
        "--height=60%",
        "--prompt=project> ",
        "--no-sort",
        f"--bind=ctrl-p:reload({prog} _toggle-pin {{}} >/dev/null 2>&1 && {prog} _render)",
        f"--bind=ctrl-h:reload({prog} _toggle-hide {{}} >/dev/null 2>&1 && {prog} _render)",
        f"--bind=ctrl-o:execute-silent({prog} _open {{}})",
    ]
```

- [ ] **Step 6: Commit**

```bash
git add src/cdp/cli.py src/cdp/picker.py tests/test_cli.py
git commit -m "feat(picker): ctrl-p/ctrl-h/ctrl-o hotkeys via internal subcommands"
```

---

## Task 14: zsh wrapper `shell/cdp.zsh`

**Files:**
- Create: `shell/cdp.zsh`

- [ ] **Step 1: Create the wrapper file**

`shell/cdp.zsh`:
```zsh
# cdp: terminal picker for recent Claude Code projects
# This file is sourced from ~/.zshrc via install.sh.
# Requires: CDP_HOME (repo path), CDP_PYTHON (venv python).

cdp() {
  case "$1" in
    pin|unpin|hide|unhide|alias|unalias|list|-h|--help)
      # Pass through: python writes to tty, wrapper does not capture
      command "$CDP_PYTHON" -m cdp "$@"
      return $?
      ;;
    *)
      # Picker mode or direct path mode: capture stdout as target path
      local selected
      selected="$(command "$CDP_PYTHON" -m cdp "$@")" || return $?
      [[ -z "$selected" ]] && return 0
      cd "$selected" && claude
      ;;
  esac
}
```

- [ ] **Step 2: Lint-check the shell file**

Run:
```bash
zsh -n shell/cdp.zsh
```
Expected: no output (syntax OK).

- [ ] **Step 3: Commit**

```bash
git add shell/cdp.zsh
git commit -m "feat(shell): zsh wrapper dispatches by subcommand, captures path mode"
```

---

## Task 15: `install.sh`

**Files:**
- Create: `install.sh`

- [ ] **Step 1: Create the installer**

`install.sh`:
```bash
#!/usr/bin/env bash
# Install cdp: create venv, pip install, inject into ~/.zshrc.
# Idempotent: re-running is safe.

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [--name NAME]
  --name NAME   Override the command name (default: cdp)
EOF
}

COMMAND_NAME="cdp"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) COMMAND_NAME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"

# --- Check prerequisites ---------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found" >&2
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3,10) else 0)')
if [[ "$PY_OK" != "1" ]]; then
  echo "error: python3 >= 3.10 required (found $PY_VER)" >&2
  exit 1
fi

command -v fzf >/dev/null 2>&1 || \
  echo "warning: fzf not found. Install via: brew install fzf" >&2
command -v claude >/dev/null 2>&1 || \
  echo "warning: claude CLI not found. See https://docs.claude.com/claude-code" >&2

# --- Venv + pip install ----------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$REPO_DIR"

# --- If --name set, patch constants.py and shell/cdp.zsh ------------------
if [[ "$COMMAND_NAME" != "cdp" ]]; then
  # Patch constants.py
  CONST="$REPO_DIR/src/cdp/constants.py"
  python3 -c "
import re, pathlib
p = pathlib.Path('$CONST')
t = p.read_text()
t = re.sub(r'^COMMAND_NAME = .*\$', f'COMMAND_NAME = \"$COMMAND_NAME\"', t, flags=re.M)
p.write_text(t)
"
  # Patch shell function name
  WRAPPER="$REPO_DIR/shell/cdp.zsh"
  sed -i.bak "s/^cdp()/$COMMAND_NAME()/" "$WRAPPER"
  rm -f "$WRAPPER.bak"
fi

# --- Inject into ~/.zshrc (idempotent) -------------------------------------
ZSHRC="$HOME/.zshrc"
MARK_START="# >>> $COMMAND_NAME >>>"
MARK_END="# <<< $COMMAND_NAME <<<"

# Remove any existing block (handles re-runs)
if grep -q "$MARK_START" "$ZSHRC" 2>/dev/null; then
  # Use a temp file + awk; portable across macOS and Linux sed
  awk -v start="$MARK_START" -v end="$MARK_END" '
    $0 == start { skip=1; next }
    $0 == end   { skip=0; next }
    !skip
  ' "$ZSHRC" > "$ZSHRC.tmp"
  mv "$ZSHRC.tmp" "$ZSHRC"
fi

cat >> "$ZSHRC" <<EOF

$MARK_START
export CDP_HOME="$REPO_DIR"
export CDP_PYTHON="$VENV_DIR/bin/python3"
source "\$CDP_HOME/shell/cdp.zsh"
$MARK_END
EOF

echo ""
echo "Installed. Run:  source ~/.zshrc"
echo "Then try:        $COMMAND_NAME --help"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x install.sh
```

- [ ] **Step 3: Syntax check**

Run: `bash -n install.sh`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat(install): venv bootstrap and idempotent ~/.zshrc injection"
```

---

## Task 16: Manual integration test + README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Manually run the full install and verify each user flow**

Run these commands and verify each expectation. This is not automated — record any failures and return to fix before declaring the task done.

```bash
cd /Users/bjhl/Documents/手写系列/cdp
./install.sh
source ~/.zshrc
```

Manual test checklist:
- [ ] `cdp --help` prints subcommand list
- [ ] `cdp list` prints existing projects (should include the 7 from ~/.claude/projects/)
- [ ] `cdp` opens fzf, shows those projects
- [ ] Type a few chars → filter works
- [ ] Enter on a selection → shell cd's to that dir and `claude` starts
- [ ] Exit claude → shell remains in the project dir
- [ ] Open a new terminal, run `cdp`, press Esc → pwd unchanged
- [ ] `cdp pin` inside a project dir → next `cdp` shows it pinned at top
- [ ] In fzf, highlight a project, press `ctrl-p` → pin icon appears
- [ ] Press `ctrl-p` again on same → pin icon disappears
- [ ] `ctrl-h` hides a project; it disappears from list
- [ ] `cdp unhide /path` restores it
- [ ] `cdp alias /path 别名` → next `cdp list` shows `别名` instead of basename
- [ ] `cdp /tmp` → cd's to /tmp, starts claude
- [ ] `cdp ~/Documents` → cd's to Documents, starts claude
- [ ] `cdp list | grep gaokao` works (pipe not broken)

- [ ] **Step 2: Write `README.md`**

`README.md`:
````markdown
# cdp

Terminal picker for recent Claude Code projects.

## What it does

Lists projects you've opened with [Claude Code](https://claude.com/claude-code), lets you pick one via [fzf](https://github.com/junegunn/fzf), then `cd`s to the project and starts `claude`—all in the current terminal, no IDE needed.

## Install

```bash
git clone <this-repo-url> ~/Documents/cdp
cd ~/Documents/cdp
./install.sh
source ~/.zshrc
```

Prerequisites: macOS, zsh, Python ≥ 3.10, [fzf](https://github.com/junegunn/fzf), [claude](https://claude.com/claude-code).

## Usage

```bash
cdp                 # open picker
cdp /some/path      # cd there and start claude directly
cdp pin             # pin current dir to top of picker
cdp pin /path       # pin a specific path
cdp unpin [path]
cdp hide [path]
cdp unhide [path]
cdp alias [path] 别名   # set alias for a path (path defaults to $PWD)
cdp unalias [path]
cdp list            # print path<TAB>display_name (scriptable)
cdp --help
```

### Picker hotkeys (inside fzf)

| Key | Action |
|---|---|
| ↑ ↓ / ctrl-j ctrl-k | Move |
| Enter | Select → cd + launch claude |
| Esc / ctrl-c | Cancel |
| ctrl-p | Toggle pin on highlighted project |
| ctrl-h | Hide highlighted project |
| ctrl-o | Open highlighted path in Finder |

## Configuration

`~/.config/cdp/config.toml`:

```toml
[[project]]
path = "/Users/you/WorkProject/gaokao"
alias = "高考"
pinned = true

[[project]]
path = "/Users/you/old-project"
hidden = true
```

You can edit this file by hand; comments are preserved across `cdp pin`, `cdp alias`, etc.

## Rename the command

```bash
./install.sh --name myp
source ~/.zshrc
```

This rewrites `src/cdp/constants.py`, the shell function name, and re-injects your `~/.zshrc` block under the new name.

## Uninstall

1. Delete the block between `# >>> cdp >>>` and `# <<< cdp <<<` in your `~/.zshrc`.
2. Delete the repo dir.
3. (Optional) Delete `~/.config/cdp/`.

## How it works

- Auto-discovers projects by scanning `~/.claude/projects/` (Claude Code's per-project session storage).
- Sorts by most recent session mtime, with pinned projects on top in declaration order.
- `cd` is done by a zsh function (a child process can't change the parent shell's pwd), same approach as `z` / `zoxide` / `fasd`.

## Tests

```bash
.venv/bin/pytest
```
````

- [ ] **Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: README with install, usage, rename, uninstall"
```

- [ ] **Step 4: Final all-tests pass**

Run: `.venv/bin/pytest -v`
Expected: All tests green (30+ total).

---

## Post-implementation: smoke test checklist

Before declaring done, run through this list in a fresh terminal session (no stale env):

- [ ] `cdp` in a terminal that has never run it → lists projects correctly
- [ ] `cdp /tmp` → cd to /tmp, starts claude (manually exit claude with ctrl-d)
- [ ] Pin/unpin roundtrip via subcommand persists in `config.toml`
- [ ] Pin/unpin roundtrip via fzf ctrl-p persists in `config.toml`
- [ ] `cdp alias /some/real/dir 测试名` shows 测试名 in picker
- [ ] Edit `~/.config/cdp/config.toml` by hand adding a `# comment` line, run `cdp pin /another/dir`, verify the comment is still there

If any fail, fix and re-run the affected tests.
