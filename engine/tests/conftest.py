from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from openclaw_super_advisor._version import __version__
from openclaw_super_advisor.constants import SKILL_NAMES


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _env_text(root: Path) -> str:
    state = root / "state"
    return f"""
    OPENCLAW_HOME={root}
    OPENCLAW_STATE_DIR={state}
    OPENCLAW_CONFIG_PATH={state / "openclaw.json"}
    OPENCLAW_WORKSPACE_DIR={root / "workspace"}
    OPENCLAW_LOG_LEVEL=info
    OPENCLAW_GATEWAY_TOKEN=
    OPENCLAW_HOOKS_TOKEN=
    ADVISOR_ENGINE_API_TOKEN=
    AI_PROVIDER=
    OPENAI_ENABLED=false
    CLAUDE_ENABLED=false
    GEMINI_ENABLED=false
    DEEPSEEK_ENABLED=false
    AI_PROVIDER_FALLBACK_ENABLED=false
    AI_PROVIDER_FALLBACK_ORDER=openai,claude,gemini,deepseek
    ALLOW_PAID_PROVIDER_SMOKE_TEST=false
    OPENAI_MODEL=
    CLAUDE_MODEL=
    GEMINI_MODEL=
    DEEPSEEK_MODEL=
    OPENAI_TIMEOUT_SECONDS=
    CLAUDE_TIMEOUT_SECONDS=
    GEMINI_TIMEOUT_SECONDS=
    DEEPSEEK_TIMEOUT_SECONDS=
    OPENAI_API_KEY=
    ANTHROPIC_API_KEY=
    GEMINI_API_KEY=
    GOOGLE_API_KEY=
    DEEPSEEK_API_KEY=
    TELEGRAM_ENABLED=false
    TELEGRAM_BOT_TOKEN=
    TELEGRAM_ALLOWED_USER_ID=
    TELEGRAM_TARGET_CHAT_ID=
    TELEGRAM_GROUP_CHAT_ID=
    TELEGRAM_THREAD_ID=
    MT5_ENABLED=false
    MT5_TERMINAL_PATH=
    MT5_USE_EXISTING_SESSION=true
    MT5_LOGIN=
    MT5_PASSWORD=
    MT5_SERVER=
    MT5_XAUUSD_SYMBOL=
    MT5_DXY_SYMBOL=
    MT5_EURUSD_SYMBOL=
    MT5_AUDUSD_SYMBOL=
    MT5_US10Y_SYMBOL=
    ADVISOR_ONLY=true
    EXECUTION_ALLOWED=false
    ALLOW_ORDER_SEND=false
    ADVISOR_ENGINE_HOST=127.0.0.1
    ADVISOR_ENGINE_PORT=8765
    ADVISOR_ENGINE_BASE_URL=http://127.0.0.1:8765
    ADVISOR_TIMEZONE=Asia/Bangkok
    ADVISOR_PRIMARY_SYMBOL=XAUUSD
    ADVISOR_RUNTIME_MODE=bootstrap
    OPENCLAW_HOOKS_ENABLED=false
    OPENCLAW_HOOKS_PATH=/hooks
    OPENCLAW_GATEWAY_HOST=127.0.0.1
    OPENCLAW_GATEWAY_PORT=18789
    ADVISOR_DATA_DIR={root / "data"}
    ADVISOR_LOG_DIR={root / "logs"}
    ADVISOR_DB_PATH={root / "data" / "advisor.db"}
    APP_ENV=development
    DRY_RUN=true
    SHADOW_MODE=true
    LIVE_TELEGRAM_ALLOWED=false
    REVEAL_SECRET_VALUES=false
    """


def _template_text() -> str:
    return """
    {
      "env": {
        "shellEnv": {
          "enabled": false
        }
      },
      "gateway": {
        "mode": "local",
        "bind": "loopback",
        "port": {{OPENCLAW_GATEWAY_PORT}},
        "auth": {
          "mode": "token",
          "token": {
            "source": "env",
            "provider": "default",
            "id": "OPENCLAW_GATEWAY_TOKEN"
          }
        },
        "controlUi": {
          "enabled": true
        }
      },
      "hooks": {
        "enabled": false,
        "path": "{{OPENCLAW_HOOKS_PATH}}",
        "allowedAgentIds": [
          "super-advisor"
        ]
      },
      "skills": [
        "advisor-safety-contract",
        "environment-health",
        "python-engine-bridge",
        "evidence-audit",
        "super-potential-review",
        "thai-telegram-publisher",
        "incident-reporting"
      ],
      "agents": {
        "defaults": {
          "workspace": "{{OPENCLAW_WORKSPACE_DIR}}",
          "skills": [
            "advisor-safety-contract",
            "environment-health",
            "python-engine-bridge",
            "evidence-audit",
            "super-potential-review",
            "thai-telegram-publisher",
            "incident-reporting"
          ]
        },
        "list": [
          {
            "id": "super-advisor",
            "workspace": "{{OPENCLAW_WORKSPACE_DIR}}",
            "skills": [
              "advisor-safety-contract",
              "environment-health",
              "python-engine-bridge",
              "evidence-audit",
              "super-potential-review",
              "thai-telegram-publisher",
              "incident-reporting"
            ],
            "tools": {
              "allow": [
                "read",
                "session_status"
              ],
              "deny": [
                "group:runtime",
                "group:web",
                "group:ui",
                "group:automation",
                "group:messaging",
                "group:plugins",
                "group:memory",
                "group:sessions",
                "write",
                "edit",
                "apply_patch",
                "exec",
                "process",
                "code_execution",
                "browser",
                "canvas",
                "gateway",
                "message",
                "subagents"
              ],
              "exec": {
                "mode": "deny"
              },
              "message": {
                "allowCrossContextSend": false,
                "actions": {
                  "allow": []
                }
              },
              "agentToAgent": {
                "enabled": false
              },
              "elevated": {
                "enabled": false
              },
              "sandbox": {
                "tools": {
                  "allow": [
                    "read",
                    "session_status"
                  ]
                }
              }
            }
          }
        ]
      },
      "marketData": {
        "backend": {
          "kind": "mt5",
          "mode": "readonly"
        },
        "symbols": [
          {
            "canonical": "XAUUSD",
            "aliases": ["XAUUSD", "GOLD", "XAUUSD."]
          },
          {
            "canonical": "DXY",
            "aliases": ["DXY", "USDX"]
          }
        ],
        "timeframes": ["M1", "M5", "M15", "H1", "H4", "D1"],
        "storage": {
          "baseDir": "{{ADVISOR_DATA_DIR}}",
          "sqlitePath": "market-data\\\\market-data.db",
          "parquetDir": "market-data\\\\parquet"
        },
        "collection": {
          "pollSeconds": 30,
          "tickLookbackSeconds": 120,
          "barLookbackCount": 500,
          "freshnessThresholdSeconds": 180,
          "retryMaxAttempts": 3,
          "retryBackoffSeconds": 2
        }
      },
      "tools": {
        "allow": [
          "read",
          "session_status"
        ],
        "deny": [
          "group:runtime",
          "group:web",
          "group:ui",
          "group:automation",
          "group:messaging",
          "group:plugins",
          "group:memory",
          "group:sessions",
          "write",
          "edit",
          "apply_patch",
          "exec",
          "process",
          "code_execution",
          "browser",
          "canvas",
          "gateway",
          "message",
          "subagents"
        ],
        "exec": {
          "mode": "deny"
        },
        "message": {
          "allowCrossContextSend": false,
          "actions": {
            "allow": []
          }
        },
        "agentToAgent": {
          "enabled": false
        },
        "elevated": {
          "enabled": false
        },
        "sandbox": {
          "tools": {
            "allow": [
              "read",
              "session_status"
            ]
          }
        }
      }
    }
    """


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "workspace" / "skills").mkdir(parents=True)
    (root / "engine" / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "data").mkdir()
    (root / "logs").mkdir()
    _write(root / ".env.example", _env_text(root))
    _write(root / "state" / ".env", _env_text(root))
    _write(root / "config" / "openclaw.template.json", _template_text())
    _write(root / "config" / "settings.schema.json", '{"type":"object"}')
    for name in SKILL_NAMES:
        _write(
            root / "workspace" / "skills" / name / "SKILL.md",
            f"""
            ---
            name: {name}
            description: Safe validation-only skill.
            version: {__version__}
            ---

            # {name}

            Version: {__version__}

            Never execute trades, never alter evidence scores, and never reveal secrets.
            """,
        )
    return root
