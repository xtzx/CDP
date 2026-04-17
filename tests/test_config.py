from pathlib import Path

import pytest

from cdp.config import Config, ConfigEntry


def test_load_missing_file_returns_empty(tmp_path):
    cfg = Config.load(tmp_path / "nope.toml")
    assert cfg.entries == []


def test_load_valid_file(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('''
# top-level comment

[[project]]
path = "/a"
pinned = true

[[project]]
path = "/b"
alias = "bee"

[[project]]
path = "/c"
hidden = true
''')
    cfg = Config.load(f)
    assert cfg.entries == [
        ConfigEntry(path="/a", pinned=True),
        ConfigEntry(path="/b", alias="bee"),
        ConfigEntry(path="/c", hidden=True),
    ]


def test_save_roundtrip_preserves_comments(tmp_path):
    f = tmp_path / "c.toml"
    original = '''# pin order comment
# another line

[[project]]
path = "/a"
pinned = true
'''
    f.write_text(original)
    cfg = Config.load(f)
    cfg.save()
    # Header comments and blank lines preserved
    assert "# pin order comment" in f.read_text()
    assert "# another line" in f.read_text()


def test_load_invalid_toml_raises(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('not a valid toml = = =')
    with pytest.raises(Exception) as exc_info:
        Config.load(f)
    # Any exception is fine; message should mention the file
    assert str(f) in str(exc_info.value) or "toml" in str(exc_info.value).lower()


def test_pin_adds_new_entry(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin("/a")
    assert cfg.entries == [ConfigEntry(path="/a", pinned=True)]


def test_pin_sets_flag_on_existing_entry(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[[project]]\npath = "/a"\nalias = "ay"\n')
    cfg = Config.load(f)
    cfg.pin("/a")
    assert cfg.entries == [ConfigEntry(path="/a", alias="ay", pinned=True)]


def test_unpin_clears_flag(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin("/a")
    cfg.unpin("/a")
    # Entry with no flags left is removed entirely
    assert cfg.entries == []


def test_unpin_keeps_entry_if_other_flags_present(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.set_alias("/a", "ay")
    cfg.pin("/a")
    cfg.unpin("/a")
    assert cfg.entries == [ConfigEntry(path="/a", alias="ay")]


def test_hide_and_unhide(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.hide("/a")
    assert cfg.entries == [ConfigEntry(path="/a", hidden=True)]
    cfg.unhide("/a")
    assert cfg.entries == []


def test_set_and_clear_alias(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.set_alias("/a", "ay")
    assert cfg.entries == [ConfigEntry(path="/a", alias="ay")]
    cfg.clear_alias("/a")
    assert cfg.entries == []


def test_pin_preserves_order_of_existing_pins(tmp_path):
    cfg = Config.load(tmp_path / "c.toml")
    cfg.pin("/a")
    cfg.pin("/b")
    cfg.pin("/c")
    assert [e.path for e in cfg.entries if e.pinned] == ["/a", "/b", "/c"]


# --- Robustness / safety regressions ---------------------------------------


def test_load_rejects_non_bool_pinned(tmp_path):
    """M-1: a string 'false' must NOT be silently treated as truthy."""
    f = tmp_path / "c.toml"
    f.write_text('[[project]]\npath = "/a"\npinned = "false"\n')
    with pytest.raises(ValueError) as exc_info:
        Config.load(f)
    assert "pinned" in str(exc_info.value).lower()


def test_load_rejects_non_bool_hidden(tmp_path):
    """M-1: integers are not bools — reject, don't coerce."""
    f = tmp_path / "c.toml"
    f.write_text('[[project]]\npath = "/a"\nhidden = 1\n')
    with pytest.raises(ValueError) as exc_info:
        Config.load(f)
    assert "hidden" in str(exc_info.value).lower()


def test_load_rejects_wrong_project_shape(tmp_path):
    """M-3: `project = "oops"` (scalar) must raise a clear error, not crash cryptically."""
    f = tmp_path / "c.toml"
    f.write_text('project = "oops"\n')
    with pytest.raises(ValueError) as exc_info:
        Config.load(f)
    msg = str(exc_info.value).lower()
    assert "project" in msg
    assert str(f) in str(exc_info.value) or "array" in msg or "table" in msg


def test_save_writes_atomically(tmp_path, monkeypatch):
    """I-2: save() must write to a temp file and os.replace into place."""
    import cdp.config as cfg_mod

    f = tmp_path / "c.toml"
    cfg = Config.load(f)
    cfg.pin("/a")

    replace_calls: list[tuple] = []
    original_replace = cfg_mod.os.replace

    def tracking_replace(src, dst):
        replace_calls.append((str(src), str(dst)))
        return original_replace(src, dst)

    monkeypatch.setattr(cfg_mod.os, "replace", tracking_replace)

    cfg.save()
    assert len(replace_calls) == 1, "save() should use os.replace exactly once"
    assert "/a" in f.read_text()
    # no stray .tmp file
    assert list(f.parent.glob("*.tmp")) == []


def test_save_leaves_original_intact_on_failure(tmp_path, monkeypatch):
    """I-2: if os.replace fails mid-write, the original file is preserved."""
    import cdp.config as cfg_mod

    f = tmp_path / "c.toml"
    # Pre-populate with committed original state
    seed = Config.load(f)
    seed.pin("/original")
    seed.save()
    original_content = f.read_text()

    # Reload and modify; simulate crash during the rename step
    cfg = Config.load(f)
    cfg.pin("/new")

    def failing_replace(src, dst):
        raise OSError("simulated crash")

    monkeypatch.setattr(cfg_mod.os, "replace", failing_replace)

    with pytest.raises(OSError):
        cfg.save()

    # Original file must be byte-identical to pre-save state
    assert f.read_text() == original_content
    assert "/new" not in f.read_text()
