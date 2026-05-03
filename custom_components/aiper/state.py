"""Device-state normalization helpers for Aiper payloads."""
from __future__ import annotations

from typing import Any

from .const import Status, status_high_bit, status_value
from .profiles import Capability, derive_device_profile, has_capability


def _coerce_int(value: Any) -> int | None:
    """Coerce common numeric payload values into an int."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _shadow_machine(device: dict[str, Any]) -> dict[str, Any]:
    shadow = device.get("shadow") or {}
    machine = shadow.get("machine") or {}
    return machine if isinstance(machine, dict) else {}


def _has_run_control(device: dict[str, Any]) -> bool:
    if "_ha_capabilities" in device:
        return has_capability(device, Capability.RUN_CONTROL)
    return Capability.RUN_CONTROL in derive_device_profile(device).capabilities


def normalize_device_state(device: dict[str, Any]) -> None:
    """Normalize raw REST/shadow state into Home Assistant-facing fields.

    Aiper's Machine.status carries the base status in the lower 7 bits. The
    observed high bit indicates that the robot is actively running. Normalize
    that once here so entity code does not need to know the protocol detail.
    """
    machine = _shadow_machine(device)
    run_control = _has_run_control(device)

    raw_status = _coerce_int(machine.get("status"))
    if raw_status is None:
        raw_status = _coerce_int(device.get("machineStatus"))

    if raw_status is not None:
        running = status_high_bit(raw_status)
        value = status_value(raw_status)
        device["running"] = running
        if run_control and not running:
            device["machineStatus"] = int(Status.IDLE)
        elif value is not None:
            device["machineStatus"] = value
    else:
        device["running"] = None

    mode = _coerce_int(machine.get("mode"))
    if mode is None:
        mode = _coerce_int(device.get("mode"))

    if run_control and device.get("running") is False:
        device["mode"] = 0
    elif mode is not None:
        device["mode"] = mode
