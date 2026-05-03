"""Tests for Aiper select capability gating."""

from __future__ import annotations

from custom_components.aiper.select import _supports_clean_path, _supports_mode_control


def test_surfer_s2_does_not_expose_select_controls() -> None:
    """Surfer S2 exposes on/off run control through switch, not selects."""
    dev = {
        "deviceModel": "Surfer_S2",
        "_ha_capabilities": ["battery", "history", "online", "run_control"],
        "_ha_supported_mode_ids": [1, 2, 3, 4, 5],
        "_ha_supported_modes_explicit": False,
    }

    assert _supports_clean_path(dev) is False
    assert _supports_mode_control(dev) is False


def test_mode_capability_allows_mode_control() -> None:
    """The select helper follows the normalized profile capability."""
    dev = {
        "deviceModel": "Shark_X",
        "_ha_capabilities": ["mode_select"],
        "_ha_supported_mode_ids": [1, 5],
        "_ha_supported_modes_explicit": True,
    }

    assert _supports_mode_control(dev) is True
