# P2.4 Telegram Message Audit

## Current State

- Telegram enable flag exists in environment validation
- Telegram token and target chat IDs are modeled in config
- The `thai-telegram-publisher` skill exists
- No isolated `telegram-publisher` runtime agent exists yet
- No live Telegram delivery was attempted in this turn

## Compliance Gaps

- No snapshot/golden test for the final Thai message format yet
- No live delivery receipt evidence exists
- No deduplication or cooldown state exists yet
- No dead-letter record exists yet
- No live channel binding has been validated

## Required Message Rules

- Thai-first
- Concise
- No fabricated prices or probabilities
- No raw JSON
- Missing values remain `UNKNOWN`
- No automatic sending without approval
