"""Unit tests for FX basket computation (LC-003).

Tests verify: direction logic (reverse/direct), INSUFFICIENT_DATA threshold,
formula version, internal ID, no NaN/Infinity, UNKNOWN preservation, stale marking.
"""
from __future__ import annotations

import math

import pytest

from openclaw_super_advisor.constants import (
    FX_BASKET_INTERNAL_ID,
    FX_BASKET_PAIRS,
    FX_BASKET_REVERSE_PAIRS,
    REALTIME_CLASS_INTRADAY_REALTIME,
    REALTIME_CLASS_STALE,
    REALTIME_CLASS_UNKNOWN,
)
from openclaw_super_advisor.market_data.fx_basket import (
    FORMULA_VERSION,
    compute_fx_basket,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _full_pair_data(
    pairs: tuple[str, ...] = FX_BASKET_PAIRS,
    *,
    rtclass: str = REALTIME_CLASS_INTRADAY_REALTIME,
    pct_move: float = 0.0,
) -> dict[str, tuple[float | None, float | None, str]]:
    """All seven pairs with a uniform pct_move from 1.0 prev_close."""
    base = 1.0
    close = base * (1 + pct_move)
    return {pair: (close, base, rtclass) for pair in pairs}


# ── formula version and internal ID ──────────────────────────────────────────

def test_formula_version_constant() -> None:
    assert FORMULA_VERSION == "fx-basket-v1-normalized-returns"


def test_result_formula_version() -> None:
    result = compute_fx_basket(_full_pair_data())
    assert result.formula_version == FORMULA_VERSION


def test_result_internal_id() -> None:
    result = compute_fx_basket(_full_pair_data())
    assert result.internal_id == FX_BASKET_INTERNAL_ID
    assert result.internal_id == "FX_BASKET_COMPUTED"


# ── zero-move all valid ───────────────────────────────────────────────────────

def test_all_seven_pairs_valid_zero_move() -> None:
    """When all pairs are flat, basket_value must be 0.0."""
    result = compute_fx_basket(_full_pair_data(pct_move=0.0))
    assert result.status == "VALID"
    assert result.component_count_used == 7
    assert result.component_count_total == 7
    assert result.basket_value == pytest.approx(0.0)


# ── direction logic: REVERSE pairs (USD is quote) ─────────────────────────────

def test_eurusd_rise_weakens_usd() -> None:
    """EURUSD rising by 1% → USD return is -1% → negative basket contribution."""
    data = _full_pair_data(pct_move=0.0)
    data["EURUSD"] = (1.0100, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    eur_comp = next(c for c in result.components if c.logical_symbol == "EURUSD")
    assert eur_comp.is_reversed is True
    assert eur_comp.return_value == pytest.approx(-0.01)


def test_gbpusd_rise_weakens_usd() -> None:
    data = _full_pair_data(pct_move=0.0)
    data["GBPUSD"] = (1.2600, 1.2500, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    gbp_comp = next(c for c in result.components if c.logical_symbol == "GBPUSD")
    assert gbp_comp.is_reversed is True
    assert gbp_comp.return_value == pytest.approx(-((1.2600 / 1.2500) - 1.0))


def test_audusd_and_nzdusd_are_reversed() -> None:
    for pair in ("AUDUSD", "NZDUSD"):
        data = _full_pair_data(pct_move=0.0)
        data[pair] = (1.0100, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
        result = compute_fx_basket(data)
        comp = next(c for c in result.components if c.logical_symbol == pair)
        assert comp.is_reversed is True, f"{pair} must be marked reversed"
        assert comp.return_value == pytest.approx(-0.01), f"{pair} return must be negated"


# ── direction logic: DIRECT pairs (USD is base) ───────────────────────────────

def test_usdjpy_rise_strengthens_usd() -> None:
    """USDJPY rising by 1% → USD return is +1% → positive basket contribution."""
    data = _full_pair_data(pct_move=0.0)
    data["USDJPY"] = (152.00, 150.50, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    jpy_comp = next(c for c in result.components if c.logical_symbol == "USDJPY")
    assert jpy_comp.is_reversed is False
    expected = (152.00 / 150.50) - 1.0
    assert jpy_comp.return_value == pytest.approx(expected)


def test_usdchf_and_usdcad_are_direct() -> None:
    for pair in ("USDCHF", "USDCAD"):
        data = _full_pair_data(pct_move=0.0)
        data[pair] = (1.0100, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
        result = compute_fx_basket(data)
        comp = next(c for c in result.components if c.logical_symbol == pair)
        assert comp.is_reversed is False, f"{pair} must NOT be reversed"
        assert comp.return_value == pytest.approx(0.01), f"{pair} return must keep sign"


# ── basket_value calculation ──────────────────────────────────────────────────

def test_basket_value_in_basis_points() -> None:
    """Basket = avg_usd_return x 10,000, rounded to 4dp."""
    # All 7 pairs: all flat except USDJPY +1%
    data = _full_pair_data(pct_move=0.0)
    data["USDJPY"] = (1.0100, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    # 6 components return 0, 1 returns +0.01 → avg = 0.01/7
    expected_bp = round((0.01 / 7) * 10_000, 4)
    assert result.basket_value == pytest.approx(expected_bp, rel=1e-4)


def test_symmetric_all_usd_strong_by_1pct() -> None:
    """If all pairs move uniformly to reflect 1% USD strength, basket ≈ 100 bps."""
    data: dict[str, tuple[float | None, float | None, str]] = {}
    for pair in FX_BASKET_PAIRS:
        if pair in FX_BASKET_REVERSE_PAIRS:
            # EUR/GBP/AUD/NZD must FALL 1% for USD to be 1% stronger
            data[pair] = (0.9900, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
        else:
            # USD/JPY/CHF/CAD must RISE 1% for USD to be 1% stronger
            data[pair] = (1.0100, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    # All components contribute approximately +0.01 return → avg ≈ 0.01 → 100 bps
    assert result.basket_value == pytest.approx(100.0, rel=0.01)


# ── insufficient data ─────────────────────────────────────────────────────────

def test_fewer_than_3_valid_insufficient_data() -> None:
    data: dict[str, tuple[float | None, float | None, str]] = {
        "EURUSD": (1.01, 1.00, REALTIME_CLASS_INTRADAY_REALTIME),
        "GBPUSD": (1.26, 1.25, REALTIME_CLASS_INTRADAY_REALTIME),
    }
    result = compute_fx_basket(data)
    assert result.status == "INSUFFICIENT_DATA"
    assert result.basket_value is None
    assert result.component_count_used == 2


def test_exactly_3_valid_computes_basket() -> None:
    data: dict[str, tuple[float | None, float | None, str]] = {
        "EURUSD": (1.01, 1.00, REALTIME_CLASS_INTRADAY_REALTIME),
        "USDJPY": (150.00, 150.00, REALTIME_CLASS_INTRADAY_REALTIME),
        "USDCHF": (0.90, 0.90, REALTIME_CLASS_INTRADAY_REALTIME),
    }
    result = compute_fx_basket(data)
    assert result.status in ("VALID", "STALE")  # 3 valid → computes
    assert result.basket_value is not None
    assert result.component_count_used == 3


def test_empty_input_returns_insufficient_data() -> None:
    result = compute_fx_basket({})
    assert result.status == "INSUFFICIENT_DATA"
    assert result.basket_value is None
    assert result.component_count_used == 0
    assert result.component_count_total == len(FX_BASKET_PAIRS)


# ── missing / incomplete components ──────────────────────────────────────────

def test_missing_pair_marked_missing() -> None:
    data = _full_pair_data(pct_move=0.0)
    del data["EURUSD"]
    result = compute_fx_basket(data)
    eur_comp = next(c for c in result.components if c.logical_symbol == "EURUSD")
    assert eur_comp.status == "MISSING"
    assert eur_comp.return_value is None


def test_none_close_marks_incomplete() -> None:
    data = _full_pair_data(pct_move=0.0)
    data["EURUSD"] = (None, 1.0000, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    eur_comp = next(c for c in result.components if c.logical_symbol == "EURUSD")
    assert eur_comp.status == "INCOMPLETE"
    assert eur_comp.return_value is None


def test_none_prev_close_marks_incomplete() -> None:
    data = _full_pair_data(pct_move=0.0)
    data["USDJPY"] = (152.00, None, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    jpy_comp = next(c for c in result.components if c.logical_symbol == "USDJPY")
    assert jpy_comp.status == "INCOMPLETE"
    assert jpy_comp.return_value is None


def test_zero_prev_close_skipped() -> None:
    """Division by zero must not occur — prev_close=0.0 must be treated as incomplete."""
    data = _full_pair_data(pct_move=0.0)
    data["USDCAD"] = (1.3600, 0.0, REALTIME_CLASS_INTRADAY_REALTIME)
    result = compute_fx_basket(data)
    cad_comp = next(c for c in result.components if c.logical_symbol == "USDCAD")
    assert cad_comp.status == "INCOMPLETE"
    assert cad_comp.return_value is None


# ── NaN / Infinity guard ──────────────────────────────────────────────────────

def test_no_nan_in_basket_value() -> None:
    result = compute_fx_basket(_full_pair_data(pct_move=0.001))
    if result.basket_value is not None:
        assert not math.isnan(result.basket_value)


def test_no_infinity_in_basket_value() -> None:
    result = compute_fx_basket(_full_pair_data(pct_move=1.0))  # 100% move
    if result.basket_value is not None:
        assert not math.isinf(result.basket_value)


def test_no_nan_in_component_returns() -> None:
    result = compute_fx_basket(_full_pair_data(pct_move=0.001))
    for comp in result.components:
        if comp.return_value is not None:
            assert not math.isnan(comp.return_value)
            assert not math.isinf(comp.return_value)


# ── stale status ──────────────────────────────────────────────────────────────

def test_stale_component_marks_basket_stale() -> None:
    """Any stale component in the valid set → basket status STALE."""
    data = _full_pair_data(pct_move=0.0)
    data["EURUSD"] = (1.0100, 1.0000, REALTIME_CLASS_STALE)
    result = compute_fx_basket(data)
    assert result.status == "STALE"
    assert result.realtime_class == REALTIME_CLASS_STALE


def test_unknown_realtime_class_marks_basket_stale() -> None:
    """UNKNOWN realtime class in a valid component → basket status STALE."""
    data = _full_pair_data(pct_move=0.0)
    data["USDJPY"] = (152.00, 150.00, REALTIME_CLASS_UNKNOWN)
    result = compute_fx_basket(data)
    assert result.status == "STALE"


def test_all_fresh_components_basket_valid() -> None:
    result = compute_fx_basket(_full_pair_data(rtclass=REALTIME_CLASS_INTRADAY_REALTIME))
    assert result.status == "VALID"
    assert result.realtime_class == REALTIME_CLASS_INTRADAY_REALTIME


# ── provenance ────────────────────────────────────────────────────────────────

def test_provenance_contains_formula_and_pairs() -> None:
    result = compute_fx_basket(_full_pair_data())
    prov = result.provenance
    assert prov["formula"] == FORMULA_VERSION
    assert set(prov["pairs"]) == set(FX_BASKET_PAIRS)
    assert prov["internal_id"] == FX_BASKET_INTERNAL_ID


def test_provenance_components_used_matches_result() -> None:
    result = compute_fx_basket(_full_pair_data())
    assert result.provenance["components_used"] == result.component_count_used
    assert result.provenance["components_total"] == result.component_count_total


# ── component count ───────────────────────────────────────────────────────────

def test_total_components_always_seven() -> None:
    """All 7 pairs appear in components regardless of validity."""
    result = compute_fx_basket({})
    assert result.component_count_total == 7
    assert len(result.components) == 7


def test_reverse_pairs_set_matches_catalog() -> None:
    result = compute_fx_basket(_full_pair_data(pct_move=0.01))
    for comp in result.components:
        if comp.logical_symbol in FX_BASKET_REVERSE_PAIRS:
            assert comp.is_reversed is True
        else:
            assert comp.is_reversed is False
