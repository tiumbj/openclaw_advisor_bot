from __future__ import annotations

from ..market_data.collector import MarketDataService


def run_collection_cycles(
    service: MarketDataService,
    cycles: int,
    sleep_seconds: int | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    return service.collect_cycles(cycles=cycles, sleep_seconds=sleep_seconds, dry_run=dry_run)
