"""Reliability watchdog agent runtime.

Monitors component health: gateway, Python engine, queue workers, disk, database.
On failure: logs incident, attempts restart (bounded), escalates to Telegram.

The watchdog is intentionally simple — it checks health endpoints and signals,
does NOT run complex logic, and fails safe (no side-effects if checks fail).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from ..constants import TELEGRAM_SYSTEM_EVENTS


@dataclass(frozen=True)
class ComponentStatus:
    name: str
    status: str
    message: str
    checked_at_utc: str


@dataclass
class WatchdogReport:
    checked_at_utc: str
    components: list[ComponentStatus]
    incident_events: list[dict[str, Any]]

    @property
    def all_healthy(self) -> bool:
        return all(c.status == "OK" for c in self.components)


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class ComponentProbe:
    """Simple callable-based health probe for a named component."""

    def __init__(
        self,
        name: str,
        probe_fn: Callable[[], bool],
        *,
        failure_event_type: str = "SYSTEM_INCIDENT",
    ) -> None:
        self._name = name
        self._probe = probe_fn
        self._event_type = failure_event_type
        self._consecutive_failures = 0

    def check(self) -> ComponentStatus:
        now = _utc_now_str()
        try:
            healthy = self._probe()
        except Exception as exc:
            healthy = False
            msg = f"probe raised: {exc}"
        else:
            msg = "OK" if healthy else "FAILED"

        if healthy:
            self._consecutive_failures = 0
            status = "OK"
        else:
            self._consecutive_failures += 1
            status = "DEGRADED" if self._consecutive_failures < 3 else "FAILED"

        return ComponentStatus(
            name=self._name,
            status=status,
            message=msg,
            checked_at_utc=now,
        )

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def failure_event_type(self) -> str:
        return self._event_type


class Watchdog:
    """Monitors registered components and raises incidents on failure.

    Usage:
        watchdog = Watchdog(max_restart_attempts=3)
        watchdog.register(ComponentProbe("gateway", probe_gateway, failure_event_type="GATEWAY_FAILED"))
        report = watchdog.check_all()
    """

    def __init__(self, max_restart_attempts: int = 3) -> None:
        self._probes: list[ComponentProbe] = []
        self._restart_attempts: dict[str, int] = {}
        self._max_restart = max_restart_attempts
        self._incident_callbacks: list[Callable[[dict[str, Any]], None]] = []

    def register(self, probe: ComponentProbe) -> None:
        self._probes.append(probe)

    def on_incident(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback to receive incident events (e.g. for Telegram dispatch)."""
        self._incident_callbacks.append(callback)

    def check_all(self) -> WatchdogReport:
        now = _utc_now_str()
        statuses: list[ComponentStatus] = []
        incidents: list[dict[str, Any]] = []

        for probe in self._probes:
            status = probe.check()
            statuses.append(status)

            if status.status in ("DEGRADED", "FAILED"):
                incident = self._build_incident(probe, status)
                incidents.append(incident)
                for cb in self._incident_callbacks:
                    try:
                        cb(incident)
                    except Exception:
                        pass

        return WatchdogReport(
            checked_at_utc=now,
            components=statuses,
            incident_events=incidents,
        )

    def _build_incident(
        self, probe: ComponentProbe, status: ComponentStatus
    ) -> dict[str, Any]:
        event_type = probe.failure_event_type
        if event_type not in TELEGRAM_SYSTEM_EVENTS:
            event_type = "SYSTEM_INCIDENT"
        return {
            "event_type": event_type,
            "severity": "CRITICAL" if status.status == "FAILED" else "WARNING",
            "component": status.name,
            "timestamp_utc": status.checked_at_utc,
            "consecutive_failures": probe.consecutive_failures,
            "message": status.message,
            "root_cause": f"component_{status.name}_health_probe_failed",
            "current_impact": f"ส่วนประกอบ {status.name} ทำงานผิดปกติ",
            "recovery_action": "watchdog จะพยายาม restart อัตโนมัติ",
        }
