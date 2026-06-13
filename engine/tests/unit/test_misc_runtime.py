from __future__ import annotations

import json
import logging
import runpy
from pathlib import Path

import pytest

from openclaw_super_advisor._version import __version__
from openclaw_super_advisor.bridge import bridge_contract_summary
from openclaw_super_advisor.logging_setup import JsonFormatter, configure_logging
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.schemas import BridgeEnvelope, EvidencePacketSchema


def test_bridge_logging_and_main(monkeypatch: pytest.MonkeyPatch, sample_project: Path) -> None:
    summary = bridge_contract_summary()
    assert summary["advisor_only"] is True
    assert "schema_version" in summary["required_fields"]

    schema = EvidencePacketSchema()
    envelope = BridgeEnvelope(__version__, "evt", "2026-01-01T00:00:00Z", True, False)
    assert schema.execution_allowed is False
    assert envelope.event_id == "evt"

    record = logging.LogRecord("demo", logging.INFO, __file__, 10, "hello", (), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello"

    logger = configure_logging("debug")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1

    monkeypatch.setattr("openclaw_super_advisor.cli.main", lambda: 0)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("openclaw_super_advisor.__main__", run_name="__main__")
    assert exc.value.code == 0

    paths = build_paths(sample_project)
    assert paths.runtime_config_path.name == "openclaw.json"
