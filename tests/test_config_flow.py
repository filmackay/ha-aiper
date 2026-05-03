"""Tests for the Aiper config flow helpers."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.aiper.config_flow import CONF_REGION, InvalidAuth, validate_input


class FakeHass:
    """Small async executor shim for config-flow unit tests."""

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class FakeAiperApi:
    """Fake Aiper API client used by validate_input tests."""

    instances: list[FakeAiperApi] = []
    login_result = True
    devices = [{"sn": "SN1"}, {"sn": "SN2"}]

    def __init__(self, username: str, password: str, region: str) -> None:
        self.username = username
        self.password = password
        self.region = region
        self.disconnected = False
        self.__class__.instances.append(self)

    def login(self) -> bool:
        return self.login_result

    def get_devices(self) -> list[dict[str, str]]:
        return self.devices

    def disconnect(self) -> None:
        self.disconnected = True


@pytest.fixture(autouse=True)
def fake_api(monkeypatch: pytest.MonkeyPatch) -> type[FakeAiperApi]:
    """Patch the config flow to use a fake API client."""
    FakeAiperApi.instances = []
    FakeAiperApi.login_result = True
    FakeAiperApi.devices = [{"sn": "SN1"}, {"sn": "SN2"}]
    monkeypatch.setattr("custom_components.aiper.config_flow.AiperApi", FakeAiperApi)
    return FakeAiperApi


@pytest.mark.asyncio
async def test_validate_input_returns_title_and_device_count() -> None:
    """Successful validation returns display info and disconnects the client."""
    data = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_REGION: "eu",
    }

    result = await validate_input(FakeHass(), data)

    assert result == {
        "title": "Aiper (user@example.com)",
        "device_count": 2,
    }
    assert FakeAiperApi.instances[0].region == "eu"
    assert FakeAiperApi.instances[0].disconnected is True


@pytest.mark.asyncio
async def test_validate_input_accepts_australia_region_alias() -> None:
    """Australia is a first-class region option backed by Asia/Pacific."""
    data = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_REGION: "au",
    }

    await validate_input(FakeHass(), data)

    assert FakeAiperApi.instances[0].region == "au"


@pytest.mark.asyncio
async def test_validate_input_raises_invalid_auth_when_login_fails(
    fake_api: type[FakeAiperApi],
) -> None:
    """A false login result is treated as invalid credentials."""
    fake_api.login_result = False
    data = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "bad-secret",
        CONF_REGION: "eu",
    }

    with pytest.raises(InvalidAuth):
        await validate_input(FakeHass(), data)

    assert FakeAiperApi.instances[0].disconnected is True
