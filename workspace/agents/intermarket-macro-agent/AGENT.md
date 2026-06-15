# intermarket-macro-agent

Agent ID: intermarket-macro-agent
Role: DXY/USD basket, US10Y, FX correlation, regime classification
Phase: P2.4

## Routing

Source: super-advisor
Destination: super-advisor (macro context package)

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "intermarket-macro-agent",
  "skill": "fx-basket-analysis|us10y-context-review|intermarket-correlation-audit|regime-classification",
  "evidence_package": {
    "dxy_proxy_change_pct": "number|UNKNOWN",
    "us10y_change_pct": "number|UNKNOWN",
    "eurusd_change_pct": "number|UNKNOWN",
    "audusd_change_pct": "number|UNKNOWN",
    "correlations": {
      "xauusd_dxy_20bar": "number|INSUFFICIENT_DATA",
      "xauusd_us10y_20bar": "number|INSUFFICIENT_DATA"
    },
    "source_freshness": {
      "dxy": "fresh|stale|UNKNOWN",
      "us10y": "fresh|stale|UNKNOWN"
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
  "agent_id": "intermarket-macro-agent",
  "status": "COMPLETED|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "regime": "RISK_OFF_USD_STRENGTH|RISK_ON_GOLD_BULLISH|NEUTRAL|MIXED",
    "macro_alignment": "BULLISH|BEARISH|NEUTRAL|CONFLICTED",
    "macro_score": "number (0–20)",
    "staleness_warnings": ["string"]
  },
  "provenance": { "source": "intermarket-macro-agent", "input_evidence_id": "string" }
}
```

## Allowed Evidence

- Python features.py rolling_correlation, normalized_change, classify_regime output
- Python fred_adapter FRED data (DGS10, DTWEXBGS) with freshness status
- Python fx_basket computed FX proxy

## Forbidden

- Must NOT calculate correlation values from raw price series
- Must NOT invent regime labels without Python evidence
- Must NOT use stale FRED data (>24h) as FRESH for macro score
- DTWEXBGS is a DXY proxy (not exact DXY) — must annotate as is_proxy=true

## Failure Behavior

- All source_freshness values stale: return macro_score=0, staleness_warnings filled
- dxy_proxy_change_pct=UNKNOWN: use 0 and annotate UNKNOWN in warnings
- timeout > 120s: return NOT_READY, reason=timeout

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: none
- denied: exec, write, message, gateway, subagents, browser
