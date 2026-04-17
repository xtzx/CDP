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
