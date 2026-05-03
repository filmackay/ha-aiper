"""Tests for Aiper status-code normalization."""

from __future__ import annotations

from custom_components.aiper.const import status_high_bit, status_label, status_value
from custom_components.aiper.state import normalize_device_state


def test_status_label_uses_lower_status_bits() -> None:
    """Surfer status reports set a high bit while preserving base state."""
    assert status_value(128) == 0
    assert status_value(129) == 1
    assert status_label(128) == "Idle"
    assert status_label(129) == "Cleaning"


def test_status_high_bit_preserves_observed_flag() -> None:
    """The high status bit is tracked separately from the base state."""
    assert status_high_bit(128) is True
    assert status_high_bit(129) is True
    assert status_high_bit(1) is False


def test_surfer_standby_state_is_normalized_at_boundary() -> None:
    """Surfer reports mode 5 while stopped; normalize the exposed mode to off."""
    device = {
        "model": "Surfer_S2",
        "machineStatus": 0,
        "shadow": {"machine": {"status": 0, "mode": 5}},
    }

    normalize_device_state(device)

    assert device["machineStatus"] == 0
    assert device["running"] is False
    assert device["mode"] == 0


def test_running_status_is_normalized_to_base_status() -> None:
    """Raw status is interpreted once into base status and running state."""
    device = {
        "model": "Surfer_S2",
        "machineStatus": 129,
        "shadow": {"machine": {"status": 129, "mode": 1}},
    }

    normalize_device_state(device)

    assert device["machineStatus"] == 1
    assert device["running"] is True
    assert device["mode"] == 1

