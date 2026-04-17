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
