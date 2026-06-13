from __future__ import annotations

from datetime import datetime

from ..market_data.normalization import ensure_utc
from ..market_data.schemas import HeartbeatRecord


def build_heartbeat(
    collector_name: str,
    status: str,
    detail: dict[str, object],
    observed_at_utc: datetime,
) -> HeartbeatRecord:
    redacted_detail = {
        key: value
        for key, value in detail.items()
        if "password" not in key.lower() and "token" not in key.lower()
    }
    return HeartbeatRecord(
        collector_name=collector_name,
        status=status,
        detail=redacted_detail,
        observed_at_utc=ensure_utc(observed_at_utc),
    )
