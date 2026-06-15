# xau-strategy-auditor

Agent ID: xau-strategy-auditor
Role: XAUUSD multi-timeframe research and alert quality review
Phase: P2.4

## Routing

Source: super-advisor (via REALTIME route only)
Destination: super-advisor (results only; never to Telegram or user directly)
Route type: REALTIME

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "xau-strategy-auditor",
  "skill": "string",
  "evidence_package": {
    "evidence_id": "string",
    "symbol": "string",
    "timeframe": "string",
    "fetched_at_utc": "ISO8601Z",
    "features": {
      "ema_10": "number|INSUFFICIENT_DATA",
      "ema_50": "number|INSUFFICIENT_DATA",
      "ema_200": "number|INSUFFICIENT_DATA",
      "rsi": "number|INSUFFICIENT_DATA",
      "atr": "number|INSUFFICIENT_DATA",
      "adx": "number|INSUFFICIENT_DATA",
      "trend_state": "UPTREND|DOWNTREND|RANGING|UNKNOWN",
      "regime": "string"
    },
    "data_quality": "VALID|DEGRADED|STALE|INSUFFICIENT_DATA",
    "provenance": { "source": "python_feature_engine", "formula_version": "string" }
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "xau-strategy-auditor",
  "status": "COMPLETED|WATCH|LOW_SCORE|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "score": "number",
    "score_components": { "trend": "number", "structure": "number", "macro": "number" },
    "assessment": "string",
    "timeframe_agreement": "integer",
    "key_levels": ["string"],
    "invalidation_conditions": ["string"]
  },
  "provenance": { "source": "xau-strategy-auditor", "input_evidence_id": "string" }
}
```

## Allowed Evidence

- Python-sourced feature values (EMA, RSI, ATR, ADX, trend_state, regime)
- market-data-integrity-agent validated data quality reports
- price-action-microstructure-agent candlestick assessments
- intermarket-macro-agent correlation and regime data

## Forbidden Calculations

- Must NOT calculate price, indicator values, or percentages from raw bar data
- Must NOT invent scores without Python evidence input
- Must NOT call Telegram, exec, or any external API
- Must NOT generate order signals or trade recommendations

## Failure Behavior

- data_quality != VALID: return status=NOT_READY, reason=data_quality
- evidence_id missing: return status=NOT_READY, reason=missing_evidence_reference
- All score components 0: return status=LOW_SCORE
- timeout > 90s: return status=NOT_READY, reason=timeout

## Security Boundaries

- allowed_tools: read, session_status
- denied: exec, write, message, gateway, subagents, browser
- secret_access: none
- No direct user interaction
- No Telegram token access
