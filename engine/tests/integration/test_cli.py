from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest

from openclaw_super_advisor._version import PHASE
from openclaw_super_advisor.cli import _parse_datetime, build_parser, main
from openclaw_super_advisor.market_data import build_market_data_service
from openclaw_super_advisor.market_data.fake_backend import FakeMt5Backend, FakeMt5Scenario
from openclaw_super_advisor.paths import build_paths


def _run(command: list[str]) -> dict[str, object]:
    buffer = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = buffer
        exit_code = main(command)
    finally:
        sys.stdout = stdout
    assert exit_code == 0
    return json.loads(buffer.getvalue())


def _run_result(command: list[str]) -> tuple[int, dict[str, object]]:
    buffer = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = buffer
        exit_code = main(command)
    finally:
        sys.stdout = stdout
    return exit_code, json.loads(buffer.getvalue())


def _enable_mt5(sample_project: Path) -> Path:
    env_path = sample_project / "state" / ".env"
    env_text = env_path.read_text(encoding="utf-8").replace("MT5_ENABLED=false", "MT5_ENABLED=true")
    env_path.write_text(env_text, encoding="utf-8")
    return env_path


def _scenario() -> FakeMt5Scenario:
    return FakeMt5Scenario(
        symbols=[
            {
                "name": "XAUUSD.",
                "description": "Gold",
                "path": "Metals",
                "visible": False,
                "point": 0.01,
                "digits": 2,
            },
            {
                "name": "DXY",
                "description": "Dollar Index",
                "path": "Indices",
                "visible": True,
                "point": 0.01,
                "digits": 2,
            },
        ],
        ticks_by_symbol={
            "XAUUSD.": [
                {
                    "time": int(datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC).timestamp()),
                    "time_msc": 1767225720000,
                    "bid": 2600.0,
                    "ask": 2600.2,
                    "last": 2600.1,
                    "volume": 9.0,
                    "volume_real": 9.0,
                    "flags": 1,
                }
            ]
        },
        latest_tick_by_symbol={
            "XAUUSD.": {
                "time": int(datetime(2026, 1, 1, 0, 3, 0, tzinfo=UTC).timestamp()),
                "time_msc": 1767225780000,
                "bid": 2600.1,
                "ask": 2600.3,
                "last": 2600.2,
                "volume": 10.0,
                "volume_real": 10.0,
                "flags": 1,
            }
        },
        bars_by_symbol_and_timeframe={
            ("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1): [
                {
                    "time": int(datetime(2026, 1, 1, 0, 0, tzinfo=UTC).timestamp()),
                    "open": 2600.0,
                    "high": 2603.0,
                    "low": 2599.0,
                    "close": 2602.0,
                    "tick_volume": 120,
                    "spread": 10,
                    "real_volume": 0,
                }
            ]
        },
    )


def test_cli_validation_commands(sample_project: Path) -> None:
    root = str(sample_project)
    env_file = str(sample_project / "state" / ".env")
    env_example = str(sample_project / ".env.example")

    health = _run(["health", "--project-root", root, "--json"])
    env = _run(["validate-env", "--project-root", root, "--env-file", env_file, "--json"])
    skills = _run(["validate-skills", "--project-root", root, "--env-file", env_example, "--json"])
    agents = _run(["validate-agents", "--project-root", root, "--env-file", env_example, "--json"])
    registry = _run(
        ["validate-agent-registry", "--project-root", root, "--env-file", env_example, "--json"]
    )
    routing = _run(
        ["validate-routing", "--project-root", root, "--env-file", env_example, "--json"]
    )
    list_agents = _run(["list-agents", "--project-root", root, "--env-file", env_example, "--json"])
    described = _run(
        [
            "describe-agent",
            "blueprint-coder",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--json",
        ]
    )
    route_task = _run(
        [
            "route-task",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--task-type",
            "code_implementation",
            "--dry-run",
            "--json",
        ]
    )
    manager_agents = _run(
        [
            "manager-query",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--query",
            "บอกหน้าที่ของ agent ทุกตัวในระบบ และบอกว่าแต่ละตัวห้ามทำอะไร",
            "--json",
        ]
    )
    manager_route = _run(
        [
            "manager-query",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--query",
            (
                "งานตรวจ code production-grade ควรส่งให้ agent ตัวไหน เพราะอะไร "
                "ใครต้อง review ต่อ และ agent ที่ได้รับงานห้ามทำอะไรบ้าง"
            ),
            "--json",
        ]
    )
    pipeline = _run(
        ["pipeline-dry-run", "--project-root", root, "--env-file", env_example, "--json"]
    )
    evidence = _run(
        ["evidence-verify", "--project-root", root, "--env-file", env_example, "--json"]
    )
    security = _run(["security-scan", "--project-root", root, "--json"])
    rendered = _run(
        ["render-config", "--project-root", root, "--env-file", env_example, "--validate", "--json"]
    )
    provider_policy = _run(
        ["provider-policy", "--project-root", root, "--env-file", env_example, "--json"]
    )

    assert health["runtime_agent_id"] == "super-advisor"
    assert len(health["runtime_agent_ids"]) == 13
    assert env["valid"] is True
    assert skills["valid"] is True
    assert agents["valid"] is True
    assert registry["valid"] is True
    assert routing["valid"] is True
    assert len(list_agents["agents"]) == 13
    assert described["agent"]["agent_id"] == "blueprint-coder"
    assert route_task["decision"]["selected_agent"] == "blueprint-coder"
    assert len(manager_agents["response"]["agents"]) == 13
    assert manager_route["response"]["selected_agent"] == "system-coder-auditor"
    assert pipeline["overall_pass"] is True
    assert evidence["valid"] is True
    assert security["summary"]["pass"] is True
    assert rendered["validation"]["valid"] is True
    assert provider_policy["phase"] == PHASE
    assert provider_policy["policy"]["status"] == "BLOCKED"
    assert provider_policy["policy"]["reason"] == "NO_ENABLED_PROVIDER"


def test_cli_serve_runtime_stays_alive_until_shutdown(sample_project: Path) -> None:
    root = str(sample_project)
    env_path = str(sample_project / "state" / ".env")
    command = [
        sys.executable,
        "-m",
        "openclaw_super_advisor",
        "serve",
        "--project-root",
        root,
        "--env-file",
        env_path,
        "--resume",
    ]
    proc = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10.0
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert proc.poll() is None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def test_cli_registry_generation_is_deterministic(sample_project: Path) -> None:
    root = str(sample_project)
    env_example = str(sample_project / ".env.example")
    temp_a = sample_project / "config" / "agent_capability_registry.a.json"
    temp_b = sample_project / "config" / "agent_capability_registry.b.json"

    first = _run(
        [
            "validate-agent-registry",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--write",
            "--output",
            str(temp_a),
            "--json",
        ]
    )
    second = _run(
        [
            "validate-agent-registry",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--write",
            "--output",
            str(temp_b),
            "--json",
        ]
    )

    bytes_a = temp_a.read_bytes()
    bytes_b = temp_b.read_bytes()
    canonical = (sample_project / "config" / "agent_capability_registry.json").read_bytes()

    assert first["valid"] is True
    assert second["valid"] is True
    assert bytes_a == bytes_b
    assert bytes_a == canonical
    assert first["registry"]["registry_hash"] == second["registry"]["registry_hash"]


def test_cli_manager_query_fails_closed_for_similarity_prompt(sample_project: Path) -> None:
    root = str(sample_project)
    env_example = str(sample_project / ".env.example")

    exit_code, payload = _run_result(
        [
            "manager-query",
            "--project-root",
            root,
            "--env-file",
            env_example,
            "--query",
            "งานนี้ส่งให้ agent อะไรก็ได้ที่คิดว่าใกล้เคียง",
            "--json",
        ]
    )

    assert exit_code == 0
    assert payload["response"]["selected_agent"] is None
    assert payload["response"]["task_type"] == "unknown_task_type"


def test_cli_market_data_commands(monkeypatch: pytest.MonkeyPatch, sample_project: Path) -> None:
    root = str(sample_project)
    env_path = _enable_mt5(sample_project)

    def _service_builder(_paths: object, env_path: Path | None = None) -> object:
        project_paths = build_paths(sample_project)
        selected_env = env_path or project_paths.runtime_env_path
        return build_market_data_service(
            project_paths,
            env_path=selected_env,
            backend=FakeMt5Backend(_scenario()),
        )

    monkeypatch.setattr("openclaw_super_advisor.cli.build_market_data_service", _service_builder)

    market_health = _run(
        ["mt5-health", "--project-root", root, "--env-file", str(env_path), "--json"]
    )
    discovered = _run(
        ["mt5-discover-symbols", "--project-root", root, "--env-file", str(env_path), "--json"]
    )
    collected = _run(
        [
            "market-collect",
            "--project-root",
            root,
            "--env-file",
            str(env_path),
            "--json",
            "--dry-run",
        ]
    )
    snapshot = _run(
        [
            "market-snapshot",
            "--project-root",
            root,
            "--env-file",
            str(env_path),
            "--symbol",
            "XAUUSD",
            "--refresh",
            "--json",
        ]
    )
    backfill = _run(
        [
            "market-backfill",
            "--project-root",
            root,
            "--env-file",
            str(env_path),
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--start",
            "2025-12-31T23:00:00Z",
            "--end",
            "2026-01-01T01:00:00Z",
            "--json",
            "--dry-run",
        ]
    )
    storage = _run(
        ["market-storage-check", "--project-root", root, "--env-file", str(env_path), "--json"]
    )

    assert market_health["connected"] is True
    assert discovered["count"] == 2
    assert collected["dry_run"] is True
    assert snapshot["ticks"]
    assert backfill["timeframe"] == "H1"
    assert storage["schema_version"] == "1.2.0"


def test_cli_help_and_no_trade_commands() -> None:
    help_text = build_parser().format_help()
    assert "mt5-health" in help_text
    assert "market-backfill" in help_text
    assert "market-storage-check" in help_text
    assert "provider-policy" in help_text
    assert "validate-agents" in help_text
    assert "validate-agent-registry" in help_text
    assert "validate-routing" in help_text
    assert "pipeline-dry-run" in help_text
    assert "list-agents" in help_text
    assert "describe-agent" in help_text
    assert "route-task" in help_text
    assert "manager-query" in help_text
    assert "buy" not in help_text.lower()
    assert "sell" not in help_text.lower()
    assert "trade" not in help_text.lower()


def test_parse_datetime_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="UTC offset or Z suffix"):
        _parse_datetime("2026-01-01T00:00:00")


def test_market_backfill_rejects_naive_timestamps(
    monkeypatch: pytest.MonkeyPatch, sample_project: Path
) -> None:
    root = str(sample_project)
    env_path = _enable_mt5(sample_project)

    def _service_builder(_paths: object, env_path: Path | None = None) -> object:
        project_paths = build_paths(sample_project)
        selected_env = env_path or project_paths.runtime_env_path
        return build_market_data_service(
            project_paths,
            env_path=selected_env,
            backend=FakeMt5Backend(_scenario()),
        )

    monkeypatch.setattr("openclaw_super_advisor.cli.build_market_data_service", _service_builder)

    exit_code, payload = _run_result(
        [
            "market-backfill",
            "--project-root",
            root,
            "--env-file",
            str(env_path),
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--start",
            "2025-12-31T23:00:00",
            "--end",
            "2026-01-01T01:00:00Z",
            "--json",
            "--dry-run",
        ]
    )

    assert exit_code == 1
    assert "UTC offset or Z suffix" in str(payload["error"])
