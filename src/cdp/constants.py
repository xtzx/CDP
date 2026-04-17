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
