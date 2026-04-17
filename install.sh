#!/usr/bin/env bash
# Install cdp: create venv, pip install, inject into ~/.zshrc.
# Idempotent: re-running is safe. Supports rename via --name.

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
NAME_FILE="$REPO_DIR/.installed_name"

# --- Prereqs ---------------------------------------------------------------
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

# --- Normalize command name in source files --------------------------------
# Always rewrite constants.py and shell/cdp.zsh to match $COMMAND_NAME.
# Using broad regexes so repeated renames work correctly regardless of the
# current in-file name (which a prior --name install may have changed).
CONST="$REPO_DIR/src/cdp/constants.py"
python3 -c "
import re, pathlib
p = pathlib.Path('$CONST')
t = p.read_text()
t = re.sub(r'^COMMAND_NAME = .*\$', f'COMMAND_NAME = \"$COMMAND_NAME\"', t, flags=re.M)
p.write_text(t)
"

WRAPPER="$REPO_DIR/shell/cdp.zsh"
# Match any top-level function definition `<ident>() {` and rewrite its name.
# Since the wrapper has exactly one such line, this is safe.
sed -i.bak -E "s/^[a-zA-Z_][a-zA-Z_0-9]*\(\) \{/$COMMAND_NAME() {/" "$WRAPPER"
rm -f "$WRAPPER.bak"
# Verify the rename actually took effect (the regex above requires both the
# trailing `{` and the exact spacing). Hard-fail instead of silently shipping
# a wrapper whose function name doesn't match the command name.
if ! grep -qE "^$COMMAND_NAME\(\) \{" "$WRAPPER"; then
  echo "error: failed to set wrapper function name to '$COMMAND_NAME' in $WRAPPER" >&2
  exit 1
fi

# --- Inject into ~/.zshrc (idempotent + rename-aware) ----------------------
ZSHRC="$HOME/.zshrc"
touch "$ZSHRC"

remove_block() {
  local name="$1"
  local start="# >>> $name >>>"
  local end="# <<< $name <<<"
  if grep -qF "$start" "$ZSHRC" 2>/dev/null; then
    awk -v start="$start" -v end="$end" '
      $0 == start { skip=1; next }
      $0 == end   { skip=0; next }
      !skip
    ' "$ZSHRC" > "$ZSHRC.tmp"
    mv "$ZSHRC.tmp" "$ZSHRC"
  fi
}

# Remove previously-installed block (captured in .installed_name) if its name
# differs from the one we're about to install. This cleans up after a rename.
if [[ -f "$NAME_FILE" ]]; then
  PREV_NAME="$(cat "$NAME_FILE")"
  if [[ -n "$PREV_NAME" && "$PREV_NAME" != "$COMMAND_NAME" ]]; then
    remove_block "$PREV_NAME"
  fi
fi

# Always remove the current-name block too, so re-running with the same name
# replaces the block cleanly rather than appending a duplicate.
remove_block "$COMMAND_NAME"

cat >> "$ZSHRC" <<EOF

# >>> $COMMAND_NAME >>>
export CDP_HOME="$REPO_DIR"
export CDP_PYTHON="$VENV_DIR/bin/python3"
source "\$CDP_HOME/shell/cdp.zsh"
# <<< $COMMAND_NAME <<<
EOF

# Record the name we just installed so the NEXT install can clean up after us
# if the user passes a different --name.
echo "$COMMAND_NAME" > "$NAME_FILE"

echo ""
echo "Installed. Run:  source ~/.zshrc"
echo "Then try:        $COMMAND_NAME --help"
