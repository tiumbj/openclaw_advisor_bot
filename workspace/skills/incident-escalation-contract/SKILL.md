---
name: incident-escalation-contract
description: Define escalation path for system incidents from watchdog through Telegram to human review.
version: 1.2.9
owner_agent: reliability-watchdog-agent
purpose: Ensure all incidents reach the right handler at the right severity within defined SLAs.
allowed_inputs:
  - incident payload
  - watchdog report
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
failure_behavior: return ESCALATION_FAILED if Telegram delivery fails after retry
audit_fields:
  - incident_id
  - severity
  - escalation_tier
  - telegram_sent
  - human_notified
tests:
  - unit
  - integration
promotion_status: stable
---
# incident-escalation-contract

## Procedure
1. Receive incident payload with severity: CRITICAL, WARNING, INFO
2. Determine escalation_tier based on severity and event_type:
   - CRITICAL + SYSTEM_OFFLINE_DETECTED → Tier 1: immediate Telegram + PID file check
   - CRITICAL + GATEWAY_FAILED → Tier 1: immediate Telegram
   - WARNING + any → Tier 2: Telegram within 60s, auto-recovery attempt first
   - INFO → Tier 3: log only, no Telegram
3. Send Telegram via TelegramPublisher.format_system_event (Thai format, severity icon)
4. Apply deduplication: is_duplicate() check before send
5. Return escalation record: escalation_tier, telegram_sent, human_notified

## Decision Tree
- CRITICAL → always escalate immediately
- WARNING after 3 consecutive → escalate to Tier 1
- HUMAN_INTERVENTION_REQUIRED → always Tier 1 + log to evidence archive

## Quality Gates
- Deduplication window prevents flooding (is_duplicate check)
- Telegram message format validated against Thai template before send
- No secret values in Telegram message body

## Failure Modes
- Telegram bot blocked or token invalid → ESCALATION_FAILED → log to local incident file
- Dedup false positive (same incident suppressed twice) → clear_dedup_window every 15 min
