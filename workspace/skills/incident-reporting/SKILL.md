---
name: incident-reporting
description: Report operational failures without turning them into trading signals.
---

# incident-reporting

Version: v1.0.0-P0

Purpose: report operational failures without drifting into trade advice.

Supported incidents:
- missing environment
- provider failure
- MT5 disconnection
- stale market data
- schema rejection
- Telegram failure

Forbidden:
- sending trading signals
- inventing recovery status
- hiding validation failures
