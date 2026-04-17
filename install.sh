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
