---
name: secret-exposure-scan
description: Scan agent outputs, logs, and evidence packets for accidental secret exposure.
version: 1.2.15
owner_agent: security-compliance-agent
purpose: Prevent API keys, tokens, passwords, and MT5 credentials from appearing in any output.
allowed_inputs:
  - agent output text
  - evidence packet
  - log entries
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
failure_behavior: return SECRET_EXPOSURE_DETECTED with redacted location reference
audit_fields:
  - scan_id
  - exposure_type
  - location
  - redacted_sample
  - severity
tests:
  - unit
  - integration
promotion_status: stable
---
# secret-exposure-scan

## Procedure
1. Scan text for patterns matching: API key prefixes (bearer-token-pattern, AKIA-prefix, hex-32-plus), passwords, tokens
2. Scan for env var value leakage: check if FRED_API_KEY, OPENAI_API_KEY, TELEGRAM_BOT_TOKEN values appear verbatim
3. Verify evidence packets do not contain raw credentials in any field
4. Return scan result: CLEAN or SECRET_EXPOSURE_DETECTED with severity and location

## Decision Tree
- No pattern matches → CLEAN
- Pattern match in evidence packet body → HIGH severity
- Pattern match in log line → MEDIUM severity (likely DEBUG log, redact)
- Pattern match in Telegram message draft → CRITICAL (block send immediately)

## Quality Gates
- REVEAL_SECRET_VALUES env must be false in production
- Secret scanner runs before any Telegram publish
- Scanner uses pattern matching, not agent reasoning (deterministic)

## Failure Modes
- Short token that collides with legitimate data → false positive → log but do not block
- Secret embedded in base64 encoded field → decode before scanning
