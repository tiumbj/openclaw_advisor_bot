from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.env import load_settings
from openclaw_super_advisor.market_data import (
    build_market_data_backend,
    build_market_data_service,
    parse_market_data_settings,
)
from openclaw_super_advisor.market_data.backend import (
    MT5_READONLY_METHODS,
    BackendConnectionError,
    BackendUnavailableError,
    DiscoveredSymbol,
)
from openclaw_super_advisor.market_data.connection import BoundedRetryRunner
from openclaw_super_advisor.market_data.fake_backend import (
    FakeMt5Backend,
    FakeMt5Scenario,
    build_default_scenario,
)
from openclaw_super_advisor.market_data.mt5_readonly import MetaTrader5ReadonlyAdapter
from openclaw_super_advisor.market_data.normalization import (
    as_float,
    as_int,
    as_text,
    discovered_symbol_from_payload,
    ensure_utc,
    epoch_milliseconds_to_utc,
    epoch_seconds_to_utc,
    normalize_bar,
    normalize_tick,
)
from openclaw_super_advisor.market_data.quality import (
    classify_freshness,
    detect_closed_bar_mutation,
    detect_missing_bars,
    normalize_bar_batch,
    normalize_tick_batch,
    split_current_and_closed_bars,
)
from openclaw_super_advisor.market_data.symbols import resolve_symbols
from openclaw_super_advisor.market_data.timeframes import (
    Timeframe,
    ensure_timeframe,
    timeframe_delta,
    timeframe_seconds,
)
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.runtime.market_data_runtime import run_collection_cycles


def _enable_mt5(sample_project: Path) -> Path:
    env_path = sample_project / "state" / ".env"
    env_text = env_path.read_text(encoding="utf-8").replace("MT5_ENABLED=false", "MT5_ENABLED=true")
    env_path.write_text(env_text, encoding="utf-8")
    return env_path


def _default_scenario() -> FakeMt5Scenario:
    return FakeMt5Scenario(
        symbols=[
            {
                "name": "XAUUSD.",
                "description": "Gold",
                "path": "Metals",
                "visible": False,
                "point": 0.01,
                "digits": 2,
            },
            {
                "name": "DXY",
                "description": "Dollar Index",
                "path": "Indices",
                "visible": True,
                "point": 0.01,
                "digits": 2,
            },
        ],
        ticks_by_symbol={
            "XAUUSD.": [
                {
                    "time": int(datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC).timestamp()),
                    "time_msc": 1767225720000,
                    "bid": 2600.0,
                    "ask": 2600.2,
                    "last": 2600.1,
                    "volume": 9.0,
                    "volume_real": 9.0,
                    "flags": 1,
                },
                {
                    "time": int(datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC).timestamp()),
                    "time_msc": 1767225660000,
                    "bid": 2599.9,
                    "ask": 2600.1,
                    "last": 2600.0,
                    "volume": 8.0,
                    "volume_real": 8.0,
                    "flags": 1,
                },
                {
                    "time": int(datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC).timestamp()),
                    "time_msc": 1767225720000,
                    "bid": 2600.0,
                    "ask": 2600.2,
                    "last": 2600.1,
                    "volume": 9.0,
                    "volume_real": 9.0,
                    "flags": 1,
                },
            ]
        },
        latest_tick_by_symbol={
            "XAUUSD.": {
                "time": int(datetime(2026, 1, 1, 0, 3, 0, tzinfo=UTC).timestamp()),
                "time_msc": 1767225780000,
                "bid": 2600.1,
                "ask": 2600.3,
                "last": 2600.2,
                "volume": 10.0,
                "volume_real": 10.0,
                "flags": 1,
            }
        },
        bars_by_symbol_and_timeframe={
            ("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1): [
                {
                    "time": int(datetime(2025, 12, 31, 22, 0, tzinfo=UTC).timestamp()),
                    "open": 2598.0,
                    "high": 2601.0,
                    "low": 2597.0,
                    "close": 2600.0,
                    "tick_volume": 100,
                    "spread": 10,
                    "real_volume": 0,
                },
                {
                    "time": int(datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()),
                    "open": 2600.0,
                    "high": 2603.0,
                    "low": 2599.0,
                    "close": 2602.0,
                    "tick_volume": 120,
                    "spread": 10,
                    "real_volume": 0,
                },
            ]
        },
    )


def test_market_data_settings_parse_portable_paths(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    settings = parse_market_data_settings(
        render_config(paths, env_path=paths.runtime_env_path),
        load_settings(paths, env_path=paths.runtime_env_path, strict=False),
    )
    assert settings.backend_mode == "readonly"
    assert settings.sqlite_path.name == "market-data.db"
    assert settings.parquet_root.name == "parquet"
    assert settings.timeframes == (
        Timeframe.M1,
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.D1,
    )


def test_optional_mt5_import_and_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = MetaTrader5ReadonlyAdapter(None, "", "", "", True)
    monkeypatch.setattr(
        "openclaw_super_advisor.market_data.mt5_readonly.META_TRADER5_MODULE",
        None,
    )
    with pytest.raises(BackendUnavailableError):
        adapter.initialize()
    for method_name in MT5_READONLY_METHODS:
        assert hasattr(adapter, method_name)


def test_mt5_readonly_adapter_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubMt5Module:
        def __init__(self) -> None:
            self.initialize_calls: list[dict[str, object]] = []
            self.shutdown_calls = 0
            self.selected_symbols: list[tuple[str, bool]] = []

        def initialize(self, **kwargs: object) -> bool:
            self.initialize_calls.append(kwargs)
            return True

        def shutdown(self) -> None:
            self.shutdown_calls += 1

        def version(self) -> tuple[int, ...]:
            return (5, 1, 2)

        def terminal_info(self) -> object:
            return {"path": "C:\\MT5\\terminal64.exe"}

        def account_info(self) -> object:
            return {"server": "demo-server", "login": 789012}

        def last_error(self) -> object:
            return (0, "ok")

        def symbols_get(self) -> object:
            return [{"name": "XAUUSD."}]

        def symbol_info(self, symbol: str) -> object:
            return {"name": symbol, "visible": False}

        def symbol_select(self, symbol: str, enable: bool) -> bool:
            self.selected_symbols.append((symbol, enable))
            return True

        def symbol_info_tick(self, symbol: str) -> object:
            return {"name": symbol, "bid": 2600.1}

        def copy_rates_from(
            self, symbol: str, timeframe: int, date_from: object, count: int
        ) -> object:
            return [symbol, timeframe, date_from, count]

        def copy_rates_from_pos(
            self, symbol: str, timeframe: int, start_pos: int, count: int
        ) -> object:
            return [symbol, timeframe, start_pos, count]

        def copy_rates_range(
            self,
            symbol: str,
            timeframe: int,
            date_from: object,
            date_to: object,
        ) -> object:
            return [symbol, timeframe, date_from, date_to]

        def copy_ticks_from(
            self, symbol: str, date_from: object, count: int, flags: int
        ) -> object:
            return [symbol, date_from, count, flags]

        def copy_ticks_range(
            self,
            symbol: str,
            date_from: object,
            date_to: object,
            flags: int,
        ) -> object:
            return [symbol, date_from, date_to, flags]

    module = StubMt5Module()
    monkeypatch.setattr(
        "openclaw_super_advisor.market_data.mt5_readonly.META_TRADER5_MODULE",
        module,
    )
    adapter = MetaTrader5ReadonlyAdapter(
        terminal_path=Path("C:\\MT5\\terminal64.exe"),
        login="789012",
        password="redacted",
        server="demo-server",
        use_existing_session=False,
    )

    assert adapter.initialize() is True
    assert adapter.initialize() is True
    assert module.initialize_calls == [
        {
            "timeout": 10_000,
            "path": "C:\\MT5\\terminal64.exe",
            "login": 789012,
            "password": "redacted",
            "server": "demo-server",
        }
    ]
    assert adapter.version() == (5, 1, 2)
    assert adapter.terminal_info() == {"path": "C:\\MT5\\terminal64.exe"}
    assert adapter.account_info() == {"server": "demo-server", "login": 789012}
    assert adapter.last_error() == (0, "ok")
    assert adapter.symbols_get() == [{"name": "XAUUSD."}]
    assert adapter.symbol_info("XAUUSD.") == {"name": "XAUUSD.", "visible": False}
    assert adapter.symbol_select("XAUUSD.", True) is True
    assert adapter.symbol_info_tick("XAUUSD.") == {"name": "XAUUSD.", "bid": 2600.1}
    assert adapter.copy_rates_from("XAUUSD.", 60, "from", 10) == ["XAUUSD.", 60, "from", 10]
    assert adapter.copy_rates_from_pos("XAUUSD.", 60, 1, 10) == ["XAUUSD.", 60, 1, 10]
    assert adapter.copy_rates_range("XAUUSD.", 60, "from", "to") == ["XAUUSD.", 60, "from", "to"]
    assert adapter.copy_ticks_from("XAUUSD.", "from", 10, 0) == ["XAUUSD.", "from", 10, 0]
    assert adapter.copy_ticks_range("XAUUSD.", "from", "to", 0) == ["XAUUSD.", "from", "to", 0]

    adapter.shutdown()
    adapter.shutdown()
    assert module.shutdown_calls == 1
    assert module.selected_symbols == [("XAUUSD.", True)]


def test_mt5_readonly_adapter_rejects_missing_credentials_and_init_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openclaw_super_advisor.market_data.mt5_readonly.META_TRADER5_MODULE",
        SimpleNamespace(initialize=lambda **_kwargs: True, last_error=lambda: (0, "ok")),
    )
    with pytest.raises(BackendConnectionError, match="required"):
        MetaTrader5ReadonlyAdapter(
            terminal_path=None,
            login="",
            password="",
            server="",
            use_existing_session=False,
        ).initialize()

    class FailingModule:
        def initialize(self, **_kwargs: object) -> bool:
            return False

        def last_error(self) -> object:
            return (1005, "login failed")

    monkeypatch.setattr(
        "openclaw_super_advisor.market_data.mt5_readonly.META_TRADER5_MODULE",
        FailingModule(),
    )
    adapter = MetaTrader5ReadonlyAdapter(None, "", "", "", True)
    with pytest.raises(BackendConnectionError, match="initialize failed"):
        adapter.initialize()


def test_bounded_retry_reconnects_once() -> None:
    backend = FakeMt5Backend(FakeMt5Scenario(fail_once=True))
    runner = BoundedRetryRunner(backend, max_attempts=2, backoff_seconds=0)
    result = runner.run(lambda: "connected")
    assert result == "connected"
    assert backend.connected is True


def test_bounded_retry_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        "openclaw_super_advisor.market_data.connection.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    backend = FakeMt5Backend(
        FakeMt5Scenario(initialize_success=False, last_error_value=(1001, "terminal unavailable"))
    )
    runner = BoundedRetryRunner(backend, max_attempts=3, backoff_seconds=2)
    with pytest.raises(BackendConnectionError, match="initialize failed"):
        runner.run(lambda: "never")
    assert sleep_calls == [2, 4]

    with pytest.raises(BackendConnectionError, match="without an explicit backend error"):
        BoundedRetryRunner(backend, max_attempts=0, backoff_seconds=1).run(lambda: "never")


def test_symbol_resolution_exact_alias_ambiguous_and_unknown() -> None:
    discovered = [
        DiscoveredSymbol("XAUUSD.", "Gold", "Metals", True, 0.01, 2),
        DiscoveredSymbol("GOLDmicro", "Gold", "Metals", True, 0.01, 2),
    ]
    resolved, incidents = resolve_symbols(
        (
            ("XAUUSD", ("XAUUSD",)),
            ("DXY", ("USDX",)),
            ("GOLD", ("Gold",)),
        ),
        discovered,
    )
    assert resolved[0].broker_symbol == "XAUUSD."
    kinds = {item.event_kind for item in incidents}
    assert "missing_symbol_mapping" in kinds
    assert "ambiguous_symbol_mapping" in kinds


def test_utc_normalization_and_market_contracts() -> None:
    with pytest.raises(ValueError):
        ensure_utc(datetime(2026, 1, 1))

    tick = normalize_tick(
        "XAUUSD",
        "XAUUSD.",
        {
            "time_msc": 1767225780123,
            "bid": 2600.1,
            "ask": 2600.3,
            "last": 2600.2,
            "volume": 10.0,
            "volume_real": 10.0,
            "flags": 1,
        },
        datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC),
        0.01,
    )
    assert tick.market_time_msc == 1767225780123
    assert tick.market_time_utc.microsecond == 123000
    assert tick.spread_points == 20

    with pytest.raises(ValueError):
        normalize_tick(
            "XAUUSD",
            "XAUUSD.",
            {"time_msc": 1767225780123, "bid": 2600.4, "ask": 2600.3, "last": 2600.2},
            datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC),
            0.01,
        )

    bar = normalize_bar(
        "XAUUSD",
        "XAUUSD.",
        Timeframe.H1,
        {
            "time": int(datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()),
            "open": 2600.0,
            "high": 2603.0,
            "low": 2599.0,
            "close": 2602.0,
            "tick_volume": 120,
            "spread": 10,
            "real_volume": 0,
        },
        datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    assert bar.bar_id == "XAUUSD:H1:1767225600"
    assert bar.is_closed is False

    with pytest.raises(ValueError):
        normalize_bar(
            "XAUUSD",
            "XAUUSD.",
            Timeframe.H1,
            {
                "time": int(datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()),
                "open": 2600.0,
                "high": 2590.0,
                "low": 2599.0,
                "close": 2602.0,
                "tick_volume": 120,
                "spread": 10,
                "real_volume": 0,
            },
            datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        )


def test_normalization_helpers_cover_mapping_and_validation_branches() -> None:
    class IndexPayload:
        def __getitem__(self, name: str) -> object:
            if name == "bid":
                return 2601.5
            raise KeyError(name)

    symbol = discovered_symbol_from_payload(
        SimpleNamespace(
            name="EURUSD.",
            description="Euro Dollar",
            path="FX",
            visible=True,
            point=0.0001,
            digits=5,
        )
    )
    assert symbol.broker_symbol == "EURUSD."
    assert as_text({"name": "XAUUSD"}, "name") == "XAUUSD"
    assert as_float(IndexPayload(), "bid") == 2601.5
    assert as_int({"flags": "2"}, "flags") == 2
    assert epoch_seconds_to_utc(datetime(2026, 1, 1, tzinfo=UTC)).year == 2026
    assert epoch_milliseconds_to_utc(1767225780123).microsecond == 123000

    with pytest.raises(ValueError, match="numeric"):
        as_float({"bid": object()}, "bid")
    with pytest.raises(ValueError, match="integer-like"):
        as_int({"flags": object()}, "flags")
    with pytest.raises(ValueError, match="epoch seconds must be numeric"):
        epoch_seconds_to_utc("bad")
    with pytest.raises(ValueError, match="epoch milliseconds must be numeric"):
        epoch_milliseconds_to_utc("bad")

    tick = normalize_tick(
        "EURUSD",
        symbol.broker_symbol,
        {
            "time": int(datetime(2026, 1, 1, 0, 3, tzinfo=UTC).timestamp()),
            "bid": 1.1,
            "ask": 1.2,
            "last": 1.15,
        },
        datetime(2026, 1, 1, 0, 3, 1, tzinfo=UTC),
        symbol.point,
    )
    assert tick.market_time_msc == int(datetime(2026, 1, 1, 0, 3, tzinfo=UTC).timestamp()) * 1000

    with pytest.raises(ValueError, match="bar volumes must be >= 0"):
        normalize_bar(
            "EURUSD",
            symbol.broker_symbol,
            Timeframe.M1,
            {
                "time": int(datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()),
                "open": 1.1,
                "high": 1.2,
                "low": 1.0,
                "close": 1.15,
                "tick_volume": -1,
                "spread": 1,
                "real_volume": 0,
            },
            datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        )


def test_quality_controls_for_ticks_and_bars() -> None:
    tick_one = normalize_tick(
        "XAUUSD",
        "XAUUSD.",
        {
            "time_msc": 1767225720000,
            "bid": 2600.0,
            "ask": 2600.2,
            "last": 2600.1,
            "volume": 9.0,
            "volume_real": 9.0,
            "flags": 1,
        },
        datetime(2026, 1, 1, 0, 2, 1, tzinfo=UTC),
        0.01,
    )
    tick_two = normalize_tick(
        "XAUUSD",
        "XAUUSD.",
        {
            "time_msc": 1767225660000,
            "bid": 2599.9,
            "ask": 2600.1,
            "last": 2600.0,
            "volume": 8.0,
            "volume_real": 8.0,
            "flags": 1,
        },
        datetime(2026, 1, 1, 0, 2, 1, tzinfo=UTC),
        0.01,
    )
    normalized_ticks, tick_incidents = normalize_tick_batch([tick_one, tick_two, tick_one])
    assert [item.market_time_msc for item in normalized_ticks] == [1767225660000, 1767225720000]
    assert {item.event_kind for item in tick_incidents} == {"duplicate_ticks", "out_of_order_ticks"}

    bar_one = normalize_bar(
        "XAUUSD",
        "XAUUSD.",
        Timeframe.H1,
        {
            "time": int(datetime(2025, 12, 31, 22, 0, tzinfo=UTC).timestamp()),
            "open": 2598.0,
            "high": 2601.0,
            "low": 2597.0,
            "close": 2600.0,
            "tick_volume": 100,
            "spread": 10,
            "real_volume": 0,
        },
        datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    bar_two = normalize_bar(
        "XAUUSD",
        "XAUUSD.",
        Timeframe.H1,
        {
            "time": int(datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()),
            "open": 2600.0,
            "high": 2603.0,
            "low": 2599.0,
            "close": 2602.0,
            "tick_volume": 120,
            "spread": 10,
            "real_volume": 0,
        },
        datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    normalized_bars, bar_incidents = normalize_bar_batch([bar_two, bar_one, bar_two])
    assert len(normalized_bars) == 2
    assert {item.event_kind for item in bar_incidents} == {"duplicate_bars", "out_of_order_bars"}
    assert detect_missing_bars(normalized_bars)[0].event_kind == "missing_bars"

    current_rows, closed_rows = split_current_and_closed_bars(
        normalized_bars,
        datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    assert ("XAUUSD", "H1") in current_rows
    assert ("XAUUSD", "H1") in closed_rows

    mutated_bar = normalize_bar(
        "XAUUSD",
        "XAUUSD.",
        Timeframe.H1,
        {
            "time": int(datetime(2025, 12, 31, 22, 0, tzinfo=UTC).timestamp()),
            "open": 2598.0,
            "high": 2601.5,
            "low": 2597.0,
            "close": 2600.1,
            "tick_volume": 101,
            "spread": 10,
            "real_volume": 0,
        },
        datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
    )
    mutation_incidents = detect_closed_bar_mutation(bar_one, mutated_bar)
    assert mutation_incidents[0].event_kind == "closed_bar_mutation"

    freshness, freshness_incidents = classify_freshness(
        datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC),
        normalized_ticks,
        normalized_bars,
        180,
    )
    assert freshness == {"ticks": "fresh", "bars": "fresh"}
    assert not freshness_incidents


def test_fake_backend_runtime_helpers_and_timeframes() -> None:
    scenario = build_default_scenario()
    backend = FakeMt5Backend(scenario)
    assert backend.initialize() is True
    assert backend.version() == (5, 0, 0)
    assert backend.terminal_info() == {"path": "C:\\MT5\\terminal64.exe"}
    assert backend.account_info() == {"server": "demo-server", "login": 123456}
    assert backend.symbol_info("XAUUSD.") == scenario.symbols[0]
    assert backend.symbol_info("UNKNOWN") is None
    assert backend.symbol_select("XAUUSD.", True) is True
    assert "XAUUSD." in scenario.visible_symbols
    assert backend.copy_rates_from("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1, "from", 1)
    assert backend.copy_rates_from_pos("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1, 0, 1)
    assert backend.copy_rates_range("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1, "from", "to")
    assert backend.copy_ticks_from("XAUUSD.", "from", 1, 0)
    assert backend.copy_ticks_range("XAUUSD.", "from", "to", 0)
    backend.shutdown()
    assert backend.connected is False
    assert timeframe_seconds("H1") == 3600
    assert timeframe_delta(Timeframe.H4).total_seconds() == 14_400
    assert ensure_timeframe(Timeframe.M1) is Timeframe.M1
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        ensure_timeframe("M30")


def test_service_collect_snapshot_storage_and_clean_shutdown(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=FakeMt5Backend(_default_scenario()),
    )
    observed_now = datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC)
    report = service.collect_once(now=observed_now, dry_run=False)
    snapshot = service.snapshot("XAUUSD", now=observed_now)
    storage = service.storage_check()
    service.close()
    service.close()

    assert report["tick_count"] == 3
    incident_kinds = {item["event_kind"] for item in report["quality_incidents"]}
    assert {"duplicate_ticks", "out_of_order_ticks", "missing_bars"} <= incident_kinds
    assert snapshot["ticks"]
    assert snapshot["bars"]
    assert snapshot["freshness"]["XAUUSD"]["ticks"] == "fresh"
    assert "signal" not in json.dumps(snapshot).lower()
    assert storage["parquet_file_count"] >= 2
    assert storage["migrations"] == ["001_market_data_foundation"]


def test_market_data_service_error_and_runtime_branches(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disabled_service = build_market_data_service(
        build_paths(sample_project),
        env_path=sample_project / "state" / ".env",
        backend=FakeMt5Backend(_default_scenario()),
    )
    assert disabled_service.market_health()["enabled"] is False
    disabled_service.close()

    paths = build_paths(sample_project)
    env_path = _enable_mt5(sample_project)
    settings = parse_market_data_settings(
        render_config(paths, env_path=env_path),
        load_settings(paths, env_path=env_path, strict=False),
    )
    with pytest.raises(BackendConnectionError, match="readonly MT5 backend"):
        build_market_data_backend(replace(settings, backend_mode="write"))

    class NoneSymbolsBackend(FakeMt5Backend):
        def symbols_get(self) -> object | None:
            return None

    service = build_market_data_service(paths, env_path=env_path, backend=NoneSymbolsBackend())
    with pytest.raises(BackendConnectionError, match="symbols_get failed"):
        service.discover_symbols()
    service.close()

    class RejectSelectBackend(FakeMt5Backend):
        def symbol_select(self, symbol: str, enable: bool) -> bool:
            _ = (symbol, enable)
            return False

    rejecting_service = build_market_data_service(
        paths,
        env_path=env_path,
        backend=RejectSelectBackend(_default_scenario()),
    )
    collected = rejecting_service.collect_once(
        now=datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC),
        dry_run=True,
    )
    assert any(
        incident["event_kind"] == "symbol_select_failed"
        for incident in collected["quality_incidents"]
    )
    with pytest.raises(ValueError, match="cycles must be at least 1"):
        rejecting_service.collect_cycles(0)
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        "openclaw_super_advisor.market_data.collector.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    runtime_report = run_collection_cycles(
        rejecting_service,
        cycles=2,
        sleep_seconds=5,
        dry_run=True,
    )
    assert runtime_report["cycles"] == 2
    assert sleep_calls == [5]
    with pytest.raises(ValueError, match="backfill end must be after start"):
        rejecting_service.backfill(
            "XAUUSD",
            "H1",
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            dry_run=True,
        )
    assert rejecting_service._commit_bars("XAUUSD", "H1", [], []) is None
    rejecting_service.close()


def test_cursor_does_not_advance_on_write_failure(sample_project: Path) -> None:
    env_path = _enable_mt5(sample_project)
    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=FakeMt5Backend(_default_scenario()),
    )
    original = service.parquet_store.write_ticks

    def _failing_write(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("simulated parquet failure")

    service.parquet_store.write_ticks = _failing_write  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        service.collect_once(now=datetime(2026, 1, 1, 0, 3, 30, tzinfo=UTC), dry_run=False)
    assert service.state_store.get_cursor("ticks", "XAUUSD") is None
    service.parquet_store.write_ticks = original  # type: ignore[method-assign]
    service.close()


def test_backfill_chunking_and_resume(
    sample_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = _enable_mt5(sample_project)
    template_path = sample_project / "config" / "openclaw.template.json"
    template_text = template_path.read_text(encoding="utf-8").replace(
        '"barLookbackCount": 500', '"barLookbackCount": 1'
    )
    template_path.write_text(template_text, encoding="utf-8")

    service = build_market_data_service(
        build_paths(sample_project),
        env_path=env_path,
        backend=FakeMt5Backend(_default_scenario()),
    )
    failure_count = {"value": 0}
    original_commit = service._commit_bars

    def _flaky_commit(*args: object, **kwargs: object) -> object:
        failure_count["value"] += 1
        if failure_count["value"] == 2:
            raise RuntimeError("chunk failure")
        return original_commit(*args, **kwargs)

    monkeypatch.setattr(service, "_commit_bars", _flaky_commit)
    with pytest.raises(RuntimeError):
        service.backfill(
            "XAUUSD",
            "H1",
            datetime(2025, 12, 31, 22, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
            dry_run=False,
        )

    resumed = service.backfill(
        "XAUUSD",
        "H1",
        datetime(2025, 12, 31, 22, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        dry_run=False,
    )
    state = service.state_store.get_backfill_state(str(resumed["run_key"]))
    assert state is not None
    assert state.status == "complete"
    service.close()
