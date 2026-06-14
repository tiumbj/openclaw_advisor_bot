from __future__ import annotations

import json
import logging
import runpy
from pathlib import Path

import pytest

from openclaw_super_advisor._version import __version__
from openclaw_super_advisor.bridge import bridge_contract_summary
from openclaw_super_advisor.logging_setup import JsonFormatter, configure_logging
from openclaw_super_advisor.market_models import SUPPORTED_TIMEFRAMES, QualityEvent
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.runtime import shutdown
from openclaw_super_advisor.runtime.watchdog import ComponentProbe, Watchdog
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
    assert QualityEvent.__name__ == "QualityIncident"
    assert "H1" in SUPPORTED_TIMEFRAMES


def test_shutdown_callbacks_are_idempotent() -> None:
    shutdown._SHUTDOWN_EVENT.clear()
    shutdown._CALLBACKS.clear()
    calls: list[str] = []

    shutdown.register_shutdown_callback(lambda: calls.append("first"))
    shutdown.register_shutdown_callback(lambda: calls.append("second"))

    assert not shutdown.is_shutdown_requested()
    shutdown.trigger_shutdown("unit-test")
    shutdown.trigger_shutdown("unit-test-again")

    assert shutdown.is_shutdown_requested()
    assert shutdown.wait_for_shutdown(timeout=0)
    assert calls == ["second", "first"]

    shutdown_payload = shutdown.build_shutdown_telegram_payload("gateway")
    recovery_payload = shutdown.build_recovery_telegram_payload("gateway")
    assert shutdown_payload["event_type"] == "SYSTEM_SHUTTING_DOWN"
    assert recovery_payload["event_type"] == "SYSTEM_RECOVERED"

    shutdown._SHUTDOWN_EVENT.clear()
    shutdown._CALLBACKS.clear()


def test_watchdog_builds_incidents_and_ignores_callback_errors() -> None:
    checks = {"count": 0}
    incidents: list[dict[str, object]] = []

    def probe_gateway() -> bool:
        checks["count"] += 1
        return False

    watchdog = Watchdog(max_restart_attempts=3)
    probe = ComponentProbe("gateway", probe_gateway, failure_event_type="GATEWAY_FAILED")
    watchdog.register(probe)
    watchdog.on_incident(lambda incident: incidents.append(incident))

    def broken_callback(_incident: dict[str, object]) -> None:
        raise RuntimeError("callback failed")

    watchdog.on_incident(broken_callback)

    first = watchdog.check_all()
    second = watchdog.check_all()
    third = watchdog.check_all()

    assert checks["count"] == 3
    assert not first.all_healthy
    assert first.components[0].status == "DEGRADED"
    assert second.components[0].status == "DEGRADED"
    assert third.components[0].status == "FAILED"
    assert third.incident_events[0]["event_type"] == "GATEWAY_FAILED"
    assert incidents[-1]["severity"] == "CRITICAL"

    healthy_probe = ComponentProbe("db", lambda: True)
    assert healthy_probe.check().status == "OK"
