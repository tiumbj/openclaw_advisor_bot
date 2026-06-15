"""MAIN event consumer: validate incoming signal events, enforce publication policy.

This module connects signal_engine output → EvidenceArchive → publication decision.
No tokens, no Telegram API calls — those belong in telegram.TelegramMarketTransport.

Blueprint §3.5: Event Producer/Consumer contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .events import validate_event_envelope

ALLOWED_MARKET_PUBLISH = frozenset(
    {
        "SUPER_POTENTIAL_CONFIRMED",
        "SUPER_POTENTIAL_INVALIDATED",
        "DATA_QUALITY_WARNING",
        "SYSTEM_INCIDENT",
    }
)
FORBIDDEN_MARKET_PUBLISH = frozenset(
    {
        "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
        "SYSTEM_HEALTH",
    }
)
AGENT_NUMERIC_SOURCES = frozenset({"agent", "llm", "specialist"})


class EventConsumerError(RuntimeError):
    pass


def _resolve_now_utc(now_utc: datetime | None) -> datetime:
    """Return a UTC-normalised reference clock for expiry checks.

    Production callers pass ``None`` → real wall clock.
    Test callers supply a frozen ``datetime`` → deterministic behaviour.
    A naive ``datetime`` is rejected immediately so tests cannot silently
    pass a wall-clock value disguised as a controlled clock.
    """
    if now_utc is None:
        return datetime.now(tz=UTC)
    if now_utc.tzinfo is None:
        raise EventConsumerError(
            "now_utc must be timezone-aware; received a naive datetime"
        )
    return now_utc.astimezone(UTC)


@dataclass(frozen=True)
class ConsumptionDecision:
    event_id: str
    event_type: str
    action: str
    reason: str


def _is_expired(event: dict[str, Any], now_utc: datetime) -> bool:
    """Return True if the event's expiry timestamp is at or before ``now_utc``.

    Fail-closed on malformed or missing timestamps:
    - missing field → not expired (treat as non-expiring)
    - unparseable string → expired (fail closed)
    """
    payload = event.get("payload", {})
    expires_raw = payload.get("expires_at_utc")
    if not isinstance(expires_raw, str):
        return False
    try:
        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00")).astimezone(UTC)
        return expires <= now_utc
    except ValueError:
        return True


def _has_agent_numeric_source(event: dict[str, Any]) -> bool:
    provenance = event.get("provenance", {})
    numeric = provenance.get("numeric_fields")
    if not isinstance(numeric, dict):
        return False
    return any(
        str(field_prov.get("source_system", "")).lower() in AGENT_NUMERIC_SOURCES
        for field_prov in numeric.values()
        if isinstance(field_prov, dict)
    )


def consume_event(
    event: dict[str, Any],
    *,
    seen_event_ids: set[str] | None = None,
    now_utc: datetime | None = None,
) -> ConsumptionDecision:
    """Validate a signal event and decide whether to publish, hold, or reject.

    Parameters
    ----------
    event:
        The event envelope dict to evaluate.
    seen_event_ids:
        Mutable set used for deduplication.  Pass an empty set on first call
        and the same set on subsequent calls within the same session.
    now_utc:
        Reference clock for expiry checks.  ``None`` (default) uses the real
        UTC wall clock, preserving production behaviour.  Supply a
        timezone-aware ``datetime`` in tests to make expiry checks
        deterministic regardless of when the test suite runs.
        A naive ``datetime`` raises ``EventConsumerError``.

    Rules (applied in order, fail-closed):
    1. Schema invalid → REJECT
    2. Integrity hash mismatch → REJECT
    3. Numeric evidence from agent/LLM → REJECT
    4. Missing provenance → REJECT
    5. Duplicate event_id → REJECT
    6. CANDIDATE_INTERNAL → HOLD (never published externally)
    7. Expired event → REJECT
    8. Event type not in allowed publish set → HOLD
    9. CONFIRMED / INVALIDATED / DATA_QUALITY_WARNING / SYSTEM_INCIDENT → PUBLISH
    """
    effective_now = _resolve_now_utc(now_utc)

    report = validate_event_envelope(event)
    if not report.valid:
        issues_text = "; ".join(f"{i.path}: {i.message}" for i in report.issues)
        return ConsumptionDecision(
            event_id=str(event.get("event_id", "")),
            event_type=str(event.get("event_type", "")),
            action="REJECT",
            reason=f"schema_invalid: {issues_text}",
        )

    event_id = str(event["event_id"])
    event_type = str(event["event_type"])

    if _has_agent_numeric_source(event):
        return ConsumptionDecision(
            event_id=event_id, event_type=event_type,
            action="REJECT", reason="agent_numeric_source_forbidden",
        )

    provenance = event.get("provenance")
    if not provenance:
        return ConsumptionDecision(
            event_id=event_id, event_type=event_type,
            action="REJECT", reason="missing_provenance",
        )

    if seen_event_ids is not None and event_id in seen_event_ids:
        return ConsumptionDecision(
            event_id=event_id, event_type=event_type,
            action="REJECT", reason="duplicate_event_id",
        )

    if event_type in FORBIDDEN_MARKET_PUBLISH:
        return ConsumptionDecision(
            event_id=event_id, event_type=event_type,
            action="HOLD", reason="candidate_internal_not_published",
        )

    if _is_expired(event, effective_now):
        return ConsumptionDecision(
            event_id=event_id, event_type=event_type,
            action="REJECT", reason="event_expired",
        )

    if event_type not in ALLOWED_MARKET_PUBLISH:
        return ConsumptionDecision(
            event_id=event_id, event_type=event_type,
            action="HOLD", reason=f"event_type_not_in_publish_allowlist: {event_type}",
        )

    if seen_event_ids is not None:
        seen_event_ids.add(event_id)

    return ConsumptionDecision(
        event_id=event_id, event_type=event_type,
        action="PUBLISH", reason="all_gates_passed",
    )
