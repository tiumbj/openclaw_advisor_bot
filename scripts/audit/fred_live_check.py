from __future__ import annotations

import json
import os
from pathlib import Path

from openclaw_super_advisor.constants import FRED_SERIES, REALTIME_CLASS_DAILY_MACRO
from openclaw_super_advisor.market_data.fred_adapter import FredAdapter


def _load_env_value(root: Path, name: str) -> str:
    for candidate in (root / "state" / ".env", root / "Data_for_env.txt"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(name, "").strip()


def main() -> int:
    root = Path.cwd()
    api_key = _load_env_value(root, "FRED_API_KEY")
    if not api_key:
        print(
            json.dumps(
                {
                    "credential_status": "MISSING",
                    "series": {},
                    "overall_status": "BLOCKED_CREDENTIAL",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    adapter = FredAdapter(
        api_key=api_key,
        timeout_seconds=15,
        max_retries=3,
        cache_ttl_seconds=1,
    )
    results = adapter.fetch_all()
    payload: dict[str, object] = {
        "credential_status": "PRESENT_MASKED",
        "expected_realtime_class": REALTIME_CLASS_DAILY_MACRO,
        "series": {},
    }
    series_payload: dict[str, object] = {}
    valid = True
    for key, result in results.items():
        observation = result.latest_observation
        ok = (
            result.realtime_class == REALTIME_CLASS_DAILY_MACRO
            and result.series_id == FRED_SERIES[key]["series_id"]
            and result.status in {"VALID", "STALE"}
            and observation is not None
            and observation.realtime_class == REALTIME_CLASS_DAILY_MACRO
        )
        valid = valid and ok
        series_payload[key] = {
            "series_id": result.series_id,
            "internal_id": result.internal_id,
            "status": result.status,
            "realtime_class": result.realtime_class,
            "is_proxy": result.is_proxy,
            "is_exact_dxy": result.is_exact_dxy,
            "latest_date": None if observation is None else observation.date,
            "has_value": observation is not None and observation.value is not None,
            "retrieved_at_utc": result.retrieved_at_utc,
            "error_redacted": result.error is not None,
        }
    payload["series"] = series_payload
    payload["overall_status"] = "PASS" if valid else "FAIL"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
