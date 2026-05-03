"""Tests for device profile and capability discovery."""

from __future__ import annotations

from custom_components.aiper.profiles import Capability, DeviceFamily, derive_device_profile


def test_surfer_profile_exposes_verified_controls_without_mode_select() -> None:
    """Surfer models expose verified controls without Scuba mode selection."""
    profile = derive_device_profile(
        {
            "model": "Surfer_S2",
            "_ha_supported_mode_ids": [1, 2, 3, 4, 5],
            "_ha_supported_modes_explicit": False,
            "_ha_consumables": [{"name": "Propeller"}],
        }
    )

    assert profile.family is DeviceFamily.SURFER
    assert Capability.PROPELLER_MAINTENANCE in profile.capabilities
    assert Capability.RUN_CONTROL in profile.capabilities
    assert Capability.CLEAN_PATH not in profile.capabilities
    assert Capability.CLEANING_MODE_SELECT not in profile.capabilities
    assert profile.mode_map[0] == "Off"
    assert profile.mode_map[1] == "Manual"
    assert profile.mode_map[5] == "Scheduled"


def test_scuba_profile_gets_scuba_controls_and_labels() -> None:
    """Scuba models can expose Scuba controls and Scuba-specific mode labels."""
    profile = derive_device_profile(
        {
            "model": "Scuba_X1",
            "_ha_supported_mode_ids": [1, 2, 3, 4, 5],
            "_ha_supported_modes_explicit": False,
        }
    )

    assert profile.family is DeviceFamily.SCUBA
    assert Capability.CLEAN_PATH in profile.capabilities
    assert Capability.CLEANING_MODE_SELECT in profile.capabilities
    assert profile.mode_map[1] == "Smart"
    assert profile.mode_map[5] == "Scheduled"


def test_surfer_mode_evidence_stays_read_only() -> None:
    """Surfer mode IDs describe run context, not selectable cleaning modes."""
    profile = derive_device_profile(
        {
            "model": "Surfer_S2",
            "_ha_supported_mode_ids": [1, 5],
            "_ha_supported_modes_explicit": True,
        }
    )

    assert Capability.CLEANING_MODE_SELECT not in profile.capabilities
    assert profile.mode_map == {0: "Off", 1: "Manual", 5: "Scheduled"}


def test_shark_explicit_mode_evidence_enables_cleaning_mode_control() -> None:
    """Shark can join cleaning-mode control when payloads provide mode IDs."""
    profile = derive_device_profile(
        {
            "model": "Shark_X",
            "_ha_supported_mode_ids": [1, 2],
            "_ha_supported_modes_explicit": True,
        }
    )

    assert profile.family is DeviceFamily.SHARK
    assert Capability.CLEANING_MODE_SELECT in profile.capabilities
    assert profile.mode_map == {1: "Mode 1", 2: "Mode 2"}
