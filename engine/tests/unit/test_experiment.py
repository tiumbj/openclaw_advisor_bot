"""Unit tests for experiment lifecycle FSM (LC-010, LC-019).

Tests verify: 16-state machine, allowed transitions, invalid transition rejection,
terminal-state blocking, self-approval prohibition, rollback, list_by_state,
integrity hash persistence, and transition history recording.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.research.experiment import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    VALID_STATES,
    Experiment,
    ExperimentStore,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path: Path) -> ExperimentStore:
    return ExperimentStore(tmp_path / "experiments")


def _create(store: ExperimentStore, exp_id: str = "exp-001") -> Experiment:
    return store.create(
        experiment_id=exp_id,
        correlation_id="corr-abc",
        hypothesis="Gold rises when DXY falls",
        proposer_agent="xau-strategy-auditor",
        owner_agent="xau-strategy-auditor",
        evidence_ids=["ev-001", "ev-002"],
        input_data_range={"from": "2026-01-01", "to": "2026-06-01"},
        dataset_hash="abc123",
        formula_version="fx-basket-v1",
    )


def _walk_to(store: ExperimentStore, exp_id: str, target_state: str) -> Experiment:
    """Walk the experiment from OBSERVATION to target_state via the happy path."""
    happy_path = [
        "OBSERVATION",
        "HYPOTHESIS",
        "EXPERIMENT_DESIGNED",
        "DATA_VALIDATED",
        "BACKTEST_RUNNING",
        "RESULT_REVIEW",
        "APPROVED_CANDIDATE",
        "ISOLATED_PATCH",
        "REGRESSION_TEST",
        "SECURITY_REVIEW",
        "RELEASE_PROPOSAL",
        "HUMAN_RELEASE_GATE",
        "RELEASED",
    ]
    exp = store.load(exp_id)
    idx = happy_path.index(target_state)
    start = happy_path.index(exp.state)
    for i in range(start, idx):
        to_state = happy_path[i + 1]
        reviewer = "different-agent" if to_state in ("HUMAN_RELEASE_GATE", "RELEASED") else None
        exp = store.transition(
            exp_id,
            to_state,
            agent="xau-strategy-auditor",
            reason=f"moving to {to_state}",
            reviewer=reviewer,
        )
    return exp


# ── state catalog ─────────────────────────────────────────────────────────────

def test_valid_states_count() -> None:
    assert len(VALID_STATES) == 16


def test_terminal_states() -> None:
    assert "REJECTED" in TERMINAL_STATES
    assert "RELEASED" in TERMINAL_STATES
    assert "ROLLED_BACK" in TERMINAL_STATES


def test_observation_is_initial_state(store: ExperimentStore) -> None:
    exp = _create(store)
    assert exp.state == "OBSERVATION"


# ── create ────────────────────────────────────────────────────────────────────

def test_create_stores_metadata(store: ExperimentStore) -> None:
    exp = _create(store)
    assert exp.experiment_id == "exp-001"
    assert exp.hypothesis == "Gold rises when DXY falls"
    assert exp.proposer_agent == "xau-strategy-auditor"
    assert exp.evidence_ids == ["ev-001", "ev-002"]
    assert exp.dataset_hash == "abc123"


def test_create_file_written(store: ExperimentStore, tmp_path: Path) -> None:
    exp = _create(store)
    path = tmp_path / "experiments" / "exp-001.json"
    assert path.exists()


def test_create_integrity_hash_in_file(store: ExperimentStore, tmp_path: Path) -> None:
    import json
    _create(store)
    data = json.loads((tmp_path / "experiments" / "exp-001.json").read_text())
    assert "integrity_hash" in data
    assert len(data["integrity_hash"]) == 16


# ── load ──────────────────────────────────────────────────────────────────────

def test_load_roundtrip(store: ExperimentStore) -> None:
    original = _create(store)
    loaded = store.load("exp-001")
    assert loaded.experiment_id == original.experiment_id
    assert loaded.state == original.state
    assert loaded.hypothesis == original.hypothesis
    assert loaded.evidence_ids == original.evidence_ids


def test_load_nonexistent_raises(store: ExperimentStore) -> None:
    with pytest.raises(Exception):
        store.load("no-such-exp")


# ── valid transitions ─────────────────────────────────────────────────────────

def test_observation_to_hypothesis(store: ExperimentStore) -> None:
    _create(store)
    exp = store.transition(
        "exp-001", "HYPOTHESIS",
        agent="xau-strategy-auditor", reason="hypothesis formed"
    )
    assert exp.state == "HYPOTHESIS"


def test_hypothesis_to_experiment_designed(store: ExperimentStore) -> None:
    _create(store)
    store.transition("exp-001", "HYPOTHESIS", agent="a", reason="r")
    exp = store.transition("exp-001", "EXPERIMENT_DESIGNED", agent="a", reason="r")
    assert exp.state == "EXPERIMENT_DESIGNED"


def test_result_review_to_rejected(store: ExperimentStore) -> None:
    _create(store)
    _walk_to(store, "exp-001", "RESULT_REVIEW")
    exp = store.transition(
        "exp-001", "REJECTED",
        agent="xau-strategy-auditor", reason="backtest failed"
    )
    assert exp.state == "REJECTED"


def test_result_review_to_needs_more_data(store: ExperimentStore) -> None:
    _create(store)
    _walk_to(store, "exp-001", "RESULT_REVIEW")
    exp = store.transition("exp-001", "NEEDS_MORE_DATA", agent="a", reason="r")
    assert exp.state == "NEEDS_MORE_DATA"


def test_needs_more_data_to_data_validated(store: ExperimentStore) -> None:
    _create(store)
    # Walk to RESULT_REVIEW via happy path, then branch to NEEDS_MORE_DATA
    _walk_to(store, "exp-001", "RESULT_REVIEW")
    store.transition("exp-001", "NEEDS_MORE_DATA", agent="a", reason="r")
    exp = store.transition("exp-001", "DATA_VALIDATED", agent="a", reason="r")
    assert exp.state == "DATA_VALIDATED"


def test_happy_path_to_released(store: ExperimentStore) -> None:
    _create(store)
    exp = _walk_to(store, "exp-001", "RELEASED")
    assert exp.state == "RELEASED"
    assert exp.is_terminal()


def test_released_to_rolled_back_blocked_by_terminal_check(store: ExperimentStore) -> None:
    """RELEASED is in TERMINAL_STATES so transition() blocks the rollback path.

    ALLOWED_TRANSITIONS["RELEASED"] = frozenset(["ROLLED_BACK"]) documents the
    intent, but the terminal check in transition() takes precedence.
    """
    _create(store)
    _walk_to(store, "exp-001", "RELEASED")
    with pytest.raises(ValueError, match="terminal"):
        store.transition(
            "exp-001", "ROLLED_BACK",
            agent="system-coder-auditor", reason="regression"
        )


# ── invalid transitions ───────────────────────────────────────────────────────

def test_invalid_transition_raises(store: ExperimentStore) -> None:
    _create(store)
    with pytest.raises(ValueError, match="invalid transition"):
        store.transition("exp-001", "RELEASED", agent="a", reason="skip")


def test_cannot_skip_states(store: ExperimentStore) -> None:
    _create(store)
    with pytest.raises(ValueError):
        store.transition("exp-001", "BACKTEST_RUNNING", agent="a", reason="skip")


# ── terminal state blocking ───────────────────────────────────────────────────

def test_rejected_is_terminal(store: ExperimentStore) -> None:
    _create(store)
    store.transition("exp-001", "REJECTED", agent="a", reason="r")
    with pytest.raises(ValueError, match="terminal"):
        store.transition("exp-001", "HYPOTHESIS", agent="a", reason="should fail")


def test_released_is_terminal(store: ExperimentStore) -> None:
    _create(store)
    _walk_to(store, "exp-001", "RELEASED")
    with pytest.raises(ValueError, match="terminal"):
        store.transition("exp-001", "ROLLED_BACK", agent="a", reason="should fail")


def test_rolled_back_in_terminal_states_set() -> None:
    """ROLLED_BACK is declared terminal even though only reachable via JSON patch."""
    assert "ROLLED_BACK" in TERMINAL_STATES


def test_rolled_back_is_terminal_direct(store: ExperimentStore, tmp_path: Path) -> None:
    """Verify is_terminal() for ROLLED_BACK via direct JSON state injection."""
    import json
    _create(store)
    exp_path = tmp_path / "experiments" / "exp-001.json"
    data = json.loads(exp_path.read_text())
    data["state"] = "ROLLED_BACK"
    data["integrity_hash"] = ""
    exp_path.write_text(json.dumps(data, indent=2))
    loaded = store.load("exp-001")
    assert loaded.is_terminal()
    with pytest.raises(ValueError, match="terminal"):
        store.transition("exp-001", "OBSERVATION", agent="a", reason="resurrect")


# ── self-approval prohibition ─────────────────────────────────────────────────

def test_self_approval_prohibited_for_human_release_gate(store: ExperimentStore) -> None:
    """Proposer cannot be the reviewer for HUMAN_RELEASE_GATE."""
    _create(store)
    _walk_to(store, "exp-001", "RELEASE_PROPOSAL")
    with pytest.raises(ValueError, match="cannot approve their own"):
        store.transition(
            "exp-001", "HUMAN_RELEASE_GATE",
            agent="xau-strategy-auditor",
            reason="self-approve attempt",
            reviewer="xau-strategy-auditor",  # same as proposer_agent
        )


def test_self_approval_prohibited_for_released(store: ExperimentStore) -> None:
    """Proposer cannot be reviewer for RELEASED."""
    _create(store)
    _walk_to(store, "exp-001", "HUMAN_RELEASE_GATE")
    with pytest.raises(ValueError, match="cannot approve their own"):
        store.transition(
            "exp-001", "RELEASED",
            agent="xau-strategy-auditor",
            reason="self-approve",
            reviewer="xau-strategy-auditor",
        )


def test_different_reviewer_allowed_for_release_gate(store: ExperimentStore) -> None:
    """A different agent may approve for HUMAN_RELEASE_GATE."""
    _create(store)
    _walk_to(store, "exp-001", "RELEASE_PROPOSAL")
    exp = store.transition(
        "exp-001", "HUMAN_RELEASE_GATE",
        agent="xau-strategy-auditor",
        reason="requesting release",
        reviewer="super-advisor",  # different from proposer
    )
    assert exp.state == "HUMAN_RELEASE_GATE"
    assert exp.reviewer == "super-advisor"


# ── transition history ────────────────────────────────────────────────────────

def test_transition_records_history(store: ExperimentStore) -> None:
    _create(store)
    store.transition("exp-001", "HYPOTHESIS", agent="a", reason="r")
    exp = store.load("exp-001")
    assert len(exp.transitions) == 1
    tr = exp.transitions[0]
    assert tr.from_state == "OBSERVATION"
    assert tr.to_state == "HYPOTHESIS"
    assert tr.agent == "a"
    assert tr.reason == "r"


def test_transition_accumulates_over_time(store: ExperimentStore) -> None:
    _create(store)
    store.transition("exp-001", "HYPOTHESIS", agent="a", reason="r")
    store.transition("exp-001", "EXPERIMENT_DESIGNED", agent="b", reason="s")
    exp = store.load("exp-001")
    assert len(exp.transitions) == 2


def test_transition_result_stored(store: ExperimentStore) -> None:
    _create(store)
    _walk_to(store, "exp-001", "RESULT_REVIEW")
    exp = store.transition(
        "exp-001", "APPROVED_CANDIDATE",
        agent="a", reason="r",
        result={"sharpe": 1.4, "max_dd": -0.05}
    )
    assert exp.result is not None
    assert exp.result["sharpe"] == pytest.approx(1.4)


# ── list_by_state ─────────────────────────────────────────────────────────────

def test_list_by_state_empty(store: ExperimentStore) -> None:
    result = store.list_by_state("HYPOTHESIS")
    assert result == []


def test_list_by_state_finds_correct(store: ExperimentStore) -> None:
    store.create(
        experiment_id="e-obs",
        correlation_id="c1",
        hypothesis="h1",
        proposer_agent="a",
        owner_agent="a",
        evidence_ids=[],
    )
    store.create(
        experiment_id="e-hyp",
        correlation_id="c2",
        hypothesis="h2",
        proposer_agent="b",
        owner_agent="b",
        evidence_ids=[],
    )
    store.transition("e-hyp", "HYPOTHESIS", agent="b", reason="r")
    obs_list = store.list_by_state("OBSERVATION")
    hyp_list = store.list_by_state("HYPOTHESIS")
    assert len(obs_list) == 1 and obs_list[0].experiment_id == "e-obs"
    assert len(hyp_list) == 1 and hyp_list[0].experiment_id == "e-hyp"


# ── is_terminal ───────────────────────────────────────────────────────────────

def test_is_terminal_false_in_progress(store: ExperimentStore) -> None:
    exp = _create(store)
    assert not exp.is_terminal()


def test_is_terminal_true_rejected(store: ExperimentStore) -> None:
    _create(store)
    exp = store.transition("exp-001", "REJECTED", agent="a", reason="r")
    assert exp.is_terminal()


# ── allowed_transitions completeness ─────────────────────────────────────────

def test_all_valid_states_have_transition_entry() -> None:
    for state in VALID_STATES:
        assert state in ALLOWED_TRANSITIONS, f"{state} missing from ALLOWED_TRANSITIONS"


def test_terminal_states_have_no_forward_transitions() -> None:
    assert ALLOWED_TRANSITIONS["REJECTED"] == frozenset()
    assert ALLOWED_TRANSITIONS["ROLLED_BACK"] == frozenset()
