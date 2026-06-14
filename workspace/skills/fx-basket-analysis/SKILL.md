---
name: fx-basket-analysis
description: Interpret computed FX basket (DXY proxy) value for USD strength context in XAUUSD analysis.
version: 1.2.8
owner_agent: intermarket-macro-agent
purpose: Translate basket_value (basis points) into directional USD context for gold evidence.
allowed_inputs:
  - FX basket evidence packet
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
failure_behavior: return USD_CONTEXT_UNAVAILABLE if basket_value is None
audit_fields:
  - evidence_id
  - basket_value_bps
  - usd_direction
  - valid_components
  - formula_version
tests:
  - unit
  - integration
promotion_status: stable
---
# fx-basket-analysis

## Procedure
1. Receive FX basket evidence packet (output of fx_basket.compute_fx_basket)
2. Verify formula_version == "fx-basket-v1-normalized-returns"
3. Verify valid_components >= 3 (minimum for reliable basket)
4. Classify usd_direction from basket_value_bps:
   - basket_value_bps > +10 → USD_STRENGTHENING (bearish gold pressure)
   - basket_value_bps < -10 → USD_WEAKENING (bullish gold pressure)
   - -10 to +10 → USD_NEUTRAL
5. Attach usd_direction to intermarket context evidence

## Decision Tree
- basket_value is None → USD_CONTEXT_UNAVAILABLE (proceed without macro constraint)
- valid_components < 3 → INSUFFICIENT_DATA, log which pairs missing
- basket_value present → classify direction and attach to evidence

## Quality Gates
- basket_value must come from Python fx_basket module with formula_version declared
- Agent cannot compute or adjust basket_value numerics
- Direction reversal for EUR/GBP/AUD/NZD already applied by Python module

## Failure Modes
- 3+ FX pairs unavailable simultaneously → basket degrades to None → USD_CONTEXT_UNAVAILABLE
- Stale pair prices → basket computed on stale data → annotate staleness in provenance
