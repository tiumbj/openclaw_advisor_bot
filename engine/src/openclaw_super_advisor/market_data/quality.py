from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from itertools import pairwise

from .normalization import utc_now
from .schemas import BarRecord, QualityIncident, TickRecord
from .timeframes import timeframe_delta, timeframe_seconds


def _incident(
    event_kind: str,
    logical_symbol: str,
    timeframe: str | None,
    detail: str,
    unique_suffix: str,
    observed_at_utc: datetime | None = None,
) -> QualityIncident:
    return QualityIncident(
        event_kind=event_kind,
        logical_symbol=logical_symbol,
        timeframe=timeframe,
        detail=detail,
        observed_at_utc=observed_at_utc or utc_now(),
        incident_key=f"{event_kind}:{logical_symbol}:{timeframe or 'tick'}:{unique_suffix}",
    )


def normalize_tick_batch(
    records: list[TickRecord],
) -> tuple[list[TickRecord], list[QualityIncident]]:
    if not records:
        return [], []
    incidents: list[QualityIncident] = []
    if any(left.market_time_msc > right.market_time_msc for left, right in pairwise(records)):
        incidents.append(
            _incident(
                "out_of_order_ticks",
                records[0].logical_symbol,
                None,
                "tick records arrived out of order and were normalized",
                "batch",
            )
        )
    tick_collisions = {
        record.market_time_msc
        for record in records
        if len(
            {
                item.sequence_id
                for item in records
                if item.market_time_msc == record.market_time_msc
            }
        )
        > 1
    }
    if tick_collisions:
        incidents.append(
            _incident(
                "tick_time_collision",
                records[0].logical_symbol,
                None,
                f"detected {len(tick_collisions)} timestamps with differing tick payloads",
                str(min(tick_collisions)),
            )
        )
    deduped: list[TickRecord] = []
    seen: set[str] = set()
    duplicate_count = 0
    for record in sorted(records, key=lambda item: item.market_time_msc):
        if record.sequence_id in seen:
            duplicate_count += 1
            continue
        seen.add(record.sequence_id)
        deduped.append(record)
    if duplicate_count:
        incidents.append(
            _incident(
                "duplicate_ticks",
                records[0].logical_symbol,
                None,
                f"removed {duplicate_count} duplicate tick rows",
                "batch",
            )
        )
    return deduped, incidents


def normalize_bar_batch(records: list[BarRecord]) -> tuple[list[BarRecord], list[QualityIncident]]:
    if not records:
        return [], []
    incidents: list[QualityIncident] = []
    if any(left.open_time_utc > right.open_time_utc for left, right in pairwise(records)):
        incidents.append(
            _incident(
                "out_of_order_bars",
                records[0].logical_symbol,
                records[0].timeframe,
                "bar records arrived out of order and were normalized",
                "batch",
            )
        )
    deduped: list[BarRecord] = []
    seen: set[str] = set()
    duplicate_count = 0
    for record in sorted(records, key=lambda item: item.open_time_utc):
        if record.bar_id in seen:
            duplicate_count += 1
            continue
        seen.add(record.bar_id)
        deduped.append(record)
    if duplicate_count:
        incidents.append(
            _incident(
                "duplicate_bars",
                records[0].logical_symbol,
                records[0].timeframe,
                f"removed {duplicate_count} duplicate bar rows",
                "batch",
            )
        )
    return deduped, incidents


def split_current_and_closed_bars(
    records: list[BarRecord],
    as_of_utc: datetime,
) -> tuple[dict[tuple[str, str], BarRecord], dict[tuple[str, str], BarRecord]]:
    current_rows: dict[tuple[str, str], BarRecord] = {}
    closed_rows: dict[tuple[str, str], BarRecord] = {}
    for record in records:
        key = (record.logical_symbol, record.timeframe)
        if record.close_time_utc <= as_of_utc:
            closed_rows[key] = record
        else:
            current_rows[key] = record
    return current_rows, closed_rows


def detect_missing_bars(records: list[BarRecord]) -> list[QualityIncident]:
    if len(records) < 2:
        return []
    incidents: list[QualityIncident] = []
    expected_gap = timeframe_delta(records[0].timeframe)
    for previous, current in pairwise(records):
        gap = current.open_time_utc - previous.open_time_utc
        if gap <= expected_gap:
            continue
        missing = 0
        candidate = previous.open_time_utc + expected_gap
        while candidate < current.open_time_utc:
            if candidate.weekday() < 5:
                missing += 1
            candidate += expected_gap
        if missing:
            incidents.append(
                _incident(
                    "missing_bars",
                    current.logical_symbol,
                    current.timeframe,
                    f"detected {missing} missing {current.timeframe} bars",
                    current.bar_id,
                )
            )
    return incidents


def detect_closed_bar_mutation(
    previous_closed: BarRecord | None,
    latest_closed: BarRecord | None,
) -> list[QualityIncident]:
    if previous_closed is None or latest_closed is None:
        return []
    if previous_closed.bar_id != latest_closed.bar_id:
        return []
    left = (
        previous_closed.open,
        previous_closed.high,
        previous_closed.low,
        previous_closed.close,
        previous_closed.tick_volume,
        previous_closed.real_volume,
        previous_closed.spread,
    )
    right = (
        latest_closed.open,
        latest_closed.high,
        latest_closed.low,
        latest_closed.close,
        latest_closed.tick_volume,
        latest_closed.real_volume,
        latest_closed.spread,
    )
    if left == right:
        return []
    return [
        _incident(
            "closed_bar_mutation",
            latest_closed.logical_symbol,
            latest_closed.timeframe,
            "closed bar changed after it had already been persisted",
            latest_closed.bar_id,
        )
    ]


def classify_freshness(
    now_utc: datetime,
    ticks: Iterable[TickRecord],
    bars: Iterable[BarRecord],
    freshness_threshold_seconds: int,
) -> tuple[dict[str, str], list[QualityIncident]]:
    tick_list = list(ticks)
    bar_list = list(bars)
    incidents: list[QualityIncident] = []
    status = {"ticks": "unknown", "bars": "unknown"}
    if tick_list:
        latest_tick = max(tick_list, key=lambda item: item.market_time_msc)
        tick_age = (now_utc - latest_tick.market_time_utc).total_seconds()
        status["ticks"] = "fresh" if tick_age <= freshness_threshold_seconds else "stale"
        if status["ticks"] == "stale" and now_utc.weekday() < 5:
            incidents.append(
                _incident(
                    "stale_tick",
                    latest_tick.logical_symbol,
                    None,
                    f"latest tick is older than {freshness_threshold_seconds} seconds",
                    latest_tick.sequence_id,
                    observed_at_utc=now_utc,
                )
            )
    if bar_list:
        latest_bar = max(bar_list, key=lambda item: item.open_time_utc)
        bar_age = (now_utc - latest_bar.open_time_utc).total_seconds()
        threshold = max(freshness_threshold_seconds, timeframe_seconds(latest_bar.timeframe) * 2)
        status["bars"] = "fresh" if bar_age <= threshold else "stale"
        if status["bars"] == "stale" and now_utc.weekday() < 5:
            incidents.append(
                _incident(
                    "stale_bar",
                    latest_bar.logical_symbol,
                    latest_bar.timeframe,
                    f"latest bar is older than {threshold} seconds",
                    latest_bar.bar_id,
                    observed_at_utc=now_utc,
                )
            )
    return status, incidents
