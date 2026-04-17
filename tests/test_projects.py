from pathlib import Path

from cdp.projects import decode_encoded_path


def test_simple_decode(tmp_path):
    # Create /tmp_path/Users/bjhl/Documents/gaokao
    target = tmp_path / "Users/bjhl/Documents/gaokao"
    target.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-Users-bjhl-Documents-gaokao"
    result = decode_encoded_path(encoded)
    assert result == str(target)


def test_decode_with_hyphen_in_dir_name(tmp_path):
    # Create /tmp_path/foo/galaxy-client
    target = tmp_path / "foo/galaxy-client"
    target.mkdir(parents=True)
    encoded = str(tmp_path).replace("/", "-") + "-foo-galaxy-client"
    result = decode_encoded_path(encoded)
    assert result == str(target)


def test_decode_nonexistent_path_returns_naive_join(tmp_path):
    """If no segmentation works, return naive join (will be filtered elsewhere)."""
    encoded = "-nonexistent-xyz-abc"
    result = decode_encoded_path(encoded)
    assert result == "/nonexistent/xyz/abc"
