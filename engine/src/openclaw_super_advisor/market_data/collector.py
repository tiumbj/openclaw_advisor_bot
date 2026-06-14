from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from .._version import PHASE, __version__
from ..config import ConfigValidationError, render_config
from ..env import AppSettings, load_settings
from ..paths import ProjectPaths
from ..runtime.heartbeat import build_heartbeat
from ..storage.parquet_store import ParquetStore
from ..storage.sqlite_state import SQLiteStateStore
from .backend import (
    BackendConnectionError,
    DiscoveredSymbol,
    ReadonlyMt5Backend,
    ResolvedSymbol,
    TerminalHealth,
)
from .connection import BoundedRetryRunner
from .cursors import BackfillState, advance_window
from .mt5_readonly import MetaTrader5ReadonlyAdapter
from .normalization import (
    MARKET_DATA_SCHEMA_VERSION,
    as_float,
    as_int,
    as_text,
    discovered_symbol_from_payload,
    ensure_utc,
    normalize_bar,
    normalize_tick,
    to_iso_z,
    utc_now,
)
from .quality import (
    classify_freshness,
    detect_closed_bar_mutation,
    detect_missing_bars,
    normalize_bar_batch,
    normalize_tick_batch,
    split_current_and_closed_bars,
)
from .schemas import BarRecord, QualityIncident, TickRecord
from .snapshots import build_snapshot_payload
from .symbols import resolve_symbols
from .timeframes import SUPPORTED_TIMEFRAMES, Timeframe

MT5_TIMEFRAME_MAP = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}
COPY_TICKS_ALL = 0


@dataclass(frozen=True)
class SymbolTarget:
    logical_symbol: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class MarketDataSettings:
    storage_base_dir: Path
    sqlite_path: Path
    parquet_root: Path
    backend_kind: str
    backend_mode: str
    symbols: tuple[SymbolTarget, ...]
    timeframes: tuple[Timeframe, ...]
    poll_seconds: int
    tick_lookback_seconds: int
    bar_lookback_count: int
    freshness_threshold_seconds: int
    retry_max_attempts: int
    retry_backoff_seconds: int
    mt5_enabled: bool
    mt5_terminal_path: Path | None
    mt5_login: str
    mt5_password: str
    mt5_server: str
    mt5_use_existing_session: bool
    dry_run_default: bool


def _as_dict(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{path} must be an object")
    return value


def _as_list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise ConfigValidationError(f"{path} must be a list")
    return value


def _as_int(value: object, path: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(f"{path} must be a positive integer")
    return value


def _as_str(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigValidationError(f"{path} must be a non-empty string")
    return value


def _snapshot_datetime(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def parse_market_data_settings(
    config: dict[str, object], settings: AppSettings
) -> MarketDataSettings:
    market_data = _as_dict(config.get("marketData"), "marketData")
    backend = _as_dict(market_data.get("backend"), "marketData.backend")
    storage = _as_dict(market_data.get("storage"), "marketData.storage")
    collection = _as_dict(market_data.get("collection"), "marketData.collection")
    symbols_payload = _as_list(market_data.get("symbols"), "marketData.symbols")
    timeframes_payload = _as_list(market_data.get("timeframes"), "marketData.timeframes")
    storage_base_dir = Path(_as_str(storage.get("baseDir"), "marketData.storage.baseDir"))
    sqlite_path = Path(_as_str(storage.get("sqlitePath"), "marketData.storage.sqlitePath"))
    parquet_directory = Path(_as_str(storage.get("parquetDir"), "marketData.storage.parquetDir"))

    env_aliases = {
        "XAUUSD": str(settings.raw_values.get("MT5_XAUUSD_SYMBOL", "")),
        "DXY": str(settings.raw_values.get("MT5_DXY_SYMBOL", "")),
        "EURUSD": str(settings.raw_values.get("MT5_EURUSD_SYMBOL", "")),
        "AUDUSD": str(settings.raw_values.get("MT5_AUDUSD_SYMBOL", "")),
        "US10Y": str(settings.raw_values.get("MT5_US10Y_SYMBOL", "")),
    }

    symbol_targets: list[SymbolTarget] = []
    for index, item in enumerate(symbols_payload):
        symbol_payload = _as_dict(item, f"marketData.symbols[{index}]")
        aliases_payload = _as_list(
            symbol_payload.get("aliases"),
            f"marketData.symbols[{index}].aliases",
        )
        logical_symbol = _as_str(
            symbol_payload.get("canonical"),
            f"marketData.symbols[{index}].canonical",
        )
        aliases = [
            _as_str(alias, f"marketData.symbols[{index}].aliases") for alias in aliases_payload
        ]
        env_alias = env_aliases.get(logical_symbol, "")
        if env_alias:
            aliases.append(env_alias)
        normalized_aliases = tuple(dict.fromkeys(aliases))
        symbol_targets.append(
            SymbolTarget(
                logical_symbol=logical_symbol,
                aliases=normalized_aliases,
            )
        )

    parsed_timeframes = tuple(
        Timeframe(_as_str(item, "marketData.timeframes")) for item in timeframes_payload
    )
    unsupported = sorted(
        {item.value for item in parsed_timeframes}.difference(SUPPORTED_TIMEFRAMES)
    )
    if unsupported:
        raise ConfigValidationError(f"Unsupported market-data timeframes: {unsupported}")

    data_root = storage_base_dir.resolve()
    sqlite_file = sqlite_path if sqlite_path.is_absolute() else data_root / sqlite_path
    parquet_root = (
        parquet_directory if parquet_directory.is_absolute() else data_root / parquet_directory
    )
    mt5_terminal_raw = settings.parsed_values.get("MT5_TERMINAL_PATH")
    mt5_terminal_path = mt5_terminal_raw if isinstance(mt5_terminal_raw, Path) else None
    return MarketDataSettings(
        storage_base_dir=data_root,
        sqlite_path=sqlite_file.resolve(),
        parquet_root=parquet_root.resolve(),
        backend_kind=_as_str(backend.get("kind"), "marketData.backend.kind"),
        backend_mode=_as_str(backend.get("mode"), "marketData.backend.mode"),
        symbols=tuple(symbol_targets),
        timeframes=parsed_timeframes,
        poll_seconds=_as_int(collection.get("pollSeconds"), "marketData.collection.pollSeconds"),
        tick_lookback_seconds=_as_int(
            collection.get("tickLookbackSeconds"),
            "marketData.collection.tickLookbackSeconds",
        ),
        bar_lookback_count=_as_int(
            collection.get("barLookbackCount"),
            "marketData.collection.barLookbackCount",
        ),
        freshness_threshold_seconds=_as_int(
            collection.get("freshnessThresholdSeconds"),
            "marketData.collection.freshnessThresholdSeconds",
        ),
        retry_max_attempts=_as_int(
            collection.get("retryMaxAttempts"), "marketData.collection.retryMaxAttempts"
        ),
        retry_backoff_seconds=_as_int(
            collection.get("retryBackoffSeconds"), "marketData.collection.retryBackoffSeconds"
        ),
        mt5_enabled=bool(settings.parsed_values.get("MT5_ENABLED", False)),
        mt5_terminal_path=mt5_terminal_path,
        mt5_login=str(settings.raw_values.get("MT5_LOGIN", "")),
        mt5_password=str(settings.raw_values.get("MT5_PASSWORD", "")),
        mt5_server=str(settings.raw_values.get("MT5_SERVER", "")),
        mt5_use_existing_session=bool(settings.parsed_values.get("MT5_USE_EXISTING_SESSION", True)),
        dry_run_default=bool(settings.parsed_values.get("DRY_RUN", True)),
    )


def build_market_data_backend(config: MarketDataSettings) -> ReadonlyMt5Backend:
    if config.backend_kind != "mt5" or config.backend_mode != "readonly":
        raise BackendConnectionError("Only the readonly MT5 backend is supported")
    return MetaTrader5ReadonlyAdapter(
        terminal_path=config.mt5_terminal_path,
        login=config.mt5_login,
        password=config.mt5_password,
        server=config.mt5_server,
        use_existing_session=config.mt5_use_existing_session,
    )


def build_market_data_service(
    paths: ProjectPaths,
    env_path: Path | None = None,
    backend: ReadonlyMt5Backend | None = None,
) -> MarketDataService:
    app_settings = load_settings(paths, env_path=env_path, strict=False)
    rendered_config = render_config(paths, env_path=env_path)
    settings = parse_market_data_settings(rendered_config, app_settings)
    state_store = SQLiteStateStore(settings.sqlite_path)
    parquet_store = ParquetStore(settings.parquet_root)
    active_backend = backend or build_market_data_backend(settings)
    return MarketDataService(settings, state_store, parquet_store, active_backend)


class MarketDataService:
    def __init__(
        self,
        settings: MarketDataSettings,
        state_store: SQLiteStateStore,
        parquet_store: ParquetStore,
        backend: ReadonlyMt5Backend,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.parquet_store = parquet_store
        self.backend = backend
        self.retry = BoundedRetryRunner(
            backend, settings.retry_max_attempts, settings.retry_backoff_seconds
        )

    def close(self) -> None:
        self.backend.shutdown()

    def market_health(self) -> dict[str, object]:
        if not self.settings.mt5_enabled:
            return {
                "version": __version__,
                "phase": PHASE,
                "enabled": False,
                "connected": False,
                "backend": self.backend.backend_name,
                "message": "MT5 market-data runtime is disabled in the environment",
            }
        health = self._terminal_health()
        return {
            "version": __version__,
            "phase": PHASE,
            "schema_version": MARKET_DATA_SCHEMA_VERSION,
            "enabled": health.enabled,
            "connected": health.connected,
            "backend": health.backend_name,
            "terminal_path": health.terminal_path,
            "server": health.server,
            "login": health.login,
            "ping_ms": health.ping_ms,
            "version_text": health.version,
            "message": health.message,
        }

    def discover_symbols(self) -> dict[str, object]:
        discovered = self._list_symbols()
        return {
            "version": __version__,
            "phase": PHASE,
            "count": len(discovered),
            "symbols": [item.__dict__ for item in discovered],
        }

    def collect_once(
        self,
        symbol_filter: tuple[str, ...] | None = None,
        now: datetime | None = None,
        dry_run: bool | None = None,
    ) -> dict[str, object]:
        observed_now = ensure_utc(now) if now is not None else utc_now()
        effective_dry_run = self.settings.dry_run_default if dry_run is None else dry_run
        resolved, incidents = self._resolve_symbols()
        if symbol_filter is not None:
            allowed = {item.upper() for item in symbol_filter}
            resolved = [item for item in resolved if item.logical_symbol.upper() in allowed]
        all_incidents = list(incidents)
        tick_count = 0
        bar_count = 0
        freshness: dict[str, dict[str, str]] = {}
        for symbol in resolved:
            ticks, bars, symbol_incidents, symbol_freshness = self._collect_symbol(
                symbol=symbol,
                observed_now=observed_now,
                dry_run=effective_dry_run,
            )
            tick_count += len(ticks)
            bar_count += len(bars)
            all_incidents.extend(symbol_incidents)
            freshness[symbol.logical_symbol] = symbol_freshness
        if not effective_dry_run:
            heartbeat = build_heartbeat(
                collector_name="market-data-collector",
                status="ok",
                detail={
                    "symbols": [item.logical_symbol for item in resolved],
                    "tick_count": tick_count,
                    "bar_count": bar_count,
                    "incident_count": len(all_incidents),
                },
                observed_at_utc=observed_now,
            )
            with self.state_store.transaction() as connection:
                self.state_store.record_heartbeat(connection, heartbeat)
        return {
            "version": __version__,
            "phase": PHASE,
            "dry_run": effective_dry_run,
            "symbols": [item.logical_symbol for item in resolved],
            "tick_count": tick_count,
            "bar_count": bar_count,
            "quality_incidents": [item.to_dict() for item in all_incidents],
            "freshness": freshness,
            "observed_at_utc": to_iso_z(observed_now),
        }

    def backfill(
        self,
        canonical_symbol: str,
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
        dry_run: bool | None = None,
    ) -> dict[str, object]:
        observed_start = ensure_utc(start_at)
        observed_end = ensure_utc(end_at)
        if observed_end <= observed_start:
            raise ValueError("backfill end must be after start")
        timeframe_value = Timeframe(timeframe)
        effective_dry_run = self.settings.dry_run_default if dry_run is None else dry_run
        resolved = self._resolve_symbol(canonical_symbol)
        run_key = hashlib.sha256(
            f"{resolved.logical_symbol}:{timeframe_value.value}:{observed_start.isoformat()}:{observed_end.isoformat()}".encode()
        ).hexdigest()
        state = self.state_store.get_backfill_state(run_key)
        next_start = observed_start if state is None else state.next_start_utc
        incidents: list[QualityIncident] = []
        total_bars = 0
        while next_start < observed_end:
            chunk_end = advance_window(
                next_start,
                observed_end,
                timeframe_value.value,
                self.settings.bar_lookback_count,
            )
            try:
                bars = self._load_bars(resolved, timeframe_value, next_start, chunk_end, chunk_end)
                normalized_bars, batch_incidents = normalize_bar_batch(bars)
                total_bars += len(normalized_bars)
                batch_incidents.extend(detect_missing_bars(normalized_bars))
                incidents.extend(batch_incidents)
                if not effective_dry_run:
                    self._commit_bars(
                        logical_symbol=resolved.logical_symbol,
                        timeframe=timeframe_value.value,
                        bars=normalized_bars,
                        incidents=batch_incidents,
                    )
                    with self.state_store.transaction() as connection:
                        self.state_store.upsert_backfill_state(
                            connection,
                            BackfillState(
                                run_key=run_key,
                                logical_symbol=resolved.logical_symbol,
                                timeframe=timeframe_value.value,
                                start_at_utc=observed_start,
                                end_at_utc=observed_end,
                                next_start_utc=chunk_end,
                                status="running" if chunk_end < observed_end else "complete",
                                last_error=None,
                            ),
                            updated_at_utc=to_iso_z(chunk_end),
                        )
            except Exception as exc:
                if not effective_dry_run:
                    with self.state_store.transaction() as connection:
                        self.state_store.upsert_backfill_state(
                            connection,
                            BackfillState(
                                run_key=run_key,
                                logical_symbol=resolved.logical_symbol,
                                timeframe=timeframe_value.value,
                                start_at_utc=observed_start,
                                end_at_utc=observed_end,
                                next_start_utc=next_start,
                                status="failed",
                                last_error=str(exc),
                            ),
                            updated_at_utc=to_iso_z(next_start),
                        )
                raise
            next_start = chunk_end
        return {
            "version": __version__,
            "phase": PHASE,
            "dry_run": effective_dry_run,
            "schema_version": MARKET_DATA_SCHEMA_VERSION,
            "symbol": resolved.logical_symbol,
            "timeframe": timeframe_value.value,
            "bar_count": total_bars,
            "quality_incidents": [item.to_dict() for item in incidents],
            "start_at_utc": to_iso_z(observed_start),
            "end_at_utc": to_iso_z(observed_end),
            "run_key": run_key,
        }

    def snapshot(
        self,
        canonical_symbol: str | None = None,
        refresh: bool = False,
        dry_run: bool | None = None,
        now: datetime | None = None,
    ) -> dict[str, object]:
        observed_now = ensure_utc(now) if now is not None else utc_now()
        if refresh:
            symbols = None if canonical_symbol is None else (canonical_symbol,)
            self.collect_once(symbol_filter=symbols, now=observed_now, dry_run=dry_run)
        stored_snapshot = self.state_store.snapshot(canonical_symbol)
        freshness: dict[str, dict[str, str]] = {}
        tick_rows = cast(list[dict[str, object]], stored_snapshot["ticks"])
        bar_rows = cast(list[dict[str, object]], stored_snapshot["bars"])
        for tick in tick_rows:
            logical_symbol = str(tick["logical_symbol"])
            related_bars = [
                row for row in bar_rows if str(row.get("logical_symbol")) == logical_symbol
            ]
            tick_record = [
                TickRecord(
                    schema_version=str(tick["schema_version"]),
                    collector_version=str(tick["collector_version"]),
                    logical_symbol=logical_symbol,
                    broker_symbol=str(tick["broker_symbol"]),
                    market_time_utc=_snapshot_datetime(tick["market_time_utc"]),
                    market_time_msc=as_int(tick, "market_time_msc"),
                    received_at_utc=_snapshot_datetime(tick["received_at_utc"]),
                    bid=as_float(tick, "bid"),
                    ask=as_float(tick, "ask"),
                    last=as_float(tick, "last"),
                    volume=as_float(tick, "volume"),
                    volume_real=as_float(tick, "volume_real"),
                    flags=as_int(tick, "flags"),
                    spread_points=as_int(tick, "spread_points"),
                    sequence_id=str(tick["sequence_id"]),
                    data_quality=str(tick["data_quality"]),
                    quality_flags=tuple(
                        str(item) for item in cast(list[object], tick["quality_flags"])
                    ),
                )
            ]
            bar_records = [
                BarRecord(
                    schema_version=str(row["schema_version"]),
                    collector_version=str(row["collector_version"]),
                    logical_symbol=str(row["logical_symbol"]),
                    broker_symbol=str(row["broker_symbol"]),
                    timeframe=str(row["timeframe"]),
                    open_time_utc=_snapshot_datetime(row["open_time_utc"]),
                    close_time_utc=_snapshot_datetime(row["close_time_utc"]),
                    open=as_float(row, "open"),
                    high=as_float(row, "high"),
                    low=as_float(row, "low"),
                    close=as_float(row, "close"),
                    tick_volume=as_int(row, "tick_volume"),
                    real_volume=as_int(row, "real_volume"),
                    spread=as_int(row, "spread"),
                    is_closed=bool(row["is_closed"]),
                    bar_id=str(row["bar_id"]),
                    data_quality=str(row["data_quality"]),
                    quality_flags=tuple(
                        str(item) for item in cast(list[object], row["quality_flags"])
                    ),
                )
                for row in related_bars
            ]
            status, _ = classify_freshness(
                observed_now,
                tick_record,
                bar_records,
                self.settings.freshness_threshold_seconds,
            )
            freshness[logical_symbol] = status
        return build_snapshot_payload(
            stored_snapshot=stored_snapshot,
            version=__version__,
            phase=PHASE,
            generated_at_utc=observed_now,
            freshness=freshness,
        )

    def collect_cycles(
        self,
        cycles: int,
        sleep_seconds: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, object]:
        if cycles < 1:
            raise ValueError("cycles must be at least 1")
        results: list[dict[str, object]] = []
        for index in range(cycles):
            results.append(self.collect_once(dry_run=dry_run))
            if sleep_seconds and index < cycles - 1:
                time.sleep(sleep_seconds)
        return {
            "version": __version__,
            "phase": PHASE,
            "dry_run": dry_run,
            "cycles": cycles,
            "results": results,
        }

    def storage_check(self) -> dict[str, object]:
        snapshot = self.state_store.storage_check(self.settings.parquet_root)
        snapshot["version"] = __version__
        snapshot["phase"] = PHASE
        snapshot["schema_version"] = MARKET_DATA_SCHEMA_VERSION
        return snapshot

    def _terminal_health(self) -> TerminalHealth:
        def _operation() -> TerminalHealth:
            info = self.backend.terminal_info()
            account = self.backend.account_info()
            version = self.backend.version()
            terminal_path = None if info is None else as_text(info, "path")
            server = None if account is None else as_text(account, "server")
            login_raw = None if account is None else as_text(account, "login")
            version_text = None if version is None else ".".join(str(part) for part in version)
            return TerminalHealth(
                enabled=True,
                connected=info is not None,
                backend_name=self.backend.backend_name,
                terminal_path=terminal_path,
                server=server,
                login=None if not login_raw else int(login_raw),
                ping_ms=None,
                version=version_text,
                message="connected" if info is not None else "terminal info unavailable",
            )

        return self.retry.run(_operation)

    def _list_symbols(self) -> list[DiscoveredSymbol]:
        def _operation() -> object:
            payload = self.backend.symbols_get()
            if payload is None:
                raise BackendConnectionError(
                    f"MetaTrader5 symbols_get failed: {self.backend.last_error()!r}"
                )
            return payload

        payload = self.retry.run(_operation)
        return [discovered_symbol_from_payload(item) for item in cast(list[object], payload)]

    def _resolve_symbols(self) -> tuple[list[ResolvedSymbol], list[QualityIncident]]:
        discovered = self._list_symbols()
        resolved, incidents = resolve_symbols(
            tuple((item.logical_symbol, item.aliases) for item in self.settings.symbols),
            discovered,
        )
        finalized: list[ResolvedSymbol] = []
        for symbol in resolved:
            if symbol.visible:
                finalized.append(symbol)
                continue
            broker_symbol = symbol.broker_symbol

            def _select_symbol(selected_symbol: str = broker_symbol) -> bool:
                return self.backend.symbol_select(selected_symbol, True)

            selected = self.retry.run(_select_symbol)
            if not selected:
                incidents.append(
                    QualityIncident(
                        event_kind="symbol_select_failed",
                        logical_symbol=symbol.logical_symbol,
                        timeframe=None,
                        detail="matched broker symbol could not be enabled in MarketWatch",
                        observed_at_utc=utc_now(),
                        incident_key=f"symbol_select_failed:{symbol.logical_symbol}",
                    )
                )
            finalized.append(
                ResolvedSymbol(
                    logical_symbol=symbol.logical_symbol,
                    broker_symbol=symbol.broker_symbol,
                    aliases=symbol.aliases,
                    description=symbol.description,
                    point=symbol.point,
                    digits=symbol.digits,
                    visible=selected,
                )
            )
        return finalized, incidents

    def _resolve_symbol(self, logical_symbol: str) -> ResolvedSymbol:
        resolved, incidents = self._resolve_symbols()
        for symbol in resolved:
            if symbol.logical_symbol.upper() == logical_symbol.upper():
                return symbol
        matching = [
            item.detail
            for item in incidents
            if item.logical_symbol.upper() == logical_symbol.upper()
        ]
        detail = matching[0] if matching else "symbol was not configured"
        raise ConfigValidationError(f"Unable to resolve symbol {logical_symbol!r}: {detail}")

    def _collect_symbol(
        self,
        symbol: ResolvedSymbol,
        observed_now: datetime,
        dry_run: bool,
    ) -> tuple[list[TickRecord], list[BarRecord], list[QualityIncident], dict[str, str]]:
        tick_cursor = self.state_store.get_cursor("ticks", symbol.logical_symbol)
        tick_start = (
            observed_now - timedelta(seconds=self.settings.tick_lookback_seconds)
            if tick_cursor is None
            else tick_cursor.cursor_utc
        )
        ticks, tick_incidents = self._load_ticks(symbol, tick_start, observed_now)
        bars: list[BarRecord] = []
        incidents: list[QualityIncident] = list(tick_incidents)
        current_rows: dict[tuple[str, str], BarRecord] = {}
        closed_rows: dict[tuple[str, str], BarRecord] = {}
        for timeframe in self.settings.timeframes:
            bar_cursor = self.state_store.get_cursor(
                "bars",
                symbol.logical_symbol,
                timeframe.value,
            )
            bar_start = (
                observed_now
                - timedelta(
                    seconds=MT5_TIMEFRAME_MAP[timeframe] * 60 * self.settings.bar_lookback_count
                )
                if bar_cursor is None
                else bar_cursor.cursor_utc
            )
            timeframe_bars = self._load_bars(
                symbol, timeframe, bar_start, observed_now, observed_now
            )
            normalized_bars, batch_incidents = normalize_bar_batch(timeframe_bars)
            bars.extend(normalized_bars)
            incidents.extend(batch_incidents)
            incidents.extend(detect_missing_bars(normalized_bars))
            current_update, closed_update = split_current_and_closed_bars(
                normalized_bars, observed_now
            )
            current_rows.update(current_update)
            closed_rows.update(closed_update)
        freshness, freshness_incidents = classify_freshness(
            observed_now,
            ticks,
            bars,
            self.settings.freshness_threshold_seconds,
        )
        incidents.extend(freshness_incidents)
        if not dry_run:
            self._commit_symbol(
                symbol=symbol,
                ticks=ticks,
                bars=bars,
                current_rows=current_rows,
                closed_rows=closed_rows,
                incidents=incidents,
                observed_now=observed_now,
            )
        return ticks, bars, incidents, freshness

    def _load_ticks(
        self,
        symbol: ResolvedSymbol,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[list[TickRecord], list[QualityIncident]]:
        def _range_operation() -> object:
            payload = self.backend.copy_ticks_range(
                symbol.broker_symbol,
                start_at,
                end_at,
                COPY_TICKS_ALL,
            )
            if payload is None:
                raise BackendConnectionError(
                    f"MetaTrader5 copy_ticks_range failed: {self.backend.last_error()!r}"
                )
            return payload

        payload = self.retry.run(_range_operation)
        records = [
            normalize_tick(
                symbol.logical_symbol,
                symbol.broker_symbol,
                item,
                utc_now(),
                symbol.point,
            )
            for item in cast(list[object], payload)
        ]

        latest_tick = self.retry.run(lambda: self.backend.symbol_info_tick(symbol.broker_symbol))
        if latest_tick is not None:
            records.append(
                normalize_tick(
                    symbol.logical_symbol,
                    symbol.broker_symbol,
                    latest_tick,
                    utc_now(),
                    symbol.point,
                )
            )
        normalized_ticks, incidents = normalize_tick_batch(records)
        return normalized_ticks, incidents

    def _load_bars(
        self,
        symbol: ResolvedSymbol,
        timeframe: Timeframe,
        start_at: datetime,
        end_at: datetime,
        as_of_utc: datetime,
    ) -> list[BarRecord]:
        def _range_operation() -> object:
            payload = self.backend.copy_rates_range(
                symbol.broker_symbol,
                MT5_TIMEFRAME_MAP[timeframe],
                start_at,
                end_at,
            )
            if payload is None:
                raise BackendConnectionError(
                    f"MetaTrader5 copy_rates_range failed: {self.backend.last_error()!r}"
                )
            return payload

        payload = self.retry.run(_range_operation)
        return [
            normalize_bar(symbol.logical_symbol, symbol.broker_symbol, timeframe, item, as_of_utc)
            for item in cast(list[object], payload)
        ]

    def _commit_symbol(
        self,
        symbol: ResolvedSymbol,
        ticks: list[TickRecord],
        bars: list[BarRecord],
        current_rows: dict[tuple[str, str], BarRecord],
        closed_rows: dict[tuple[str, str], BarRecord],
        incidents: list[QualityIncident],
        observed_now: datetime,
    ) -> None:
        tick_paths = self.parquet_store.write_ticks(ticks)
        bar_paths = self.parquet_store.write_bars(bars)
        _ = (tick_paths, bar_paths)
        with self.state_store.transaction() as connection:
            self.state_store.record_symbol_mapping(
                connection,
                logical_symbol=symbol.logical_symbol,
                broker_symbol=symbol.broker_symbol,
                aliases=symbol.aliases,
                description=symbol.description,
                point=symbol.point,
                digits=symbol.digits,
                visible=True,
                observed_at_utc=to_iso_z(observed_now),
            )
            for tick in ticks:
                self.state_store.upsert_latest_tick(connection, tick)
            if ticks:
                latest_tick = ticks[-1]
                self.state_store.advance_cursor(
                    connection,
                    "ticks",
                    symbol.logical_symbol,
                    "",
                    to_iso_z(latest_tick.market_time_utc),
                    latest_tick.sequence_id,
                )
            for (logical_symbol, timeframe), record in current_rows.items():
                self.state_store.upsert_latest_bar(connection, record, "current")
                self.state_store.advance_cursor(
                    connection,
                    "bars",
                    logical_symbol,
                    timeframe,
                    to_iso_z(record.open_time_utc),
                    record.bar_id,
                )
            for (logical_symbol, timeframe), record in closed_rows.items():
                previous_closed = self.state_store.get_latest_closed_bar(logical_symbol, timeframe)
                incidents.extend(detect_closed_bar_mutation(previous_closed, record))
                self.state_store.upsert_latest_bar(connection, record, "closed")
            self.state_store.record_incidents(connection, incidents)

    def _commit_bars(
        self,
        logical_symbol: str,
        timeframe: str,
        bars: list[BarRecord],
        incidents: list[QualityIncident],
    ) -> None:
        if not bars:
            return
        self.parquet_store.write_bars(bars)
        current_rows, closed_rows = split_current_and_closed_bars(bars, bars[-1].close_time_utc)
        with self.state_store.transaction() as connection:
            for (_, _), record in current_rows.items():
                self.state_store.upsert_latest_bar(connection, record, "current")
                self.state_store.advance_cursor(
                    connection,
                    "bars",
                    logical_symbol,
                    timeframe,
                    to_iso_z(record.open_time_utc),
                    record.bar_id,
                )
            for (_, _), record in closed_rows.items():
                previous_closed = self.state_store.get_latest_closed_bar(logical_symbol, timeframe)
                incidents.extend(detect_closed_bar_mutation(previous_closed, record))
                self.state_store.upsert_latest_bar(connection, record, "closed")
            self.state_store.record_incidents(connection, incidents)
