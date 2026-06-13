from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.constants import FORBIDDEN_SYMBOLS
from openclaw_super_advisor.market_data.backend import MT5_READONLY_METHODS


def test_mt5_backend_stays_read_only() -> None:
    package_root = (
        Path(__file__).resolve().parents[2] / "src" / "openclaw_super_advisor" / "market_data"
    )
    backend_text = (package_root / "backend.py").read_text(encoding="utf-8")
    adapter_text = (package_root / "mt5_readonly.py").read_text(encoding="utf-8")

    assert "importlib" not in adapter_text
    assert "__getattr__" not in adapter_text
    assert "getattr(mt5" not in adapter_text.lower()
    assert "def call(" not in adapter_text
    for forbidden in FORBIDDEN_SYMBOLS:
        assert forbidden not in adapter_text
    for method_name in MT5_READONLY_METHODS:
        assert method_name in backend_text
