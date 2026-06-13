from __future__ import annotations

from datetime import datetime

from .normalization import to_iso_z


def build_snapshot_payload(
    stored_snapshot: dict[str, object],
    version: str,
    phase: str,
    generated_at_utc: datetime,
    freshness: dict[str, dict[str, str]],
) -> dict[str, object]:
    payload = dict(stored_snapshot)
    payload["version"] = version
    payload["phase"] = phase
    payload["generated_at_utc"] = to_iso_z(generated_at_utc)
    payload["freshness"] = freshness
    return payload
