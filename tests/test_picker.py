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
