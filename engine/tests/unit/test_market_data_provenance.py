from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openclaw_super_advisor.constants import (
    REALTIME_CLASS_COMPUTED,
    REALTIME_CLASS_REALTIME,
    REALTIME_CLASS_UNKNOWN,
)
from openclaw_super_advisor.market_data.normalization import normalize_bar, normalize_tick
from openclaw_super_advisor.market_data.schemas import BarRecord
from openclaw_super_advisor.market_data.timeframes import Timeframe


def test_normalized_tick_has_explicit_mt5_provenance() -> None:
    received = datetime(2026, 6, 15, 1, 0, tzinfo=UTC)
    tick = normalize_tick(
        "XAUUSD",
        "XAUUSD.r",
        {
            "time_msc": int(received.timestamp() * 1000),
            "bid": 2300.0,
            "ask": 2300.5,
            "last": 2300.25,
            "volume": 1,
            "volume_real": 1,
            "flags": 0,
        },
        received,
        0.01,
    )

    assert tick.source == "mt5_tick"
    assert tick.source_system == "MetaTrader5"
    assert tick.fetched_at_utc == received
    assert tick.realtime_class == REALTIME_CLASS_REALTIME


def test_normalized_bar_has_explicit_mt5_provenance() -> None:
    as_of = datetime(2026, 6, 15, 1, 5, tzinfo=UTC)
    bar = normalize_bar(
        "XAUUSD",
        "XAUUSD.r",
        Timeframe.M1,
        {
            "time": int(datetime(2026, 6, 15, 1, 0, tzinfo=UTC).timestamp()),
            "open": 2300.0,
            "high": 2302.0,
            "low": 2299.0,
            "close": 2301.0,
            "tick_volume": 10,
            "real_volume": 5,
            "spread": 4,
        },
        as_of,
    )

    assert bar.source == "mt5_bar"
    assert bar.source_system == "MetaTrader5"
    assert bar.fetched_at_utc == as_of
    assert bar.realtime_class == REALTIME_CLASS_REALTIME


def test_legacy_record_defaults_to_unknown_not_realtime() -> None:
    now = datetime(2026, 6, 15, tzinfo=UTC)
    record = BarRecord(
        schema_version="legacy",
        collector_version="legacy",
        logical_symbol="XAUUSD",
        broker_symbol="XAUUSD",
        timeframe="M1",
        open_time_utc=now,
        close_time_utc=now,
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        tick_volume=1,
        real_volume=1,
        spread=1,
        is_closed=True,
        bar_id="legacy",
        data_quality="valid",
        quality_flags=(),
    )

    assert record.realtime_class == REALTIME_CLASS_UNKNOWN


def test_computed_record_requires_formula_version() -> None:
    now = datetime(2026, 6, 15, tzinfo=UTC)
    with pytest.raises(ValueError, match="formula_version"):
        BarRecord(
            schema_version="p2.4",
            collector_version="test",
            logical_symbol="FX_BASKET_COMPUTED",
            broker_symbol="FX_BASKET_COMPUTED",
            timeframe="M1",
            open_time_utc=now,
            close_time_utc=now,
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            tick_volume=1,
            real_volume=1,
            spread=1,
            is_closed=True,
            bar_id="computed",
            data_quality="valid",
            quality_flags=(),
            source="fx_basket",
            source_system="python",
            fetched_at_utc=now,
            realtime_class=REALTIME_CLASS_COMPUTED,
        )
