# Test Evidence

- Baseline commit: `d44da0983b38408575ceedfccb00b909862ff9f0`
- Generated UTC: `2026-06-15T00:57:20.800653Z`
- Evidence hash SHA256: `04b83c4d072f27539a66b438c6984c6d881eefaf99d26a92742b14ce2fbc257d`

- `python -m pip check`: `PASS`
- `python -m ruff check .`: `PASS`
- `python -m mypy engine\src`: `PASS`
- `python -m pytest -m "not live" -q --basetemp .\_tmp\audit-pytest`: `FAIL_THEN_PASS_AFTER_PARENT_TEMP_CREATED`
- `python -m build`: `PASS_WITH_SETuptools_LICENSE_DEPRECATION`
- `python -m pip_audit`: `PASS`
- `openclaw-advisor security-scan --include-history --strict`: `PASS`
- `.\scripts\Start-OpenClawUI.ps1`: `PASS`
- `.\scripts\Test-OpenClawUI.ps1`: `PASS`
- `openclaw doctor`: `WARNINGS_PRESENT`
