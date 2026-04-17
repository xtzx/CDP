import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], env_home: Path, **kwargs) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(env_home)
    env["XDG_CONFIG_HOME"] = str(env_home / ".config")
    return subprocess.run(
        [sys.executable, "-m", "cdp", *args],
        capture_output=True,
        text=True,
        env=env,
        **kwargs,
    )


def test_help(tmp_path):
    r = _run(["--help"], tmp_path)
    assert r.returncode == 0
    assert "pin" in r.stdout
    assert "alias" in r.stdout


def test_list_empty(tmp_path):
    (tmp_path / ".claude" / "projects").mkdir(parents=True)
    r = _run(["list"], tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_list_with_one_project(tmp_path):
    proj = tmp_path / "Users/bjhl/gaokao"
    proj.mkdir(parents=True)
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-Users-bjhl-gaokao"
    (claude_projects / encoded).mkdir()
    (claude_projects / encoded / "s.jsonl").write_text("{}")

    r = _run(["list"], tmp_path)
    assert r.returncode == 0
    # Format: <path>\t<display_name>
    assert f"{proj}\tgaokao" in r.stdout
