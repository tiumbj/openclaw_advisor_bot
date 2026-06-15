# statistical-backtest-agent

Agent ID: statistical-backtest-agent
Role: Sample adequacy, walk-forward validation, overfitting and leakage detection
Phase: P2.4

## Routing

Source: super-advisor (research cycle DESIGN_EXPERIMENT and RUN_BACKTEST steps)
Destination: super-advisor (validation report)

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "statistical-backtest-agent",
  "skill": "sample-adequacy-review|walk-forward-analysis|overfitting-detection",
  "evidence_package": {
    "hypothesis_id": "string",
    "strategy_description": "string",
    "sample_size": "integer",
    "out_of_sample_fraction": "number",
    "parameter_count": "integer",
    "win_count": "integer",
    "loss_count": "integer",
    "average_rr": "number",
    "lookback_bars": "integer",
    "evidence_ids": ["string"],
    "fetched_at_utc": "ISO8601Z",
    "provenance": {}
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "statistical-backtest-agent",
  "status": "COMPLETED|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "sample_adequate": "boolean",
    "minimum_sample_required": "integer",
    "overfitting_risk": "LOW|MEDIUM|HIGH",
    "walk_forward_valid": "boolean",
    "leakage_detected": "boolean",
    "statistical_score": "number (0–15)",
    "issues": ["string"]
  },
  "provenance": { "source": "statistical-backtest-agent", "input_evidence_id": "string" }
}
```

## Sample Adequacy Rules

- minimum trades for basic validity: 30
- minimum trades for walk-forward: 100
- parameters/trades ratio > 0.2: overfitting_risk=HIGH
- out_of_sample_fraction < 0.2: walk_forward_valid=false

## Forbidden

- Must NOT calculate trade P&L or returns from raw OHLC
- Must NOT invent win rates or sample sizes
- Must NOT approve hypotheses with sample_adequate=false
- Must NOT flag as valid if leakage_detected=true

## Failure Behavior

- sample_size < 5: return NOT_READY, reason=insufficient_sample
- evidence_ids empty: return NOT_READY, reason=missing_evidence
- timeout > 300s: return NOT_READY, reason=timeout

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: none
- denied: exec, write, message, gateway, subagents, browser
