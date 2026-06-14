from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from ..events import canonical_json, redact_event, sha256_hex, validate_event_envelope
from ..storage.atomic import atomic_write


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _fingerprint(payload: str) -> str:
    return sha256_hex(payload)[:12]


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _json_load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ArchiveRecord:
    record_id: str
    created_at_utc: str
    event: dict[str, Any]
    record_hash: str
    previous_hash: str


class EvidenceArchive:
    def __init__(self, archive_dir: Path) -> None:
        self.archive_dir = archive_dir
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.archive_dir / "evidence.ndjson"
        self.manifest_path = self.archive_dir / "manifest.json"

    def _records(self) -> list[ArchiveRecord]:
        records: list[ArchiveRecord] = []
        if not self.path.exists():
            return records
        previous_hash = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            record = ArchiveRecord(
                record_id=str(payload["record_id"]),
                created_at_utc=str(payload["created_at_utc"]),
                event=payload["event"],
                record_hash=str(payload["record_hash"]),
                previous_hash=str(payload["previous_hash"]),
            )
            if record.previous_hash != previous_hash:
                raise ValueError("evidence archive hash chain mismatch")
            if record.record_hash != _fingerprint(canonical_json(payload["event"])):
                raise ValueError("evidence archive record hash mismatch")
            previous_hash = record.record_hash
            records.append(record)
        return records

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        validation = validate_event_envelope(event)
        if not validation.valid:
            raise ValueError(
                "; ".join(f"{issue.path}: {issue.message}" for issue in validation.issues)
            )
        records = (
            self._records()
            if self.path.exists() and self.path.read_text(encoding="utf-8").strip()
            else []
        )
        previous_hash = records[-1].record_hash if records else ""
        assert validation.event is not None
        event_payload = validation.event
        record = {
            "record_id": event_payload["event_id"],
            "created_at_utc": utc_now(),
            "event": event_payload,
            "previous_hash": previous_hash,
            "record_hash": _fingerprint(canonical_json(event_payload)),
        }
        line = canonical_json(record)

        def _writer(target: Path) -> None:
            existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
            target.write_text(existing + line + "\n", encoding="utf-8")

        atomic_write(self.path, _writer)
        self._write_manifest()
        return record

    def verify(self) -> dict[str, Any]:
        try:
            records = self._records()
        except Exception as exc:
            return {
                "archive_dir": str(self.archive_dir),
                "record_count": 0,
                "last_record_hash": None,
                "valid": False,
                "error": str(exc),
            }
        return {
            "archive_dir": str(self.archive_dir),
            "record_count": len(records),
            "last_record_hash": records[-1].record_hash if records else None,
            "valid": True,
        }

    def export_redacted(self, export_path: Path | None = None) -> Path:
        export_path = export_path or self.archive_dir / "evidence.redacted.ndjson"
        records = self._records()
        export_lines = [
            canonical_json(
                {
                    "record_id": r.record_id,
                    "created_at_utc": r.created_at_utc,
                    "event": redact_event(r.event),
                    "record_hash": r.record_hash,
                    "previous_hash": r.previous_hash,
                }
            )
            for r in records
        ]
        export_path.write_text(
            "\n".join(export_lines) + ("\n" if export_lines else ""), encoding="utf-8"
        )
        return export_path

    def _write_manifest(self) -> None:
        records = self._records()
        manifest = {
            "archive_dir": str(self.archive_dir),
            "record_count": len(records),
            "hash_chain_head": records[-1].record_hash if records else "",
            "updated_at_utc": utc_now(),
        }
        _json_dump(self.manifest_path, manifest)


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    created_at_utc: str
    kind: str
    payload: dict[str, Any]
    previous_hash: str
    record_hash: str


class OutcomeLedger:
    def __init__(self, ledger_dir: Path) -> None:
        self.ledger_dir = ledger_dir
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.ledger_dir / "ledger.ndjson"

    def _entries(self) -> list[LedgerEntry]:
        entries: list[LedgerEntry] = []
        if not self.path.exists():
            return entries
        previous_hash = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            entry = LedgerEntry(
                entry_id=str(payload["entry_id"]),
                created_at_utc=str(payload["created_at_utc"]),
                kind=str(payload["kind"]),
                payload=payload["payload"],
                previous_hash=str(payload["previous_hash"]),
                record_hash=str(payload["record_hash"]),
            )
            if entry.previous_hash != previous_hash:
                raise ValueError("ledger hash chain mismatch")
            if entry.record_hash != _fingerprint(
                canonical_json(entry.payload | {"kind": entry.kind})
            ):
                raise ValueError("ledger record hash mismatch")
            previous_hash = entry.record_hash
            entries.append(entry)
        return entries

    def append(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        entries = (
            self._entries()
            if self.path.exists() and self.path.read_text(encoding="utf-8").strip()
            else []
        )
        previous_hash = entries[-1].record_hash if entries else ""
        entry = {
            "entry_id": payload.get("event_id")
            or payload.get("entry_id")
            or f"ledger-{len(entries) + 1}",
            "created_at_utc": utc_now(),
            "kind": kind,
            "payload": payload,
            "previous_hash": previous_hash,
            "record_hash": _fingerprint(canonical_json(payload | {"kind": kind})),
        }

        def _writer(target: Path) -> None:
            existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
            target.write_text(existing + canonical_json(entry) + "\n", encoding="utf-8")

        atomic_write(self.path, _writer)
        return entry

    def verify(self) -> dict[str, Any]:
        try:
            entries = self._entries()
        except Exception as exc:
            return {
                "ledger_dir": str(self.ledger_dir),
                "entry_count": 0,
                "last_record_hash": None,
                "valid": False,
                "error": str(exc),
            }
        return {
            "ledger_dir": str(self.ledger_dir),
            "entry_count": len(entries),
            "last_record_hash": entries[-1].record_hash if entries else None,
            "valid": True,
        }


class AgentMemoryStore:
    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def agent_dir(self, agent_id: str) -> Path:
        path = self.memory_root / agent_id / "memory"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append(
        self,
        agent_id: str,
        content: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        entry = {
            "created_at_utc": utc_now(),
            "agent_id": agent_id,
            "provenance": provenance or {},
            "content": content,
        }
        target = self.agent_dir(agent_id) / f"{datetime.now(tz=UTC).date().isoformat()}.md"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(entry) + "\n")
        return target

    def read(self, agent_id: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.agent_dir(agent_id).glob("*.md")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entries.append(json.loads(line))
        return entries


@dataclass(frozen=True)
class SkillCandidate:
    candidate_id: str
    skill_id: str
    state: str
    created_at_utc: str
    updated_at_utc: str
    proposer_agent: str
    evidence: dict[str, Any]
    test_result: dict[str, Any] | None
    reviewer: str | None
    release_version: str | None
    rollback_reference: str | None
    integrity_hash: str


class SkillCandidateStore:
    STATES = (
        "OBSERVATION",
        "CANDIDATE",
        "TESTED",
        "REJECTED",
        "APPROVED",
        "RELEASED",
        "ROLLED_BACK",
    )

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _candidate_path(self, candidate_id: str) -> Path:
        return self.store_dir / f"{candidate_id}.json"

    def create(
        self,
        skill_id: str,
        proposer_agent: str,
        evidence: dict[str, Any],
    ) -> SkillCandidate:
        candidate = SkillCandidate(
            candidate_id=f"skill-{len(list(self.store_dir.glob('*.json'))) + 1}",
            skill_id=skill_id,
            state="CANDIDATE",
            created_at_utc=utc_now(),
            updated_at_utc=utc_now(),
            proposer_agent=proposer_agent,
            evidence=evidence,
            test_result=None,
            reviewer=None,
            release_version=None,
            rollback_reference=None,
            integrity_hash="",
        )
        return self._write(candidate)

    def load(self, candidate_id: str) -> SkillCandidate:
        payload = _json_load(self._candidate_path(candidate_id))
        return SkillCandidate(**payload)

    def transition(
        self,
        candidate_id: str,
        state: str,
        *,
        reviewer: str | None = None,
        test_result: dict[str, Any] | None = None,
        release_version: str | None = None,
        rollback_reference: str | None = None,
    ) -> SkillCandidate:
        current = self.load(candidate_id)
        allowed = {
            "CANDIDATE": {"TESTED", "REJECTED"},
            "TESTED": {"APPROVED", "REJECTED"},
            "APPROVED": {"RELEASED", "REJECTED"},
            "RELEASED": {"ROLLED_BACK"},
        }
        if current.state not in allowed or state not in allowed[current.state]:
            raise ValueError(f"invalid skill candidate transition: {current.state} -> {state}")
        updated = SkillCandidate(
            candidate_id=current.candidate_id,
            skill_id=current.skill_id,
            state=state,
            created_at_utc=current.created_at_utc,
            updated_at_utc=utc_now(),
            proposer_agent=current.proposer_agent,
            evidence=current.evidence,
            test_result=test_result or current.test_result,
            reviewer=reviewer or current.reviewer,
            release_version=release_version or current.release_version,
            rollback_reference=rollback_reference or current.rollback_reference,
            integrity_hash="",
        )
        return self._write(updated)

    def validate(self, candidate_id: str) -> dict[str, Any]:
        candidate = self.load(candidate_id)
        payload = candidate.__dict__
        expected_hash = _fingerprint(
            canonical_json({k: v for k, v in payload.items() if k != "integrity_hash"})
        )
        return {
            "candidate_id": candidate_id,
            "state": candidate.state,
            "valid": candidate.integrity_hash == expected_hash,
            "candidate": payload,
        }

    def _write(self, candidate: SkillCandidate) -> SkillCandidate:
        payload = candidate.__dict__.copy()
        payload["integrity_hash"] = _fingerprint(
            canonical_json({k: v for k, v in payload.items() if k != "integrity_hash"})
        )
        _json_dump(self._candidate_path(candidate.candidate_id), payload)
        return SkillCandidate(**payload)


class BackupManager:
    def __init__(self, backup_root: Path) -> None:
        self.backup_root = backup_root
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def _hash_file(self, path: Path) -> str:
        hasher = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _should_exclude(self, path: Path) -> bool:
        normalized = str(path).replace("/", "\\").lower()
        parts = set(part for part in normalized.split("\\") if part)
        if normalized.endswith("\\.env") or normalized == ".env" or normalized == "state\\.env":
            return True
        if normalized.startswith("data\\backups") or "\\data\\backups\\" in normalized:
            return True
        if normalized.startswith("state\\npm") or "\\state\\npm\\" in normalized:
            return True
        if parts.intersection(
            {
                ".git",
                ".venv",
                "venv",
                "node_modules",
                "_tmp",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                ".tox",
                ".nox",
            }
        ):
            return True
        if any(part.endswith(".egg-info") for part in parts):
            return True
        if normalized in {".coverage", "coverage.xml"} or normalized.endswith(".coverage"):
            return True
        if normalized.startswith("htmlcov") or "\\htmlcov\\" in normalized:
            return True
        return any(
            part in normalized for part in ("apikey", "password", "token", "browser profile")
        )

    def create(self, source_root: Path) -> dict[str, Any]:
        backup_id = datetime.now(tz=UTC).strftime("backup-%Y%m%d-%H%M%S")
        target_dir = self.backup_root / backup_id
        target_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "backup_id": backup_id,
            "created_at_utc": utc_now(),
            "source_root": str(source_root),
            "files": [],
            "excluded": [],
        }
        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root)
            if self._should_exclude(relative):
                manifest["excluded"].append(str(relative))
                continue
            target = target_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            manifest["files"].append(
                {
                    "path": str(relative),
                    "sha256": self._hash_file(target),
                    "size": target.stat().st_size,
                }
            )
        manifest["manifest_sha256"] = _fingerprint(canonical_json(manifest))
        _json_dump(target_dir / "manifest.json", manifest)
        return manifest

    def verify(self, backup_id: str) -> dict[str, Any]:
        target_dir = self.backup_root / backup_id
        try:
            manifest = _json_load(target_dir / "manifest.json")
            mismatches: list[str] = []
            for item in manifest.get("files", []):
                file_path = target_dir / item["path"]
                if not file_path.exists():
                    mismatches.append(str(item["path"]))
                    continue
                if self._hash_file(file_path) != item["sha256"]:
                    mismatches.append(str(item["path"]))
            return {
                "backup_id": backup_id,
                "valid": not mismatches,
                "mismatches": mismatches,
                "manifest": manifest,
            }
        except Exception as exc:
            return {
                "backup_id": backup_id,
                "valid": False,
                "mismatches": [],
                "error": str(exc),
                "manifest": {},
            }

    def restore_drill(self, backup_id: str) -> dict[str, Any]:
        verification = self.verify(backup_id)
        target_dir = self.backup_root / backup_id
        restored_dir = Path(
            tempfile.mkdtemp(prefix=f"{backup_id}-restore-", dir=str(self.backup_root))
        )
        try:
            for file_info in verification["manifest"].get("files", []):
                source = target_dir / file_info["path"]
                destination = restored_dir / file_info["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            return {
                "backup_id": backup_id,
                "restored_dir": str(restored_dir),
                "valid": verification["valid"],
                "verified_files": len(verification["manifest"].get("files", [])),
            }
        finally:
            shutil.rmtree(restored_dir, ignore_errors=True)


_SYSTEM_EVENT_SEVERITY: dict[str, str] = {
    "SYSTEM_STARTED": "INFO",
    "SYSTEM_RECOVERED": "INFO",
    "SYSTEM_SHUTTING_DOWN": "INFO",
    "SYSTEM_OFFLINE_DETECTED": "CRITICAL",
    "GATEWAY_FAILED": "CRITICAL",
    "PYTHON_ENGINE_FAILED": "CRITICAL",
    "QUEUE_STALLED": "WARNING",
    "DATA_STALE": "WARNING",
    "MT5_DISCONNECTED": "WARNING",
    "FRED_UNAVAILABLE": "INFO",
    "DISK_LOW": "WARNING",
    "DATABASE_LOCKED": "CRITICAL",
    "EXPERIMENT_FAILED": "WARNING",
    "SECURITY_INCIDENT": "CRITICAL",
}


class TelegramPublisher:
    def __init__(self, journal_dir: Path) -> None:
        self.journal_dir = journal_dir
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.dead_letter_path = self.journal_dir / "telegram-dead-letter.ndjson"
        self.delivery_log_path = self.journal_dir / "telegram-delivery.ndjson"
        self._dedup_seen: set[str] = set()

    def format_thai(self, payload: dict[str, Any]) -> str:
        title = str(payload.get("title", "OpenClaw"))
        body = str(payload.get("body", ""))
        evidence_id = str(payload.get("evidence_id", "UNKNOWN"))
        return f"{title}\nหลักฐาน: {evidence_id}\n{body}".strip()

    def format_system_event(self, event: dict[str, Any]) -> str:
        """Format a system event payload as a Thai Telegram message."""
        event_type = str(event.get("event_type", "SYSTEM_INCIDENT"))
        severity = str(event.get("severity", _SYSTEM_EVENT_SEVERITY.get(event_type, "INFO")))
        component = str(event.get("component", "unknown"))
        timestamp_utc = str(event.get("timestamp_utc", utc_now()))
        message = str(event.get("message", ""))
        root_cause = str(event.get("root_cause", "unknown"))
        impact = str(event.get("current_impact", ""))
        recovery = str(event.get("recovery_action", ""))
        correlation_id = str(event.get("correlation_id", ""))

        severity_icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢"}.get(severity, "⚪")
        lines = [
            f"{severity_icon} [{severity}] {event_type}",
            f"ส่วนประกอบ: {component}",
            f"เวลา UTC: {timestamp_utc}",
        ]
        if message:
            lines.append(message)
        if root_cause and root_cause != "unknown":
            lines.append(f"สาเหตุ: {root_cause}")
        if impact:
            lines.append(f"ผลกระทบ: {impact}")
        if recovery:
            lines.append(f"การแก้ไข: {recovery}")
        if correlation_id:
            lines.append(f"ID: {correlation_id[:12]}")
        return "\n".join(lines)

    def _dedup_key(self, payload: dict[str, Any]) -> str:
        event_type = str(payload.get("event_type", payload.get("title", "")))
        component = str(payload.get("component", ""))
        return f"{event_type}:{component}"

    def dry_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_type = payload.get("event_type")
        if event_type and event_type in _SYSTEM_EVENT_SEVERITY:
            message = self.format_system_event(payload)
        else:
            message = self.format_thai(payload)
        record = {
            "created_at_utc": utc_now(),
            "mode": "dry_run",
            "message": message,
            "payload": payload,
            "delivery_status": "SKIPPED",
        }
        with self.delivery_log_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return record

    def reject(self, payload: dict[str, Any], reason: str) -> dict[str, Any]:
        record = {
            "created_at_utc": utc_now(),
            "reason": reason,
            "payload": payload,
        }
        with self.dead_letter_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return record

    def is_duplicate(self, payload: dict[str, Any]) -> bool:
        key = self._dedup_key(payload)
        if key in self._dedup_seen:
            return True
        self._dedup_seen.add(key)
        return False

    def clear_dedup_window(self) -> None:
        self._dedup_seen.clear()
