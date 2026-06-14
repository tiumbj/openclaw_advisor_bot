"""FX basket USD strength proxy computation.

Computes a normalized USD basket from 7 major FX pairs as a proxy for DXY.
Output internal ID: FX_BASKET_COMPUTED.

Formula is versioned in provenance so results are reproducible.
Missing or stale components are marked individually — never fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..constants import (
    FX_BASKET_INTERNAL_ID,
    FX_BASKET_PAIRS,
    FX_BASKET_REVERSE_PAIRS,
    REALTIME_CLASS_INTRADAY_REALTIME,
    REALTIME_CLASS_STALE,
    REALTIME_CLASS_UNKNOWN,
)

FORMULA_VERSION = "fx-basket-v1-normalized-returns"


@dataclass(frozen=True)
class BasketComponent:
    logical_symbol: str
    close: float | None
    prev_close: float | None
    realtime_class: str
    is_reversed: bool
    return_value: float | None
    status: str


@dataclass(frozen=True)
class FxBasketResult:
    internal_id: str
    formula_version: str
    basket_value: float | None
    component_count_used: int
    component_count_total: int
    components: tuple[BasketComponent, ...]
    realtime_class: str
    status: str
    computed_at_utc: str
    provenance: dict[str, Any]


def _utc_now_str() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def compute_fx_basket(
    pair_data: dict[str, tuple[float | None, float | None, str]],
) -> FxBasketResult:
    """Compute normalized USD basket from FX pair close prices.

    Args:
        pair_data: dict mapping logical symbol (e.g. 'EURUSD') to
                   (current_close, prev_close, realtime_class).
                   Use None for missing values — never pass fabricated fills.

    Returns:
        FxBasketResult with basket_value=None if fewer than 3 components are valid.
    """
    computed_at = _utc_now_str()
    components: list[BasketComponent] = []

    for pair in FX_BASKET_PAIRS:
        entry = pair_data.get(pair)
        if entry is None:
            components.append(BasketComponent(
                logical_symbol=pair,
                close=None,
                prev_close=None,
                realtime_class=REALTIME_CLASS_UNKNOWN,
                is_reversed=pair in FX_BASKET_REVERSE_PAIRS,
                return_value=None,
                status="MISSING",
            ))
            continue

        close, prev_close, rtclass = entry

        if close is None or prev_close is None or prev_close == 0.0:
            components.append(BasketComponent(
                logical_symbol=pair,
                close=close,
                prev_close=prev_close,
                realtime_class=rtclass,
                is_reversed=pair in FX_BASKET_REVERSE_PAIRS,
                return_value=None,
                status="INCOMPLETE",
            ))
            continue

        # Normalized return: (close / prev_close) - 1
        raw_return = (close / prev_close) - 1.0

        # For pairs where USD is quote (EURUSD, GBPUSD, AUDUSD, NZDUSD),
        # a rising close means USD weakening — reverse sign to express USD strength.
        if pair in FX_BASKET_REVERSE_PAIRS:
            usd_return = -raw_return
        else:
            usd_return = raw_return

        components.append(BasketComponent(
            logical_symbol=pair,
            close=close,
            prev_close=prev_close,
            realtime_class=rtclass,
            is_reversed=pair in FX_BASKET_REVERSE_PAIRS,
            return_value=usd_return,
            status="VALID",
        ))

    valid_components = [c for c in components if c.return_value is not None]
    total = len(FX_BASKET_PAIRS)
    used = len(valid_components)

    if used < 3:
        basket_value = None
        status = "INSUFFICIENT_DATA"
        rtclass = REALTIME_CLASS_UNKNOWN
    else:
        returns = [c.return_value for c in valid_components if c.return_value is not None]
        avg_return = sum(returns) / used
        basket_value = round(avg_return * 10_000, 4)  # basis points for readability
        stale_count = sum(
            1 for c in valid_components
            if c.realtime_class in (REALTIME_CLASS_STALE, REALTIME_CLASS_UNKNOWN)
        )
        if stale_count > 0:
            status = "STALE"
            rtclass = REALTIME_CLASS_STALE
        else:
            status = "VALID"
            rtclass = REALTIME_CLASS_INTRADAY_REALTIME

    return FxBasketResult(
        internal_id=FX_BASKET_INTERNAL_ID,
        formula_version=FORMULA_VERSION,
        basket_value=basket_value,
        component_count_used=used,
        component_count_total=total,
        components=tuple(components),
        realtime_class=rtclass,
        status=status,
        computed_at_utc=computed_at,
        provenance={
            "formula": FORMULA_VERSION,
            "pairs": list(FX_BASKET_PAIRS),
            "reverse_pairs": sorted(FX_BASKET_REVERSE_PAIRS),
            "internal_id": FX_BASKET_INTERNAL_ID,
            "components_used": used,
            "components_total": total,
        },
    )
