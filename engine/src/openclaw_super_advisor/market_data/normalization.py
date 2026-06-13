from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from .._version import __version__
from .backend import DiscoveredSymbol
from .schemas import BarRecord, TickRecord
from .timeframes import Timeframe, timeframe_delta

MARKET_DATA_SCHEMA_VERSION = "1.2.0"


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware UTC")
    return value.astimezone(UTC)


def to_iso_z(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def from_iso_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _field(payload: object, name: str) -> object:
    if isinstance(payload, dict):
        return payload.get(name)
    if hasattr(payload, "__getitem__"):
        try:
            item = cast(Any, payload)[name]
        except (KeyError, IndexError, TypeError, ValueError):
            item = None
        if item is not None:
            return item
    return getattr(payload, name, None)


def as_text(payload: object, name: str) -> str:
    value = _field(payload, name)
    return "" if value is None else str(value)


def as_float(payload: object, name: str) -> float:
    value = _field(payload, name)
    if value is None:
        return 0.0
    if not isinstance(value, str | bytes | int | float):
        raise ValueError(f"{name} must be numeric, got {value!r}")
    return float(value)


def as_int(payload: object, name: str) -> int:
    value = _field(payload, name)
    if value is None:
        return 0
    if not isinstance(value, str | bytes | int | float):
        raise ValueError(f"{name} must be integer-like, got {value!r}")
    return int(value)


def epoch_seconds_to_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value)
    if not isinstance(value, int | float):
        raise ValueError(f"epoch seconds must be numeric, got {value!r}")
    return datetime.fromtimestamp(float(value), tz=UTC)


def epoch_milliseconds_to_utc(value: object) -> datetime:
    if not isinstance(value, int | float):
        raise ValueError(f"epoch milliseconds must be numeric, got {value!r}")
    return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)


def discovered_symbol_from_payload(payload: object) -> DiscoveredSymbol:
    return DiscoveredSymbol(
        broker_symbol=as_text(payload, "name"),
        description=as_text(payload, "description"),
        path=as_text(payload, "path"),
        visible=bool(_field(payload, "visible")),
        point=as_float(payload, "point"),
        digits=as_int(payload, "digits"),
    )


def normalize_tick(
    logical_symbol: str,
    broker_symbol: str,
    payload: object,
    received_at_utc: datetime,
    point: float,
) -> TickRecord:
    market_time_msc = as_int(payload, "time_msc")
    if market_time_msc <= 0:
        market_time_msc = as_int(payload, "time") * 1000
    market_time_utc = epoch_milliseconds_to_utc(market_time_msc)
    bid = as_float(payload, "bid")
    ask = as_float(payload, "ask")
    last = as_float(payload, "last")
    volume = as_float(payload, "volume")
    volume_real = as_float(payload, "volume_real")
    flags = as_int(payload, "flags")
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("tick bid/ask prices must be positive with ask >= bid")
    spread_points = round((ask - bid) / point) if point > 0 else 0
    sequence_id = (
        f"{logical_symbol}:{broker_symbol}:{market_time_msc}:"
        f"{bid:.8f}:{ask:.8f}:{last:.8f}:{volume_real:.8f}"
    )
    return TickRecord(
        schema_version=MARKET_DATA_SCHEMA_VERSION,
        collector_version=__version__,
        logical_symbol=logical_symbol,
        broker_symbol=broker_symbol,
        market_time_utc=market_time_utc,
        market_time_msc=market_time_msc,
        received_at_utc=ensure_utc(received_at_utc),
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        volume_real=volume_real,
        flags=flags,
        spread_points=spread_points,
        sequence_id=sequence_id,
        data_quality="valid",
        quality_flags=(),
    )


def normalize_bar(
    logical_symbol: str,
    broker_symbol: str,
    timeframe: Timeframe,
    payload: object,
    as_of_utc: datetime,
) -> BarRecord:
    open_time_utc = epoch_seconds_to_utc(_field(payload, "time"))
    close_time_utc = open_time_utc + timeframe_delta(timeframe)
    open_price = as_float(payload, "open")
    high_price = as_float(payload, "high")
    low_price = as_float(payload, "low")
    close_price = as_float(payload, "close")
    tick_volume = as_int(payload, "tick_volume")
    real_volume = as_int(payload, "real_volume")
    spread = as_int(payload, "spread")
    prices = (open_price, high_price, low_price, close_price)
    if any(price <= 0 for price in prices):
        raise ValueError("bar prices must be positive")
    if high_price < max(open_price, close_price, low_price):
        raise ValueError("bar high must be >= open, close, and low")
    if low_price > min(open_price, close_price, high_price):
        raise ValueError("bar low must be <= open, close, and high")
    if tick_volume < 0 or real_volume < 0:
        raise ValueError("bar volumes must be >= 0")
    bar_id = f"{logical_symbol}:{timeframe.value}:{int(open_time_utc.timestamp())}"
    return BarRecord(
        schema_version=MARKET_DATA_SCHEMA_VERSION,
        collector_version=__version__,
        logical_symbol=logical_symbol,
        broker_symbol=broker_symbol,
        timeframe=timeframe.value,
        open_time_utc=open_time_utc,
        close_time_utc=close_time_utc,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        tick_volume=tick_volume,
        real_volume=real_volume,
        spread=spread,
        is_closed=close_time_utc <= ensure_utc(as_of_utc),
        bar_id=bar_id,
        data_quality="valid",
        quality_flags=(),
    )
