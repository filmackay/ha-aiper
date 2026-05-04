# Surfer

## Scope

This file covers devices classified as the `surfer` family, especially the
verified Surfer S2. The family is detected when a discovered model field such as
`model`, `deviceModel`, `modelName`, or `productName` contains `surfer`.

Live verification was performed against a Surfer S2 in the `asia` region on
2026-05-03.

## Known

Surfer devices use the normal Aiper account, REST, Cognito, AWS IoT, and shadow
flow used by the integration.

The Surfer S2 supports these integration capabilities:

- common cloud/shadow diagnostics
- read-only mode/run-context sensor
- read-only running binary sensor
- run switch
- propeller maintenance, when the consumables payload exposes propeller data
- solar charging, when MQTT shadow `Machine.solar_status` is present

The Surfer S2 does not currently expose a cleaning mode select in Home
Assistant. Live command tests showed `Machine.mode` is run context rather than
the same selectable cleaning-mode concept used by Scuba devices.

Clean-path REST and MQTT contracts are documented below because they were
verified during discovery, but clean-path is not currently exposed as a Surfer
Home Assistant control. The intended Surfer control surface is on/off run
control only.

The verified history request is:

```json
{"sn":"<sn>","pageNum":1,"pageSize":20}
```

The verified consumables request is:

```json
{"sn":"<sn>"}
```

The verified clean-path query is encrypted REST:

```text
POST /equipmentCleanPathSetting/getCleanPathSetting
```

```json
{"sn":"<sn>"}
```

The verified clean-path response includes `data.cleanPath`. Values are numeric:

- `0`: S-shaped
- `1`: Adaptive
- `-1`: treat as default `0`

The verified clean-path update is encrypted REST:

```text
POST /equipmentCleanPathSetting/updateCleanPathSetting
```

```json
{"sn":"<sn>","cleanPath":0}
```

or:

```json
{"sn":"<sn>","cleanPath":1}
```

The verified immediate clean-path apply command is a plain MQTT down-channel AT
command:

```text
AT+AUTO=<value>
```

The verified run commands are:

```text
AT+MODE=1
AT+MODE=0
```

MQTT down-channel command payloads for Surfer S2 are plain compact JSON. The
payload shape is:

```json
{"type":"Machine","data":{"sn":"<sn>","timeZone":"UTC+10","cmd":"AT+MODE=1"},"res":0,"chksum":12345}
```

The checksum is CRC16 over the compact JSON `data` object. The device sends AT
acknowledgements on `upChan`, usually containing `+OK` or `+ERROR`.

## Mode And Run Context

Surfer S2 status and mode behavior verified on 2026-05-03:

- schedule-window cleaning reported `Machine.status=129` and `Machine.mode=5`
- manual cleaning after `AT+MODE=1` reported `Machine.status=129` and
  `Machine.mode=1`
- stopping with `AT+MODE=0` reported `Machine.status=128` and `Machine.mode=5`
- `AT+MODE=2`, `AT+MODE=3`, `AT+MODE=4`, and `AT+MODE=5` returned `+ERROR`
  while the device was already cleaning manually
- `AT+MODE=2`, `AT+MODE=3`, and `AT+MODE=4` returned `+ERROR` while the
  device was cleaning in a schedule window

This means Surfer `Machine.mode` should be treated as read-only run context:
`1` has been verified as manual cleaning and `5` has been verified as scheduled
cleaning or idle-after-stop context. Surfer `Machine.status` appears to carry
the normal status value in the lower seven bits, with the high bit indicating
the device is running. For example, `128` is `0x80 | 0` (running flag set with
base idle) and `129` is `0x80 | 1` (running flag set with base cleaning).
When the run is stopped from the app, the device reports `Machine.status=0` and
`Machine.mode=5`. Home Assistant should show the general read entities
`Status`, `Running`, and `Mode`; the Surfer-specific command entity is only the
`Run` switch. The mode sensor should show `Off` when the high status bit is
clear, not from a reported `Machine.mode=0`. Surfer should not be exposed
through the Scuba/Shark cleaning-mode select unless new evidence proves a
Surfer firmware exposes selectable cleaning modes.

## Rejected Or Redundant During Verification

The following were tested against Surfer S2 and should not be used for Surfer
runtime behavior without new evidence:

- encrypted MQTT down-channel payloads: published but did not acknowledge
- `AT+WORKMODE=<mode_id>`: acknowledged as `+ERROR`
- `AUTO <value>`: no useful acknowledgement observed
- `AT+CPATH=<value>`: no useful acknowledgement observed
- `AT+CLEANPATH=<value>`: acknowledged as `+ERROR`
- `AT+SETPATH=<value>`: acknowledged as `+ERROR`
- clean-path REST update key `cleanPathSetting`: application code `6002`
- clean-path REST update key `clean_path_setting`: application code `6002`
- Scuba-style mode select for Surfer: observed mode values represent manual
  versus scheduled run context, and most `AT+MODE=<id>` values returned
  `+ERROR`

## Unknown

- Whether all Surfer revisions share the Surfer S2 contracts.
- Whether clean-path values beyond `0` and `1` exist on newer firmware.
- Whether shadow reported state ever carries an authoritative clean-path value
  for Surfer. The verified Surfer S2 relied on REST for persisted preference.
- Whether return-to-charge or pause commands are exposed through the same AT
  command family.

## At Risk

- MQTT is optional in the integration, but run control depends on MQTT
  down-channel commands. If AWS IoT connection fails, REST polling can still
  expose state, but controls are unavailable.
- The device classification depends on model strings. A Surfer device with a
  nonstandard model string may fall back to `unknown` and lose verified controls.
- The cloud clean-path endpoint appears current and verified for Surfer S2, but
  Aiper can change backend contracts without firmware changes.
- Mode IDs are not public. Incorrect labels are more likely than incorrect
  numeric command transport, so labels should stay conservative until verified.
- The high status bit has been inferred as the running flag from app stop and
  MQTT command probes. The integration still preserves raw status in diagnostic
  attributes because the cloud protocol is not public.
- Probe output contains real device/cloud payloads. Keep credentials, tokens,
  Cognito IDs, AWS secrets, and serial-adjacent sensitive data out of committed
  fixtures.

## Verification Commands

Useful non-live tests:

```bash
uv run pytest tests/test_api_clean_path.py tests/test_profiles.py tests/test_select.py tests/test_platform_entities.py
```

Useful live probes, with credentials in environment variables:

```bash
uv run tools/aiper_probe.py history --region asia --sn <sn>
uv run tools/aiper_probe.py consumables --region asia --sn <sn>
uv run tools/aiper_probe.py contract-verify --region asia --sn <sn> --allow-control
uv run tools/aiper_probe.py guided --region asia --profile surfer-s2 --sn <sn>
```
