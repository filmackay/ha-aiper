# Device Model Notes

This directory records device-family evidence used by the integration. These
notes are device-focused: what is known for a model type, what remains unknown,
and what is operationally risky for Home Assistant support.

Runtime family detection currently lives in
`custom_components/aiper/profiles.py` and uses model-name markers:

- `surfer`: model string contains `surfer`
- `scuba`: model string contains `scuba`
- `shark`: model string contains `shark`
- `unknown`: no known marker matched

These files are not runtime configuration. They are engineering notes for
maintainers. Runtime behavior must still be backed by parser tests, coordinator
tests, and, where possible, probe output from `tools/aiper_probe.py`.

## Model Types

- [Surfer](surfer.md)
- [Scuba](scuba.md)
- [Shark](shark.md)
- [Unknown](unknown.md)

## Shared Cloud And MQTT Details

All currently supported model types use Aiper cloud credentials and regional
REST endpoints from `custom_components/aiper/const.py`:

- `eu`: `https://apieurope.aiper.com`
- `us`: `https://apiamerica.aiper.com`
- `asia`: `https://apiasia.aiper.com`
- `au`: aliases to the Asia/Pacific backend

REST calls use the encrypted Aiper request envelope for most device operations.
MQTT uses AWS IoT credentials obtained from Aiper's `getOpenIdToken` and Cognito
exchange flow.

Common MQTT topics:

- up channel: `aiper/things/{sn}/upChan`
- down channel: `aiper/things/{sn}/downChan`
- shadow get request: `$aws/things/{sn}/shadow/get`
- shadow get accepted: `$aws/things/{sn}/shadow/get/accepted`
- shadow update: `$aws/things/{sn}/shadow/update`
- shadow update accepted: `$aws/things/{sn}/shadow/update/accepted`
- shadow update delta: `$aws/things/{sn}/shadow/update/delta`
- shadow update documents: `$aws/things/{sn}/shadow/update/documents`
- shadow report: `aiper/things/{sn}/shadow/report`
- X9-style app report: `aiper/things/{sn}/app/report`

Common integration capabilities:

- battery
- online
- status
- warning
- wifi
- history
- firmware
- MQTT shadow
- bluetooth diagnostics
- device link diagnostics

The shared capabilities are broad assumptions from the integration's current
payload normalizers. Device-family docs below describe where support is verified
or still tentative.
