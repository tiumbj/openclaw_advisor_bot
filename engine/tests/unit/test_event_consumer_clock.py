"""Deterministic boundary tests for event_consumer expiry and clock injection.

These tests confirm:
- _is_expired boundaries (before / at / after expiry)
- now_utc injection makes consume_event deterministic
- malformed expiry fails closed
- missing expiry is treated as non-expiring
- timezone-aware non-UTC clocks are normalised
- naive datetime input is rejected with a clear error
- supplied clock cannot bypass schema or integrity validation
- expired events remain rejected regardless of clock source
- duplicate events remain rejected
- candidate-internal events remain HOLD
- invalidated events publish once before expiry
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from openclaw_super_advisor.event_consumer import (
    EventConsumerError,
    _is_expired,
    _resolve_now_utc,
    consume_event,
)
from openclaw_super_advisor.events import build_event_envelope
from openclaw_super_advisor.signal_engine import (
    SignalInput,
    build_signal_event,
    evaluate_signal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANCHOR = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
_EXPIRY_ISO = "2026-06-15T12:30:00Z"   # 30 min after anchor


def _event_with_expiry(expires: str | None) -> dict:
    payload: dict = {"score": 85.0, "some_key": "value"}
    if expires is not None:
        payload["expires_at_utc"] = expires
    return {"payload": payload}


def _valid_confirmed_event(now: datetime) -> dict:
    """Build a schema-valid CONFIRMED event that expires 1 h after *now*."""
    signal = SignalInput(
        symbol="XAUUSD",
        timeframe="M15",
        setup_id="setup-clock-test",
        trigger_version="trigger-v1",
        score_components={"trend": 55.0, "structure": 25.0, "macro": 5.0},
        evidence_ids=("ev-c1", "ev-c2", "ev-c3"),
        data_quality="VALID",
        headroom_atr=1.5,
        timeframe_agreement=3,
        fetched_at_utc=now.isoformat().replace("+00:00", "Z"),
        invalidation_rule="close below support",
        provenance={"source": "python-evidence-packet"},
    )
    decision = evaluate_signal(signal, now=now)
    return build_signal_event(signal, decision)


# ---------------------------------------------------------------------------
# _resolve_now_utc
# ---------------------------------------------------------------------------

class TestResolveNowUtc:
    def test_none_returns_utc_datetime(self) -> None:
        result = _resolve_now_utc(None)
        assert result.tzinfo is not None
        assert result.tzinfo == UTC

    def test_utc_aware_returned_unchanged(self) -> None:
        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert _resolve_now_utc(ts) == ts

    def test_non_utc_aware_normalised_to_utc(self) -> None:
        tz_plus7 = timezone(timedelta(hours=7))
        ts = datetime(2026, 6, 15, 19, 0, 0, tzinfo=tz_plus7)   # 12:00 UTC
        result = _resolve_now_utc(ts)
        assert result.tzinfo == UTC
        assert result.hour == 12

    def test_naive_datetime_raises(self) -> None:
        naive = datetime(2026, 6, 15, 12, 0, 0)
        with pytest.raises(EventConsumerError, match="naive datetime"):
            _resolve_now_utc(naive)


# ---------------------------------------------------------------------------
# _is_expired boundaries
# ---------------------------------------------------------------------------

class TestIsExpiredBoundaries:
    def test_strictly_before_expiry_not_expired(self) -> None:
        event = _event_with_expiry(_EXPIRY_ISO)
        now = _ANCHOR + timedelta(seconds=1)  # 1 second BEFORE anchor+1800 = 12:30
        # now=12:00:01, expires=12:30:00 → not expired
        assert not _is_expired(event, now)

    def test_exactly_at_expiry_is_expired(self) -> None:
        event = _event_with_expiry(_EXPIRY_ISO)
        expiry = datetime(2026, 6, 15, 12, 30, 0, tzinfo=UTC)
        assert _is_expired(event, expiry)

    def test_after_expiry_is_expired(self) -> None:
        event = _event_with_expiry(_EXPIRY_ISO)
        after = datetime(2026, 6, 15, 12, 30, 1, tzinfo=UTC)
        assert _is_expired(event, after)

    def test_missing_expiry_field_not_expired(self) -> None:
        event = _event_with_expiry(None)
        assert not _is_expired(event, _ANCHOR)

    def test_malformed_expiry_fails_closed(self) -> None:
        event = _event_with_expiry("not-a-date")
        assert _is_expired(event, _ANCHOR)

    def test_non_string_expiry_not_expired(self) -> None:
        # Non-string type → treat as missing → not expired
        event = {"payload": {"expires_at_utc": 12345}}
        assert not _is_expired(event, _ANCHOR)


# ---------------------------------------------------------------------------
# consume_event with now_utc injection
# ---------------------------------------------------------------------------

class TestConsumeEventClockInjection:
    def test_valid_event_before_expiry_publishes(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        result = consume_event(event, now_utc=now)
        assert result.action == "PUBLISH"

    def test_valid_event_after_expiry_rejects(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        # Move clock past the expiry (CONFIRMED: deduplication_window_seconds=3600)
        after_expiry = now + timedelta(seconds=3601)
        result = consume_event(event, now_utc=after_expiry)
        assert result.action == "REJECT"
        assert result.reason == "event_expired"

    def test_naive_now_utc_raises(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        naive = datetime(2026, 6, 15, 12, 0, 0)
        with pytest.raises(EventConsumerError, match="naive datetime"):
            consume_event(event, now_utc=naive)

    def test_non_utc_aware_clock_accepted_and_normalised(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        tz_plus7 = timezone(timedelta(hours=7))
        now_th = datetime(2026, 6, 15, 19, 0, 0, tzinfo=tz_plus7)
        result = consume_event(event, now_utc=now_th)
        assert result.action == "PUBLISH"

    def test_injected_clock_cannot_bypass_schema_validation(self) -> None:
        bad_event: dict = {
            "event_type": "SUPER_POTENTIAL_CONFIRMED",
            "schema_version": "wrong",
            "event_id": "x",
            "payload": {},
            "integrity_hash": "badhash",
        }
        result = consume_event(bad_event, now_utc=_ANCHOR)
        assert result.action == "REJECT"
        assert "schema_invalid" in result.reason

    def test_injected_clock_cannot_bypass_integrity_check(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        tampered = dict(event)
        tampered_payload = dict(tampered["payload"])
        tampered_payload["score"] = 0.0
        tampered["payload"] = tampered_payload
        result = consume_event(tampered, now_utc=now)
        assert result.action == "REJECT"
        assert "schema_invalid" in result.reason


# ---------------------------------------------------------------------------
# Regression: core pipeline invariants must hold with injected clock
# ---------------------------------------------------------------------------

class TestRegressionPipelineInvariants:
    def test_expired_event_still_rejected(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        future = now + timedelta(hours=2)
        result = consume_event(event, now_utc=future)
        assert result.action == "REJECT"
        assert "expired" in result.reason

    def test_duplicate_event_still_rejected(self) -> None:
        now = _ANCHOR
        event = _valid_confirmed_event(now)
        seen: set[str] = set()
        r1 = consume_event(event, seen_event_ids=seen, now_utc=now)
        assert r1.action == "PUBLISH"
        r2 = consume_event(event, seen_event_ids=seen, now_utc=now)
        assert r2.action == "REJECT"
        assert "duplicate" in r2.reason

    def test_candidate_internal_still_held(self) -> None:
        now = _ANCHOR
        signal = SignalInput(
            symbol="XAUUSD",
            timeframe="M15",
            setup_id="setup-hold",
            trigger_version="trigger-v1",
            score_components={"trend": 35.0, "structure": 25.0, "macro": 5.0},
            evidence_ids=("ev-h1", "ev-h2", "ev-h3"),
            data_quality="VALID",
            headroom_atr=1.5,
            timeframe_agreement=3,
            fetched_at_utc=now.isoformat().replace("+00:00", "Z"),
            invalidation_rule="rule",
            provenance={"source": "python"},
        )
        decision = evaluate_signal(signal, now=now)
        assert decision.state == "CANDIDATE_INTERNAL"
        event = build_signal_event(signal, decision)
        result = consume_event(event, now_utc=now)
        assert result.action == "HOLD"

    def test_invalidated_event_publishes_once_before_expiry(self) -> None:
        now = _ANCHOR
        signal = SignalInput(
            symbol="XAUUSD",
            timeframe="M15",
            setup_id="setup-inv",
            trigger_version="trigger-v1",
            score_components={"trend": 10.0, "structure": 10.0, "macro": 5.0},
            evidence_ids=("ev-i1", "ev-i2", "ev-i3"),
            data_quality="VALID",
            headroom_atr=1.5,
            timeframe_agreement=3,
            fetched_at_utc=now.isoformat().replace("+00:00", "Z"),
            invalidation_rule="rule",
            provenance={"source": "python"},
        )
        decision = evaluate_signal(signal, now=now)
        assert decision.state == "INVALIDATED"
        event = build_signal_event(signal, decision)
        seen: set[str] = set()
        r1 = consume_event(event, seen_event_ids=seen, now_utc=now)
        assert r1.action == "PUBLISH"
        r2 = consume_event(event, seen_event_ids=seen, now_utc=now)
        assert r2.action == "REJECT"
        assert "duplicate" in r2.reason

    def test_agent_numeric_source_still_rejected(self) -> None:
        event = build_event_envelope(
            "SUPER_POTENTIAL_CONFIRMED",
            {"score": 85.0},
            source_component="rogue",
            source_agent="rogue-agent",
            evidence_reference="ev-rogue",
            symbol="XAUUSD",
            timeframe="M15",
            provenance={
                "numeric_fields": {
                    "score": {
                        "source": "llm_scorer",
                        "source_system": "llm",
                        "fetched_at_utc": "2026-06-15T12:00:00Z",
                        "realtime_class": "COMPUTED",
                        "formula_version": "v1",
                    }
                }
            },
        )
        result = consume_event(event, now_utc=_ANCHOR)
        assert result.action == "REJECT"
