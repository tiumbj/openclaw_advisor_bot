# Architecture

OpenClaw Super Advisor is an advisor-only stack.

1. MT5 terminal provides read-only market and account observations.
2. Python engine validates configuration and shapes future structured evidence packets.
3. OpenClaw `super-advisor` reviews only structured, read-only evidence.
4. Telegram publishing remains gated and disabled until environment validation passes.
