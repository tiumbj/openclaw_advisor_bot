"""Heartbeat module — internal collector record and external signed heartbeat emitter.

Internal: build_heartbeat() creates HeartbeatRecord for system-local monitoring.
External: HeartbeatEmitter creates signed ExternalHeartbeat payloads for remote monitors.

IMPORTANT: If no external endpoint is configured, the emitter logs
HEARTBEAT_EXTERNAL_NOT_CONFIGURED and does NOT fail the pipeline.
The local machine cannot notify Telegram after a power failure — external monitoring is required.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from ..market_data.normalization import ensure_utc
from ..market_data.schemas import HeartbeatRecord

HEARTBEAT_SCHEMA_VERSION = "heartbeat-v1"


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


@dataclass(frozen=True)
class ComponentHealth:
    gateway: str
    python_engine: str
    queue: str
    mt5: str


@dataclass(frozen=True)
class ExternalHeartbeat:
    schema_version: str
    system_id: str
    emitted_at_utc: str
    sequence: int
    component_health: ComponentHealth
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "system_id": self.system_id,
            "emitted_at_utc": self.emitted_at_utc,
            "sequence": self.sequence,
            "component_health": {
                "gateway": self.component_health.gateway,
                "python_engine": self.component_health.python_engine,
                "queue": self.component_health.queue,
                "mt5": self.component_health.mt5,
            },
            "signature": self.signature,
        }


@dataclass(frozen=True)
class MissedHeartbeatIncident:
    schema_version: str
    system_id: str
    last_seen_at_utc: str
    detected_at_utc: str
    missed_count: int
    threshold_count: int
    telegram_event_type: str
    severity: str
    message: str


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _sign_payload(payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_external_heartbeat(
    system_id: str,
    sequence: int,
    component_health: ComponentHealth,
    signing_secret: str,
) -> ExternalHeartbeat:
    """Build a signed ExternalHeartbeat payload."""
    emitted_at = _utc_now_str()
    unsigned = json.dumps(
        {
            "schema_version": HEARTBEAT_SCHEMA_VERSION,
            "system_id": system_id,
            "emitted_at_utc": emitted_at,
            "sequence": sequence,
            "component_health": {
                "gateway": component_health.gateway,
                "python_engine": component_health.python_engine,
                "queue": component_health.queue,
                "mt5": component_health.mt5,
            },
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    signature = _sign_payload(unsigned, signing_secret)
    return ExternalHeartbeat(
        schema_version=HEARTBEAT_SCHEMA_VERSION,
        system_id=system_id,
        emitted_at_utc=emitted_at,
        sequence=sequence,
        component_health=component_health,
        signature=signature,
    )


def build_missed_heartbeat_incident(
    system_id: str,
    last_seen_at_utc: str,
    missed_count: int,
    threshold_count: int,
) -> MissedHeartbeatIncident:
    """Build a missed-heartbeat incident payload for Telegram dispatch."""
    return MissedHeartbeatIncident(
        schema_version=HEARTBEAT_SCHEMA_VERSION,
        system_id=system_id,
        last_seen_at_utc=last_seen_at_utc,
        detected_at_utc=_utc_now_str(),
        missed_count=missed_count,
        threshold_count=threshold_count,
        telegram_event_type="SYSTEM_OFFLINE_DETECTED",
        severity="CRITICAL",
        message=(
            f"ระบบ {system_id} ไม่ส่ง heartbeat มา {missed_count} รอบ "
            f"(เกณฑ์: {threshold_count} รอบ) "
            f"ครั้งล่าสุดที่พบ: {last_seen_at_utc}"
        ),
    )


class HeartbeatEmitter:
    """Emits signed heartbeats to an optional external monitor endpoint.

    If endpoint is None or empty, logs HEARTBEAT_EXTERNAL_NOT_CONFIGURED.
    Failure to emit does NOT stop the pipeline.
    """

    def __init__(
        self,
        system_id: str,
        signing_secret: str,
        endpoint: str | None = None,
        timeout_seconds: int = 10,
    ) -> None:
        self._system_id = system_id
        self._signing_secret = signing_secret
        self._endpoint = endpoint or ""
        self._timeout = timeout_seconds
        self._sequence = 0

    def emit(self, component_health: ComponentHealth) -> dict[str, Any]:
        """Build and emit a heartbeat. Returns a result dict."""
        self._sequence += 1
        hb = build_external_heartbeat(
            system_id=self._system_id,
            sequence=self._sequence,
            component_health=component_health,
            signing_secret=self._signing_secret,
        )

        if not self._endpoint:
            return {
                "status": "HEARTBEAT_EXTERNAL_NOT_CONFIGURED",
                "heartbeat": hb.to_dict(),
                "warning": "No external endpoint configured; local heartbeat only.",
            }

        payload = json.dumps(hb.to_dict(), ensure_ascii=True).encode("utf-8")
        req = Request(
            self._endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                return {"status": "EMITTED", "http_status": resp.status, "heartbeat": hb.to_dict()}
        except URLError as exc:
            return {
                "status": "EMIT_FAILED",
                "error": str(exc),
                "heartbeat": hb.to_dict(),
            }
        except Exception as exc:
            return {
                "status": "EMIT_FAILED",
                "error": str(exc),
                "heartbeat": hb.to_dict(),
            }
