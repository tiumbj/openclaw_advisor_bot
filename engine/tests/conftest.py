from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest


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
    OPENCLAW_TELEGRAM_OPERATOR_ENABLED=false
    OPENCLAW_TELEGRAM_OPERATOR_BOT_TOKEN=
    OPENCLAW_TELEGRAM_OPERATOR_OWNER_USER_ID=
    OPENCLAW_TELEGRAM_OPERATOR_ALLOWED_CHAT_IDS=
    OPENCLAW_TELEGRAM_OPERATOR_MODE=polling
    OPENCLAW_TELEGRAM_OPERATOR_WEBHOOK_ENABLED=false
    OPENCLAW_TELEGRAM_MARKET_ENABLED=false
    OPENCLAW_TELEGRAM_MARKET_BOT_TOKEN=
    OPENCLAW_TELEGRAM_MARKET_TARGET_CHAT_ID=
    OPENCLAW_TELEGRAM_MARKET_TARGET_THREAD_ID=
    OPENCLAW_TELEGRAM_MARKET_INBOUND_ENABLED=false
    MT5_ENABLED=false
    MT5_TERMINAL_PATH=
    MT5_USE_EXISTING_SESSION=true
    MT5_LOGIN=
    MT5_PASSWORD=
    MT5_SERVER=
    MT5_XAUUSD_SYMBOL=
    MT5_EURUSD_SYMBOL=
    MT5_GBPUSD_SYMBOL=
    MT5_AUDUSD_SYMBOL=
    MT5_NZDUSD_SYMBOL=
    MT5_USDJPY_SYMBOL=
    MT5_USDCHF_SYMBOL=
    MT5_USDCAD_SYMBOL=
    MT5_DXY_SYMBOL=
    MT5_US10Y_SYMBOL=
    FRED_ENABLED=false
    FRED_API_KEY=
    FRED_BASE_URL=https://api.stlouisfed.org/fred
    FRED_TIMEOUT_SECONDS=15
    FRED_MAX_RETRIES=3
    FRED_CACHE_TTL_SECONDS=3600
    FRED_US10Y_SERIES_ID=DGS10
    FRED_USD_BROAD_SERIES_ID=DTWEXBGS
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


def _copy_repo_file(repo_root: Path, relative_path: str, destination: Path) -> None:
    source = repo_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "workspace").mkdir()
    (root / "engine" / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "data").mkdir()
    (root / "logs").mkdir()
    _copy_repo_file(repo_root, ".env.example", root / ".env.example")
    _write(root / ".env.example", _env_text(root))
    _write(root / "state" / ".env", _env_text(root))
    _copy_repo_file(
        repo_root, "config/openclaw.template.json", root / "config" / "openclaw.template.json"
    )
    _copy_repo_file(
        repo_root, "config/settings.schema.json", root / "config" / "settings.schema.json"
    )
    shutil.copytree(repo_root / "workspace" / "skills", root / "workspace" / "skills")
    return root
