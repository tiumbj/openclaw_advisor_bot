# Project Status

- Project: `openclaw_advisor_bot`
- Current package version: `1.2.4`
- Current phase: `P2.4`
- Current work package: `WP-P2_4-BLUEPRINT`
- Phase status: `BLOCKED`
- Last update UTC: `2026-06-14T02:40:00Z`
- Implementation commit: `89daf1379333ddba61a813cf700d37ff3fa4426b`
- Status report commit: `9595ed445ce3fef66024ea70c473571d034d5f9d`
- Observed remote HEAD: `1a2850e9f1eb924a94d68649a2aba029ab77b935`
- Working tree status: `DIRTY`
- CI status: `NOT RUN`
- Security status: `PASS_WITH_WARNINGS`
- Groq removal status: `REMOVED_FROM_TRACED_CODE_AND_ACTIVE_RUNTIME_SNAPSHOT; legacy shell env reference still visible`
- Supported providers: `OpenAI, Claude, Gemini, DeepSeek`
- Selected provider: `openai`
- Provider static validation: `PASS`
- Real provider test: `BLOCKED`
- Credit blocker: `GATEWAY_SCOPE_UPGRADE_PENDING_APPROVAL_AND_MODEL_REGISTRY_MISMATCH`
- Gateway status: `BLOCKED (probe ok; agent turn requires scope upgrade approval)`
- Agent status: `BLOCKED (default model is not registered for the allowed gateway turn)`
- Blueprint status: `P2_4 blueprint and compliance matrix drafted from verified repo/runtime state`
- Next action: `Normalize the remaining P2.4 audit artifacts, then decide whether the gateway auth mismatch can be resolved safely`

## Recovery Matrix

| Work Item | Current Status | Evidence | Remaining Work |
| --------- | -------------- | -------- | -------------- |
| Groq removal from tracked code and policy | PASS | `engine/src/openclaw_super_advisor/providers.py`, `.env.example`, `engine/src/openclaw_super_advisor/env.py`, `engine/src/openclaw_super_advisor/cli.py` | Keep Groq out of active config and runtime snapshots |
| Four-provider allowlist foundation | PASS | `engine/src/openclaw_super_advisor/providers.py`, `.env.example`, `engine/tests/unit/test_providers.py` | Keep the allowlist as the only supported provider set |
| Static provider validation | PASS | `engine/tests/unit/test_providers.py`, `engine/tests/integration/test_cli.py`, `docs/P2_2_PROVIDER_STATIC_VALIDATION.json` | Re-run after any provider-policy change |
| Offline OpenClaw audit | BLOCKED | `docs/P2_2_OPENCLAW_OFFLINE_RUNTIME_AUDIT.json`, `openclaw status --json` | Resolve the gateway auth mismatch and rerun a controlled live provider smoke test |
| P2.4 blueprint draft | IN_PROGRESS | `docs/P2_4_PREPRODUCTION_BLUEPRINT.md`, `docs/P2_4_BLUEPRINT_COMPLIANCE_MATRIX.md` | Fill the remaining wiring, learning, backup, and self-improvement gaps |
| P2.4 readiness summaries | IN_PROGRESS | `docs/P2_4_PREPRODUCTION_READINESS_REPORT.md`, `docs/P2_4_PIPELINE_WIRING_AUDIT.md`, `docs/P2_4_TELEGRAM_MESSAGE_AUDIT.md` | Capture the current gap state without claiming runtime readiness |

## Current Evidence

- `python -m pip check` -> `PASS`
- `python -m mypy engine\src` -> `PASS`
- `python -m pytest -m "not live" --no-cov --basetemp C:\Data\OpenClawSuperAdvisor\_tmp\pytest` -> `PASS` (`63 passed, 1 deselected`)
- `python -m pytest -m "not live" --cov=openclaw_super_advisor --cov-report=term-missing --cov-report=json --basetemp C:\Data\OpenClawSuperAdvisor\_tmp\pytest` -> `PASS` (`63 passed, 1 deselected`, total coverage `95.73%`)
- `openclaw-advisor validate-skills --strict --project-root . --env-file .env.example --json` -> `PASS`
- `openclaw-advisor render-config --validate --strict --project-root . --env-file .env.example --json` -> `PASS`
- `openclaw-advisor provider-policy --strict --project-root . --env-file .env.example --json` -> `BLOCKED` with `NO_ENABLED_PROVIDER`
- `openclaw-advisor security-scan --include-history --strict --project-root . --json` -> `PASS`
- `python -m pip_audit` -> `TIMEOUT` after 10 minutes
- `engine/tests/unit/test_report_artifacts.py` -> `PASS`
- `openclaw gateway status` -> `PASS` for connectivity probe, `read-only` capability, and local loopback auth with the current runtime token
- `openclaw gateway probe` -> `PASS`
- `openclaw agent --agent super-advisor --message "Return exactly: OPENCLAW_PROVIDER_OK" --timeout 120 --thinking off --json` -> `BLOCKED` by scope upgrade approval and missing `openai/gpt-5.3-chat-latest` model registration
- `openclaw status --json` -> gateway listening on `127.0.0.1:18789`, auth mismatch reported in the ambient shell, super-advisor enabled
- `openclaw models status --json` -> default model resolves to `openai/gpt-5.3-chat-latest`; shell env still exposes historical provider credentials outside the repo

## Notes

- `git grep -n -i groq -- .` returned no matches in the tracked tree.
- The ignored runtime snapshot still contains historical Groq artifacts under `state\agents\...`; they are outside git but should be cleaned from the active runtime snapshot.
- The live provider gate now has a concrete blocker: the agent turn requires a scope upgrade approval and the default openai model is not registered in the model provider catalog.
- Report artifact integrity tests now enforce LF line endings, append-only ledger ordering, and secret-free reports.
