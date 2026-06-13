---
name: incident-reporting
description: Report operational failures without turning them into trading signals.
version: 1.2.1
---

# incident-reporting

Version: 1.2.1

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
