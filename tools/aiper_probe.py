#!/usr/bin/env python3
"""Aiper discovery utility.

This tool intentionally reuses the integration's AiperApi implementation. It
adds only orchestration, capture, redaction, and reporting around the same REST
and MQTT code Home Assistant uses.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, datetime
import getpass
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only in incomplete dev envs
    yaml = None

from custom_components.aiper.api import AiperApi  # noqa: E402
from custom_components.aiper.redaction import redact  # noqa: E402


DEFAULT_OUTPUT_DIR = Path("probe-output")
DISCOVERY_FLOWS_DIR = REPO_ROOT / "tools" / "discovery_flows"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return repr(value)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact(data), indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _append_ndjson(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(redact(data), sort_keys=True, default=_json_default) + "\n")


def _run_dir(base_dir: Path, prefix: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = base_dir / f"{stamp}-{prefix}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _device_sn(device: dict[str, Any]) -> str | None:
    for key in ("sn", "deviceSn", "serialNumber", "equipmentSn", "deviceSN"):
        value = device.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _device_label(device: dict[str, Any]) -> str:
    return str(
        device.get("name")
        or device.get("deviceName")
        or device.get("productName")
        or device.get("model")
        or "Aiper device"
    )


def _load_discovery_flow(profile: str) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for guided discovery flows")

    path = DISCOVERY_FLOWS_DIR / f"{profile}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in DISCOVERY_FLOWS_DIR.glob("*.yaml")))
        raise FileNotFoundError(f"Unknown discovery profile '{profile}'. Available profiles: {available}")

    flow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(flow, dict):
        raise ValueError(f"Discovery profile {path} must contain a mapping")
    steps = flow.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"Discovery profile {path} must define at least one step")
    return flow


def _credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    username = args.username or os.environ.get("AIPER_USERNAME")
    password = args.password or os.environ.get("AIPER_PASSWORD")
    region = args.region or os.environ.get("AIPER_REGION") or "eu"

    if not username:
        raise SystemExit("Provide --username or AIPER_USERNAME")
    if not password:
        password = getpass.getpass("Aiper password: ")
    if not password:
        raise SystemExit("Provide --password or AIPER_PASSWORD")
    return username, password, region


def _make_api(args: argparse.Namespace) -> AiperApi:
    username, password, region = _credentials(args)
    api = AiperApi(username=username, password=password, region=region)
    api.mqtt_debug = bool(getattr(args, "mqtt_debug", False))
    if not api.login():
        raise SystemExit("Aiper login failed")
    return api


def _get_devices(api: AiperApi) -> list[dict[str, Any]]:
    devices = api.get_devices()
    if not devices:
        raise SystemExit("No Aiper devices found")
    return devices


def _select_sn(devices: list[dict[str, Any]], sn: str | None) -> str:
    if sn:
        return sn
    first_sn = _device_sn(devices[0])
    if not first_sn:
        raise SystemExit("Could not infer a serial number from the first device; pass --sn")
    return first_sn


def _capture_call(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    started = _utc_now()
    try:
        return {
            "name": name,
            "started": started,
            "ok": True,
            "data": fn(),
        }
    except Exception as err:
        return {
            "name": name,
            "started": started,
            "ok": False,
            "error": f"{type(err).__name__}: {err}",
        }


def capture_rest_snapshot(api: AiperApi, sn: str) -> dict[str, Any]:
    """Capture read-only REST state for a device."""
    return {
        "captured_at": _utc_now(),
        "sn": sn,
        "calls": {
            "status": _capture_call("get_device_status", lambda: api.get_device_status(sn)),
            "info": _capture_call("get_device_info", lambda: api.get_device_info(sn)),
            "history": _capture_call("get_cleaning_history", lambda: api.get_cleaning_history(sn)),
            "consumables": _capture_call("get_consumables", lambda: api.get_consumables(sn)),
            "clean_path": _capture_call("query_clean_path_setting", lambda: api.query_clean_path_setting(sn)),
        },
    }


class EventRecorder:
    """Record MQTT events to an ndjson file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.count = 0

    def __call__(self, *args: Any) -> None:
        if len(args) == 2:
            sn, payload = args
        elif len(args) == 1:
            payload = args[0]
            sn = payload.get("_sn") if isinstance(payload, dict) else None
        else:
            sn = None
            payload = {"args": list(args)}

        event = {
            "ts": _utc_now(),
            "kind": "mqtt",
            "sn": sn,
            "topic": payload.get("_topic") if isinstance(payload, dict) else None,
            "payload": payload,
        }
        _append_ndjson(self.path, event)
        self.count += 1


def _connect_and_subscribe(api: AiperApi, sn: str, recorder: EventRecorder) -> None:
    if not api.connect_mqtt():
        raise SystemExit("MQTT connection failed")
    if not api.subscribe_device(sn, recorder):
        raise SystemExit(f"MQTT subscription failed for {sn}")


def _write_manifest(path: Path, args: argparse.Namespace, command: str, sn: str | None, devices: list[dict[str, Any]]) -> None:
    _write_json(
        path / "manifest.json",
        {
            "tool": "aiper_probe",
            "command": command,
            "created_at": _utc_now(),
            "region": getattr(args, "region", None) or os.environ.get("AIPER_REGION") or "eu",
            "sn": sn,
            "devices": devices,
        },
    )


def cmd_list(args: argparse.Namespace) -> int:
    api = _make_api(args)
    try:
        devices = _get_devices(api)
        print(json.dumps(redact(devices), indent=2, sort_keys=True, default=_json_default))
        return 0
    finally:
        api.disconnect()


def cmd_snapshot(args: argparse.Namespace) -> int:
    api = _make_api(args)
    try:
        devices = _get_devices(api)
        sn = _select_sn(devices, args.sn)
        out_dir = _run_dir(args.output_dir, "snapshot")
        _write_manifest(out_dir, args, "snapshot", sn, devices)
        _write_json(out_dir / "devices.json", devices)
        _write_json(out_dir / "rest-snapshot.json", capture_rest_snapshot(api, sn))
        _write_summary(out_dir, "snapshot", sn, 0)
        print(out_dir)
        return 0
    finally:
        api.disconnect()


def cmd_observe(args: argparse.Namespace) -> int:
    api = _make_api(args)
    try:
        devices = _get_devices(api)
        sn = _select_sn(devices, args.sn)
        out_dir = _run_dir(args.output_dir, "observe")
        _write_manifest(out_dir, args, "observe", sn, devices)
        recorder = EventRecorder(out_dir / "mqtt.ndjson")
        _connect_and_subscribe(api, sn, recorder)
        api.request_shadow(sn)
        time.sleep(args.seconds)
        _write_summary(out_dir, "observe", sn, recorder.count)
        print(out_dir)
        return 0
    finally:
        api.disconnect()


def cmd_shadow(args: argparse.Namespace) -> int:
    args.seconds = max(args.seconds, 5)
    return cmd_observe(args)


def cmd_at(args: argparse.Namespace) -> int:
    if not args.allow_control:
        raise SystemExit("Refusing to send control command without --allow-control")

    api = _make_api(args)
    try:
        devices = _get_devices(api)
        sn = _select_sn(devices, args.sn)
        out_dir = _run_dir(args.output_dir, "at")
        _write_manifest(out_dir, args, "at", sn, devices)
        recorder = EventRecorder(out_dir / "mqtt.ndjson")
        _connect_and_subscribe(api, sn, recorder)
        api.request_shadow(sn)
        result = api.send_machine_at(sn, args.command, timeout=args.timeout)
        _write_json(
            out_dir / "command-result.json",
            {
                "ts": _utc_now(),
                "sn": sn,
                "command": args.command,
                "acknowledged": result,
            },
        )
        time.sleep(args.observe_seconds)
        _write_summary(out_dir, "at", sn, recorder.count)
        print(out_dir)
        return 0
    finally:
        api.disconnect()


def cmd_guided(args: argparse.Namespace) -> int:
    flow = _load_discovery_flow(args.profile)
    api = _make_api(args)
    try:
        devices = _get_devices(api)
        sn = _select_sn(devices, args.sn)
        out_dir = _run_dir(args.output_dir, f"guided-{args.profile}")
        _write_manifest(out_dir, args, "guided", sn, devices)
        _write_json(out_dir / "flow.json", flow)
        recorder = EventRecorder(out_dir / "mqtt.ndjson")
        _connect_and_subscribe(api, sn, recorder)

        for step in flow["steps"]:
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("id") or f"step-{flow['steps'].index(step) + 1}")
            prompt = str(step.get("prompt") or f"Ready for {step_id}.")
            capture = step.get("capture") if isinstance(step.get("capture"), dict) else {}
            observe_seconds = int(capture.get("observe_seconds", args.seconds))

            print(f"\n[{step_id}] {prompt}")
            input("Press Enter to start capture...")

            step_dir = out_dir / "steps" / step_id
            if capture.get("rest", True):
                _write_json(step_dir / "rest-before.json", capture_rest_snapshot(api, sn))
            if capture.get("shadow", True):
                api.request_shadow(sn)

            time.sleep(observe_seconds)

            if capture.get("rest", True):
                _write_json(step_dir / "rest-after.json", capture_rest_snapshot(api, sn))
            if capture.get("shadow", True):
                api.request_shadow(sn)

            _write_json(
                step_dir / "step.json",
                {
                    "id": step_id,
                    "prompt": prompt,
                    "observe_seconds": observe_seconds,
                    "completed_at": _utc_now(),
                },
            )

        _write_summary(out_dir, f"guided:{args.profile}", sn, recorder.count)
        print(out_dir)
        return 0
    finally:
        api.disconnect()


def _write_summary(out_dir: Path, command: str, sn: str, mqtt_events: int) -> None:
    summary = (
        f"# Aiper Probe Summary\n\n"
        f"- Command: `{command}`\n"
        f"- Serial number: `{sn}`\n"
        f"- MQTT events captured: {mqtt_events}\n"
        f"- Created at: {_utc_now()}\n\n"
        "Attach this directory when reporting discovery results. Review it first; "
        "the tool redacts sensitive keys but intentionally keeps serial numbers.\n"
    )
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--username", help="Aiper account username, or AIPER_USERNAME")
    common.add_argument("--password", help="Aiper account password, or AIPER_PASSWORD")
    common.add_argument("--region", choices=("eu", "us", "asia", "au"), help="Aiper API region")
    common.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    common.add_argument("--mqtt-debug", action="store_true", help="Enable verbose MQTT logging in AiperApi")

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", parents=[common], help="List account devices")
    list_parser.set_defaults(func=cmd_list)

    snapshot_parser = subparsers.add_parser("snapshot", parents=[common], help="Capture read-only REST state")
    snapshot_parser.add_argument("--sn", help="Device serial number; defaults to the first discovered device")
    snapshot_parser.set_defaults(func=cmd_snapshot)

    observe_parser = subparsers.add_parser("observe", parents=[common], help="Observe MQTT events")
    observe_parser.add_argument("--sn", help="Device serial number; defaults to the first discovered device")
    observe_parser.add_argument("--seconds", type=int, default=120)
    observe_parser.set_defaults(func=cmd_observe)

    shadow_parser = subparsers.add_parser("shadow", parents=[common], help="Request shadow and observe responses")
    shadow_parser.add_argument("--sn", help="Device serial number; defaults to the first discovered device")
    shadow_parser.add_argument("--seconds", type=int, default=15)
    shadow_parser.set_defaults(func=cmd_shadow)

    at_parser = subparsers.add_parser("at", parents=[common], help="Send one AT command and capture responses")
    at_parser.add_argument("--sn", help="Device serial number; defaults to the first discovered device")
    at_parser.add_argument("--command", required=True, help="AT command to send")
    at_parser.add_argument("--timeout", type=float, default=4.0, help="Ack wait timeout")
    at_parser.add_argument("--observe-seconds", type=int, default=15)
    at_parser.add_argument("--allow-control", action="store_true", help="Allow commands that can affect a real device")
    at_parser.set_defaults(func=cmd_at)

    guided_parser = subparsers.add_parser("guided", parents=[common], help="Run a guided discovery flow")
    guided_parser.add_argument("--sn", help="Device serial number; defaults to the first discovered device")
    guided_parser.add_argument("--profile", default="generic", help="Discovery flow name from tools/discovery_flows")
    guided_parser.add_argument("--seconds", type=int, default=30, help="Default observe seconds per step")
    guided_parser.set_defaults(func=cmd_guided)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
