"""Unit tests for FRED adapter (LC-002, LC-013).

All tests use injected HTTP transport — no live FRED API calls.
Tests verify: series classification, is_proxy, realtime_class, missing values,
error handling, cache, circuit breaker, retry, and secret non-exposure.
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openclaw_super_advisor.market_data.fred_adapter import (
    CircuitBreaker,
    FredAdapter,
    FredApiError,
    FredCache,
    FredObservation,
    FredSeriesResult,
)
from openclaw_super_advisor.constants import FRED_SERIES, REALTIME_CLASS_DAILY_MACRO


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_adapter(api_key: str = "test-key", *, max_retries: int = 1) -> FredAdapter:
    return FredAdapter(
        api_key=api_key,
        base_url="http://fred.test",
        timeout_seconds=5,
        max_retries=max_retries,
        cache_ttl_seconds=60,
    )


def _mock_response(observations: list[dict[str, Any]]) -> MagicMock:
    body = json.dumps({"observations": observations}).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _obs(date: str, value: str) -> dict[str, Any]:
    return {"date": date, "value": value}


# ── FRED_SERIES catalog ───────────────────────────────────────────────────────

def test_fred_series_catalog_has_us10y() -> None:
    assert "US10Y" in FRED_SERIES
    meta = FRED_SERIES["US10Y"]
    assert meta["series_id"] == "DGS10"
    assert meta["internal_id"] == "US10Y_DAILY"
    assert meta.get("is_proxy") is False
    assert meta.get("is_exact_dxy") is False


def test_fred_series_catalog_has_usd_broad() -> None:
    assert "USD_BROAD" in FRED_SERIES
    meta = FRED_SERIES["USD_BROAD"]
    assert meta["series_id"] == "DTWEXBGS"
    assert meta["internal_id"] == "DXY_PROXY_FRED"
    assert meta.get("is_proxy") is True
    assert meta.get("is_exact_dxy") is False


def test_fred_dgs10_daily_classification() -> None:
    """DGS10 (US10Y) must be classified as DAILY_MACRO — never intraday."""
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-13", "4.25")])):
        result = adapter.fetch_series("US10Y")
    assert result.realtime_class == REALTIME_CLASS_DAILY_MACRO
    assert result.latest_observation is not None
    assert result.latest_observation.realtime_class == REALTIME_CLASS_DAILY_MACRO


def test_fred_dtwexbgs_is_marked_proxy() -> None:
    """DTWEXBGS must be is_proxy=True, is_exact_dxy=False."""
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-13", "118.5")])):
        result = adapter.fetch_series("USD_BROAD")
    assert result.is_proxy is True
    assert result.is_exact_dxy is False


def test_fred_internal_id_us10y_daily() -> None:
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-13", "4.25")])):
        result = adapter.fetch_series("US10Y")
    assert result.internal_id == "US10Y_DAILY"
    assert result.series_id == "DGS10"


def test_fred_internal_id_dxy_proxy_fred() -> None:
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-13", "118.5")])):
        result = adapter.fetch_series("USD_BROAD")
    assert result.internal_id == "DXY_PROXY_FRED"
    assert result.series_id == "DTWEXBGS"


# ── missing-value handling ────────────────────────────────────────────────────

def test_fred_missing_dot_value_skipped() -> None:
    """'.' (FRED missing marker) must not be treated as zero — skip to next."""
    adapter = _make_adapter()
    obs_list = [_obs("2026-06-14", "."), _obs("2026-06-13", "4.22")]
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response(obs_list)):
        result = adapter.fetch_series("US10Y")
    assert result.latest_observation is not None
    assert result.latest_observation.value == pytest.approx(4.22)
    assert result.latest_observation.date == "2026-06-13"


def test_fred_all_missing_returns_source_unavailable() -> None:
    """If all observations are '.', status must be SOURCE_UNAVAILABLE."""
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-13", ".")])):
        result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"
    assert result.latest_observation is None


def test_fred_empty_observations_returns_source_unavailable() -> None:
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([])):
        result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"


# ── API key validation ─────────────────────────────────────────────────────────

def test_fred_no_api_key_returns_source_unavailable() -> None:
    """Empty API key: no HTTP call, SOURCE_UNAVAILABLE with meaningful error."""
    adapter = _make_adapter(api_key="")
    result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"
    assert "FRED_API_KEY" in (result.error or "")


def test_fred_api_key_not_in_error_string() -> None:
    """API key must never appear in any error message."""
    secret_key = "super-secret-fred-key-12345"
    adapter = _make_adapter(api_key=secret_key)
    from urllib.error import HTTPError
    http_err = HTTPError("url", 401, "Unauthorized", {}, None)  # type: ignore[arg-type]
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen", side_effect=http_err):
        result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"
    assert secret_key not in (result.error or "")


# ── unknown series key ────────────────────────────────────────────────────────

def test_fred_unknown_series_key() -> None:
    """Unknown key returns SOURCE_UNAVAILABLE without HTTP call."""
    adapter = _make_adapter()
    result = adapter.fetch_series("NONEXISTENT_KEY")
    assert result.status == "SOURCE_UNAVAILABLE"
    assert "unknown" in (result.error or "").lower()


# ── pipeline non-blocking ─────────────────────────────────────────────────────

def test_fred_failure_does_not_raise() -> None:
    """fetch_series must never raise — non-blocking by design."""
    adapter = _make_adapter()
    from urllib.error import URLError
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               side_effect=URLError("timeout")), \
         patch("openclaw_super_advisor.market_data.fred_adapter.time.sleep"):
        result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"


def test_fred_http_error_non_retryable_401() -> None:
    """HTTP 401 must not retry and must return SOURCE_UNAVAILABLE."""
    adapter = _make_adapter()
    from urllib.error import HTTPError
    http_err = HTTPError("url", 401, "Unauthorized", {}, None)  # type: ignore[arg-type]
    call_count = 0

    def _side(req, timeout=None):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        raise http_err

    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen", side_effect=_side):
        result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"
    assert call_count == 1  # must not retry on 401


def test_fred_fetch_all_independent_failures() -> None:
    """fetch_all: one failing series must not prevent others from being fetched."""
    adapter = _make_adapter()
    call_count = 0

    def _side(req, timeout=None):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from urllib.error import URLError
            raise URLError("fail first")
        return _mock_response([_obs("2026-06-13", "118.5")])

    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen", side_effect=_side), \
         patch("openclaw_super_advisor.market_data.fred_adapter.time.sleep"):
        results = adapter.fetch_all()
    assert len(results) == len(FRED_SERIES)
    assert any(r.status == "SOURCE_UNAVAILABLE" for r in results.values())
    assert any(r.status != "SOURCE_UNAVAILABLE" for r in results.values())


# ── cache ─────────────────────────────────────────────────────────────────────

def test_fred_cache_hit_avoids_second_request() -> None:
    adapter = _make_adapter()
    call_count = 0

    def _side(req, timeout=None):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        return _mock_response([_obs("2026-06-13", "4.25")])

    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen", side_effect=_side):
        r1 = adapter.fetch_series("US10Y")
        r2 = adapter.fetch_series("US10Y")
    assert call_count == 1
    assert r1.latest_observation is not None
    assert r2.latest_observation is not None


def test_fred_cache_expiry() -> None:
    cache = FredCache(ttl_seconds=1)
    dummy: FredSeriesResult = MagicMock(spec=FredSeriesResult)
    cache.set("DGS10", dummy)
    assert cache.get("DGS10") is dummy
    time.sleep(1.1)
    assert cache.get("DGS10") is None


def test_fred_cache_miss_on_new_key() -> None:
    cache = FredCache(ttl_seconds=60)
    assert cache.get("MISSING_KEY") is None


# ── circuit breaker ───────────────────────────────────────────────────────────

def test_circuit_breaker_opens_after_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_seconds=300)
    assert not cb.is_open()
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert cb.is_open()


def test_circuit_breaker_resets_after_timeout() -> None:
    cb = CircuitBreaker(failure_threshold=1, reset_seconds=0)
    cb.record_failure()
    assert cb.is_open()
    time.sleep(0.01)
    assert not cb.is_open()


def test_circuit_breaker_success_resets_failures() -> None:
    cb = CircuitBreaker(failure_threshold=3, reset_seconds=300)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert not cb.is_open()


def test_circuit_breaker_success_reopens_after_more_failures() -> None:
    cb = CircuitBreaker(failure_threshold=2, reset_seconds=300)
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()


def test_fred_circuit_open_returns_source_unavailable() -> None:
    """When circuit is open, fetch_series must return SOURCE_UNAVAILABLE immediately."""
    adapter = _make_adapter()
    for _ in range(3):
        adapter._circuit.record_failure()
    assert adapter._circuit.is_open()
    result = adapter.fetch_series("US10Y")
    assert result.status == "SOURCE_UNAVAILABLE"


# ── stale last-known value ─────────────────────────────────────────────────────

def test_fred_stale_last_known_returned_on_failure() -> None:
    """On HTTP failure after a successful fetch, the last known observation is returned."""
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-10", "4.20")])):
        _ = adapter.fetch_series("US10Y")

    # Expire the cache, then fail the network
    adapter._cache = FredCache(ttl_seconds=0)
    time.sleep(0.01)
    from urllib.error import URLError
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               side_effect=URLError("timeout")), \
         patch("openclaw_super_advisor.market_data.fred_adapter.time.sleep"):
        result = adapter.fetch_series("US10Y")

    assert result.latest_observation is not None
    assert result.latest_observation.value == pytest.approx(4.20)


# ── observation stale marking ─────────────────────────────────────────────────

def test_fred_observation_stale_when_old() -> None:
    """Observation older than 5 days must be marked stale=True."""
    adapter = _make_adapter()
    # Use a clearly old date
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-01-01", "4.10")])):
        result = adapter.fetch_series("US10Y")
    assert result.status == "STALE"
    assert result.latest_observation is not None
    assert result.latest_observation.stale is True


def test_fred_observation_fresh_recent_date() -> None:
    """A very recent observation must have stale=False and status=VALID."""
    adapter = _make_adapter()
    with patch("openclaw_super_advisor.market_data.fred_adapter.urlopen",
               return_value=_mock_response([_obs("2026-06-13", "4.25")])):
        result = adapter.fetch_series("US10Y")
    assert result.status == "VALID"
    assert result.latest_observation is not None
    assert result.latest_observation.stale is False
