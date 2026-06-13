# OpenClaw Super Advisor

Advisor-only OpenClaw foundation hardening package for validating environment, skills, config templates, and security boundaries without enabling any trading runtime.

## Status

- Package version: `1.1.1`
- Phase: `P1.1`
- Trading execution: disabled by contract
- CLI surface: validation and audit only
- Runtime config source: `config\openclaw.template.json`
- Runtime state: local only under `state\`

## Safety Contract

- No order placement, modification, cancellation, or position close logic.
- No broker execution bridge, execution kernel, or auto trade flow.
- No MT5 live connector, market data engine, indicators, pattern engine, voting, or Telegram trading alerts.
- Skills and CLI commands are validation-only and read-only by design.

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy engine\src
.\.venv\Scripts\python.exe -m pytest -m "not live"
.\.venv\Scripts\openclaw-advisor.exe health
.\.venv\Scripts\openclaw-advisor.exe validate-env
.\.venv\Scripts\openclaw-advisor.exe validate-skills --strict
.\.venv\Scripts\openclaw-advisor.exe security-scan --strict
.\.venv\Scripts\openclaw-advisor.exe render-config --validate --strict
```

## Test Layout

- `engine\tests\unit`
- `engine\tests\integration`
- `engine\tests\security`
- `engine\tests\live`

Live tests use `@pytest.mark.live` and are excluded by default.
