# OpenClaw Super Advisor

Advisor-only OpenClaw foundation for validating structured evidence packets and preparing controlled notifications.

## Status

- Current phase: v1.1.0-P1
- Automatic trading: not implemented
- Trading execution: disabled by contract
- MT5 bridge: read-only placeholder
- Telegram publishing: disabled until environment validation passes

## Architecture

MT5 Terminal -> Python Deterministic Engine -> Structured Evidence Packet -> OpenClaw Super Advisor -> Telegram after explicit approval

## Folder Structure

- `state/` OpenClaw state, config, and canonical `.env`
- `workspace/` super-advisor bootstrap files and local skills
- `engine/` Python runtime skeleton and tests
- `scripts/` validation/report helpers
- `docs/` validation and publication artifacts

## Installation Summary

1. Install Node 24 and Python 3.12.
2. Install OpenClaw with the official PowerShell installer.
3. Fill `state/.env` manually from `.env.example` or `state/.env.example`.
4. Validate config and run tests.

## Environment Template

Use `.env.example` as the publication-safe template and `state/.env` as the only runtime env file.

## Test Commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s engine\tests -p 'test_*.py'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.\.venv\Scripts\python.exe scripts\p1_validate.py
```

## Security Boundary

- No broker write APIs
- No shell access for the production agent
- No secrets committed to Git
- No legacy archive used at runtime

## Not Implemented Yet

- market data engine
- indicators
- pattern logic
- voting
- scoring thresholds
- trading alerts
