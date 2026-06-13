from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .timeframes import timeframe_delta


@dataclass(frozen=True)
class CursorState:
    stream_kind: str
    logical_symbol: str
    timeframe: str
    cursor_utc: datetime
    marker_id: str


@dataclass(frozen=True)
class BackfillState:
    run_key: str
    logical_symbol: str
    timeframe: str
    start_at_utc: datetime
    end_at_utc: datetime
    next_start_utc: datetime
    status: str
    last_error: str | None


def advance_window(
    start_at_utc: datetime,
    end_at_utc: datetime,
    timeframe: str,
    max_bars: int,
) -> datetime:
    return min(end_at_utc, start_at_utc + (timeframe_delta(timeframe) * max_bars))
