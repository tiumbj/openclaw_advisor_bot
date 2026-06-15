"""Deterministic market feature calculations for XAUUSD signal scoring.

All functions are pure (no side effects, no external I/O).
Every output field carries formula_version, source evidence IDs,
realtime_class=COMPUTED, and quality_status.

Formula version: features-p2.4-v1
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

FORMULA_VERSION = "features-p2.4-v1"


# ---------------------------------------------------------------------------
# Feature output container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureResult:
    name: str
    value: float | str
    quality_status: str
    formula_version: str
    realtime_class: str = "COMPUTED"

    def provenance(self, evidence_ids: tuple[str, ...], fetched_at_utc: str) -> dict[str, Any]:
        return {
            "source": "python_feature_engine",
            "source_system": "python",
            "fetched_at_utc": fetched_at_utc,
            "realtime_class": self.realtime_class,
            "formula_version": self.formula_version,
            "evidence_ids": list(evidence_ids),
        }


# ---------------------------------------------------------------------------
# Trend and volatility
# ---------------------------------------------------------------------------

def ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average (Wilder smoothing)."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for price in values[period:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def compute_ema_features(
    closes: list[float],
) -> dict[str, FeatureResult]:
    results: dict[str, FeatureResult] = {}
    for period in (10, 50, 200):
        series = ema(closes, period)
        name = f"ema_{period}"
        if not series:
            results[name] = FeatureResult(
                name=name, value="INSUFFICIENT_DATA",
                quality_status="INSUFFICIENT_DATA",
                formula_version=FORMULA_VERSION,
            )
        else:
            results[name] = FeatureResult(
                name=name, value=round(series[-1], 5),
                quality_status="VALID",
                formula_version=FORMULA_VERSION,
            )
    return results


def compute_rsi(closes: list[float], period: int = 14) -> FeatureResult:
    if len(closes) < period + 1:
        return FeatureResult(
            name="rsi", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-(period):]
    gains = [max(c, 0.0) for c in recent]
    losses = [abs(min(c, 0.0)) for c in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        rsi_value = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_value = 100.0 - (100.0 / (1.0 + rs))
    return FeatureResult(
        name="rsi", value=round(rsi_value, 4),
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def compute_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> FeatureResult:
    if len(highs) < period + 1:
        return FeatureResult(
            name="atr", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
    trs = [
        max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        for i in range(1, len(highs))
    ]
    atr_value = sum(trs[-period:]) / period
    return FeatureResult(
        name="atr", value=round(atr_value, 5),
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def compute_macd(
    closes: list[float],
    fast: int = 12, slow: int = 26, signal_period: int = 9,
) -> dict[str, FeatureResult]:
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    min_len = min(len(ema_fast), len(ema_slow))
    if min_len < signal_period:
        stub = FeatureResult(
            name="macd", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
        return {"macd_line": stub, "macd_signal": stub, "macd_histogram": stub}
    macd_line = [f - s for f, s in zip(ema_fast[-min_len:], ema_slow[-min_len:], strict=False)]
    signal_line = ema(macd_line, signal_period)
    if not signal_line:
        stub = FeatureResult(
            name="macd", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
        return {"macd_line": stub, "macd_signal": stub, "macd_histogram": stub}
    histogram = macd_line[-1] - signal_line[-1]
    return {
        "macd_line": FeatureResult(
            name="macd_line", value=round(macd_line[-1], 6),
            quality_status="VALID", formula_version=FORMULA_VERSION,
        ),
        "macd_signal": FeatureResult(
            name="macd_signal", value=round(signal_line[-1], 6),
            quality_status="VALID", formula_version=FORMULA_VERSION,
        ),
        "macd_histogram": FeatureResult(
            name="macd_histogram", value=round(histogram, 6),
            quality_status="VALID", formula_version=FORMULA_VERSION,
        ),
    }


def compute_adx(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14,
) -> FeatureResult:
    if len(highs) < period * 2:
        return FeatureResult(
            name="adx", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
    plus_dm, minus_dm, true_ranges = [], [], []
    for i in range(1, len(highs)):
        h_diff = highs[i] - highs[i - 1]
        l_diff = lows[i - 1] - lows[i]
        plus_dm.append(max(h_diff, 0) if h_diff > l_diff else 0)
        minus_dm.append(max(l_diff, 0) if l_diff > h_diff else 0)
        true_ranges.append(
            max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        )
    smoothed_tr = sum(true_ranges[:period])
    smoothed_plus = sum(plus_dm[:period])
    smoothed_minus = sum(minus_dm[:period])
    for i in range(period, len(true_ranges)):
        smoothed_tr = smoothed_tr - smoothed_tr / period + true_ranges[i]
        smoothed_plus = smoothed_plus - smoothed_plus / period + plus_dm[i]
        smoothed_minus = smoothed_minus - smoothed_minus / period + minus_dm[i]
    if smoothed_tr == 0:
        return FeatureResult(
            name="adx", value=0.0, quality_status="VALID", formula_version=FORMULA_VERSION,
        )
    plus_di = 100 * smoothed_plus / smoothed_tr
    minus_di = 100 * smoothed_minus / smoothed_tr
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
    return FeatureResult(
        name="adx", value=round(dx, 4), quality_status="VALID", formula_version=FORMULA_VERSION,
    )


# ---------------------------------------------------------------------------
# Market structure
# ---------------------------------------------------------------------------

def detect_swing_highs_lows(
    highs: list[float], lows: list[float], lookback: int = 3
) -> dict[str, Any]:
    if len(highs) < lookback * 2 + 1:
        return {"swing_highs": [], "swing_lows": [], "quality_status": "INSUFFICIENT_DATA"}
    swing_highs: list[int] = []
    swing_lows: list[int] = []
    for i in range(lookback, len(highs) - lookback):
        if highs[i] == max(highs[i - lookback: i + lookback + 1]):
            swing_highs.append(i)
        if lows[i] == min(lows[i - lookback: i + lookback + 1]):
            swing_lows.append(i)
    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "quality_status": "VALID",
        "formula_version": FORMULA_VERSION,
    }


def classify_trend(
    closes: list[float], ema50_series: list[float], ema200_series: list[float]
) -> FeatureResult:
    if not ema50_series or not ema200_series or len(closes) < 3:
        return FeatureResult(
            name="trend_state", value="UNKNOWN",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
    price = closes[-1]
    ema50 = ema50_series[-1]
    ema200 = ema200_series[-1]
    if price > ema50 > ema200:
        state = "UPTREND"
    elif price < ema50 < ema200:
        state = "DOWNTREND"
    else:
        state = "RANGING"
    return FeatureResult(
        name="trend_state", value=state,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def compute_headroom_atr(
    current_price: float, nearest_resistance: float, atr: float
) -> FeatureResult:
    if atr <= 0:
        return FeatureResult(
            name="headroom_atr", value="INVALID_ATR",
            quality_status="INVALID", formula_version=FORMULA_VERSION,
        )
    distance = abs(nearest_resistance - current_price)
    headroom = round(distance / atr, 4)
    return FeatureResult(
        name="headroom_atr", value=headroom,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


# ---------------------------------------------------------------------------
# Price action
# ---------------------------------------------------------------------------

def compute_body_wick_ratio(open_: float, high: float, low: float, close: float) -> FeatureResult:
    candle_range = high - low
    if candle_range == 0:
        return FeatureResult(
            name="body_wick_ratio", value=0.0,
            quality_status="DOJI", formula_version=FORMULA_VERSION,
        )
    body = abs(close - open_)
    ratio = round(body / candle_range, 4)
    return FeatureResult(
        name="body_wick_ratio", value=ratio,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def detect_engulfing(
    prev_open: float, prev_close: float, curr_open: float, curr_close: float
) -> FeatureResult:
    prev_bullish = prev_close > prev_open
    curr_bullish = curr_close > curr_open
    bullish_engulf = (
        not prev_bullish and curr_bullish
        and curr_close > prev_open and curr_open < prev_close
    )
    bearish_engulf = (
        prev_bullish and not curr_bullish
        and curr_open > prev_close and curr_close < prev_open
    )
    if bullish_engulf:
        pattern = "BULLISH_ENGULFING"
    elif bearish_engulf:
        pattern = "BEARISH_ENGULFING"
    else:
        pattern = "NONE"
    return FeatureResult(
        name="engulfing", value=pattern,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def detect_rejection(high: float, low: float, open_: float, close: float) -> FeatureResult:
    candle_range = high - low
    if candle_range == 0:
        return FeatureResult(
            name="rejection", value="NONE",
            quality_status="DOJI", formula_version=FORMULA_VERSION,
        )
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    if lower_wick / candle_range > 0.6:
        pattern = "BULLISH_REJECTION"
    elif upper_wick / candle_range > 0.6:
        pattern = "BEARISH_REJECTION"
    else:
        pattern = "NONE"
    return FeatureResult(
        name="rejection", value=pattern,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


# ---------------------------------------------------------------------------
# Intermarket: normalized change + rolling correlation
# ---------------------------------------------------------------------------

def normalized_change(values: list[float]) -> FeatureResult:
    if len(values) < 2 or values[-2] == 0:
        return FeatureResult(
            name="normalized_change", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
    pct = (values[-1] - values[-2]) / abs(values[-2]) * 100
    return FeatureResult(
        name="normalized_change", value=round(pct, 6),
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def rolling_correlation(series_a: list[float], series_b: list[float], window: int) -> FeatureResult:
    if len(series_a) < window or len(series_b) < window:
        return FeatureResult(
            name="correlation", value="INSUFFICIENT_DATA",
            quality_status="INSUFFICIENT_DATA", formula_version=FORMULA_VERSION,
        )
    a = series_a[-window:]
    b = series_b[-window:]
    mean_a = sum(a) / window
    mean_b = sum(b) / window
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=False)) / window
    std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / window)
    std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b) / window)
    if std_a == 0 or std_b == 0:
        return FeatureResult(
            name="correlation", value=0.0,
            quality_status="ZERO_VARIANCE", formula_version=FORMULA_VERSION,
        )
    corr = round(cov / (std_a * std_b), 6)
    return FeatureResult(
        name="correlation", value=corr,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )


def classify_regime(
    dxy_change: float, us10y_change: float, xau_ema_trend: str
) -> FeatureResult:
    if dxy_change > 0.2 and us10y_change > 0.05:
        regime = "RISK_OFF_USD_STRENGTH"
    elif dxy_change < -0.2 and xau_ema_trend == "UPTREND":
        regime = "RISK_ON_GOLD_BULLISH"
    elif abs(dxy_change) < 0.1 and abs(us10y_change) < 0.02:
        regime = "NEUTRAL"
    else:
        regime = "MIXED"
    return FeatureResult(
        name="regime", value=regime,
        quality_status="VALID", formula_version=FORMULA_VERSION,
    )
