---
name: evidence-audit
description: Audit structured evidence integrity without recalculating or altering scores.
version: 1.1.1
---

# evidence-audit

Version: 1.1.1

Purpose: audit evidence quality without recalculating it.

Checks:
- freshness
- completeness
- contradictions
- unknown fields
- evidence identifiers
- schema integrity

Forbidden:
- generating a new score
- changing an existing score
- repairing numbers by guesswork
