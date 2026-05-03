"""Switch platform for Aiper integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_QUEUE_OFFLINE_COMMANDS, DOMAIN
from .controller import AiperDeviceController
from .coordinator import AiperDataUpdateCoordinator
from .profiles import Capability, has_capability


def _coerce_bool(val: Any) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(int(val))
    if isinstance(val, str):
        s = val.strip().lower()
        if s in {"true", "on", "yes", "1"}:
            return True
        if s in {"false", "off", "no", "0"}:
            return False
    return None


def _coerce_int(val: Any) -> int | None:
    if isinstance(val, bool) or val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str) and val.strip().lstrip("-").isdigit():
        return int(val.strip())
    return None


def _device_online(coordinator: AiperDataUpdateCoordinator, sn: str) -> bool | None:
    dev = (coordinator.data or {}).get(sn) or {}
    rest = _coerce_bool(dev.get("_ha_online"))
    if rest is not None:
        return rest

    try:
        netstat = coordinator.get_netstat(sn) or {}
    except Exception:
        netstat = {}
    return _coerce_bool(netstat.get("online"))


def _device_name(dev: dict[str, Any], sn: str) -> str:
    return str(dev.get("name") or dev.get("deviceName") or dev.get("productName") or sn)


def _device_model(dev: dict[str, Any]) -> str:
    return str(
        dev.get("model")
        or dev.get("deviceModel")
        or dev.get("modelName")
        or dev.get("productName")
        or "Aiper Pool Cleaner"
    )


def _supports_run_control(dev: dict[str, Any]) -> bool:
    """Return whether the device supports simple on/off run control."""
    return has_capability(dev, Capability.RUN_CONTROL)


class AiperRunSwitch(CoordinatorEntity[AiperDataUpdateCoordinator], SwitchEntity):
    """Switch for simple start/stop control."""

    _attr_icon = "mdi:pool"

    def __init__(
        self,
        coordinator: AiperDataUpdateCoordinator,
        controller: AiperDeviceController,
        entry: ConfigEntry,
        sn: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self.controller = controller
        self._config_entry = entry
        self._sn = sn
        self._attr_name = f"{name} Run"
        self._attr_unique_id = f"{sn}_run"

    @property
    def device_info(self) -> DeviceInfo:
        dev = (self.coordinator.data or {}).get(self._sn) or {}
        sw = dev.get("_ha_fw_main") or dev.get("firmwareVersion")
        return {
            "identifiers": {(DOMAIN, self._sn)},
            "name": dev.get("name") or dev.get("deviceName") or self._sn,
            "manufacturer": "Aiper",
            "model": _device_model(dev),
            "sw_version": sw,
        }

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        if not self.coordinator.api.is_mqtt_connected():
            return False

        allow_offline = bool(self._config_entry.options.get(CONF_QUEUE_OFFLINE_COMMANDS, False))
        if allow_offline:
            return True

        online = _device_online(self.coordinator, self._sn)
        return online is not False

    @property
    def is_on(self) -> bool | None:
        dev = (self.coordinator.data or {}).get(self._sn) or {}
        running = dev.get("running")
        return running if isinstance(running, bool) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "mqtt_connected": self.coordinator.api.is_mqtt_connected(),
            "allow_offline_commands": bool(self._config_entry.options.get(CONF_QUEUE_OFFLINE_COMMANDS, False)),
        }

        online = _device_online(self.coordinator, self._sn)
        if online is not None:
            attrs["device_online"] = online

        dev = (self.coordinator.data or {}).get(self._sn) or {}
        mode = _coerce_int(dev.get("mode"))
        if dev.get("running") is not None:
            attrs["running"] = dev.get("running")
        if mode is not None:
            attrs["machine_mode"] = mode

        try:
            cmd = self.coordinator.get_command_state(self._sn)
            if cmd:
                attrs["pending_commands"] = cmd.get("pending")
                attrs["last_commands"] = cmd.get("last")
        except Exception:
            pass

        return attrs

    def _raise_if_control_blocked(self) -> None:
        if not self.coordinator.api.is_mqtt_connected():
            raise HomeAssistantError("Aiper MQTT connection is not available; cannot send this command.")

        allow_offline = bool(self._config_entry.options.get(CONF_QUEUE_OFFLINE_COMMANDS, False))
        online = _device_online(self.coordinator, self._sn)
        if not allow_offline and online is False:
            raise HomeAssistantError(
                "Device is offline; controls are disabled. "
                "Enable 'Queue commands while device is offline' in the integration options to allow scheduling."
            )

    async def _set_running(self, running: bool) -> None:
        self._raise_if_control_blocked()

        result = await self.controller.set_running(self._sn, running)
        if not result.ok:
            raise HomeAssistantError(f"Failed to set cleaning state: {result.reason or 'device rejected the command'}")

        try:
            await self.controller.refresh_shadow(self._sn)
        except Exception:
            pass

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start cleaning."""
        await self._set_running(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        await self._set_running(False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up switch entities from a config entry."""
    coordinator: AiperDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    controller: AiperDeviceController = hass.data[DOMAIN][entry.entry_id]["controller"]

    entities: list[SwitchEntity] = []
    if coordinator.data:
        for sn, dev in coordinator.data.items():
            if _supports_run_control(dev):
                entities.append(AiperRunSwitch(coordinator, controller, entry, sn, _device_name(dev, sn)))

    async_add_entities(entities)
