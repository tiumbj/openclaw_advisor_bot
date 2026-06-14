---
name: environment-health
description: Audit environment readiness using present or missing style results without revealing values.
version: 1.2.5
---

# environment-health

Version: 1.2.5

Purpose: inspect bootstrap environment readiness without exposing secrets.

Output contract:
- Report each required variable as `present`, `missing`, or `invalid format`.
- Never print any variable value.
- Treat disabled bridge and disabled Telegram delivery as expected until validation passes.
