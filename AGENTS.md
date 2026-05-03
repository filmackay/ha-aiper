# Repository Instructions

## Purpose

This repository is a HACS-compatible Home Assistant custom integration for Aiper pool cleaners. It connects to Aiper's cloud REST API and optional AWS IoT MQTT control plane to expose sensors, binary sensors, select controls, diagnostics, and a raw AT-command service.

## Stack

- Python Home Assistant custom component under `custom_components/aiper`.
- Home Assistant config flow, options flow, `DataUpdateCoordinator`, and `CoordinatorEntity` platforms.
- Synchronous cloud client in `api.py` using `requests`; Home Assistant calls it through executor jobs.
- AWS IoT MQTT via `AWSIoTPythonSDK`, using temporary Cognito credentials from Aiper's API.
- HACS distribution with `hacs.json` and a zip release artifact.

## Architecture

- `custom_components/aiper/__init__.py` handles config-entry setup, coordinator creation, platform forwarding, MQTT subscription setup, legacy entity cleanup, and the `aiper.send_at_command` service.
- `custom_components/aiper/api.py` owns all Aiper REST, encryption, AWS credential exchange, MQTT publish/subscribe, command acknowledgement, and low-level protocol handling.
- `custom_components/aiper/coordinator.py` normalizes device list, status, info, history, consumables, clean-path state, and MQTT shadow updates into the data shape consumed by entities.
- `custom_components/aiper/sensor.py`, `binary_sensor.py`, and `select.py` define entity descriptions and entity behavior.
- `custom_components/aiper/crypto.py` implements the Aiper AES/RSA request envelope.
- `custom_components/aiper/diagnostics.py` redacts config/runtime data for issue reports.

## Current State

The integration is functional but carries reverse-engineering complexity and limited development scaffolding. There is no test suite, no lint/type configuration, no local Home Assistant docker compose, and no dependency/dev requirements file.

The code intentionally contains compatibility paths for regional API and firmware variance. Preserve that behavior unless a test or live payload proves a branch is obsolete.

## Working Rules

- Keep changes small and Home Assistant idiomatic. Prefer `ConfigEntry`, `DataUpdateCoordinator`, entity descriptions, translations, repairs/reauth, and diagnostics patterns over custom machinery.
- Do not make live Aiper API calls in tests. Mock `AiperApi` and cover parser/coordinator/entity behavior with representative payload fixtures.
- Treat credentials, tokens, Cognito identities, MQTT payloads, and serial numbers as sensitive. Do not add logs that expose them.
- The REST client is synchronous by design today. If converting to async, do it as a dedicated refactor with tests rather than mixing styles opportunistically.
- Before touching command/control behavior, read `api.py`, `coordinator.py`, and `select.py`; command state is split across all three.
- Before changing entity unique IDs or names, check the legacy cleanup/migration code in `__init__.py` so existing dashboards are not broken accidentally.
- After changes, run at least Python compilation and any available tests. Once test tooling exists, prefer targeted pytest runs plus Home Assistant component tests for config flow and setup/unload.

## Modernization Priorities

1. Add a minimal development environment: `docker-compose.yml`, `ha-config/configuration.yaml`, `.gitignore`, and documented commands.
2. Add pytest/Home Assistant test scaffolding for config flow, setup/unload, diagnostics, parser helpers, and entity state mapping.
3. Tighten config-flow error classification so connection failures, invalid auth, and unexpected payloads produce distinct user-facing errors.
4. Update manifest metadata toward current Home Assistant expectations, including dependency transparency and quality-scale fields where appropriate.
5. Reduce duplicate helper functions across entity/coordinator modules once tests protect behavior.
