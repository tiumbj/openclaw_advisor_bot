from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from .constants import (
    REALTIME_CLASS_ALLOWED,
    REALTIME_CLASS_COMPUTED,
    REALTIME_CLASS_UNKNOWN,
)

EVENT_SCHEMA_VERSION = "p2.4-event-v1"
ALLOWED_EVENT_TYPES = {
    "SYSTEM_HEALTH",
    "DATA_QUALITY_WARNING",
    "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
    "SUPER_POTENTIAL_CONFIRMED",
    "SUPER_POTENTIAL_INVALIDATED",
    "SYSTEM_INCIDENT",
}
REQUIRED_EVENT_FIELDS = (
    "schema_version",
    "event_id",
    "event_type",
    "created_at_utc",
    "correlation_id",
    "causation_id",
    "source_component",
    "source_agent",
    "symbol",
    "timeframe",
    "evidence_reference",
    "payload",
    "provenance",
    "redaction_status",
    "integrity_hash",
)


@dataclass(frozen=True)
class EventIssue:
    path: str
    rule: str
    message: str


@dataclass(frozen=True)
class EventValidationReport:
    valid: bool
    issues: tuple[EventIssue, ...]
    event: dict[str, Any] | None


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _numeric_payload_fields(payload: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        key
        for key, value in payload.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    )


def _validate_numeric_provenance(
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> tuple[EventIssue, ...]:
    issues: list[EventIssue] = []
    numeric_fields = _numeric_payload_fields(payload)
    if not numeric_fields:
        return ()
    field_provenance = provenance.get("numeric_fields")
    if not isinstance(field_provenance, dict):
        return (
            EventIssue(
                "provenance.numeric_fields",
                "missing",
                "numeric payload fields require per-field provenance",
            ),
        )
    for field in numeric_fields:
        entry = field_provenance.get(field)
        if not isinstance(entry, dict):
            issues.append(
                EventIssue(
                    f"provenance.numeric_fields.{field}",
                    "missing",
                    "numeric field provenance is missing",
                )
            )
            continue
        for required in ("source", "source_system", "fetched_at_utc", "realtime_class"):
            if not entry.get(required):
                issues.append(
                    EventIssue(
                        f"provenance.numeric_fields.{field}.{required}",
                        "missing",
                        "numeric provenance field is required",
                    )
                )
        realtime_class = entry.get("realtime_class")
        if realtime_class not in REALTIME_CLASS_ALLOWED or realtime_class == REALTIME_CLASS_UNKNOWN:
            issues.append(
                EventIssue(
                    f"provenance.numeric_fields.{field}.realtime_class",
                    "invalid",
                    "numeric provenance realtime_class must be explicit",
                )
            )
        if realtime_class == REALTIME_CLASS_COMPUTED and not entry.get("formula_version"):
            issues.append(
                EventIssue(
                    f"provenance.numeric_fields.{field}.formula_version",
                    "missing",
                    "COMPUTED numeric provenance requires formula_version",
                )
            )
        source_system = str(entry.get("source_system", "")).lower()
        if source_system in {"agent", "llm", "specialist"}:
            issues.append(
                EventIssue(
                    f"provenance.numeric_fields.{field}.source_system",
                    "forbidden",
                    "agents may not originate numeric market evidence",
                )
            )
    return tuple(issues)


def build_event_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    source_component: str,
    source_agent: str,
    evidence_reference: str,
    symbol: str = "UNKNOWN",
    timeframe: str = "UNKNOWN",
    correlation_id: str | None = None,
    causation_id: str | None = None,
    provenance: dict[str, Any] | None = None,
    redaction_status: str = "REDACTED",
) -> dict[str, Any]:
    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": str(uuid4()),
        "event_type": event_type,
        "created_at_utc": utc_now(),
        "correlation_id": correlation_id or str(uuid4()),
        "causation_id": causation_id or "",
        "source_component": source_component,
        "source_agent": source_agent,
        "symbol": symbol,
        "timeframe": timeframe,
        "evidence_reference": evidence_reference,
        "payload": payload,
        "provenance": provenance or {},
        "redaction_status": redaction_status,
        "integrity_hash": "",
    }
    event["integrity_hash"] = sha256_hex(canonical_json(event))
    return event


def validate_event_envelope(event: dict[str, Any]) -> EventValidationReport:
    issues: list[EventIssue] = []
    for field in REQUIRED_EVENT_FIELDS:
        if field not in event:
            issues.append(EventIssue(field, "missing", "required event field is missing"))
    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        issues.append(
            EventIssue(
                "schema_version",
                "version_mismatch",
                f"expected {EVENT_SCHEMA_VERSION!r}",
            )
        )
    event_type = event.get("event_type")
    if event_type not in ALLOWED_EVENT_TYPES:
        issues.append(EventIssue("event_type", "unsupported", "unsupported event type"))
    for key in set(event).difference(REQUIRED_EVENT_FIELDS):
        if key not in REQUIRED_EVENT_FIELDS:
            issues.append(EventIssue(key, "unknown_field", "unknown field not allowed"))
    payload = event.get("payload")
    if not isinstance(payload, dict):
        issues.append(EventIssue("payload", "type", "payload must be an object"))
    provenance = event.get("provenance")
    if not isinstance(provenance, dict):
        issues.append(EventIssue("provenance", "type", "provenance must be an object"))
    elif isinstance(payload, dict):
        issues.extend(_validate_numeric_provenance(payload, provenance))
    if event.get("symbol") is None or event.get("timeframe") is None:
        issues.append(EventIssue("symbol", "missing", "symbol/timeframe required"))
    integrity_hash = event.get("integrity_hash")
    if isinstance(integrity_hash, str):
        candidate = dict(event)
        candidate["integrity_hash"] = ""
        expected_hash = sha256_hex(canonical_json(candidate))
        if integrity_hash != expected_hash:
            issues.append(
                EventIssue("integrity_hash", "mismatch", "integrity hash does not match payload")
            )
    else:
        issues.append(EventIssue("integrity_hash", "missing", "integrity hash is required"))
    return EventValidationReport(
        valid=not issues, issues=tuple(issues), event=event if not issues else None
    )


def redact_event(event: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(canonical_json(event))
    payload = redacted.get("payload")
    if isinstance(payload, dict):
        for key in ("price", "probability", "entry", "stop_loss", "take_profit", "score"):
            if key in payload:
                payload[key] = "UNKNOWN"
    redacted["redaction_status"] = "REDACTED"
    redacted["integrity_hash"] = ""
    redacted["integrity_hash"] = sha256_hex(canonical_json(redacted))
    return cast(dict[str, Any], redacted)
