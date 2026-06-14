"""FRED (Federal Reserve Economic Data) adapter.

Fetches macro series (DGS10, DTWEXBGS) from the St. Louis Fed API.
All data is classified DAILY_MACRO and must not be used as intraday triggers.

FRED failure is non-blocking: pipeline continues with SOURCE_UNAVAILABLE status.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from ..constants import (
    FRED_SERIES,
    REALTIME_CLASS_DAILY_MACRO,
    REALTIME_CLASS_UNKNOWN,
)


class FredApiError(RuntimeError):
    """Raised when the FRED API returns a non-retryable error."""


@dataclass(frozen=True)
class FredObservation:
    series_id: str
    internal_id: str
    date: str
    value: float | None
    realtime_class: str
    is_proxy: bool
    is_exact_dxy: bool
    source: str
    stale: bool
    retrieved_at_utc: str


@dataclass(frozen=True)
class FredSeriesResult:
    internal_id: str
    series_id: str
    realtime_class: str
    is_proxy: bool
    is_exact_dxy: bool
    latest_observation: FredObservation | None
    status: str
    error: str | None
    retrieved_at_utc: str


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


class FredCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, FredSeriesResult]] = {}

    def get(self, series_id: str) -> FredSeriesResult | None:
        entry = self._store.get(series_id)
        if entry is None:
            return None
        stored_at, result = entry
        if (time.monotonic() - stored_at) > self._ttl:
            return None
        return result

    def set(self, series_id: str, result: FredSeriesResult) -> None:
        self._store[series_id] = (time.monotonic(), result)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_seconds: int = 300) -> None:
        self._threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if (time.monotonic() - self._opened_at) > self._reset_seconds:
            self._failures = 0
            self._opened_at = None
            return False
        return True

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = time.monotonic()

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None


class FredAdapter:
    """Non-blocking FRED data adapter.

    API key must be provided from env — never committed to source.
    On any failure, returns SOURCE_UNAVAILABLE status without stopping the pipeline.
    """

    BASE_URL = "https://api.stlouisfed.org"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout_seconds: int = 20,
        max_retries: int = 3,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._cache = FredCache(ttl_seconds=cache_ttl_seconds)
        self._circuit = CircuitBreaker()
        self._last_known: dict[str, FredObservation] = {}

    def _fetch_observations(self, series_id: str) -> list[dict[str, Any]]:
        """Fetch observations from FRED API with bounded retry."""
        if self._circuit.is_open():
            raise FredApiError(f"circuit breaker open for FRED {series_id}")

        url = (
            f"{self._base_url}/fred/series/observations"
            f"?series_id={series_id}"
            f"&api_key={self._api_key}"
            f"&file_type=json"
            f"&sort_order=desc"
            f"&limit=10"
        )
        req = Request(url)
        req.add_header("User-Agent", "openclaw-advisor/1.0")

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                with urlopen(req, timeout=self._timeout) as resp:
                    raw = resp.read().decode("utf-8")
                body = json.loads(raw)
                self._circuit.record_success()
                return list(body.get("observations", []))
            except (HTTPError, URLError) as exc:
                last_exc = exc
                if isinstance(exc, HTTPError) and exc.code in (400, 401, 403):
                    self._circuit.record_failure()
                    raise FredApiError(f"FRED API non-retryable HTTP {exc.code}: {series_id}") from exc
                backoff = 2 ** attempt
                time.sleep(backoff)
            except Exception as exc:
                last_exc = exc
                self._circuit.record_failure()
                raise FredApiError(f"FRED fetch error for {series_id}: {exc}") from exc

        self._circuit.record_failure()
        raise FredApiError(f"FRED {series_id} failed after {self._max_retries} retries") from last_exc

    def _parse_latest(
        self,
        observations: list[dict[str, Any]],
        series_id: str,
        series_meta: dict[str, Any],
    ) -> FredObservation | None:
        """Extract the most recent non-missing observation."""
        retrieved = _utc_now_str()
        for obs in observations:
            raw_value = obs.get("value", ".")
            if raw_value == ".":
                continue
            try:
                value = float(raw_value)
            except ValueError:
                continue
            date_str = str(obs.get("date", ""))
            obs_date = _parse_date(date_str) if date_str else datetime.now(tz=UTC)
            age_days = (datetime.now(tz=UTC) - obs_date).days
            stale = age_days > 5
            return FredObservation(
                series_id=series_id,
                internal_id=str(series_meta.get("internal_id", series_id)),
                date=date_str,
                value=value,
                realtime_class=REALTIME_CLASS_DAILY_MACRO,
                is_proxy=bool(series_meta.get("is_proxy", False)),
                is_exact_dxy=bool(series_meta.get("is_exact_dxy", False)),
                source="FRED",
                stale=stale,
                retrieved_at_utc=retrieved,
            )
        return None

    def fetch_series(self, series_key: str) -> FredSeriesResult:
        """Fetch a named series (e.g. 'US10Y' or 'USD_BROAD').

        Returns a FredSeriesResult with status SOURCE_UNAVAILABLE on any failure.
        Never raises — non-blocking by design.
        """
        retrieved = _utc_now_str()
        series_meta = FRED_SERIES.get(series_key)
        if series_meta is None:
            return FredSeriesResult(
                internal_id=series_key,
                series_id=series_key,
                realtime_class=REALTIME_CLASS_UNKNOWN,
                is_proxy=False,
                is_exact_dxy=False,
                latest_observation=None,
                status="SOURCE_UNAVAILABLE",
                error=f"unknown FRED series key: {series_key!r}",
                retrieved_at_utc=retrieved,
            )

        series_id = str(series_meta["series_id"])
        internal_id = str(series_meta["internal_id"])
        is_proxy = bool(series_meta.get("is_proxy", False))
        is_exact_dxy = bool(series_meta.get("is_exact_dxy", False))

        if not self._api_key:
            return FredSeriesResult(
                internal_id=internal_id,
                series_id=series_id,
                realtime_class=REALTIME_CLASS_DAILY_MACRO,
                is_proxy=is_proxy,
                is_exact_dxy=is_exact_dxy,
                latest_observation=self._last_known.get(series_id),
                status="SOURCE_UNAVAILABLE",
                error="FRED_API_KEY not configured",
                retrieved_at_utc=retrieved,
            )

        cached = self._cache.get(series_id)
        if cached is not None:
            return cached

        try:
            observations = self._fetch_observations(series_id)
            obs = self._parse_latest(observations, series_id, series_meta)
            status = "VALID" if obs is not None else "SOURCE_UNAVAILABLE"
            if obs is not None and obs.stale:
                status = "STALE"
            if obs is not None:
                obs_copy = FredObservation(
                    series_id=obs.series_id,
                    internal_id=obs.internal_id,
                    date=obs.date,
                    value=obs.value,
                    realtime_class=obs.realtime_class,
                    is_proxy=obs.is_proxy,
                    is_exact_dxy=obs.is_exact_dxy,
                    source=obs.source,
                    stale=obs.stale,
                    retrieved_at_utc=obs.retrieved_at_utc,
                )
                self._last_known[series_id] = obs_copy
            result = FredSeriesResult(
                internal_id=internal_id,
                series_id=series_id,
                realtime_class=REALTIME_CLASS_DAILY_MACRO,
                is_proxy=is_proxy,
                is_exact_dxy=is_exact_dxy,
                latest_observation=obs,
                status=status,
                error=None,
                retrieved_at_utc=retrieved,
            )
            self._cache.set(series_id, result)
            return result
        except FredApiError as exc:
            return FredSeriesResult(
                internal_id=internal_id,
                series_id=series_id,
                realtime_class=REALTIME_CLASS_DAILY_MACRO,
                is_proxy=is_proxy,
                is_exact_dxy=is_exact_dxy,
                latest_observation=self._last_known.get(series_id),
                status="SOURCE_UNAVAILABLE",
                error=str(exc),
                retrieved_at_utc=retrieved,
            )
        except Exception as exc:
            return FredSeriesResult(
                internal_id=internal_id,
                series_id=series_id,
                realtime_class=REALTIME_CLASS_DAILY_MACRO,
                is_proxy=is_proxy,
                is_exact_dxy=is_exact_dxy,
                latest_observation=self._last_known.get(series_id),
                status="SOURCE_UNAVAILABLE",
                error=f"unexpected error: {exc}",
                retrieved_at_utc=retrieved,
            )

    def fetch_all(self) -> dict[str, FredSeriesResult]:
        """Fetch all configured FRED series. Failure per series is independent."""
        return {key: self.fetch_series(key) for key in FRED_SERIES}
