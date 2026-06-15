from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.agent_topology import (
    build_agent_topology,
    validate_agent_topology,
    validate_routing,
)
from openclaw_super_advisor.cli import main
from openclaw_super_advisor.config import render_config
from openclaw_super_advisor.constants import REALTIME_CLASS_COMPUTED, REALTIME_CLASS_REALTIME
from openclaw_super_advisor.events import build_event_envelope, validate_event_envelope
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.persistence import (
    AgentMemoryStore,
    BackupManager,
    EvidenceArchive,
    OutcomeLedger,
    SkillCandidateStore,
    TelegramPublisher,
)


def test_required_agents_exist(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    report = validate_agent_topology(rendered, paths)
    assert report.valid, f"topology issues: {report.issues} route_issues: {report.route_issues}"
    assert [agent.agent_id for agent in report.agents] == [
        "super-advisor",
        "xau-strategy-auditor",
        "system-coder-auditor",
        "telegram-publisher",
        "market-data-integrity-agent",
        "price-action-microstructure-agent",
        "intermarket-macro-agent",
        "statistical-backtest-agent",
        "failure-root-cause-agent",
        "security-compliance-agent",
        "reliability-watchdog-agent",
        "knowledge-skill-manager",
    ]


def test_agent_workspaces_are_isolated(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    agents = build_agent_topology(paths)
    assert len({agent.workspace for agent in agents}) == 12
    assert len({agent.agent_dir for agent in agents}) == 12
    assert len({agent.session_store for agent in agents}) == 12
    assert len({agent.memory_dir for agent in agents}) == 12


def test_realtime_route_happy_path(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    route_report = validate_routing(rendered["routing"])  # type: ignore[index]
    assert route_report.valid


def test_circular_route_rejected() -> None:
    report = validate_routing(
        {
            "realtime": [["evidence-archive", "super-advisor"], ["super-advisor", "super-advisor"]],
            "code-audit": [
                ["source-bundle", "system-coder-auditor"],
                ["system-coder-auditor", "audit-report"],
            ],
        }
    )
    assert not report.valid


def test_event_schema_round_trip() -> None:
    event = build_event_envelope(
        "SYSTEM_HEALTH",
        {"status": "ok", "detail": "read-only"},
        source_component="test-suite",
        source_agent="super-advisor",
        evidence_reference="evidence-001",
    )
    report = validate_event_envelope(event)
    assert report.valid
    assert report.event is not None
    assert report.event["integrity_hash"]


def test_numeric_event_requires_provenance() -> None:
    event = build_event_envelope(
        "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
        {"entry": 2310.25},
        source_component="test-suite",
        source_agent="super-advisor",
        evidence_reference="evidence-002",
    )

    report = validate_event_envelope(event)

    assert not report.valid
    assert any(issue.path == "provenance.numeric_fields" for issue in report.issues)


def test_numeric_event_accepts_market_provenance() -> None:
    event = build_event_envelope(
        "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
        {"entry": 2310.25},
        source_component="test-suite",
        source_agent="super-advisor",
        evidence_reference="evidence-003",
        provenance={
            "numeric_fields": {
                "entry": {
                    "source": "mt5_tick",
                    "source_system": "MetaTrader5",
                    "fetched_at_utc": "2026-06-15T00:00:00Z",
                    "realtime_class": REALTIME_CLASS_REALTIME,
                }
            }
        },
    )

    report = validate_event_envelope(event)

    assert report.valid


def test_computed_numeric_event_requires_formula_version() -> None:
    event = build_event_envelope(
        "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
        {"score": 72.0},
        source_component="test-suite",
        source_agent="super-advisor",
        evidence_reference="evidence-004",
        provenance={
            "numeric_fields": {
                "score": {
                    "source": "fx_basket",
                    "source_system": "python",
                    "fetched_at_utc": "2026-06-15T00:00:00Z",
                    "realtime_class": REALTIME_CLASS_COMPUTED,
                }
            }
        },
    )

    report = validate_event_envelope(event)

    assert not report.valid
    assert any(
        issue.rule == "missing" and "formula_version" in issue.path for issue in report.issues
    )


def test_evidence_archive_is_append_only(tmp_path: Path) -> None:
    archive = EvidenceArchive(tmp_path / "evidence")
    event = build_event_envelope(
        "SYSTEM_HEALTH",
        {"status": "ok"},
        source_component="test-suite",
        source_agent="super-advisor",
        evidence_reference="evidence-001",
    )
    archive.append(event)
    report = archive.verify()
    assert report["valid"] is True
    assert report["record_count"] == 1
    assert archive.export_redacted().exists()


def test_ledger_is_append_only(tmp_path: Path) -> None:
    ledger = OutcomeLedger(tmp_path / "ledger")
    ledger.append("publication_approved", {"event_id": "event-001", "result": "ok"})
    report = ledger.verify()
    assert report["valid"] is True
    assert report["entry_count"] == 1


def test_memory_is_agent_isolated(tmp_path: Path) -> None:
    memory = AgentMemoryStore(tmp_path / "memory")
    path = memory.append("super-advisor", "approved", provenance={"source": "test"})
    assert path.exists()
    assert memory.read("super-advisor")
    assert not memory.read("telegram-publisher")


def test_skill_candidate_state_machine(tmp_path: Path) -> None:
    store = SkillCandidateStore(tmp_path / "candidates")
    candidate = store.create("new-skill", "system-coder-auditor", {"evidence_id": "e1"})
    assert candidate.state == "CANDIDATE"
    tested = store.transition(candidate.candidate_id, "TESTED", test_result={"pass": True})
    assert tested.state == "TESTED"
    approved = store.transition(candidate.candidate_id, "APPROVED", reviewer="super-advisor")
    assert approved.state == "APPROVED"
    released = store.transition(candidate.candidate_id, "RELEASED", release_version="1.0.0")
    assert released.state == "RELEASED"
    rolled_back = store.transition(candidate.candidate_id, "ROLLED_BACK", rollback_reference="r1")
    assert rolled_back.state == "ROLLED_BACK"


def test_backup_excludes_secrets(tmp_path: Path, sample_project: Path) -> None:
    backup = BackupManager(tmp_path / "backups")
    manifest = backup.create(sample_project)
    assert any(item.replace("\\", "/").endswith("state/.env") for item in manifest["excluded"])
    assert backup.verify(manifest["backup_id"])["valid"] is True


def test_telegram_uses_approved_evidence_only(tmp_path: Path) -> None:
    publisher = TelegramPublisher(tmp_path / "telegram")
    dry_run = publisher.dry_run({"title": "OpenClaw", "body": "พร้อมเผยแพร่", "evidence_id": "e1"})
    assert "หลักฐาน: e1" in dry_run["message"]
    assert dry_run["delivery_status"] == "SKIPPED"


def test_self_improvement_defaults_to_dry_run(sample_project: Path) -> None:
    exit_code = main(
        [
            "self-improvement",
            "dry-run",
            "--project-root",
            str(sample_project),
            "--env-file",
            str(sample_project / "state" / ".env"),
            "--json",
        ]
    )
    assert exit_code == 0
