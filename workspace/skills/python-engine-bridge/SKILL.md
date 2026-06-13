---
name: python-engine-bridge
description: Define the future read-only contract between Python evidence packets and OpenClaw.
version: 1.1.1
---

# python-engine-bridge

Version: 1.1.1

Purpose: define the future read-only bridge between Python and OpenClaw.

Required payload fields:
- `schema_version`
- `event_id`
- `timestamp_utc`
- `advisor_only`
- `execution_allowed`
- `evidence`

Reject when:
- Market numbers are supplied free-form instead of inside the structured payload.
- `event_id`, `timestamp_utc`, or `schema_version` is missing.
- `advisor_only` is not `true`.
- `execution_allowed` is not `false`.
- The payload is stale, malformed, or fails schema checks.
