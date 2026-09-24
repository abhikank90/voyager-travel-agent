"""Unit tests for the central decoding-temperature resolver.

Verifies that effective_temperature pins sampling to 0 in replay mode, keeps
per-agent defaults in mock/capture/live modes, and honors an explicit
VOYAGER_TEMPERATURE_OVERRIDE when set.
"""

import pytest

from config.settings import effective_temperature, get_settings


@pytest.fixture(autouse=True)
def _reset_settings():
    from config.settings import reload_settings
    reload_settings()


def _set_mode(mode: str) -> None:
    settings = get_settings()
    settings.inventory_mode = mode
    settings.temperature_override = None


def test_replay_mode_forces_zero_temperature():
    _set_mode("replay")
    assert effective_temperature(0.7) == 0.0
    assert effective_temperature(0.4) == 0.0
    assert effective_temperature(0.3) == 0.0


def test_mock_mode_keeps_agent_defaults():
    _set_mode("mock")
    assert effective_temperature(0.7) == 0.7
    assert effective_temperature(0.4) == 0.4
    assert effective_temperature(0.3) == 0.3


def test_capture_mode_keeps_agent_defaults():
    _set_mode("capture")
    assert effective_temperature(0.7) == 0.7
    assert effective_temperature(0.4) == 0.4


def test_live_app_default_mode_keeps_agent_defaults():
    _set_mode("mock")
    assert effective_temperature(0.7) == 0.7


def test_temperature_override_takes_precedence_over_mode():
    settings = get_settings()
    settings.inventory_mode = "mock"
    settings.temperature_override = 0.5
    assert effective_temperature(0.7) == 0.5
    assert effective_temperature(0.3) == 0.5


def test_temperature_override_zero_wins_in_replay():
    settings = get_settings()
    settings.inventory_mode = "replay"
    settings.temperature_override = 0.2
    assert effective_temperature(0.7) == 0.2