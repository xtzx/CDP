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
