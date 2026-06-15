---
name: xauusd-market-analysis
description: XAUUSD market analysis skill.
version: 1.2.12
owner_agent: xau-strategy-auditor
purpose: Audit XAUUSD structure and setup quality.
allowed_inputs:
  - market evidence
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
failure_behavior: return structured audit failure
audit_fields:
  - evidence_id
  - correlation_id
  - provenance
tests:
  - unit
  - integration
promotion_status: stable
---
# xauusd-market-analysis

Audits XAUUSD market structure and setup quality from Python-sourced feature evidence.
All score components must be derived from Python features (formula_version: scoring-p2.4-v1).

## Procedure

1. Receive evidence package from xau-strategy-auditor.
2. Verify provenance.formula_version=features-p2.4-v1; reject if mismatched.
3. Verify data_quality=VALID; if not, return all scores as 0.
4. Compute Trend score (0-35) from trend_state, ema relationships, adx.
5. Compute Structure score (0-25) from headroom_atr and swing alignment.
6. Compute Macro score (0-20) from regime and macro_alignment.
7. Compute Price Action score (0-20) from rejection, engulfing, body_wick_ratio.
8. Sum components to total score; apply scoring-p2.4-v1 decision thresholds.
9. Return structured output with all score_components, evidence_reference, provenance.

## Required Input Fields

- `evidence_id`: Python evidence package ID (must be present)
- `features.ema_10/50/200`: EMA values or INSUFFICIENT_DATA
- `features.rsi`: RSI(14) or INSUFFICIENT_DATA
- `features.atr`: ATR(14) or INSUFFICIENT_DATA
- `features.adx`: ADX(14) or INSUFFICIENT_DATA
- `features.trend_state`: UPTREND|DOWNTREND|RANGING|UNKNOWN
- `features.headroom_atr`: normalized distance to nearest resistance
- `features.rejection`, `features.engulfing`: price action patterns from Python
- `features.regime`: intermarket regime classification
- `data_quality`: VALID|DEGRADED|STALE|INSUFFICIENT_DATA
- `provenance.formula_version`: must be `features-p2.4-v1`

## Output Fields

- `score_components.trend` (0-35), `structure` (0-25), `macro` (0-20), `pa` (0-20)
- `assessment`: brief summary (Thai acceptable)
- `timeframe_agreement`: count of timeframes in alignment (integer)
- `key_levels`: list of price level strings
- `invalidation_conditions`: conditions that would negate the setup
- `evidence_reference`: must equal input `evidence_id`
- `provenance.formula_version`: `scoring-p2.4-v1`

## Scoring Rules (scoring-p2.4-v1)

**Trend (max 35):** trend_state=UPTREND +20; price>ema50>ema200 +10; adx>25 +5

**Structure (max 25):** headroom_atr>=2.0 +15; headroom_atr>=1.0 +8; swing alignment +10

**Macro (max 20):** regime=RISK_ON_GOLD_BULLISH and macro_alignment=BULLISH +20; NEUTRAL +10; BEARISH 0

**Price Action (max 20):** rejection matching trend +10; engulfing matching trend +10; body_wick_ratio>=0.6 +5 (capped at 20)

## Decision Tree

- data_quality != VALID: all score_components = 0, assessment = INSUFFICIENT_DATA
- Any feature = INSUFFICIENT_DATA: that component score = 0
- Total >= 80: forward as CONFIRMED candidate to signal_engine
- Total 65-79: forward as CANDIDATE_INTERNAL
- Total <= 45: forward as INVALIDATED
- Otherwise: NO_SETUP

## Failure Modes

- STALE data: all scores 0, assessment = STALE_DATA
- Missing evidence_id: return REJECTED, reason = missing_evidence_reference
- Numeric value from agent/LLM (not Python): return REJECTED, reason = agent_numeric_source_forbidden
- Schema mismatch: return REJECTED, log structured error, do not partially process
- Source unavailable: return SOURCE_UNAVAILABLE; never substitute fabricated values
