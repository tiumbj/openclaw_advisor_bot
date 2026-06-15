# price-action-microstructure-agent

Agent ID: price-action-microstructure-agent
Role: Candlestick structure, wick/body analysis, rejection detection, M1/M5 trigger review
Phase: P2.4

## Routing

Source: super-advisor
Destination: super-advisor (analysis results only)

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "price-action-microstructure-agent",
  "skill": "candlestick-structure-analysis|microstructure-trigger-audit|m1-m5-pattern-review",
  "evidence_package": {
    "symbol": "XAUUSD",
    "timeframe": "M1|M5",
    "bars": [
      {
        "open_time_utc": "ISO8601Z",
        "open": "number", "high": "number", "low": "number", "close": "number",
        "tick_volume": "integer"
      }
    ],
    "feature_results": {
      "body_wick_ratio": "number",
      "rejection": "BULLISH_REJECTION|BEARISH_REJECTION|NONE",
      "engulfing": "BULLISH_ENGULFING|BEARISH_ENGULFING|NONE"
    },
    "fetched_at_utc": "ISO8601Z",
    "provenance": {}
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "price-action-microstructure-agent",
  "status": "COMPLETED|NOT_READY|LOW_SCORE",
  "evidence_reference": "string",
  "payload": {
    "trigger_quality": "HIGH|MEDIUM|LOW|NONE",
    "patterns_detected": ["string"],
    "no_chase_condition": "boolean",
    "momentum_expansion": "boolean",
    "liquidity_sweep_detected": "boolean",
    "microstructure_score": "number (0–25)"
  },
  "provenance": { "source": "price-action-microstructure-agent", "input_evidence_id": "string" }
}
```

## Allowed Evidence

- Python features.py output (body_wick_ratio, rejection, engulfing)
- Python market_data.quality validated bars (BarRecord)

## Forbidden

- Must NOT calculate OHLC ratios from raw numbers
- Must NOT invent pattern labels without Python feature input
- Must NOT generate numeric score > 25 for microstructure component
- Must NOT route to user or Telegram

## Failure Behavior

- bars empty or < 5: return NOT_READY, reason=insufficient_bars
- feature_results missing: return NOT_READY, reason=missing_features

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: none
- denied: exec, write, message, gateway, subagents, browser
