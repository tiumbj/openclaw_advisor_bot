"""Continuous research cycle orchestrator.

MAIN uses this to coordinate the evidence → hypothesis → experiment → knowledge loop.
Each cycle step dispatches work to the appropriate specialist agent via the job queue.
The cycle is non-blocking: each step schedules a job and returns; the queue worker drives
execution asynchronously.

This module defines the cycle contract and step router — it does not implement AI calling.
All numeric evidence originates from Python, never from agent inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class CycleStep(str, Enum):
    COLLECT_EVIDENCE = "COLLECT_EVIDENCE"
    FORM_HYPOTHESIS = "FORM_HYPOTHESIS"
    DESIGN_EXPERIMENT = "DESIGN_EXPERIMENT"
    VALIDATE_DATA = "VALIDATE_DATA"
    RUN_BACKTEST = "RUN_BACKTEST"
    REVIEW_RESULT = "REVIEW_RESULT"
    UPDATE_KNOWLEDGE = "UPDATE_KNOWLEDGE"
    FAILURE_ANALYSIS = "FAILURE_ANALYSIS"


# Maps each cycle step to the responsible specialist agent
STEP_AGENT_MAP: dict[CycleStep, str] = {
    CycleStep.COLLECT_EVIDENCE: "market-data-integrity-agent",
    CycleStep.FORM_HYPOTHESIS: "xau-strategy-auditor",
    CycleStep.DESIGN_EXPERIMENT: "statistical-backtest-agent",
    CycleStep.VALIDATE_DATA: "market-data-integrity-agent",
    CycleStep.RUN_BACKTEST: "statistical-backtest-agent",
    CycleStep.REVIEW_RESULT: "xau-strategy-auditor",
    CycleStep.UPDATE_KNOWLEDGE: "knowledge-skill-manager",
    CycleStep.FAILURE_ANALYSIS: "failure-root-cause-agent",
}

# Valid step sequences (non-branching happy path)
STEP_SEQUENCE = (
    CycleStep.COLLECT_EVIDENCE,
    CycleStep.FORM_HYPOTHESIS,
    CycleStep.DESIGN_EXPERIMENT,
    CycleStep.VALIDATE_DATA,
    CycleStep.RUN_BACKTEST,
    CycleStep.REVIEW_RESULT,
    CycleStep.UPDATE_KNOWLEDGE,
)


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CycleJob:
    cycle_id: str
    step: CycleStep
    agent: str
    payload: dict[str, Any]
    scheduled_at_utc: str
    correlation_id: str


@dataclass(frozen=True)
class ResearchCycleConfig:
    cycle_interval_seconds: int = 3600
    max_concurrent_experiments: int = 3
    min_evidence_count: int = 10
    require_human_gate: bool = True


class ResearchCycleRouter:
    """Routes each research cycle step to the correct specialist agent.

    MAIN calls next_step() to determine which agent should handle the next
    phase of an experiment. The router enforces:
    - Agent assignment from STEP_AGENT_MAP (not hardcoded in MAIN)
    - Self-approval prohibition is enforced at ExperimentStore level
    - HUMAN_RELEASE_GATE is a blocking step (no auto-advance)
    """

    def __init__(self, config: ResearchCycleConfig | None = None) -> None:
        self._config = config or ResearchCycleConfig()

    def next_step(self, current_step: CycleStep | None) -> CycleStep | None:
        """Return the next step in the happy path, or None if cycle is complete."""
        if current_step is None:
            return CycleStep.COLLECT_EVIDENCE
        try:
            idx = STEP_SEQUENCE.index(current_step)
        except ValueError:
            return None
        next_idx = idx + 1
        if next_idx >= len(STEP_SEQUENCE):
            return None
        return STEP_SEQUENCE[next_idx]

    def agent_for_step(self, step: CycleStep) -> str:
        """Return the specialist agent responsible for the given step."""
        return STEP_AGENT_MAP[step]

    def build_cycle_job(
        self,
        cycle_id: str,
        step: CycleStep,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> CycleJob:
        return CycleJob(
            cycle_id=cycle_id,
            step=step,
            agent=self.agent_for_step(step),
            payload=payload,
            scheduled_at_utc=_utc_now_str(),
            correlation_id=correlation_id,
        )

    def is_human_gate_required(self, step: CycleStep) -> bool:
        """HUMAN_RELEASE_GATE must not be bypassed automatically."""
        return step == CycleStep.REVIEW_RESULT and self._config.require_human_gate
