# Project Status

- Project: `openclaw_advisor_bot`
- Current package version: `1.2.1`
- Current phase: `P2.2`
- Current work package: `WP-CODEX-01/02/03`
- Phase status: `BLOCKED`
- Last update UTC: `2026-06-14T01:43:09Z`
- Implementation commit: `PENDING`
- Status report commit: `PENDING`
- Observed remote HEAD: `65a5cae2088129e549a0f782bec4dcaabc57c35a`
- Working tree status: `DIRTY`
- CI status: `NOT RUN`
- Security status: `PASS_WITH_WARNINGS`
- Groq removal status: `REMOVED_FROM_TRACED_CODE_AND_ACTIVE_RUNTIME_SNAPSHOT; legacy shell env reference still visible`
- Supported providers: `OpenAI, Claude, Gemini, DeepSeek`
- Selected provider: `none`
- Provider static validation: `PASS`
- Real provider test: `BLOCKED`
- Credit blocker: `NO_AVAILABLE_AI_CREDIT`
- Gateway status: `BLOCKED (ECONNREFUSED 127.0.0.1:18789)`
- Agent status: `PASS (super-advisor enabled; runtime offline)`
- Next action: `Add valid credit to one allowed provider and run one controlled smoke test`

## Recovery Matrix

| Work Item | Current Status | Evidence | Remaining Work |
| --------- | -------------- | -------- | -------------- |
| Groq removal from tracked code and policy | PASS | `engine/src/openclaw_super_advisor/providers.py`, `.env.example`, `engine/src/openclaw_super_advisor/env.py`, `engine/src/openclaw_super_advisor/cli.py` | Commit and push the tracked changes |
| Four-provider allowlist foundation | PASS | `engine/src/openclaw_super_advisor/providers.py`, `.env.example`, `engine/tests/unit/test_providers.py` | Keep the allowlist as the only supported provider set |
| Static provider validation | PASS | `engine/tests/unit/test_providers.py`, `engine/tests/integration/test_cli.py`, `docs/P2_2_PROVIDER_STATIC_VALIDATION.json` | Re-run after any provider-policy change |
| Offline OpenClaw audit | BLOCKED | `docs/P2_2_OPENCLAW_OFFLINE_RUNTIME_AUDIT.json` | Add valid credit and retry a controlled live provider smoke test |

## Current Evidence

- `python -m pip check` -> `PASS`
- `python -m mypy engine\src` -> `PASS`
- `python -m pytest -m "not live" --no-cov --basetemp C:\Data\OpenClawSuperAdvisor\_tmp\pytest` -> `PASS` (`52 passed, 1 deselected`)
- `python -m pytest -m "not live" --cov=openclaw_super_advisor --cov-report=term-missing --cov-report=json --basetemp C:\Data\OpenClawSuperAdvisor\_tmp\pytest` -> `PASS` (`52 passed, 1 deselected`, total coverage `93.84%`)
- `openclaw-advisor validate-skills --strict --project-root . --env-file .env.example --json` -> `PASS`
- `openclaw-advisor render-config --validate --strict --project-root . --env-file .env.example --json` -> `PASS`
- `openclaw-advisor provider-policy --strict --project-root . --env-file .env.example --json` -> `BLOCKED` with `NO_ENABLED_PROVIDER`
- `openclaw-advisor security-scan --include-history --strict --project-root . --json` -> `PASS`
- `python -m pip_audit` -> `TIMEOUT` after 10 minutes
- `openclaw status --json` -> gateway unreachable, super-advisor enabled, default agent present
- `openclaw models status --json` -> default model now resolves to `openai/gpt-5.3-chat-latest`; legacy shell env still exposes historical provider credentials

## Notes

- `git grep -n -i groq -- .` returned no matches in the tracked tree.
- The ignored runtime snapshot was updated to remove the Groq provider block and point the default model at an allowed provider namespace.
- The live provider gate remains blocked because no paid AI credit is available for a controlled smoke test.
