# cdp

Terminal picker for recent Claude Code projects.

## What it does

Lists projects you've opened with [Claude Code](https://claude.com/claude-code), lets you pick one via [fzf](https://github.com/junegunn/fzf), then `cd`s to the project and starts `claude`—all in the current terminal, no IDE needed.

## Install

```bash
git clone <this-repo-url> ~/Documents/cdp
cd ~/Documents/cdp
./install.sh
source ~/.zshrc
```

Prerequisites: macOS, zsh, Python ≥ 3.10, [fzf](https://github.com/junegunn/fzf), [claude](https://claude.com/claude-code).

## Usage

```bash
cdp                 # open picker
cdp /some/path      # cd there and start claude directly
cdp pin             # pin current dir to top of picker
cdp pin /path       # pin a specific path
cdp unpin [path]
cdp hide [path]
cdp unhide [path]
cdp alias [path] 别名   # set alias for a path (path defaults to $PWD)
cdp unalias [path]
cdp list            # print path<TAB>display_name (scriptable)
cdp --help
```

### Picker hotkeys (inside fzf)

| Key | Action |
|---|---|
| ↑ ↓ / ctrl-j ctrl-k | Move |
| Enter | Select → cd + launch claude |
| Esc / ctrl-c | Cancel |
| ctrl-p | Toggle pin on highlighted project |
| ctrl-h | Hide highlighted project |
| ctrl-o | Open highlighted path in Finder |

## Configuration

`~/.config/cdp/config.toml`:

```toml
[[project]]
path = "/Users/you/WorkProject/gaokao"
alias = "高考"
pinned = true

[[project]]
path = "/Users/you/old-project"
hidden = true
```

You can edit this file by hand; comments are preserved across `cdp pin`, `cdp alias`, etc.

## Rename the command

```bash
./install.sh --name myp
source ~/.zshrc
```

This rewrites `src/cdp/constants.py`, the shell function name, and re-injects your `~/.zshrc` block under the new name.

## Uninstall

1. Delete the block between `# >>> cdp >>>` and `# <<< cdp <<<` in your `~/.zshrc`.
2. Delete the repo dir.
3. (Optional) Delete `~/.config/cdp/`.

## How it works

- Auto-discovers projects by scanning `~/.claude/projects/` (Claude Code's per-project session storage).
- Sorts by most recent session mtime, with pinned projects on top in declaration order.
- `cd` is done by a zsh function (a child process can't change the parent shell's pwd), same approach as `z` / `zoxide` / `fasd`.

## Tests

```bash
.venv/bin/pytest
```
