"""argparse-based CLI for cdp."""
from __future__ import annotations

import argparse
import sys

from cdp import combine, config as cfg_mod, constants, projects


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=constants.COMMAND_NAME,
        description="Terminal picker for recent Claude Code projects.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="print projects (path<TAB>display_name)")

    for name in ("pin", "unpin", "hide", "unhide"):
        sp = sub.add_parser(name, help=f"{name} a path (defaults to $PWD)")
        sp.add_argument("path", nargs="?", default=None)

    # `alias` takes 1 or 2 positional args:
    #   cdp alias <name>             → path=$PWD, name=<name>
    #   cdp alias <path> <name>      → explicit path and name
    # We use nargs="+" and post-process to avoid argparse's ambiguous
    # behavior with "optional followed by required" positionals.
    sp_alias = sub.add_parser("alias", help="set alias for a path")
    sp_alias.add_argument("args", nargs="+", help="[path] <name>")

    sp_unalias = sub.add_parser("unalias", help="remove alias for a path")
    sp_unalias.add_argument("path", nargs="?", default=None)

    # Direct path mode is captured as a positional arg outside of subparsers.
    # argparse doesn't natively mix subparsers and a leading positional, so we
    # fall back to argv inspection for that case.
    if argv is None:
        argv = sys.argv[1:]

    known_subcommands = {"list", "pin", "unpin", "hide", "unhide", "alias", "unalias"}
    if argv and argv[0] not in known_subcommands and not argv[0].startswith("-"):
        return _cmd_direct_path(argv[0])

    args = parser.parse_args(argv)
    if args.cmd == "list":
        return _cmd_list()
    if args.cmd is None:
        return _cmd_picker()
    if args.cmd in ("pin", "unpin", "hide", "unhide"):
        return _cmd_config_toggle(args.cmd, args.path)
    if args.cmd == "alias":
        return _cmd_alias(args.args)
    if args.cmd == "unalias":
        return _cmd_unalias(args.path)
    return 0


def _cmd_list() -> int:
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    discovered = projects.scan_recent_projects(constants.CLAUDE_PROJECTS_DIR)
    for p in combine.get_display_projects(discovered, cfg):
        print(f"{p.path}\t{p.display_name}")
    return 0


def _cmd_picker() -> int:
    # Implemented in a later task
    print("picker: not yet implemented", file=sys.stderr)
    return 2


def _cmd_direct_path(raw: str) -> int:
    # Implemented in a later task
    print(f"direct path mode: not yet implemented ({raw!r})", file=sys.stderr)
    return 2


def _cmd_config_toggle(cmd: str, path: str | None) -> int:
    import os as _os
    target = _os.path.abspath(_os.path.expanduser(path)) if path else _os.getcwd()
    if not _os.path.isdir(target):
        print(f"warning: {target} does not exist, {cmd}ning anyway", file=sys.stderr)
    cfg = cfg_mod.Config.load(constants.CONFIG_PATH)
    getattr(cfg, cmd)(target)
    cfg.save()
    return 0


def _cmd_alias(args_list: list[str]) -> int:
    print("alias: not yet implemented", file=sys.stderr)
    return 2


def _cmd_unalias(path: str | None) -> int:
    print("unalias: not yet implemented", file=sys.stderr)
    return 2
