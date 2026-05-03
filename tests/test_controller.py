"""Tests for the typed Aiper command controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from custom_components.aiper.controller import AiperDeviceController
from custom_components.aiper.profiles import Capability


@dataclass
class FakeApi:
    """Fake low-level API used by controller tests."""

    mode_result: bool = True
    clean_path_result: bool = True
    modes: list[tuple[str, int]] = field(default_factory=list)
    run_states: list[tuple[str, bool]] = field(default_factory=list)
    clean_paths: list[tuple[str, int]] = field(default_factory=list)

    async def set_cleaning_mode(self, sn: str, mode: int) -> bool:
        self.modes.append((sn, mode))
        return self.mode_result

    async def set_surfer_running(self, sn: str, running: bool) -> bool:
        self.run_states.append((sn, running))
        return self.mode_result

    async def update_clean_path_setting(self, sn: str, clean_path: int) -> bool:
        self.clean_paths.append((sn, clean_path))
        return self.clean_path_result


@dataclass
class FakeCoordinator:
    """Fake coordinator carrying device capabilities and command state calls."""

    data: dict[str, dict[str, Any]]
    sent: list[tuple[str, str, Any, str]] = field(default_factory=list)
    failed: list[tuple[str, str, Any, str, str]] = field(default_factory=list)

    def note_command_sent(self, sn: str, kind: str, target: Any, *, source: str = "select") -> None:
        self.sent.append((sn, kind, target, source))

    def note_command_failed(
        self,
        sn: str,
        kind: str,
        target: Any,
        *,
        reason: str,
        source: str = "select",
    ) -> None:
        self.failed.append((sn, kind, target, reason, source))


def _controller(api: FakeApi, coordinator: FakeCoordinator) -> AiperDeviceController:
    return AiperDeviceController(cast(Any, api), cast(Any, coordinator))


@pytest.mark.asyncio
async def test_set_cleaning_mode_uses_typed_controller_and_records_command_state() -> None:
    """Cleaning mode changes use device intent rather than raw AT commands."""
    api = FakeApi()
    coordinator = FakeCoordinator({"SN123": {"_ha_capabilities": [Capability.CLEANING_MODE_SELECT.value]}})

    result = await _controller(api, coordinator).set_cleaning_mode("SN123", 2)

    assert result.ok is True
    assert result.command == "cleaning_mode"
    assert api.modes == [("SN123", 2)]
    assert coordinator.sent == [("SN123", "cleaning_mode", 2, "controller")]
    assert coordinator.failed == []


@pytest.mark.asyncio
async def test_clean_path_rejects_devices_without_capability() -> None:
    """Unsupported device families should not receive clean-path commands."""
    api = FakeApi()
    coordinator = FakeCoordinator({"SN123": {"_ha_capabilities": []}})

    result = await _controller(api, coordinator).set_clean_path("SN123", 1)

    assert result.ok is False
    assert result.reason == "device does not advertise clean_path"
    assert api.clean_paths == []
    assert coordinator.sent == []


@pytest.mark.asyncio
async def test_set_cleaning_mode_records_device_rejection() -> None:
    """Rejected low-level commands are surfaced as structured command results."""
    api = FakeApi(mode_result=False)
    coordinator = FakeCoordinator({"SN123": {"_ha_capabilities": [Capability.CLEANING_MODE_SELECT.value]}})

    result = await _controller(api, coordinator).set_cleaning_mode("SN123", 5)

    assert result.ok is False
    assert result.reason == "device rejected"
    assert coordinator.failed == [("SN123", "cleaning_mode", 5, "device rejected", "controller")]


@pytest.mark.asyncio
async def test_set_running_uses_surfer_mode_commands() -> None:
    """Surfer run control maps on/off intent to the verified AT mode IDs."""
    api = FakeApi()
    coordinator = FakeCoordinator({"SN123": {"_ha_capabilities": [Capability.RUN_CONTROL.value]}})
    controller = _controller(api, coordinator)

    on_result = await controller.set_running("SN123", True)
    off_result = await controller.set_running("SN123", False)

    assert on_result.ok is True
    assert off_result.ok is True
    assert api.run_states == [("SN123", True), ("SN123", False)]
    assert coordinator.sent == [
        ("SN123", "run", True, "controller"),
        ("SN123", "run", False, "controller"),
    ]


@pytest.mark.asyncio
async def test_set_running_rejects_devices_without_capability() -> None:
    """Devices without verified simple run control should not receive commands."""
    api = FakeApi()
    coordinator = FakeCoordinator({"SN123": {"_ha_capabilities": []}})

    result = await _controller(api, coordinator).set_running("SN123", True)

    assert result.ok is False
    assert result.reason == "device does not advertise run_control"
    assert api.modes == []
    assert coordinator.sent == []
