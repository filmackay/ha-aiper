"""Constants for the Aiper integration."""
from __future__ import annotations

from enum import IntEnum, StrEnum

DOMAIN = "aiper"

# Options
CONF_ENABLE_MQTT = "enable_mqtt"
CONF_MQTT_DEBUG = "mqtt_debug"

# Control semantics
CONF_QUEUE_OFFLINE_COMMANDS = "queue_offline_commands"
CONF_POLL_INTERVAL = "poll_interval"

# Slower-changing data refresh options (hours)
CONF_HISTORY_REFRESH_HOURS = "history_refresh_hours"
CONF_CONSUMABLES_REFRESH_HOURS = "consumables_refresh_hours"
CONF_CLEAN_PATH_REFRESH_HOURS = "clean_path_refresh_hours"

DEFAULT_HISTORY_REFRESH_HOURS = 6
DEFAULT_CONSUMABLES_REFRESH_HOURS = 24
DEFAULT_CLEAN_PATH_REFRESH_HOURS = 6

# API Endpoints by region
API_ENDPOINTS = {
    "us": "https://apiamerica.aiper.com",
    "eu": "https://apieurope.aiper.com",
    "asia": "https://apiasia.aiper.com"
}

# MQTT Topics (templates with {sn} placeholder)
TOPIC_READ = "aiper/things/{sn}/upChan"
TOPIC_WRITE = "aiper/things/{sn}/downChan"
TOPIC_SHADOW_GET = "$aws/things/{sn}/shadow/get/accepted"
TOPIC_SHADOW_GET_REQUEST = "$aws/things/{sn}/shadow/get"
TOPIC_SHADOW_UPDATE = "$aws/things/{sn}/shadow/update"
TOPIC_SHADOW_UPDATE_ACCEPTED = "$aws/things/{sn}/shadow/update/accepted"
TOPIC_SHADOW_UPDATE_DELTA = "$aws/things/{sn}/shadow/update/delta"
TOPIC_SHADOW_UPDATE_DOCUMENTS = "$aws/things/{sn}/shadow/update/documents"
TOPIC_SHADOW_REPORT = "aiper/things/{sn}/shadow/report"
TOPIC_SHADOW_REPORT_X9 = "aiper/things/{sn}/app/report"

# XOR Key for message encryption
XOR_KEY = bytes([0x12, 0x34, 0x56, 0x78])

class Status(IntEnum):
    """Known Aiper device status values carried in the lower status bits."""

    IDLE = 0
    CLEANING = 1
    RETURNING = 2
    CHARGING = 3
    CHARGED = 4
    ERROR = 5
    SLEEPING = 6


STATUS_VALUE_MASK = 0x7F
STATUS_HIGH_BIT = 0x80


def status_value(status: int | Status) -> int | None:
    """Return the lower-bit status value from a raw status code."""
    try:
        return int(status) & STATUS_VALUE_MASK
    except (TypeError, ValueError):
        return None


def status_high_bit(status: int | Status) -> bool:
    """Return whether the observed high status bit is set."""
    try:
        return bool(int(status) & STATUS_HIGH_BIT)
    except (TypeError, ValueError):
        return False


def status_label(status: int | Status) -> str:
    """Return a display label for a known status code."""
    value = status_value(status)
    if value is None:
        return f"Status {status}"
    try:
        return Status(value).name.replace("_", " ").title()
    except ValueError:
        return f"Status {status}"


class Mode(IntEnum):
    """Default Aiper cleaning mode IDs.

    Mode IDs are device-specific. Use these only as fallback labels when the
    coordinator has not discovered a device-specific mode map.
    """

    SMART = 1
    FLOOR = 2
    WALL = 3
    WATERLINE = 4
    SCHEDULED = 5


class ModelMarker(StrEnum):
    """Model-name markers used for broad device-family detection."""

    SCUBA = "scuba"
    SURFER = "surfer"
    SHARK = "shark"


# Cleaning modes
#
# IMPORTANT: These numeric codes are device-specific. For Scuba X1 we have observed
# that the device reports a numeric `Machine.mode` that maps to app modes. Current mapping (based on testing): 1=Smart, 2=Floor, 3=Wall, 4=Waterline.
#
# Other modes are inferred and should be validated with the probe tooling before
# being exposed as stable Home Assistant controls.

MODE_MAP: dict[int, str] = {
    # NOTE: Mode IDs are device-specific and not documented publicly.
    # For Scuba X1 (tested): Machine.mode=1=Smart, 2=Floor, 3=Wall, 4=Waterline.
    # If your device reports different IDs, validate them with the probe tooling before exposing them.
    int(Mode.SCHEDULED): "Scheduled",
    int(Mode.SMART): "Smart",
    int(Mode.FLOOR): "Floor",
    int(Mode.WALL): "Wall",
    int(Mode.WATERLINE): "Waterline",
}

# Warning codes (partial list, expand as discovered)
WARN_CODES = {
    0: "No Warning",
    1: "Stuck",
    2: "Lifted",
    3: "Filter Full",
    4: "Low Battery",
    5: "Out of Water",
    # Add more as discovered from logs
}

# X9 Series device prefixes (use different topic pattern)
X9_SERIES_PREFIXES = ["X9", "SE", "SL"]

# Scan interval (seconds)
DEFAULT_SCAN_INTERVAL = 120
DEFAULT_PUSH_RECONCILE_INTERVAL = 3600

# Connection timeout
CONNECT_TIMEOUT = 10

# Clean path preference (Scuba X-series)
# Two observed values: 0=S-shaped (default), 1=Adaptive.
# Server responses may sometimes return -1; treat as default (0).
CLEAN_PATH_S_SHAPED = 0
CLEAN_PATH_ADAPTIVE = 1

CLEAN_PATH_MAP: dict[int, str] = {
    CLEAN_PATH_S_SHAPED: "S-shaped",
    CLEAN_PATH_ADAPTIVE: "Adaptive",
}

CLEAN_PATH_LABEL_TO_VALUE: dict[str, int] = {v: k for k, v in CLEAN_PATH_MAP.items()}

# Surfer S2 run control/status codes verified on 2026-05-03.
SURFER_RUN_STOP_MODE = 0
SURFER_RUN_START_MODE = 1
