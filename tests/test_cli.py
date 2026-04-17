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


def test_pin_uses_pwd_when_no_arg(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    # Run with cwd=proj so $PWD default resolves there
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    r = subprocess.run(
        [sys.executable, "-m", "cdp", "pin"],
        capture_output=True, text=True, env=env, cwd=str(proj),
    )
    assert r.returncode == 0
    toml_text = (tmp_path / ".config/cdp/config.toml").read_text()
    assert str(proj) in toml_text
    assert "pinned" in toml_text


def test_pin_explicit_path(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    r = _run(["pin", str(proj)], tmp_path)
    assert r.returncode == 0
    toml_text = (tmp_path / ".config/cdp/config.toml").read_text()
    assert str(proj) in toml_text


def test_pin_nonexistent_path_warns_but_succeeds(tmp_path):
    target = str(tmp_path / "does-not-exist")
    r = _run(["pin", target], tmp_path)
    assert r.returncode == 0
    assert "does not exist" in r.stderr
    # still recorded
    assert target in (tmp_path / ".config/cdp/config.toml").read_text()


def test_unpin_removes(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["pin", str(proj)], tmp_path)
    _run(["unpin", str(proj)], tmp_path)
    toml_text = (tmp_path / ".config/cdp/config.toml").read_text()
    assert "pinned" not in toml_text


def test_hide_and_unhide(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["hide", str(proj)], tmp_path)
    assert "hidden" in (tmp_path / ".config/cdp/config.toml").read_text()
    _run(["unhide", str(proj)], tmp_path)
    assert "hidden" not in (tmp_path / ".config/cdp/config.toml").read_text()


def test_alias_set_and_show_in_list(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-p"
    (claude_projects / encoded).mkdir()
    (claude_projects / encoded / "s.jsonl").write_text("{}")

    r = _run(["alias", str(proj), "foobar"], tmp_path)
    assert r.returncode == 0
    r2 = _run(["list"], tmp_path)
    assert f"{proj}\tfoobar" in r2.stdout


def test_alias_pwd_default(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    r = subprocess.run(
        [sys.executable, "-m", "cdp", "alias", "myname"],
        capture_output=True, text=True, env=env, cwd=str(proj),
    )
    assert r.returncode == 0
    assert 'alias = "myname"' in (tmp_path / ".config/cdp/config.toml").read_text()


def test_unalias_removes(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["alias", str(proj), "x"], tmp_path)
    _run(["unalias", str(proj)], tmp_path)
    assert "alias" not in (tmp_path / ".config/cdp/config.toml").read_text()


def test_direct_path_prints_absolute(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    r = _run([str(proj)], tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == str(proj)


def test_direct_path_expands_tilde(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    # HOME is tmp_path, so ~/p → tmp_path/p
    r = _run(["~/p"], tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == str(proj)


def test_direct_path_rejects_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    r = _run([str(f)], tmp_path)
    assert r.returncode != 0
    assert "not a directory" in r.stderr


def test_direct_path_rejects_missing(tmp_path):
    r = _run([str(tmp_path / "nope")], tmp_path)
    assert r.returncode != 0


def test_internal_render_outputs_picker_lines(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    claude_projects = tmp_path / ".claude/projects"
    claude_projects.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-p"
    (claude_projects / encoded).mkdir()
    (claude_projects / encoded / "s.jsonl").write_text("{}")

    r = _run(["_render"], tmp_path)
    assert r.returncode == 0
    # output should contain a line with the path
    assert str(proj) in r.stdout


def test_internal_toggle_pin_flips_state(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    # Starts unpinned
    r1 = _run(["_toggle-pin", str(proj)], tmp_path)
    assert r1.returncode == 0
    assert "pinned" in (tmp_path / ".config/cdp/config.toml").read_text()
    # Second call unpins
    r2 = _run(["_toggle-pin", str(proj)], tmp_path)
    assert r2.returncode == 0
    assert "pinned" not in (tmp_path / ".config/cdp/config.toml").read_text()


def test_internal_toggle_hide_flips_state(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _run(["_toggle-hide", str(proj)], tmp_path)
    assert "hidden" in (tmp_path / ".config/cdp/config.toml").read_text()
    _run(["_toggle-hide", str(proj)], tmp_path)
    assert "hidden" not in (tmp_path / ".config/cdp/config.toml").read_text()
