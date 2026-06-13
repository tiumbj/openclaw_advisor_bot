# P1 Validation Report

## Section 1 — Environment Validation

| Variable | Status | Required Action |
| --- | --- | --- |
| ADVISOR_DATA_DIR | PRESENT | None |
| ADVISOR_DB_PATH | PRESENT | None |
| ADVISOR_ENGINE_API_TOKEN | BLANK | Fill value |
| ADVISOR_ENGINE_BASE_URL | PRESENT | None |
| ADVISOR_ENGINE_HOST | PRESENT | None |
| ADVISOR_ENGINE_PORT | PRESENT | None |
| ADVISOR_LOG_DIR | PRESENT | None |
| ADVISOR_ONLY | PRESENT | None |
| ADVISOR_PRIMARY_SYMBOL | PRESENT | None |
| ADVISOR_RUNTIME_MODE | PRESENT | None |
| ADVISOR_TIMEZONE | PRESENT | None |
| AI_FALLBACK_MODEL_1 | BLANK | Fill value |
| AI_FALLBACK_MODEL_2 | BLANK | Fill value |
| AI_FALLBACK_MODEL_3 | BLANK | Fill value |
| AI_FALLBACK_PROVIDER_1 | BLANK | Fill value |
| AI_FALLBACK_PROVIDER_2 | BLANK | Fill value |
| AI_FALLBACK_PROVIDER_3 | BLANK | Fill value |
| AI_PRIMARY_MODEL | BLANK | Fill value |
| AI_PRIMARY_PROVIDER | BLANK | Fill value |
| ALLOW_ORDER_SEND | PRESENT | None |
| ANTHROPIC_API_KEY | BLANK | Fill value |
| APP_ENV | PRESENT | None |
| DEEPSEEK_API_KEY | BLANK | Fill value |
| DRY_RUN | PRESENT | None |
| EXECUTION_ALLOWED | PRESENT | None |
| GEMINI_API_KEY | BLANK | Fill value |
| GOOGLE_API_KEY | BLANK | Fill value |
| LIVE_TELEGRAM_ALLOWED | PRESENT | None |
| MT5_AUDUSD_SYMBOL | BLANK | Fill value |
| MT5_DXY_SYMBOL | BLANK | Fill value |
| MT5_ENABLED | PRESENT | None |
| MT5_EURUSD_SYMBOL | BLANK | Fill value |
| MT5_LOGIN | BLANK | Fill value |
| MT5_PASSWORD | BLANK | Fill value |
| MT5_SERVER | BLANK | Fill value |
| MT5_TERMINAL_PATH | BLANK | Fill value |
| MT5_US10Y_SYMBOL | BLANK | Fill value |
| MT5_USE_EXISTING_SESSION | PRESENT | None |
| MT5_XAUUSD_SYMBOL | BLANK | Fill value |
| OPENAI_API_KEY | BLANK | Fill value |
| OPENCLAW_CONFIG_PATH | PRESENT | None |
| OPENCLAW_GATEWAY_HOST | PRESENT | None |
| OPENCLAW_GATEWAY_PORT | PRESENT | None |
| OPENCLAW_GATEWAY_TOKEN | BLANK | Fill value |
| OPENCLAW_HOME | PRESENT | None |
| OPENCLAW_HOOKS_ENABLED | PRESENT | None |
| OPENCLAW_HOOKS_PATH | PRESENT | None |
| OPENCLAW_HOOKS_TOKEN | BLANK | Fill value |
| OPENCLAW_LOG_LEVEL | PRESENT | None |
| OPENCLAW_STATE_DIR | PRESENT | None |
| OPENCLAW_WORKSPACE_DIR | PRESENT | None |
| REVEAL_SECRET_VALUES | PRESENT | None |
| SHADOW_MODE | PRESENT | None |
| TELEGRAM_ALLOWED_USER_ID | BLANK | Fill value |
| TELEGRAM_BOT_TOKEN | BLANK | Fill value |
| TELEGRAM_ENABLED | PRESENT | None |
| TELEGRAM_GROUP_CHAT_ID | BLANK | Fill value |
| TELEGRAM_TARGET_CHAT_ID | BLANK | Fill value |
| TELEGRAM_THREAD_ID | BLANK | Fill value |

## Section 2 — OpenClaw Validation

- Version: OpenClaw 2026.6.6 (8c802aa)
- Config status: {"valid":true,"path":"C:\\Data\\OpenClawSuperAdvisor\\state\\openclaw.json"}
- State path: C:\Data\OpenClawSuperAdvisor\state
- Workspace path: C:\Data\OpenClawSuperAdvisor\workspace
- Gateway status: foreground service not installed; runtime probe available in gateway status JSON
- Agent status: [
  {
    "id": "super-advisor",
    "name": "OpenClaw Super Advisor",
    "identityName": "OpenClaw Super Advisor",
    "identitySource": "identity",
    "workspace": "C:\\Data\\OpenClawSuperAdvisor\\workspace",
    "agentDir": "C:\\Data\\OpenClawSuperAdvisor\\state\\agents\\super-advisor\\agent",
    "bindings": 0,
    "isDefault": true
  }
]
- Skill status: see `P1_CLEANROOM_VERIFICATION.json` and `skills info` checks

## Section 3 — Provider Results

| Provider | Model | Authentication | Response | Latency |
| --- | --- | --- | --- | --- |
| BLANK | BLANK | NOT RUN | NOT RUN | NOT RUN |
| BLANK | BLANK | NOT RUN | NOT RUN | NOT RUN |
| BLANK | BLANK | NOT RUN | NOT RUN | NOT RUN |
| BLANK | BLANK | NOT RUN | NOT RUN | NOT RUN |

## Section 4 — MT5 Read-only Result

- Connected: NOT RUN
- Terminal: NOT RUN
- Symbol mapping: NOT RUN
- Timeframes: NOT RUN
- Freshness: NOT RUN
- Forbidden methods status: source boundary only

## Section 5 — Telegram Result

- Authentication: NOT RUN
- Target validation: NOT RUN
- Dry-run/live test: NOT RUN
- Delivery status: NOT RUN
- Duplicate status: NOT RUN

## Section 6 — Security Audit

- Forbidden symbol scan: PASS
- Dependency scan: PASS
- Secret scan: PASS
- `.env` tracking status: PASS
- Git history status: branch `main`, local commits `0`

## Section 7 — Files Created or Changed

| File | Version | Purpose |
| --- | --- | --- |
| README.md | v1.1.0-P1 | Publication-safe project overview |
| .env.example | v1.1.0-P1 | Publication-safe env template pointer |
| docs/ARCHITECTURE.md | v1.1.0-P1 | Architecture summary |
| docs/SECURITY.md | v1.1.0-P1 | Security boundary summary |
| docs/INSTALL_WINDOWS.md | v1.1.0-P1 | Windows install steps |
| docs/ENVIRONMENT_VARIABLES.md | v1.1.0-P1 | Env file guidance |
| docs/TESTING.md | v1.1.0-P1 | Test guidance |
| docs/P1_VALIDATION_REPORT.md | v1.1.0-P1 | P1 validation report |

