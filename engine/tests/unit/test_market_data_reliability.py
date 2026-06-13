from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from openclaw_super_advisor.market_data import build_market_data_service
from openclaw_super_advisor.market_data.fake_backend import FakeMt5Backend, FakeMt5Scenario
from openclaw_super_advisor.market_data.normalization import normalize_tick
from openclaw_super_advisor.market_data.quality import normalize_tick_batch
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.storage.atomic import atomic_write
from openclaw_super_advisor.storage.parquet_store import ParquetStore


def _enable_mt5(sample_project: Path) -> Path:
    env_path = sample_project / "state" / ".env"
    env_text = env_path.read_text(encoding="utf-8").replace("MT5_ENABLED=false", "MT5_ENABLED=true")
    env_path.write_text(env_text, encoding="utf-8")
    return env_path


def _tick_payload(
    *,
    time_msc: int,
    bid: float,
    ask: float,
    last: float,
    volume: float = 1.0,
    volume_real: float = 1.0,
) -> dict[str, object]:
    return {
        "time": time_msc // 1000,
        "time_msc": time_msc,
        "bid": bid,
        "ask": ask,
        "last": last,
        "volume": volume,
        "volume_real": volume_real,
        "flags": 1,
    }


def _bar_payload(
    *,
    timestamp: datetime,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> dict[str, object]:
    return {
        "time": int(timestamp.timestamp()),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "tick_volume": 10,
        "spread": 5,
        "real_volume": 0,
    }


def _scenario_with_data() -> FakeMt5Scenario:
    return FakeMt5Scenario(
        symbols=[
            {
                "name": "XAUUSD.",
                "description": "Gold",
                "path": "Metals",
                "visible": True,
                "point": 0.01,
                "digits": 2,
            }
        ],
        ticks_by_symbol={
            "XAUUSD.": [
                _tick_payload(time_msc=1767225720000, bid=2600.0, ask=2600.2, last=2600.1),
            ]
        },
        latest_tick_by_symbol={
            "XAUUSD.": _tick_payload(
                time_msc=1767225780000,
                bid=2600.1,
                ask=2600.3,
                last=2600.2,
            )
        },
        bars_by_symbol_and_timeframe={
            ("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1): [
                _bar_payload(
                    timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
                    open_price=2600.0,
                    high_price=2603.0,
                    low_price=2599.0,
                    close_price=2602.0,
                )
            ]
        },
    )


def test_symbols_get_none_retries_and_recovers(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    scenario = _scenario_with_data()
    scenario.last_error_value = (1002, "symbols unavailable")
    scenario.symbols_get_sequence = [None, scenario.symbols]
    backend = FakeMt5Backend(scenario)
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=backend,
    )

    discovered = service.discover_symbols()

    assert discovered["count"] == 1
    assert backend.initialize_calls == 2
    assert backend.shutdown_calls == 1
    service.close()


def test_tick_none_result_retries_and_recovers(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    scenario = _scenario_with_data()
    scenario.last_error_value = (1003, "tick stream unavailable")
    scenario.copy_ticks_range_sequence = {
        "XAUUSD.": [
            None,
            scenario.ticks_by_symbol["XAUUSD."],
        ]
    }
    backend = FakeMt5Backend(scenario)
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=backend,
    )

    report = service.collect_once(now=datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC), dry_run=True)

    assert report["tick_count"] >= 2
    assert backend.initialize_calls >= 2
    assert backend.shutdown_calls >= 1
    service.close()


def test_bar_none_result_retries_and_recovers(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    scenario = _scenario_with_data()
    scenario.last_error_value = (1004, "bar stream unavailable")
    scenario.copy_rates_range_sequence = {
        ("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1): [
            None,
            scenario.bars_by_symbol_and_timeframe[("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1)],
        ]
    }
    backend = FakeMt5Backend(scenario)
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=backend,
    )

    report = service.collect_once(now=datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC), dry_run=True)

    assert report["bar_count"] >= 1
    assert backend.initialize_calls >= 2
    assert backend.shutdown_calls >= 1
    service.close()


def test_tick_time_collision_is_reported() -> None:
    tick_one = normalize_tick(
        "XAUUSD",
        "XAUUSD.",
        _tick_payload(time_msc=1767225780123, bid=2600.1, ask=2600.3, last=2600.2),
        datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC),
        0.01,
    )
    tick_two = normalize_tick(
        "XAUUSD",
        "XAUUSD.",
        _tick_payload(time_msc=1767225780123, bid=2600.2, ask=2600.4, last=2600.3),
        datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC),
        0.01,
    )

    records, incidents = normalize_tick_batch([tick_one, tick_two])

    assert len(records) == 2
    assert any(item.event_kind == "tick_time_collision" for item in incidents)


def test_partial_tick_payload_does_not_advance_cursor(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    scenario = _scenario_with_data()
    scenario.copy_ticks_range_sequence = {
        "XAUUSD.": [
            [
                {
                    "time_msc": 1767225780123,
                    "ask": 2600.3,
                    "last": 2600.2,
                }
            ]
        ]
    }
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=FakeMt5Backend(scenario),
    )

    with pytest.raises(ValueError, match="tick bid/ask prices must be positive"):
        service.collect_once(now=datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC), dry_run=False)

    assert service.state_store.get_cursor("ticks", "XAUUSD") is None
    service.close()


def test_quality_incident_deduplicates_with_hit_count(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    scenario = _scenario_with_data()
    scenario.ticks_by_symbol["XAUUSD."] = [
        _tick_payload(time_msc=1767225000000, bid=2600.0, ask=2600.2, last=2600.1)
    ]
    scenario.latest_tick_by_symbol["XAUUSD."] = _tick_payload(
        time_msc=1767225000000, bid=2600.0, ask=2600.2, last=2600.1
    )
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=FakeMt5Backend(scenario),
    )
    observed_now = datetime(2026, 1, 1, 0, 10, 0, tzinfo=UTC)

    service.collect_once(now=observed_now, dry_run=False)
    service.collect_once(now=observed_now, dry_run=False)

    with service.state_store.connect() as connection:
        row = connection.execute(
            """
            SELECT hit_count
            FROM quality_incidents
            WHERE incident_key = ?
            """,
            ("stale_tick:XAUUSD:tick:XAUUSD:XAUUSD.:1767225000000:2600.00000000:2600.20000000:2600.10000000:1.00000000",),
        ).fetchone()
    assert row is not None
    assert int(row["hit_count"]) == 2
    service.close()


def test_atomic_write_cleans_temp_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_path = tmp_path / "artifact.txt"

    def _writer(path: Path) -> None:
        path.write_text("payload", encoding="utf-8")

    def _replace(_source: object, _target: object) -> object:
        raise PermissionError("simulated replace failure")

    monkeypatch.setattr(os, "replace", _replace)

    with pytest.raises(PermissionError):
        atomic_write(target_path, _writer)

    assert not target_path.exists()
    assert not (tmp_path / ".tmp-artifact.txt").exists()


def test_parquet_validation_failure_leaves_no_visible_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ParquetStore(tmp_path)
    record = normalize_tick(
        "XAUUSD",
        "XAUUSD.",
        _tick_payload(time_msc=1767225780123, bid=2600.1, ask=2600.3, last=2600.2),
        datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC),
        0.01,
    )

    def _read_schema(_path: object) -> object:
        raise ValueError("corrupted parquet temp file")

    monkeypatch.setattr(pq, "read_schema", _read_schema)

    with pytest.raises(ValueError, match="corrupted parquet temp file"):
        store.write_ticks([record])

    assert not list(tmp_path.rglob("*.parquet"))


def test_sqlite_transaction_rolls_back_on_error(tmp_path: Path) -> None:
    database_path = tmp_path / "state.db"
    from openclaw_super_advisor.storage.sqlite_state import SQLiteStateStore

    store = SQLiteStateStore(database_path)

    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction() as connection:
            connection.execute(
                """
                INSERT INTO symbol_mappings (
                    logical_symbol, broker_symbol, aliases_json, description,
                    point, digits, visible, updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("XAUUSD", "XAUUSD.", "[]", "Gold", 0.01, 2, 1, "2026-01-01T00:00:00Z"),
            )
            connection.execute(
                """
                INSERT INTO symbol_mappings (
                    logical_symbol, broker_symbol, aliases_json, description,
                    point, digits, visible, updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("XAUUSD", "XAUUSD-second", "[]", "Gold", 0.01, 2, 1, "2026-01-01T00:00:01Z"),
            )

    with store.connect() as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM symbol_mappings").fetchone()
    assert row is not None
    assert int(row["count"]) == 0
