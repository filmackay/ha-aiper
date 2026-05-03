"""Tests for Aiper payload parser helpers."""

from __future__ import annotations

from datetime import timezone

from custom_components.aiper.coordinator import _clean_path_value, _parse_cleaning_history, _parse_consumables
from custom_components.aiper.sensor import _collect_warning_codes, _normalize_warn_code


def test_clean_path_value_normalizes_common_variants() -> None:
    """Clean-path payloads vary across REST, shadow, and firmware reports."""
    assert _clean_path_value(-1) == 0
    assert _clean_path_value("0") == 0
    assert _clean_path_value("Adaptive") == 1
    assert _clean_path_value("S-shaped") == 0
    assert _clean_path_value("unknown") is None


def test_warning_code_normalization_and_collection() -> None:
    """Warning codes should be stable for user-facing warning sensors."""
    assert _normalize_warn_code(12) == "e12"
    assert _normalize_warn_code("E-013") == "e13"
    assert _normalize_warn_code(0) is None

    assert _collect_warning_codes(
        {
            "warnCodeList": [12, "e13", 0],
            "errorCode": "14",
        }
    ) == ["e12", "e13", "e14"]


def test_parse_cleaning_history_extracts_totals_and_records() -> None:
    """History parsing should handle common list wrappers and minute totals."""
    total_count, total_hours, records = _parse_cleaning_history(
        {
            "data": {
                "totalCleanCount": 2,
                "totalCleanMinutes": 150,
                "list": [
                    {
                        "mode": 1,
                        "startTime": "2026-05-01 10:00:00",
                        "duration": "90 min",
                    },
                    {
                        "mode": 2,
                        "startTime": "2026-04-30 10:00:00",
                        "duration": "60 min",
                    },
                ],
            }
        }
    )

    assert total_count == 2
    assert total_hours == 2.5
    assert [record["duration_min"] for record in records] == [90.0, 60.0]
    assert records[0]["start"].tzinfo == timezone.utc


def test_parse_cleaning_history_handles_surfer_s2_long_runs() -> None:
    """Surfer S2 history can contain multi-hour skimming sessions."""
    total_count, total_hours, records = _parse_cleaning_history(
        {
            "code": "200",
            "data": {
                "list": [
                    {
                        "mode": "5",
                        "cleanTime": 14401,
                        "cleanTimeMin": 240,
                        "utcStartTimeStamp": 1777741200000,
                    },
                    {
                        "mode": "1",
                        "cleanTime": 49713,
                        "cleanTimeMin": 828,
                        "utcStartTimeStamp": 1777691487000,
                    },
                ],
                "pageNum": 1,
                "pageSize": 20,
                "total": 2,
            },
        }
    )

    assert total_count == 2
    assert total_hours == 17.8
    assert [record["duration_min"] for record in records] == [240.0, 828.0]


def test_parse_consumables_normalizes_remaining_percent_and_timestamp() -> None:
    """Consumables should expose stable names and derived percent-left values."""
    consumables = _parse_consumables(
        {
            "data": {
                "list": [
                    {
                        "id": "brush",
                        "name": "Roller Brush",
                        "componentReplaceRemainHour": "4380",
                        "longestUseTime": "8760",
                        "lastChangeTime": 1_714_608_000_000,
                    }
                ]
            }
        }
    )

    assert consumables == [
        {
            "key": "brush_roller_brush",
            "name": "Roller Brush",
            "remaining_hours": 4380.0,
            "percent_left": 50.0,
            "last_replacement": consumables[0]["last_replacement"],
            "raw": {
                "id": "brush",
                "name": "Roller Brush",
                "componentReplaceRemainHour": "4380",
                "longestUseTime": "8760",
                "lastChangeTime": 1_714_608_000_000,
            },
        }
    ]
    assert consumables[0]["last_replacement"].tzinfo == timezone.utc
