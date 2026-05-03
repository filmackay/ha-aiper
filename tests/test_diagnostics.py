"""Tests for diagnostics redaction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.aiper.const import DOMAIN
from custom_components.aiper.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_sensitive_runtime_data() -> None:
    """Diagnostics should not expose credentials, tokens, or AWS secrets."""
    entry = SimpleNamespace(
        entry_id="entry-1",
        title="Aiper",
        data={
            "username": "person@example.com",
            "password": "top-secret",
            "region": "eu",
        },
        options={"enable_mqtt": True},
    )
    api = SimpleNamespace(
        base_url="https://apieurope.aiper.com",
        region="eu",
        _iot_endpoint="abcdefghijk.iot.eu-central-1.amazonaws.com",
        _identity_id="eu-central-1:1234567890",
        _aws_region="eu-central-1",
        _mqtt_client=SimpleNamespace(last_error=None, reconnect_count=1),
        is_mqtt_connected=lambda: True,
    )
    coordinator = SimpleNamespace(
        last_update_success=True,
        update_interval=None,
        data={
            "SN123": {
                "name": "Pool Robot",
                "token": "runtime-token",
                "nested": {"SecretKey": "aws-secret"},
            }
        },
        _command_state={
            "SN123": {
                "pending": {
                    "mode": {
                        "accessKeyId": "AKIA...",
                        "value": 1,
                    }
                }
            }
        },
    )
    hass = SimpleNamespace(data={DOMAIN: {entry.entry_id: {"api": api, "coordinator": coordinator}}})

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"] == {
        "region": "eu",
        "username": "per...com",
    }
    assert diagnostics["devices"]["SN123"]["token"] == "***"
    assert diagnostics["devices"]["SN123"]["nested"]["SecretKey"] == "***"
    assert diagnostics["command_state"]["SN123"]["pending"]["mode"]["accessKeyId"] == "***"
    assert diagnostics["command_state"]["SN123"]["pending"]["mode"]["value"] == 1
    assert diagnostics["api"]["mqtt_client"] == "SimpleNamespace"
    assert diagnostics["api"]["mqtt_reconnect_count"] == 1
