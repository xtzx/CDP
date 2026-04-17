"""fzf rendering and invocation."""
from __future__ import annotations

import shutil
import subprocess
import sys

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


def _fzf_available() -> bool:
    return shutil.which("fzf") is not None


def parse_selection(line: str) -> str | None:
    """Extract the path from a picker line. Path follows at least 2 spaces."""
    line = line.rstrip("\n")
    if not line.strip():
        return None
    # Line format is "<prefix><name_padded>  <path>", and the path itself does
    # not contain a double-space. Split on the LAST occurrence of "  ".
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
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return parse_selection(r.stdout)
