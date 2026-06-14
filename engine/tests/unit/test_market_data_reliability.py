from __future__ import annotations

import os
import sqlite3
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter

import pyarrow.parquet as pq
import pytest

from openclaw_super_advisor.market_data import build_market_data_service
from openclaw_super_advisor.market_data.collector import (
    MarketDataService,
    MarketDataSettings,
    SymbolTarget,
)
from openclaw_super_advisor.market_data.fake_backend import FakeMt5Backend, FakeMt5Scenario
from openclaw_super_advisor.market_data.normalization import normalize_tick
from openclaw_super_advisor.market_data.quality import normalize_tick_batch
from openclaw_super_advisor.market_data.schemas import BarRecord, TickRecord
from openclaw_super_advisor.market_data.timeframes import Timeframe
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.storage.atomic import atomic_write
from openclaw_super_advisor.storage.parquet_store import ParquetStore
from openclaw_super_advisor.storage.sqlite_state import SQLiteStateStore


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

    tick_count = report["tick_count"]
    assert isinstance(tick_count, int)
    assert tick_count >= 2
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

    bar_count = report["bar_count"]
    assert isinstance(bar_count, int)
    assert bar_count >= 1
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
            (
                "stale_tick:XAUUSD:tick:XAUUSD:XAUUSD.:1767225000000:2600.00000000:2600.20000000:2600.10000000:1.00000000",
            ),
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


class InstrumentedParquetStore(ParquetStore):
    def __init__(self, root_dir: Path) -> None:
        super().__init__(root_dir)
        self.write_latencies_ms: list[float] = []

    def write_ticks(self, records: list[TickRecord], dry_run: bool = False) -> list[Path]:
        started = perf_counter()
        written = super().write_ticks(records, dry_run=dry_run)
        self.write_latencies_ms.append((perf_counter() - started) * 1000)
        return written

    def write_bars(self, records: list[BarRecord], dry_run: bool = False) -> list[Path]:
        started = perf_counter()
        written = super().write_bars(records, dry_run=dry_run)
        self.write_latencies_ms.append((perf_counter() - started) * 1000)
        return written


class SoakFakeMt5Backend:
    backend_name = "fake-mt5-soak"

    def __init__(self, start_at: datetime) -> None:
        self.start_at = start_at
        self.last_error_value: tuple[int, str] = (0, "ok")
        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.recovery_count = 0
        self._latest_tick_by_symbol: dict[str, dict[str, object]] = {}
        self._failed_once: set[tuple[str, int, int | None]] = set()
        self._tick_failure_cycles = {6, 18, 30, 42}
        self._bar_failure_cycles = {
            (12, FakeMt5Backend.TIMEFRAME_H1),
            (24, FakeMt5Backend.TIMEFRAME_H4),
            (36, FakeMt5Backend.TIMEFRAME_H1),
            (48, FakeMt5Backend.TIMEFRAME_D1),
        }

    def initialize(self) -> bool:
        self.initialize_calls += 1
        return True

    def shutdown(self) -> None:
        self.shutdown_calls += 1

    def version(self) -> tuple[int, ...] | None:
        return (5, 0, 0)

    def terminal_info(self) -> object | None:
        return {"path": "C:\\MT5\\terminal64.exe"}

    def account_info(self) -> object | None:
        return {"server": "demo-server", "login": 123456}

    def last_error(self) -> object:
        return self.last_error_value

    def symbols_get(self) -> object | None:
        return [
            {
                "name": "XAUUSD.",
                "description": "Gold",
                "path": "Metals",
                "visible": True,
                "point": 0.01,
                "digits": 2,
            }
        ]

    def symbol_info(self, symbol: str) -> object | None:
        symbols = self.symbols_get()
        assert isinstance(symbols, list)
        return next((item for item in symbols if item["name"] == symbol), None)

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        _ = (symbol, enable)
        return True

    def symbol_info_tick(self, symbol: str) -> object | None:
        return self._latest_tick_by_symbol.get(symbol)

    def copy_rates_from(
        self, symbol: str, timeframe: int, date_from: object, count: int
    ) -> object | None:
        _ = count
        return self.copy_rates_range(symbol, timeframe, date_from, self.start_at)

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> object | None:
        _ = (start_pos, count)
        return self.copy_rates_range(symbol, timeframe, self.start_at, self.start_at)

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: object,
        date_to: object,
    ) -> object | None:
        start_at = date_from if isinstance(date_from, datetime) else self.start_at
        end_at = date_to if isinstance(date_to, datetime) else self.start_at
        cycle = self._cycle_number(end_at)
        failure_key = ("bars", cycle, timeframe)
        if (cycle, timeframe) in self._bar_failure_cycles and failure_key not in self._failed_once:
            self._failed_once.add(failure_key)
            self.recovery_count += 1
            self.last_error_value = (2001, f"simulated bar disconnect timeframe={timeframe}")
            return None
        interval = timedelta(minutes=timeframe)
        aligned_end = self._align_down(end_at, interval)
        open_times = [
            aligned_end - interval * step
            for step in range(3, -1, -1)
            if aligned_end - interval * step >= start_at
        ]
        return [self._bar_payload(symbol, timeframe, open_time) for open_time in open_times]

    def copy_ticks_from(
        self, symbol: str, date_from: object, count: int, flags: int
    ) -> object | None:
        _ = (count, flags)
        return self.copy_ticks_range(symbol, date_from, self.start_at, 0)

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: object,
        date_to: object,
        flags: int,
    ) -> object | None:
        _ = (date_from, flags)
        end_at = date_to if isinstance(date_to, datetime) else self.start_at
        cycle = self._cycle_number(end_at)
        failure_key = ("ticks", cycle, None)
        if cycle in self._tick_failure_cycles and failure_key not in self._failed_once:
            self._failed_once.add(failure_key)
            self.recovery_count += 1
            self.last_error_value = (2000, "simulated tick disconnect")
            return None
        tick_time = end_at - timedelta(seconds=15)
        history_tick = end_at - timedelta(minutes=1)
        payload = [
            self._tick_payload(symbol, history_tick, 2600.0 + cycle * 0.1),
            self._tick_payload(symbol, tick_time, 2600.05 + cycle * 0.1),
        ]
        self._latest_tick_by_symbol[symbol] = self._tick_payload(
            symbol, end_at, 2600.1 + cycle * 0.1
        )
        return payload

    def _cycle_number(self, end_at: datetime) -> int:
        elapsed = end_at - self.start_at
        return int(elapsed.total_seconds() // 1800) + 1

    def _align_down(self, value: datetime, interval: timedelta) -> datetime:
        seconds = int(interval.total_seconds())
        epoch = int(value.timestamp())
        return datetime.fromtimestamp(epoch - (epoch % seconds), tz=UTC)

    def _tick_payload(self, symbol: str, timestamp: datetime, bid: float) -> dict[str, object]:
        return {
            "symbol": symbol,
            "time": int(timestamp.timestamp()),
            "time_msc": int(timestamp.timestamp() * 1000),
            "bid": round(bid, 5),
            "ask": round(bid + 0.2, 5),
            "last": round(bid + 0.1, 5),
            "volume": 1.0,
            "volume_real": 1.0,
            "flags": 1,
        }

    def _bar_payload(self, symbol: str, timeframe: int, open_time: datetime) -> dict[str, object]:
        cycle = self._cycle_number(open_time + timedelta(minutes=timeframe))
        base = 2600.0 + cycle * 0.1 + timeframe / 1000
        _ = symbol
        return {
            "time": int(open_time.timestamp()),
            "open": round(base, 5),
            "high": round(base + 0.4, 5),
            "low": round(base - 0.3, 5),
            "close": round(base + 0.2, 5),
            "tick_volume": 100 + cycle,
            "spread": 5,
            "real_volume": 0,
        }


def _build_soak_service(
    project_root: Path,
) -> tuple[MarketDataService, InstrumentedParquetStore, Path]:
    data_dir = project_root / "data" / "soak"
    sqlite_path = data_dir / "market-data.db"
    parquet_root = data_dir / "parquet"
    settings = MarketDataSettings(
        storage_base_dir=data_dir,
        sqlite_path=sqlite_path,
        parquet_root=parquet_root,
        backend_kind="mt5",
        backend_mode="readonly",
        symbols=(SymbolTarget("XAUUSD", ("XAUUSD.", "XAUUSD")),),
        timeframes=(Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1),
        poll_seconds=30,
        tick_lookback_seconds=900,
        bar_lookback_count=4,
        freshness_threshold_seconds=1800,
        retry_max_attempts=2,
        retry_backoff_seconds=0,
        mt5_enabled=True,
        mt5_terminal_path=None,
        mt5_login="",
        mt5_password="",
        mt5_server="",
        mt5_use_existing_session=True,
        dry_run_default=False,
    )
    backend = SoakFakeMt5Backend(datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    state_store = SQLiteStateStore(sqlite_path)
    parquet_store = InstrumentedParquetStore(parquet_root)
    return (
        MarketDataService(settings, state_store, parquet_store, backend),
        parquet_store,
        sqlite_path,
    )


def run_simulated_24h_soak(project_root: Path) -> dict[str, int | float]:
    service, parquet_store, sqlite_path = _build_soak_service(project_root)
    backend = service.backend
    assert isinstance(backend, SoakFakeMt5Backend)
    observed_times = [
        datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=30 * index)
        for index in range(48)
    ]
    total_ticks = 0
    duplicate_incidents = 0
    error_count = 0
    loop_latencies_ms: list[float] = []

    tracemalloc.start()
    try:
        for observed_now in observed_times:
            started = perf_counter()
            try:
                report = service.collect_once(now=observed_now, dry_run=False)
            except Exception:
                error_count += 1
                raise
            loop_latencies_ms.append((perf_counter() - started) * 1000)
            tick_count = report["tick_count"]
            assert isinstance(tick_count, int)
            total_ticks += tick_count
            incidents = report["quality_incidents"]
            assert isinstance(incidents, list)
            duplicate_incidents += sum(
                1 for item in incidents if str(item.get("event_kind", "")).startswith("duplicate")
            )
    finally:
        _, peak_memory_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        service.close()

    parquet_files = list(service.settings.parquet_root.rglob("*.parquet"))
    sqlite_size = sqlite_path.stat().st_size
    with service.state_store.connect() as connection:
        heartbeat_count = int(
            connection.execute("SELECT COUNT(*) AS count FROM collector_heartbeats").fetchone()[
                "count"
            ]
        )
        latest_tick_count = int(
            connection.execute("SELECT COUNT(*) AS count FROM latest_ticks").fetchone()["count"]
        )
        latest_bar_count = int(
            connection.execute("SELECT COUNT(*) AS count FROM latest_bars").fetchone()["count"]
        )
        cursor_count = int(
            connection.execute("SELECT COUNT(*) AS count FROM collection_cursors").fetchone()[
                "count"
            ]
        )

    return {
        "cycles": len(observed_times),
        "error_count": error_count,
        "recovery_count": backend.recovery_count,
        "shutdown_calls": backend.shutdown_calls,
        "heartbeat_count": heartbeat_count,
        "latest_tick_count": latest_tick_count,
        "latest_bar_count": latest_bar_count,
        "cursor_count": cursor_count,
        "total_ticks": total_ticks,
        "duplicate_incidents": duplicate_incidents,
        "parquet_file_count": len(parquet_files),
        "sqlite_size_bytes": sqlite_size,
        "peak_memory_bytes": peak_memory_bytes,
        "max_loop_latency_ms": max(loop_latencies_ms),
        "max_write_latency_ms": max(parquet_store.write_latencies_ms),
        "timeframe_count": len(service.settings.timeframes),
    }


def test_simulated_24h_soak_runtime_has_bounded_state(sample_project: Path) -> None:
    metrics = run_simulated_24h_soak(sample_project)

    assert metrics["error_count"] == 0
    assert metrics["recovery_count"] == 8
    assert metrics["shutdown_calls"] == metrics["recovery_count"] + 1
    assert metrics["heartbeat_count"] == metrics["cycles"]
    assert metrics["latest_tick_count"] == 1
    assert metrics["latest_bar_count"] <= metrics["timeframe_count"] * 2
    assert metrics["cursor_count"] == 1 + metrics["timeframe_count"]
    assert metrics["total_ticks"] >= metrics["cycles"] * 2
    assert metrics["duplicate_incidents"] == 0
    assert metrics["sqlite_size_bytes"] > 0
    assert 0 < metrics["parquet_file_count"] <= metrics["cycles"] * (metrics["timeframe_count"] + 2)
    assert metrics["peak_memory_bytes"] < 5_000_000
    assert metrics["max_loop_latency_ms"] < 5_000
    assert metrics["max_write_latency_ms"] < 3_000
