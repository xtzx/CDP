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
