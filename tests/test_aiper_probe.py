"""Tests for the Aiper probe utility's non-live behavior."""

from __future__ import annotations

from argparse import Namespace

import pytest

from tools import aiper_probe


def test_load_discovery_flow() -> None:
    """Discovery flows are declarative YAML files."""
    flow = aiper_probe._load_discovery_flow("surfer-s2")

    assert flow["name"] == "Surfer S2"
    assert flow["steps"]
    assert flow["steps"][0]["id"] == "baseline_idle"


def test_at_command_requires_explicit_control_permission() -> None:
    """The probe should not send control commands by default."""
    args = Namespace(allow_control=False)

    with pytest.raises(SystemExit, match="--allow-control"):
        aiper_probe.cmd_at(args)


def test_device_sn_preserves_serial_value() -> None:
    """The probe should use real serial numbers for correlation."""
    assert aiper_probe._device_sn({"serialNumber": "S2SERIAL123"}) == "S2SERIAL123"


def test_credentials_use_region_environment_when_cli_region_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parser default should not mask AIPER_REGION."""
    monkeypatch.setenv("AIPER_USERNAME", "user@example.com")
    monkeypatch.setenv("AIPER_PASSWORD", "secret")
    monkeypatch.setenv("AIPER_REGION", "asia")

    username, password, region = aiper_probe._credentials(Namespace(username=None, password=None, region=None))

    assert username == "user@example.com"
    assert password == "secret"
    assert region == "asia"
