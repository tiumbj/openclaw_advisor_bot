from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest

from openclaw_super_advisor.cli import build_parser, main
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
    security = _run(["security-scan", "--project-root", root, "--json"])
    rendered = _run(
        ["render-config", "--project-root", root, "--env-file", env_example, "--validate", "--json"]
    )

    assert health["runtime_agent_id"] == "super-advisor"
    assert env["valid"] is True
    assert skills["valid"] is True
    assert security["summary"]["pass"] is True
    assert rendered["validation"]["valid"] is True


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
    assert "buy" not in help_text.lower()
    assert "sell" not in help_text.lower()
    assert "trade" not in help_text.lower()
