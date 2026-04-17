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
