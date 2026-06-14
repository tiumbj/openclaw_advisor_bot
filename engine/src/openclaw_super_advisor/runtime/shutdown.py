"""Graceful shutdown handler for Windows and POSIX platforms.

Registers signal handlers for:
- Windows: CTRL_SHUTDOWN_EVENT, CTRL_C_EVENT via ctypes signal or SIGBREAK
- POSIX: SIGTERM, SIGINT

On shutdown signal:
1. Stop accepting new jobs
2. Checkpoint all active jobs
3. Flush evidence archive and outcome ledger
4. Notify callbacks (send SYSTEM_SHUTTING_DOWN)
5. Stop workers in reverse startup order

The handler is idempotent — multiple signals trigger shutdown once.
"""
from __future__ import annotations

import signal
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

_SHUTDOWN_EVENT = threading.Event()
_SHUTDOWN_LOCK = threading.Lock()
_CALLBACKS: list[Callable[[], None]] = []


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def is_shutdown_requested() -> bool:
    """Return True if a graceful shutdown has been signalled."""
    return _SHUTDOWN_EVENT.is_set()


def wait_for_shutdown(timeout: float | None = None) -> bool:
    """Block until shutdown is signalled. Returns True if shutdown occurred."""
    return _SHUTDOWN_EVENT.wait(timeout=timeout)


def register_shutdown_callback(fn: Callable[[], None]) -> None:
    """Register a callback to run on graceful shutdown."""
    with _SHUTDOWN_LOCK:
        _CALLBACKS.append(fn)


def trigger_shutdown(reason: str = "manual") -> None:
    """Trigger graceful shutdown programmatically."""
    _do_shutdown(f"programmatic:{reason}")


def _do_shutdown(source: str) -> None:
    _ = source
    with _SHUTDOWN_LOCK:
        if _SHUTDOWN_EVENT.is_set():
            return
        _SHUTDOWN_EVENT.set()

    callbacks = list(_CALLBACKS)
    for callback in reversed(callbacks):
        try:
            callback()
        except Exception:
            pass


def _sigterm_handler(signum: int, frame: object) -> None:
    _ = frame
    _do_shutdown(f"signal:{signum}")


def _sigint_handler(signum: int, frame: object) -> None:
    _ = (signum, frame)
    _do_shutdown("signal:SIGINT")


def install_signal_handlers() -> None:
    """Install OS signal handlers for graceful shutdown."""
    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (OSError, AttributeError):
        pass
    try:
        signal.signal(signal.SIGINT, _sigint_handler)
    except (OSError, AttributeError):
        pass
    # Windows SIGBREAK (Ctrl+Break)
    try:
        signal.signal(signal.SIGBREAK, _sigterm_handler)
    except (OSError, AttributeError):
        pass


def build_shutdown_telegram_payload(component: str = "python_engine") -> dict[str, Any]:
    """Build the SYSTEM_SHUTTING_DOWN Telegram alert payload."""
    now_utc = _utc_now_str()
    return {
        "event_type": "SYSTEM_SHUTTING_DOWN",
        "severity": "INFO",
        "component": component,
        "timestamp_utc": now_utc,
        "message": f"ระบบ {component} กำลังปิดตัวอย่างปลอดภัย",
        "root_cause": "graceful_shutdown_signal",
        "current_impact": "ระบบจะหยุดรับงานใหม่และบันทึก checkpoint ก่อนปิด",
        "recovery_action": "ระบบจะเริ่มใหม่อัตโนมัติเมื่อ Windows บูต",
    }


def build_recovery_telegram_payload(component: str = "python_engine") -> dict[str, Any]:
    """Build the SYSTEM_RECOVERED Telegram alert payload."""
    now_utc = _utc_now_str()
    return {
        "event_type": "SYSTEM_RECOVERED",
        "severity": "INFO",
        "component": component,
        "timestamp_utc": now_utc,
        "message": f"ระบบ {component} เริ่มทำงานใหม่เรียบร้อยแล้ว",
        "root_cause": "system_restart",
        "current_impact": "none",
        "recovery_action": "กำลังกลับมาทำงานต่อจาก checkpoint",
    }
