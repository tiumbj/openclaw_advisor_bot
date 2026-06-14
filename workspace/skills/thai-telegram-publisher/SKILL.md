---
name: thai-telegram-publisher
description: Format approved structured payloads into concise Thai without adding numbers or sending automatically.
version: 1.2.5
---

# thai-telegram-publisher

Version: 1.2.5

Purpose: convert an approved structured payload into concise Thai text.

Rules:
- Preserve every supplied number exactly.
- Preserve direction, timestamp, and invalidation exactly.
- Never add a price, score, or probability.
- Never send an unapproved payload.
- Delivery stays disabled until environment validation passes.
