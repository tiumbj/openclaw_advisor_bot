from __future__ import annotations

from datetime import timedelta
from enum import StrEnum


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


TIMEFRAME_SECONDS = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.H1: 3600,
    Timeframe.H4: 14400,
    Timeframe.D1: 86400,
}
SUPPORTED_TIMEFRAMES = tuple(item.value for item in Timeframe)


def ensure_timeframe(value: str | Timeframe) -> Timeframe:
    if isinstance(value, Timeframe):
        return value
    try:
        return Timeframe(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported timeframe: {value}") from exc


def timeframe_seconds(value: str | Timeframe) -> int:
    return TIMEFRAME_SECONDS[ensure_timeframe(value)]


def timeframe_delta(value: str | Timeframe) -> timedelta:
    return timedelta(seconds=timeframe_seconds(value))
