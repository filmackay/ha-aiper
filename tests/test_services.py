"""Tests for Aiper Home Assistant services."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from custom_components.aiper import (
    _async_find_service_target,
    _async_send_at_command_service,
    async_setup,
)
from custom_components.aiper.const import DOMAIN


@dataclass
class FakeApi:
    """Fake API object recording AT commands and shadow requests."""

    sent: list[tuple[str, str]] = field(default_factory=list)
    shadows: list[str] = field(default_factory=list)

    def send_machine_at(self, sn: str, command: str) -> None:
        self.sent.append((sn, command))

    def request_shadow(self, sn: str) -> None:
        self.shadows.append(sn)


@dataclass
class FakeCoordinator:
    """Fake coordinator with a minimal data mapping."""

    data: dict[str, dict]


class FakeServices:
    """Minimal Home Assistant service registry shim."""

    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], object] = {}

    def has_service(self, domain: str, service: str) -> bool:
        return (domain, service) in self._handlers

    def async_register(self, domain: str, service: str, handler) -> None:
        self._handlers[(domain, service)] = handler


class FakeHass:
    """Minimal Home Assistant shim for service tests."""

    def __init__(self) -> None:
        self.data = {DOMAIN: {}}
        self.services = FakeServices()

    async def async_add_executor_job(self, target, *args):
        return target(*args)


@dataclass
class FakeServiceCall:
    """Minimal service-call object with data."""

    data: dict


def _add_entry(hass: FakeHass, entry_id: str, api: FakeApi, serials: list[str]) -> None:
    hass.data[DOMAIN][entry_id] = {
        "api": api,
        "coordinator": FakeCoordinator({sn: {} for sn in serials}),
    }


@pytest.mark.asyncio
async def test_async_setup_registers_send_at_service_once() -> None:
    """The debug AT service is a global integration service."""
    hass = FakeHass()

    assert await async_setup(hass, {}) is True
    assert await async_setup(hass, {}) is True

    assert len(hass.services._handlers) == 1
    assert hass.services.has_service(DOMAIN, "send_at_command")


def test_find_service_target_uses_requested_serial() -> None:
    """An explicit serial number should select the matching loaded entry."""
    hass = FakeHass()
    api_1 = FakeApi()
    api_2 = FakeApi()
    _add_entry(hass, "entry-1", api_1, ["SN1"])
    _add_entry(hass, "entry-2", api_2, ["SN2"])

    target = _async_find_service_target(hass, "SN2")

    assert target is not None
    api, coordinator, sn = target
    assert api is api_2
    assert coordinator.data == {"SN2": {}}
    assert sn == "SN2"


def test_find_service_target_falls_back_to_first_available_device() -> None:
    """When no serial is supplied, use the first discovered device."""
    hass = FakeHass()
    api = FakeApi()
    _add_entry(hass, "entry-1", api, ["SN1"])

    target = _async_find_service_target(hass, None)

    assert target is not None
    assert target[0] is api
    assert target[2] == "SN1"


@pytest.mark.asyncio
async def test_send_at_service_dispatches_to_matching_entry_and_normalizes_command() -> None:
    """The service should find the device owner and add the AT+ prefix."""
    hass = FakeHass()
    api_1 = FakeApi()
    api_2 = FakeApi()
    _add_entry(hass, "entry-1", api_1, ["SN1"])
    _add_entry(hass, "entry-2", api_2, ["SN2"])

    await _async_send_at_command_service(hass, FakeServiceCall({"sn": "SN2", "command": "MODE=2"}))

    assert api_1.sent == []
    assert api_2.sent == [("SN2", "AT+MODE=2")]
    assert api_2.shadows == ["SN2"]


@pytest.mark.asyncio
async def test_send_at_service_ignores_unknown_serial() -> None:
    """Unknown serial numbers should not dispatch to the wrong entry."""
    hass = FakeHass()
    api = FakeApi()
    _add_entry(hass, "entry-1", api, ["SN1"])

    await _async_send_at_command_service(hass, FakeServiceCall({"sn": "missing", "command": "MODE=2"}))

    assert api.sent == []
    assert api.shadows == []
