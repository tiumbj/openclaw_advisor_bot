---
name: evidence-audit
description: Audit structured evidence integrity without recalculating or altering scores.
---

# evidence-audit

Version: v1.0.0-P0

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
