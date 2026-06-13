---
name: thai-telegram-publisher
description: Format approved structured payloads into concise Thai without adding numbers or sending automatically.
---

# thai-telegram-publisher

Version: v1.0.0-P0

Purpose: convert an approved structured payload into concise Thai text.

Rules:
- Preserve every supplied number exactly.
- Preserve direction, timestamp, and invalidation exactly.
- Never add a price, score, or probability.
- Never send an unapproved payload.
- Delivery stays disabled until environment validation passes.
