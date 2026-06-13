from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime


def _to_iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware UTC")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TickRecord:
    schema_version: str
    collector_version: str
    logical_symbol: str
    broker_symbol: str
    market_time_utc: datetime
    market_time_msc: int
    received_at_utc: datetime
    bid: float
    ask: float
    last: float
    volume: float
    volume_real: float
    flags: int
    spread_points: int
    sequence_id: str
    data_quality: str
    quality_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["market_time_utc"] = _to_iso_z(self.market_time_utc)
        payload["received_at_utc"] = _to_iso_z(self.received_at_utc)
        payload["quality_flags"] = list(self.quality_flags)
        return payload


@dataclass(frozen=True)
class BarRecord:
    schema_version: str
    collector_version: str
    logical_symbol: str
    broker_symbol: str
    timeframe: str
    open_time_utc: datetime
    close_time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    real_volume: int
    spread: int
    is_closed: bool
    bar_id: str
    data_quality: str
    quality_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["open_time_utc"] = _to_iso_z(self.open_time_utc)
        payload["close_time_utc"] = _to_iso_z(self.close_time_utc)
        payload["quality_flags"] = list(self.quality_flags)
        return payload


@dataclass(frozen=True)
class QualityIncident:
    event_kind: str
    logical_symbol: str
    timeframe: str | None
    detail: str
    observed_at_utc: datetime
    incident_key: str

    def to_dict(self) -> dict[str, object]:
        return {
            "event_kind": self.event_kind,
            "logical_symbol": self.logical_symbol,
            "timeframe": self.timeframe,
            "detail": self.detail,
            "observed_at_utc": _to_iso_z(self.observed_at_utc),
            "incident_key": self.incident_key,
        }


@dataclass(frozen=True)
class HeartbeatRecord:
    collector_name: str
    status: str
    detail: dict[str, object]
    observed_at_utc: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "collector_name": self.collector_name,
            "status": self.status,
            "detail": self.detail,
            "observed_at_utc": _to_iso_z(self.observed_at_utc),
        }
