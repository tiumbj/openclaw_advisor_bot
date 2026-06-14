"""Experiment lifecycle state machine (16 states).

Every research hypothesis goes through this machine before any code change
can be proposed. The HUMAN_RELEASE_GATE state requires explicit external approval.
No agent may approve its own experiment.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

# 16-state machine as specified in Blueprint §14
VALID_STATES = (
    "OBSERVATION",
    "HYPOTHESIS",
    "EXPERIMENT_DESIGNED",
    "DATA_VALIDATED",
    "BACKTEST_RUNNING",
    "RESULT_REVIEW",
    "REJECTED",
    "NEEDS_MORE_DATA",
    "APPROVED_CANDIDATE",
    "ISOLATED_PATCH",
    "REGRESSION_TEST",
    "SECURITY_REVIEW",
    "RELEASE_PROPOSAL",
    "HUMAN_RELEASE_GATE",
    "RELEASED",
    "ROLLED_BACK",
)

# Terminal states — no further transitions
TERMINAL_STATES = frozenset(("REJECTED", "RELEASED", "ROLLED_BACK"))

# Valid forward transitions
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "OBSERVATION": frozenset(["HYPOTHESIS", "REJECTED"]),
    "HYPOTHESIS": frozenset(["EXPERIMENT_DESIGNED", "REJECTED"]),
    "EXPERIMENT_DESIGNED": frozenset(["DATA_VALIDATED", "REJECTED"]),
    "DATA_VALIDATED": frozenset(["BACKTEST_RUNNING", "REJECTED"]),
    "BACKTEST_RUNNING": frozenset(["RESULT_REVIEW", "REJECTED"]),
    "RESULT_REVIEW": frozenset(["REJECTED", "NEEDS_MORE_DATA", "APPROVED_CANDIDATE"]),
    "NEEDS_MORE_DATA": frozenset(["DATA_VALIDATED", "REJECTED"]),
    "APPROVED_CANDIDATE": frozenset(["ISOLATED_PATCH", "REJECTED"]),
    "ISOLATED_PATCH": frozenset(["REGRESSION_TEST", "REJECTED"]),
    "REGRESSION_TEST": frozenset(["SECURITY_REVIEW", "REJECTED"]),
    "SECURITY_REVIEW": frozenset(["RELEASE_PROPOSAL", "REJECTED"]),
    "RELEASE_PROPOSAL": frozenset(["HUMAN_RELEASE_GATE", "REJECTED"]),
    "HUMAN_RELEASE_GATE": frozenset(["RELEASED", "REJECTED"]),
    "RELEASED": frozenset(["ROLLED_BACK"]),
    "REJECTED": frozenset(),
    "ROLLED_BACK": frozenset(),
}


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _fingerprint(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class ExperimentTransition:
    from_state: str
    to_state: str
    transitioned_at_utc: str
    agent: str
    reason: str
    reviewer: str | None
    evidence_ids: list[str]


@dataclass
class Experiment:
    experiment_id: str
    correlation_id: str
    hypothesis: str
    proposer_agent: str
    owner_agent: str
    state: str
    created_at_utc: str
    updated_at_utc: str
    input_data_range: dict[str, str]
    dataset_hash: str
    formula_version: str
    evidence_ids: list[str]
    transitions: list[ExperimentTransition]
    result: dict[str, Any] | None
    failure_reason: str | None
    reviewer: str | None
    rollback_reference: str | None
    integrity_hash: str = field(default="", compare=False)

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "correlation_id": self.correlation_id,
            "hypothesis": self.hypothesis,
            "proposer_agent": self.proposer_agent,
            "owner_agent": self.owner_agent,
            "state": self.state,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "input_data_range": self.input_data_range,
            "dataset_hash": self.dataset_hash,
            "formula_version": self.formula_version,
            "evidence_ids": self.evidence_ids,
            "transitions": [
                {
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "transitioned_at_utc": t.transitioned_at_utc,
                    "agent": t.agent,
                    "reason": t.reason,
                    "reviewer": t.reviewer,
                    "evidence_ids": t.evidence_ids,
                }
                for t in self.transitions
            ],
            "result": self.result,
            "failure_reason": self.failure_reason,
            "reviewer": self.reviewer,
            "rollback_reference": self.rollback_reference,
        }


class ExperimentStore:
    """Persistent store for experiment lifecycle records."""

    def __init__(self, store_dir: Path) -> None:
        self._store_dir = store_dir
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, experiment_id: str) -> Path:
        return self._store_dir / f"{experiment_id}.json"

    def create(
        self,
        *,
        experiment_id: str,
        correlation_id: str,
        hypothesis: str,
        proposer_agent: str,
        owner_agent: str,
        evidence_ids: list[str],
        input_data_range: dict[str, str] | None = None,
        dataset_hash: str = "",
        formula_version: str = "",
    ) -> Experiment:
        now = _utc_now_str()
        exp = Experiment(
            experiment_id=experiment_id,
            correlation_id=correlation_id,
            hypothesis=hypothesis,
            proposer_agent=proposer_agent,
            owner_agent=owner_agent,
            state="OBSERVATION",
            created_at_utc=now,
            updated_at_utc=now,
            input_data_range=input_data_range or {},
            dataset_hash=dataset_hash,
            formula_version=formula_version,
            evidence_ids=list(evidence_ids),
            transitions=[],
            result=None,
            failure_reason=None,
            reviewer=None,
            rollback_reference=None,
        )
        self._write(exp)
        return exp

    def load(self, experiment_id: str) -> Experiment:
        path = self._path(experiment_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        transitions = [
            ExperimentTransition(**t) for t in data.get("transitions", [])
        ]
        return Experiment(
            experiment_id=data["experiment_id"],
            correlation_id=data["correlation_id"],
            hypothesis=data["hypothesis"],
            proposer_agent=data["proposer_agent"],
            owner_agent=data["owner_agent"],
            state=data["state"],
            created_at_utc=data["created_at_utc"],
            updated_at_utc=data["updated_at_utc"],
            input_data_range=data.get("input_data_range", {}),
            dataset_hash=data.get("dataset_hash", ""),
            formula_version=data.get("formula_version", ""),
            evidence_ids=data.get("evidence_ids", []),
            transitions=transitions,
            result=data.get("result"),
            failure_reason=data.get("failure_reason"),
            reviewer=data.get("reviewer"),
            rollback_reference=data.get("rollback_reference"),
            integrity_hash=data.get("integrity_hash", ""),
        )

    def transition(
        self,
        experiment_id: str,
        to_state: str,
        *,
        agent: str,
        reason: str,
        reviewer: str | None = None,
        evidence_ids: list[str] | None = None,
        result: dict[str, Any] | None = None,
        failure_reason: str | None = None,
        rollback_reference: str | None = None,
    ) -> Experiment:
        exp = self.load(experiment_id)

        if exp.state in TERMINAL_STATES:
            raise ValueError(
                f"experiment {experiment_id!r} is in terminal state {exp.state!r}"
            )
        allowed = ALLOWED_TRANSITIONS.get(exp.state, frozenset())
        if to_state not in allowed:
            raise ValueError(
                f"invalid transition {exp.state!r} → {to_state!r} "
                f"for experiment {experiment_id!r}"
            )

        # Self-approval check: proposer cannot approve their own experiment
        if to_state in ("RELEASED", "HUMAN_RELEASE_GATE") and reviewer == exp.proposer_agent:
            raise ValueError(
                f"agent {reviewer!r} cannot approve their own experiment {experiment_id!r}"
            )

        now = _utc_now_str()
        tr = ExperimentTransition(
            from_state=exp.state,
            to_state=to_state,
            transitioned_at_utc=now,
            agent=agent,
            reason=reason,
            reviewer=reviewer,
            evidence_ids=list(evidence_ids or []),
        )
        exp.state = to_state
        exp.updated_at_utc = now
        exp.transitions.append(tr)
        if result is not None:
            exp.result = result
        if failure_reason is not None:
            exp.failure_reason = failure_reason
        if reviewer is not None:
            exp.reviewer = reviewer
        if rollback_reference is not None:
            exp.rollback_reference = rollback_reference
        self._write(exp)
        return exp

    def list_by_state(self, state: str) -> list[Experiment]:
        experiments: list[Experiment] = []
        for path in self._store_dir.glob("*.json"):
            try:
                exp = self.load(path.stem)
                if exp.state == state:
                    experiments.append(exp)
            except Exception:
                continue
        return experiments

    def _write(self, exp: Experiment) -> None:
        payload = exp.to_dict()
        payload["integrity_hash"] = _fingerprint(payload)
        self._path(exp.experiment_id).write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
