"""Integration tests for PersistentJobQueue (LC-009).

Uses a real temporary SQLite database (no mocking) to verify:
enqueue, lease, heartbeat, acknowledge, retry, DLQ, expiry recovery,
idempotency, circuit breaker, cancellation.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from openclaw_super_advisor.scheduler.job_queue import (
    JOB_STATE_CANCELLED,
    JOB_STATE_COMPLETED,
    JOB_STATE_DEAD_LETTER,
    JOB_STATE_LEASED,
    JOB_STATE_QUEUED,
    PersistentJobQueue,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def queue(tmp_path: Path) -> PersistentJobQueue:
    return PersistentJobQueue(tmp_path / "jobs.db", lease_seconds=30)


@pytest.fixture()
def short_lease_queue(tmp_path: Path) -> PersistentJobQueue:
    """Queue with very short lease for expiry tests."""
    return PersistentJobQueue(tmp_path / "jobs_short.db", lease_seconds=1)


# ── enqueue ───────────────────────────────────────────────────────────────────

def test_enqueue_returns_job(queue: PersistentJobQueue) -> None:
    job = queue.enqueue("job-1", "research", {"key": "val"})
    assert job is not None
    assert job.job_id == "job-1"
    assert job.state == JOB_STATE_QUEUED
    assert job.attempt == 0
    assert job.payload == {"key": "val"}


def test_enqueue_duplicate_idempotency_returns_none(queue: PersistentJobQueue) -> None:
    j1 = queue.enqueue("job-2", "research", {}, idempotency_key="idem-a")
    j2 = queue.enqueue("job-3", "research", {}, idempotency_key="idem-a")
    assert j1 is not None
    assert j2 is None  # deduplicated


def test_enqueue_null_idempotency_allows_duplicates(queue: PersistentJobQueue) -> None:
    j1 = queue.enqueue("job-4", "research", {}, idempotency_key=None)
    j2 = queue.enqueue("job-5", "research", {}, idempotency_key=None)
    assert j1 is not None
    assert j2 is not None


def test_enqueue_correlation_id_stored(queue: PersistentJobQueue) -> None:
    job = queue.enqueue("job-corr", "research", {}, correlation_id="corr-123")
    assert job is not None
    assert job.correlation_id == "corr-123"


def test_enqueue_parent_job_id_stored(queue: PersistentJobQueue) -> None:
    queue.enqueue("parent", "type-a", {})
    child = queue.enqueue("child", "type-a", {}, parent_job_id="parent")
    assert child is not None
    assert child.parent_job_id == "parent"


# ── lease ─────────────────────────────────────────────────────────────────────

def test_lease_next_returns_job(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-l1", "research", {})
    job = queue.lease_next()
    assert job is not None
    assert job.state == JOB_STATE_LEASED
    assert job.attempt == 1
    assert job.lease_expires is not None


def test_lease_next_empty_queue_returns_none(queue: PersistentJobQueue) -> None:
    result = queue.lease_next()
    assert result is None


def test_lease_next_by_type(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-a", "type-a", {})
    queue.enqueue("job-b", "type-b", {})
    job = queue.lease_next(job_type="type-b")
    assert job is not None
    assert job.job_id == "job-b"


def test_lease_next_leaves_wrong_type(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-only-a", "type-a", {})
    result = queue.lease_next(job_type="type-z")
    assert result is None


def test_lease_sets_expires(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-exp", "research", {})
    job = queue.lease_next()
    assert job is not None
    assert job.lease_expires is not None
    now_approx = time.time()
    assert job.lease_expires > now_approx


# ── priority ordering ─────────────────────────────────────────────────────────

def test_priority_ordering(queue: PersistentJobQueue) -> None:
    queue.enqueue("low", "research", {}, priority=200)
    queue.enqueue("high", "research", {}, priority=10)
    queue.enqueue("mid", "research", {}, priority=100)
    j1 = queue.lease_next()
    j2 = queue.lease_next()
    j3 = queue.lease_next()
    assert j1 is not None and j1.job_id == "high"
    assert j2 is not None and j2.job_id == "mid"
    assert j3 is not None and j3.job_id == "low"


# ── complete ──────────────────────────────────────────────────────────────────

def test_complete_job(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-done", "research", {})
    queue.lease_next()
    success = queue.complete("job-done")
    assert success is True
    job = queue.get("job-done")
    assert job is not None
    assert job.state == JOB_STATE_COMPLETED


def test_complete_non_leased_job_fails(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-q", "research", {})
    result = queue.complete("job-q")
    assert result is False
    job = queue.get("job-q")
    assert job is not None
    assert job.state == JOB_STATE_QUEUED


# ── fail / retry ─────────────────────────────────────────────────────────────

def test_fail_requeues_within_max_attempts(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-retry", "research", {}, max_attempts=3)
    queue.lease_next()
    job = queue.fail("job-retry", "transient error")
    assert job is not None
    assert job.state == JOB_STATE_QUEUED
    assert job.error == "transient error"


def test_fail_sends_to_dlq_after_max_attempts(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-dlq", "research", {}, max_attempts=1)
    queue.lease_next()  # attempt = 1
    job = queue.fail("job-dlq", "fatal error")
    assert job is not None
    assert job.state == JOB_STATE_DEAD_LETTER


def test_fail_nonexistent_job_returns_none(queue: PersistentJobQueue) -> None:
    result = queue.fail("ghost-job", "some error")
    assert result is None


# ── heartbeat / lease renewal ─────────────────────────────────────────────────

def test_renew_lease_extends_expiry(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-hb", "research", {})
    leased = queue.lease_next()
    assert leased is not None
    original_expires = leased.lease_expires
    time.sleep(0.1)
    success = queue.renew_lease("job-hb")
    assert success is True
    refreshed = queue.get("job-hb")
    assert refreshed is not None
    assert refreshed.lease_expires is not None
    assert refreshed.lease_expires > original_expires  # type: ignore[operator]


def test_renew_lease_on_non_leased_returns_false(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-nl", "research", {})
    result = queue.renew_lease("job-nl")
    assert result is False


# ── lease expiry recovery ─────────────────────────────────────────────────────

def test_expired_lease_recovered_on_next_lease(short_lease_queue: PersistentJobQueue) -> None:
    short_lease_queue.enqueue("job-exp", "research", {})
    leased = short_lease_queue.lease_next()
    assert leased is not None
    assert leased.state == JOB_STATE_LEASED

    time.sleep(1.1)  # wait for lease to expire

    # Next lease_next call resets the expired lease
    recovered = short_lease_queue.lease_next()
    assert recovered is not None
    assert recovered.job_id == "job-exp"
    assert recovered.state == JOB_STATE_LEASED


def test_resume_in_progress_resets_expired(short_lease_queue: PersistentJobQueue) -> None:
    short_lease_queue.enqueue("job-rip", "research", {})
    short_lease_queue.lease_next()
    time.sleep(1.1)
    jobs = short_lease_queue.resume_in_progress()
    assert any(j.job_id == "job-rip" and j.state == JOB_STATE_QUEUED for j in jobs)


# ── checkpoint ───────────────────────────────────────────────────────────────

def test_checkpoint_saved_and_loadable(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-cp", "research", {})
    queue.lease_next()
    queue.checkpoint("job-cp", {"step": "phase-2", "records_done": 150})
    job = queue.get("job-cp")
    assert job is not None
    assert job.checkpoint == {"step": "phase-2", "records_done": 150}


def test_checkpoint_on_non_leased_returns_false(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-cpq", "research", {})
    result = queue.checkpoint("job-cpq", {"x": 1})
    assert result is False


# ── circuit breaker ───────────────────────────────────────────────────────────

def test_circuit_opens_after_threshold(queue: PersistentJobQueue) -> None:
    job_type = "fragile-type"
    for i in range(5):
        queue.enqueue(f"cb-job-{i}", job_type, {}, max_attempts=10)
        queue.lease_next(job_type=job_type)
        queue.fail(f"cb-job-{i}", "recurring failure")
    assert queue.is_circuit_open(job_type) is True


def test_circuit_open_sends_to_dlq(queue: PersistentJobQueue) -> None:
    """When circuit is open, next failure goes to DLQ regardless of attempt count."""
    job_type = "circuit-type"
    # Open the circuit
    for i in range(5):
        queue.enqueue(f"circ-{i}", job_type, {}, max_attempts=100)
        queue.lease_next(job_type=job_type)
        queue.fail(f"circ-{i}", "fail")
    assert queue.is_circuit_open(job_type)

    queue.enqueue("circ-victim", job_type, {}, max_attempts=100)
    queue.lease_next(job_type=job_type)
    victim = queue.fail("circ-victim", "circuit fail")
    assert victim is not None
    assert victim.state == JOB_STATE_DEAD_LETTER


def test_reset_circuit(queue: PersistentJobQueue) -> None:
    job_type = "resettable"
    for i in range(5):
        queue.enqueue(f"r-{i}", job_type, {}, max_attempts=10)
        queue.lease_next(job_type=job_type)
        queue.fail(f"r-{i}", "fail")
    assert queue.is_circuit_open(job_type)
    queue.reset_circuit(job_type)
    assert not queue.is_circuit_open(job_type)


# ── cancellation ─────────────────────────────────────────────────────────────

def test_cancel_queued_job(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-cancel", "research", {})
    result = queue.cancel("job-cancel")
    assert result is True
    job = queue.get("job-cancel")
    assert job is not None
    assert job.state == JOB_STATE_CANCELLED


def test_cancel_leased_job(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-cancel-l", "research", {})
    queue.lease_next()
    result = queue.cancel("job-cancel-l")
    assert result is True
    job = queue.get("job-cancel-l")
    assert job is not None
    assert job.state == JOB_STATE_CANCELLED


def test_cancel_completed_job_returns_false(queue: PersistentJobQueue) -> None:
    queue.enqueue("job-done-c", "research", {})
    queue.lease_next()
    queue.complete("job-done-c")
    result = queue.cancel("job-done-c")
    assert result is False


# ── stats ─────────────────────────────────────────────────────────────────────

def test_stats_reflects_queue_state(queue: PersistentJobQueue) -> None:
    queue.enqueue("s1", "research", {})
    queue.enqueue("s2", "research", {})
    queue.lease_next()
    stats = queue.stats()
    assert stats["states"].get(JOB_STATE_QUEUED, 0) == 1
    assert stats["states"].get(JOB_STATE_LEASED, 0) == 1
    assert "dead_letters" in stats


def test_stats_dead_letters_count(queue: PersistentJobQueue) -> None:
    queue.enqueue("dlq-stat", "research", {}, max_attempts=1)
    queue.lease_next()
    queue.fail("dlq-stat", "fatal")
    stats = queue.stats()
    assert stats["dead_letters"] >= 1


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_nonexistent_returns_none(queue: PersistentJobQueue) -> None:
    result = queue.get("phantom-job")
    assert result is None
