"""Shared fixtures for all tests."""
import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect HOME to tmp_path so tests don't touch the real ~."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    # Reload constants so they pick up the new HOME
    import importlib
    import cdp.constants
    importlib.reload(cdp.constants)
    yield tmp_path
    importlib.reload(cdp.constants)
