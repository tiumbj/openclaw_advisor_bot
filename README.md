# OpenClaw Super Advisor

Advisor-only OpenClaw foundation package for validating environment, skills, config templates,
security boundaries, and MT5 read-only market-data runtime without enabling trade execution.

## Status

- Package version: `1.2.6`
- Phase: `P2.4`
- Trading execution: disabled by contract
- CLI surface: validation, audit, and MT5 read-only market-data commands
- Runtime config source: `config\openclaw.template.json`
- Runtime state: local only under `state\`

## Safety Contract

- No order placement, modification, cancellation, or position close logic.
- No broker execution bridge, execution kernel, or auto trade flow.
- No order placement, broker-write execution, indicators, pattern engine, voting, or Telegram
  trading alerts.
- MT5 support is restricted to explicit read-only adapter and market-data collection surfaces.

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
.\.venv\Scripts\openclaw-advisor.exe provider-policy --strict
.\.venv\Scripts\openclaw-advisor.exe render-config --validate --strict
```

## Test Layout

- `engine\tests\unit`
- `engine\tests\integration`
- `engine\tests\security`
- `engine\tests\live`

Live tests use `@pytest.mark.live` and are excluded by default.
