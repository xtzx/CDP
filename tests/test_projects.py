import os
from pathlib import Path

from cdp.projects import decode_encoded_path
from cdp.projects import DiscoveredProject, scan_recent_projects


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
