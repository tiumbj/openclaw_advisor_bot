from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from .events import build_event_envelope

SignalState = Literal["NO_SETUP", "CANDIDATE_INTERNAL", "CONFIRMED", "INVALIDATED", "EXPIRED"]


@dataclass(frozen=True)
class ThresholdConfig:
    version: str = "signal-thresholds-p2.4-v1"
    candidate_threshold: float = 65.0
    confirmed_threshold: float = 80.0
    invalidation_threshold: float = 45.0
    minimum_evidence_count: int = 3
    minimum_data_quality: str = "VALID"
    minimum_headroom_atr: float = 1.0
    minimum_timeframe_agreement: int = 2
    freshness_seconds: int = 180
    cooldown_seconds: int = 3600
    deduplication_window_seconds: int = 3600
    invalidation_expiry_seconds: int = 1800


@dataclass(frozen=True)
class SignalInput:
    symbol: str
    timeframe: str
    setup_id: str
    trigger_version: str
    score_components: dict[str, float]
    evidence_ids: tuple[str, ...]
    data_quality: str
    headroom_atr: float
    timeframe_agreement: int
    fetched_at_utc: str
    invalidation_rule: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class SignalDecision:
    state: SignalState
    score: float
    threshold_version: str
    trigger_reasons: tuple[str, ...]
    failed_gates: tuple[str, ...]
    invalidation_rule: str
    evidence_ids: tuple[str, ...]
    provenance: dict[str, Any]
    created_at_utc: str
    expires_at_utc: str
    dedup_key: str


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def evaluate_signal(
    signal: SignalInput,
    *,
    thresholds: ThresholdConfig | None = None,
    now: datetime | None = None,
) -> SignalDecision:
    config = thresholds or ThresholdConfig()
    now = now or _utc_now()
    score = round(sum(signal.score_components.values()), 4)
    failed: list[str] = []
    if len(signal.evidence_ids) < config.minimum_evidence_count:
        failed.append("minimum_evidence_count")
    if signal.data_quality != config.minimum_data_quality:
        failed.append("minimum_data_quality")
    if signal.headroom_atr < config.minimum_headroom_atr:
        failed.append("minimum_headroom")
    if signal.timeframe_agreement < config.minimum_timeframe_agreement:
        failed.append("timeframe_agreement")
    if (now - _parse_utc(signal.fetched_at_utc)).total_seconds() > config.freshness_seconds:
        failed.append("freshness")
    if not signal.provenance:
        failed.append("provenance")

    if failed:
        state: SignalState = "NO_SETUP"
    elif score >= config.confirmed_threshold:
        state = "CONFIRMED"
    elif score >= config.candidate_threshold:
        state = "CANDIDATE_INTERNAL"
    elif score <= config.invalidation_threshold:
        state = "INVALIDATED"
    else:
        state = "NO_SETUP"

    expires = now + timedelta(
        seconds=(
            config.invalidation_expiry_seconds
            if state == "INVALIDATED"
            else config.deduplication_window_seconds
        )
    )
    reasons = tuple(
        key for key, value in sorted(signal.score_components.items()) if value > 0
    )
    dedup_key = (
        f"SUPER_POTENTIAL_{state}:{signal.symbol}:{signal.timeframe}:"
        f"{signal.setup_id}:{signal.trigger_version}"
    )
    return SignalDecision(
        state=state,
        score=score,
        threshold_version=config.version,
        trigger_reasons=reasons,
        failed_gates=tuple(failed),
        invalidation_rule=signal.invalidation_rule,
        evidence_ids=signal.evidence_ids,
        provenance=signal.provenance,
        created_at_utc=_iso_z(now),
        expires_at_utc=_iso_z(expires),
        dedup_key=dedup_key,
    )


def build_signal_event(signal: SignalInput, decision: SignalDecision) -> dict[str, Any]:
    event_type = {
        "CANDIDATE_INTERNAL": "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
        "CONFIRMED": "SUPER_POTENTIAL_CONFIRMED",
        "INVALIDATED": "SUPER_POTENTIAL_INVALIDATED",
    }.get(decision.state)
    if event_type is None:
        raise ValueError(f"state {decision.state} is not publishable as a signal event")
    return build_event_envelope(
        event_type,
        {
            "score": decision.score,
            "score_components": signal.score_components,
            "threshold_version": decision.threshold_version,
            "trigger_reasons": list(decision.trigger_reasons),
            "failed_gates": list(decision.failed_gates),
            "invalidation_rule": decision.invalidation_rule,
            "evidence_ids": list(decision.evidence_ids),
            "created_at_utc": decision.created_at_utc,
            "expires_at_utc": decision.expires_at_utc,
            "dedup_key": decision.dedup_key,
        },
        source_component="python-signal-engine",
        source_agent="super-advisor",
        evidence_reference=",".join(decision.evidence_ids),
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        provenance={
            **decision.provenance,
            "numeric_fields": {
                "score": {
                    "source": "python_signal_engine",
                    "source_system": "python",
                    "fetched_at_utc": signal.fetched_at_utc,
                    "realtime_class": "COMPUTED",
                    "formula_version": decision.threshold_version,
                }
            },
        },
    )
