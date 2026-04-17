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
