"""Persistent job queue with lease, heartbeat, idempotency, DLQ, and bounded retry.

Uses SQLite for durability. Safe to restart — jobs are resumed from last checkpoint.
Each job has a lease that must be renewed; expired leases are reset to QUEUED.

Job states: QUEUED → LEASED → COMPLETED | FAILED | DEAD_LETTER
            LEASED → QUEUED (lease expired)
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generator


JOB_STATE_QUEUED = "QUEUED"
JOB_STATE_LEASED = "LEASED"
JOB_STATE_COMPLETED = "COMPLETED"
JOB_STATE_FAILED = "FAILED"
JOB_STATE_DEAD_LETTER = "DEAD_LETTER"
JOB_STATE_CANCELLED = "CANCELLED"

SCHEMA_VERSION = 1

_CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS _schema (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO _schema VALUES (1);

CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    job_type        TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'QUEUED',
    priority        INTEGER NOT NULL DEFAULT 100,
    payload         TEXT NOT NULL DEFAULT '{}',
    checkpoint      TEXT NOT NULL DEFAULT '{}',
    attempt         INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    lease_expires   REAL,
    correlation_id  TEXT,
    parent_job_id   TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS dead_letters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    job_type        TEXT NOT NULL,
    payload         TEXT NOT NULL,
    final_error     TEXT,
    archived_at     REAL NOT NULL
);
"""


def _utc_now() -> float:
    return datetime.now(tz=UTC).timestamp()


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass
class Job:
    job_id: str
    idempotency_key: str | None
    job_type: str
    state: str
    priority: int
    payload: dict[str, Any]
    checkpoint: dict[str, Any]
    attempt: int
    max_attempts: int
    created_at: float
    updated_at: float
    lease_expires: float | None
    correlation_id: str | None
    parent_job_id: str | None
    error: str | None

    @property
    def is_lease_expired(self) -> bool:
        if self.state != JOB_STATE_LEASED or self.lease_expires is None:
            return False
        return _utc_now() > self.lease_expires


class PersistentJobQueue:
    """SQLite-backed persistent job queue.

    Supports: idempotency, lease/heartbeat, bounded retry, DLQ, checkpoint,
    cancellation, and circuit breaker per job type.
    """

    DEFAULT_LEASE_SECONDS = 300

    def __init__(self, db_path: Path, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lease_seconds = lease_seconds
        self._circuit_failures: dict[str, int] = {}
        self._circuit_threshold = 5
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_CREATE_SCHEMA)

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            job_id=row["job_id"],
            idempotency_key=row["idempotency_key"],
            job_type=row["job_type"],
            state=row["state"],
            priority=row["priority"],
            payload=json.loads(row["payload"]),
            checkpoint=json.loads(row["checkpoint"]),
            attempt=row["attempt"],
            max_attempts=row["max_attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lease_expires=row["lease_expires"],
            correlation_id=row["correlation_id"],
            parent_job_id=row["parent_job_id"],
            error=row["error"],
        )

    def enqueue(
        self,
        job_id: str,
        job_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        priority: int = 100,
        max_attempts: int = 3,
        correlation_id: str | None = None,
        parent_job_id: str | None = None,
    ) -> Job | None:
        """Enqueue a job. Returns None if idempotency_key already exists."""
        now = _utc_now()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT job_id FROM jobs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone() if idempotency_key else None
            if existing:
                return None
            conn.execute(
                """
                INSERT INTO jobs
                    (job_id, idempotency_key, job_type, state, priority, payload,
                     checkpoint, attempt, max_attempts, created_at, updated_at,
                     correlation_id, parent_job_id)
                VALUES (?, ?, ?, 'QUEUED', ?, ?, '{}', 0, ?, ?, ?, ?, ?)
                """,
                (
                    job_id, idempotency_key, job_type, priority,
                    json.dumps(payload), max_attempts, now, now,
                    correlation_id, parent_job_id,
                ),
            )
        return self.get(job_id)

    def lease_next(self, job_type: str | None = None) -> Job | None:
        """Atomically lease the next available job."""
        now = _utc_now()
        with self._conn() as conn:
            # First reset expired leases
            conn.execute(
                """
                UPDATE jobs
                SET state = 'QUEUED', lease_expires = NULL, updated_at = ?
                WHERE state = 'LEASED' AND lease_expires IS NOT NULL AND lease_expires < ?
                """,
                (now, now),
            )
            # Fetch next queued job
            if job_type:
                row = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE state = 'QUEUED' AND job_type = ?
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """,
                    (job_type,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE state = 'QUEUED'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """
                ).fetchone()
            if row is None:
                return None
            lease_exp = now + self._lease_seconds
            conn.execute(
                """
                UPDATE jobs
                SET state = 'LEASED', lease_expires = ?, updated_at = ?, attempt = attempt + 1
                WHERE job_id = ?
                """,
                (lease_exp, now, row["job_id"]),
            )
        return self.get(row["job_id"])

    def renew_lease(self, job_id: str) -> bool:
        """Renew lease heartbeat for an active job."""
        now = _utc_now()
        with self._conn() as conn:
            result = conn.execute(
                """
                UPDATE jobs
                SET lease_expires = ?, updated_at = ?
                WHERE job_id = ? AND state = 'LEASED'
                """,
                (now + self._lease_seconds, now, job_id),
            )
            return result.rowcount > 0

    def checkpoint(self, job_id: str, checkpoint_data: dict[str, Any]) -> bool:
        """Save checkpoint data for a leased job."""
        now = _utc_now()
        with self._conn() as conn:
            result = conn.execute(
                """
                UPDATE jobs
                SET checkpoint = ?, updated_at = ?
                WHERE job_id = ? AND state = 'LEASED'
                """,
                (json.dumps(checkpoint_data), now, job_id),
            )
            return result.rowcount > 0

    def complete(self, job_id: str) -> bool:
        """Mark a job as completed."""
        now = _utc_now()
        with self._conn() as conn:
            result = conn.execute(
                """
                UPDATE jobs
                SET state = 'COMPLETED', lease_expires = NULL, updated_at = ?
                WHERE job_id = ? AND state = 'LEASED'
                """,
                (now, job_id),
            )
            if result.rowcount > 0:
                row = conn.execute(
                    "SELECT job_type FROM jobs WHERE job_id = ?", (job_id,)
                ).fetchone()
                if row:
                    self._circuit_failures.pop(row["job_type"], None)
            return result.rowcount > 0

    def fail(self, job_id: str, error: str) -> Job | None:
        """Mark a job attempt as failed; requeue or send to DLQ."""
        now = _utc_now()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return None
            job = self._row_to_job(row)
            jtype = job.job_type
            self._circuit_failures[jtype] = self._circuit_failures.get(jtype, 0) + 1

            if job.attempt >= job.max_attempts or self._circuit_failures.get(jtype, 0) >= self._circuit_threshold:
                conn.execute(
                    """
                    UPDATE jobs
                    SET state = 'DEAD_LETTER', lease_expires = NULL,
                        updated_at = ?, error = ?
                    WHERE job_id = ?
                    """,
                    (now, error, job_id),
                )
                conn.execute(
                    """
                    INSERT INTO dead_letters (job_id, job_type, payload, final_error, archived_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (job_id, jtype, json.dumps(job.payload), error, now),
                )
            else:
                backoff = min(2 ** job.attempt, 300)
                conn.execute(
                    """
                    UPDATE jobs
                    SET state = 'QUEUED', lease_expires = NULL,
                        updated_at = ?, error = ?
                    WHERE job_id = ?
                    """,
                    (now, error, job_id),
                )
        return self.get(job_id)

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued or leased job."""
        now = _utc_now()
        with self._conn() as conn:
            result = conn.execute(
                """
                UPDATE jobs
                SET state = 'CANCELLED', lease_expires = NULL, updated_at = ?
                WHERE job_id = ? AND state IN ('QUEUED', 'LEASED')
                """,
                (now, job_id),
            )
            return result.rowcount > 0

    def get(self, job_id: str) -> Job | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._row_to_job(row) if row else None

    def resume_in_progress(self) -> list[Job]:
        """On startup: reset expired leases and return resumable jobs."""
        now = _utc_now()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET state = 'QUEUED', lease_expires = NULL, updated_at = ?
                WHERE state = 'LEASED' AND lease_expires < ?
                """,
                (now, now),
            )
            rows = conn.execute(
                "SELECT * FROM jobs WHERE state IN ('QUEUED', 'LEASED') ORDER BY priority ASC"
            ).fetchall()
            return [self._row_to_job(row) for row in rows]

    def is_circuit_open(self, job_type: str) -> bool:
        return self._circuit_failures.get(job_type, 0) >= self._circuit_threshold

    def reset_circuit(self, job_type: str) -> None:
        self._circuit_failures.pop(job_type, None)

    def stats(self) -> dict[str, Any]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state"
            ).fetchall()
            dl_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM dead_letters"
            ).fetchone()
            return {
                "states": {row["state"]: row["cnt"] for row in rows},
                "dead_letters": dl_count["cnt"] if dl_count else 0,
                "circuit_failures": dict(self._circuit_failures),
            }
