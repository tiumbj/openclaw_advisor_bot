from __future__ import annotations

import importlib

import pytest

from openclaw_super_advisor.market_data import build_market_data_service
from openclaw_super_advisor.paths import build_paths


@pytest.mark.live
@pytest.mark.windows
@pytest.mark.mt5
def test_live_mt5_health_smoke() -> None:
    if importlib.util.find_spec("MetaTrader5") is None:
        pytest.skip("MetaTrader5 package is not installed")
    paths = build_paths()
    if not paths.runtime_env_path.exists():
        pytest.skip("runtime env is not configured")

    env_text = paths.runtime_env_path.read_text(encoding="utf-8")
    if "MT5_ENABLED=true" not in env_text:
        pytest.skip("MT5 live mode is disabled")

    service = build_market_data_service(paths, env_path=paths.runtime_env_path)
    try:
        health = service.market_health()
    finally:
        service.close()
    assert "backend" in health
