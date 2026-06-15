from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openclaw_super_advisor.events import validate_event_envelope
from openclaw_super_advisor.signal_engine import SignalInput, build_signal_event, evaluate_signal


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _signal(now: datetime, **overrides: object) -> SignalInput:
    base = {
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "setup_id": "setup-1",
        "trigger_version": "trigger-v1",
        "score_components": {"trend": 35.0, "structure": 25.0, "macro": 20.0},
        "evidence_ids": ("ev-1", "ev-2", "ev-3"),
        "data_quality": "VALID",
        "headroom_atr": 1.5,
        "timeframe_agreement": 3,
        "fetched_at_utc": _iso(now - timedelta(seconds=10)),
        "invalidation_rule": "M15 close below support",
        "provenance": {"source": "python-evidence-packet"},
    }
    base.update(overrides)
    return SignalInput(**base)  # type: ignore[arg-type]


def test_signal_engine_confirms_only_when_deterministic_gates_pass() -> None:
    now = datetime(2026, 6, 15, tzinfo=UTC)

    decision = evaluate_signal(_signal(now), now=now)

    assert decision.state == "CONFIRMED"
    assert decision.score == 80.0
    assert decision.failed_gates == ()
    assert decision.threshold_version == "signal-thresholds-p2.4-v1"
    assert decision.dedup_key == "SUPER_POTENTIAL_CONFIRMED:XAUUSD:M15:setup-1:trigger-v1"


def test_signal_engine_fails_closed_on_data_quality_and_freshness() -> None:
    now = datetime(2026, 6, 15, tzinfo=UTC)

    decision = evaluate_signal(
        _signal(now, data_quality="DEGRADED", fetched_at_utc=_iso(now - timedelta(minutes=10))),
        now=now,
    )

    assert decision.state == "NO_SETUP"
    assert "minimum_data_quality" in decision.failed_gates
    assert "freshness" in decision.failed_gates


def test_confirmed_signal_event_has_python_numeric_provenance() -> None:
    now = datetime(2026, 6, 15, tzinfo=UTC)
    signal = _signal(now)
    decision = evaluate_signal(signal, now=now)

    event = build_signal_event(signal, decision)
    report = validate_event_envelope(event)

    assert report.valid
    assert event["event_type"] == "SUPER_POTENTIAL_CONFIRMED"
    score_provenance = event["provenance"]["numeric_fields"]["score"]
    assert score_provenance["source_system"] == "python"
    assert score_provenance["formula_version"] == decision.threshold_version
