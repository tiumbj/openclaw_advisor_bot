---
name: candlestick-structure-analysis
description: Classify XAUUSD candlestick formations on M1/M5/H1 timeframes from MT5 OHLC data.
version: 1.2.15
owner_agent: price-action-microstructure-agent
purpose: Provide deterministic candle pattern labels used in evidence scoring.
allowed_inputs:
  - OHLC evidence packet
required_input_schema: object
output_schema: object
allowed_tools:
  - read
  - session_status
denied_tools:
  - group:runtime
  - group:web
  - group:ui
  - group:automation
  - group:messaging
  - group:plugins
  - group:memory
  - group:sessions
  - write
  - edit
  - apply_patch
  - exec
  - process
  - code_execution
  - browser
  - canvas
  - gateway
  - message
  - subagents
safety_constraints:
  - advisor-only
  - no secret access
  - no execution
  - read-only market data
failure_behavior: return UNCLASSIFIED with reason; never fabricate candle label
audit_fields:
  - evidence_id
  - timeframe
  - candle_pattern
  - confidence
  - provenance
tests:
  - unit
  - integration
promotion_status: stable
---
# candlestick-structure-analysis

## Procedure
1. Receive OHLC evidence packet with at minimum 3 completed candles per timeframe
2. Classify last closed candle: engulfing, doji, hammer, shooting-star, pin-bar, marubozu, or UNCLASSIFIED
3. Compute body_ratio = (close-open)/(high-low); wick_ratio = upper_wick/(high-low)
4. Attach classification with confidence (HIGH/MEDIUM/LOW) based on ratio thresholds
5. Return structured evidence with candle_pattern, confidence, body_ratio, wick_ratio

## Decision Tree
- body_ratio > 0.7 → marubozu (HIGH)
- body_ratio < 0.1 and wick_ratio symmetric → doji (HIGH)
- lower_wick > 2×body and upper_wick < 0.2×range → hammer (MEDIUM)
- Insufficient OHLC data (<3 candles) → UNCLASSIFIED

## Quality Gates
- Only classify fully closed candles (not the current live candle)
- Classification uses Python deterministic rules, not LLM inference for numerics

## Failure Modes
- Partial candle included → over-estimate pattern significance → skip unfinished candles
- Low volume candle: pattern technically valid but unreliable → annotate low_volume=true
