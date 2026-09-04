"""Shared test fixtures.

Restores the settings cache to its initial state after each test so inventory
mode mutations (capture/replay in test_inventory.py) never leak into later
tests once they have finished. The cached ``config.settings._settings`` global
is not reverted by ``monkeypatch`` env restoration, so without this, later
tests would run under a leaked capture/replay mode and (with API keys present)
hit real providers.
"""

import pytest

from config.settings import get_settings, reload_settings


@pytest.fixture(autouse=True)
def _restore_settings_after_test():
    initial = get_settings().model_dump()
    yield
    reload_settings()
    current = get_settings()
    for key, value in initial.items():
        setattr(current, key, value)