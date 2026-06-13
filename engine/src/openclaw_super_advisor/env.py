from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse

from .constants import CANONICAL_ENV_PATH, PROHIBITED_ENV_PATHS

EnvStatus = Literal["PRESENT", "MISSING", "BLANK", "INVALID_FORMAT"]


class DuplicateEnvError(RuntimeError):
    """Raised when a non-canonical .env file is present."""


class CanonicalEnvMissingError(RuntimeError):
    """Raised when the canonical .env file does not exist."""


class SettingsValidationError(RuntimeError):
    """Raised when strict settings validation fails."""


@dataclass(frozen=True)
class SecretValue:
    value: str

    def is_blank(self) -> bool:
        return self.value == ""

    def redacted(self) -> str:
        if self.is_blank():
            return "<blank>"
        return f"<redacted:{sha256(self.value.encode('utf-8')).hexdigest()[:12]}>"

    def __repr__(self) -> str:
        return self.redacted()


@dataclass(frozen=True)
class ValidationIssue:
    name: str
    status: EnvStatus
    message: str


@dataclass(frozen=True)
class EnvSnapshot:
    values: dict[str, str]
    statuses: dict[str, EnvStatus]
    duplicate_paths: tuple[Path, ...]
    issues: tuple[ValidationIssue, ...]

    def status(self, name: str) -> EnvStatus:
        return self.statuses.get(name, "MISSING")


@dataclass(frozen=True)
class OpenClawPaths:
    home: Path
    state_dir: Path
    config_path: Path
    workspace_dir: Path
    log_level: str


@dataclass(frozen=True)
class OpenClawSecurity:
    gateway_token: SecretValue
    hooks_token: SecretValue
    advisor_engine_api_token: SecretValue


@dataclass(frozen=True)
class ProviderSelection:
    primary_provider: str
    primary_model: str
    fallback_provider_1: str
    fallback_model_1: str
    fallback_provider_2: str
    fallback_model_2: str
    fallback_provider_3: str
    fallback_model_3: str


@dataclass(frozen=True)
class ProviderKeys:
    deepseek_api_key: SecretValue
    openai_api_key: SecretValue
    anthropic_api_key: SecretValue
    gemini_api_key: SecretValue
    google_api_key: SecretValue


@dataclass(frozen=True)
class TelegramSettings:
    enabled: bool
    bot_token: SecretValue
    allowed_user_id: str
    target_chat_id: str
    group_chat_id: str
    thread_id: str
    live_telegram_allowed: bool


@dataclass(frozen=True)
class MT5Settings:
    enabled: bool
    terminal_path: Path | None
    use_existing_session: bool
    login: str
    password: SecretValue
    server: str
    xauusd_symbol: str
    dxy_symbol: str
    eurusd_symbol: str
    audusd_symbol: str
    us10y_symbol: str


@dataclass(frozen=True)
class AdvisorEngineSettings:
    advisor_only: bool
    execution_allowed: bool
    allow_order_write: bool
    host: str
    port: int
    base_url: str
    timezone: str
    primary_symbol: str
    runtime_mode: str


@dataclass(frozen=True)
class HooksSettings:
    enabled: bool
    path: str
    gateway_host: str
    gateway_port: int


@dataclass(frozen=True)
class StorageSettings:
    data_dir: Path
    log_dir: Path
    db_path: Path


@dataclass(frozen=True)
class DevelopmentSettings:
    app_env: str
    dry_run: bool
    shadow_mode: bool
    live_telegram_allowed: bool
    reveal_secret_values: bool


@dataclass(frozen=True)
class AppSettings:
    openclaw: OpenClawPaths
    security: OpenClawSecurity
    providers: ProviderSelection
    provider_keys: ProviderKeys
    telegram: TelegramSettings
    mt5: MT5Settings
    advisor: AdvisorEngineSettings
    hooks: HooksSettings
    storage: StorageSettings
    development: DevelopmentSettings


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    parser: Callable[[str], object]
    allow_blank: bool = True
    exact: str | None = None


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env line: {raw_line!r}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def detect_duplicate_env_files() -> tuple[Path, ...]:
    return tuple(path for path in PROHIBITED_ENV_PATHS if path.exists())


def _parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("expected true or false")


def _parse_int(raw: str) -> int:
    return int(raw)


def _parse_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("expected absolute http(s) URL")
    return raw


def _parse_path(raw: str) -> Path:
    return Path(raw)


def _parse_string(raw: str) -> str:
    return raw


def _secret(raw: str) -> SecretValue:
    return SecretValue(raw)


ENV_SPECS: tuple[EnvVarSpec, ...] = (
    EnvVarSpec("OPENCLAW_HOME", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor"),
    EnvVarSpec("OPENCLAW_STATE_DIR", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor\state"),
    EnvVarSpec("OPENCLAW_CONFIG_PATH", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor\state\openclaw.json"),
    EnvVarSpec("OPENCLAW_WORKSPACE_DIR", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor\workspace"),
    EnvVarSpec("OPENCLAW_LOG_LEVEL", _parse_string, allow_blank=False),
    EnvVarSpec("OPENCLAW_GATEWAY_TOKEN", _secret),
    EnvVarSpec("OPENCLAW_HOOKS_TOKEN", _secret),
    EnvVarSpec("ADVISOR_ENGINE_API_TOKEN", _secret),
    EnvVarSpec("AI_PRIMARY_PROVIDER", _parse_string),
    EnvVarSpec("AI_PRIMARY_MODEL", _parse_string),
    EnvVarSpec("AI_FALLBACK_PROVIDER_1", _parse_string),
    EnvVarSpec("AI_FALLBACK_MODEL_1", _parse_string),
    EnvVarSpec("AI_FALLBACK_PROVIDER_2", _parse_string),
    EnvVarSpec("AI_FALLBACK_MODEL_2", _parse_string),
    EnvVarSpec("AI_FALLBACK_PROVIDER_3", _parse_string),
    EnvVarSpec("AI_FALLBACK_MODEL_3", _parse_string),
    EnvVarSpec("DEEPSEEK_API_KEY", _secret),
    EnvVarSpec("OPENAI_API_KEY", _secret),
    EnvVarSpec("ANTHROPIC_API_KEY", _secret),
    EnvVarSpec("GEMINI_API_KEY", _secret),
    EnvVarSpec("GOOGLE_API_KEY", _secret),
    EnvVarSpec("TELEGRAM_ENABLED", _parse_bool, allow_blank=False),
    EnvVarSpec("TELEGRAM_BOT_TOKEN", _secret),
    EnvVarSpec("TELEGRAM_ALLOWED_USER_ID", _parse_string),
    EnvVarSpec("TELEGRAM_TARGET_CHAT_ID", _parse_string),
    EnvVarSpec("TELEGRAM_GROUP_CHAT_ID", _parse_string),
    EnvVarSpec("TELEGRAM_THREAD_ID", _parse_string),
    EnvVarSpec("MT5_ENABLED", _parse_bool, allow_blank=False),
    EnvVarSpec("MT5_TERMINAL_PATH", _parse_path),
    EnvVarSpec("MT5_USE_EXISTING_SESSION", _parse_bool, allow_blank=False),
    EnvVarSpec("MT5_LOGIN", _parse_string),
    EnvVarSpec("MT5_PASSWORD", _secret),
    EnvVarSpec("MT5_SERVER", _parse_string),
    EnvVarSpec("MT5_XAUUSD_SYMBOL", _parse_string),
    EnvVarSpec("MT5_DXY_SYMBOL", _parse_string),
    EnvVarSpec("MT5_EURUSD_SYMBOL", _parse_string),
    EnvVarSpec("MT5_AUDUSD_SYMBOL", _parse_string),
    EnvVarSpec("MT5_US10Y_SYMBOL", _parse_string),
    EnvVarSpec("ADVISOR_ONLY", _parse_bool, allow_blank=False, exact="true"),
    EnvVarSpec("EXECUTION_ALLOWED", _parse_bool, allow_blank=False, exact="false"),
    EnvVarSpec("ALLOW_ORDER" "_SEND", _parse_bool, allow_blank=False, exact="false"),
    EnvVarSpec("ADVISOR_ENGINE_HOST", _parse_string, allow_blank=False),
    EnvVarSpec("ADVISOR_ENGINE_PORT", _parse_int, allow_blank=False),
    EnvVarSpec("ADVISOR_ENGINE_BASE_URL", _parse_url, allow_blank=False),
    EnvVarSpec("ADVISOR_TIMEZONE", _parse_string, allow_blank=False),
    EnvVarSpec("ADVISOR_PRIMARY_SYMBOL", _parse_string, allow_blank=False),
    EnvVarSpec("ADVISOR_RUNTIME_MODE", _parse_string, allow_blank=False),
    EnvVarSpec("OPENCLAW_HOOKS_ENABLED", _parse_bool, allow_blank=False),
    EnvVarSpec("OPENCLAW_HOOKS_PATH", _parse_string, allow_blank=False),
    EnvVarSpec("OPENCLAW_GATEWAY_HOST", _parse_string, allow_blank=False),
    EnvVarSpec("OPENCLAW_GATEWAY_PORT", _parse_int, allow_blank=False),
    EnvVarSpec("ADVISOR_DATA_DIR", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor\data"),
    EnvVarSpec("ADVISOR_LOG_DIR", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor\logs"),
    EnvVarSpec("ADVISOR_DB_PATH", _parse_path, allow_blank=False, exact=r"C:\Data\OpenClawSuperAdvisor\data\advisor.db"),
    EnvVarSpec("APP_ENV", _parse_string, allow_blank=False),
    EnvVarSpec("DRY_RUN", _parse_bool, allow_blank=False),
    EnvVarSpec("SHADOW_MODE", _parse_bool, allow_blank=False),
    EnvVarSpec("LIVE_TELEGRAM_ALLOWED", _parse_bool, allow_blank=False),
    EnvVarSpec("REVEAL_SECRET_VALUES", _parse_bool, allow_blank=False),
)

ENV_SPEC_MAP = {spec.name: spec for spec in ENV_SPECS}


def audit_environment() -> EnvSnapshot:
    if not CANONICAL_ENV_PATH.exists():
        raise CanonicalEnvMissingError(f"Missing canonical env file: {CANONICAL_ENV_PATH}")
    duplicate_paths = detect_duplicate_env_files()
    if duplicate_paths:
        raise DuplicateEnvError(
            "Found prohibited .env files: " + ", ".join(str(path) for path in duplicate_paths)
        )
    values = _parse_env_file(CANONICAL_ENV_PATH)
    statuses: dict[str, EnvStatus] = {}
    issues: list[ValidationIssue] = []
    for spec in ENV_SPECS:
        if spec.name not in values:
            statuses[spec.name] = "MISSING"
            issues.append(ValidationIssue(spec.name, "MISSING", "Variable is missing from canonical .env"))
            continue
        raw = values[spec.name]
        if raw == "":
            statuses[spec.name] = "BLANK"
            if not spec.allow_blank:
                issues.append(ValidationIssue(spec.name, "BLANK", "Required variable is blank"))
            continue
        try:
            parsed = spec.parser(raw)
            if spec.exact is not None:
                if isinstance(parsed, Path):
                    if str(parsed) != spec.exact:
                        raise ValueError(f"expected {spec.exact}")
                elif raw.lower() != spec.exact.lower():
                    raise ValueError(f"expected {spec.exact}")
            statuses[spec.name] = "PRESENT"
        except ValueError as exc:
            statuses[spec.name] = "INVALID_FORMAT"
            issues.append(ValidationIssue(spec.name, "INVALID_FORMAT", str(exc)))

    token_names = ("OPENCLAW_GATEWAY_TOKEN", "OPENCLAW_HOOKS_TOKEN", "ADVISOR_ENGINE_API_TOKEN")
    non_blank_tokens = {name: values.get(name, "") for name in token_names if values.get(name, "")}
    if len(set(non_blank_tokens.values())) != len(non_blank_tokens):
        issues.append(
            ValidationIssue(
                "OPENCLAW_TOKENS",
                "INVALID_FORMAT",
                "Gateway, hooks, and engine tokens must be distinct when provided",
            )
        )

    if values.get("MT5_USE_EXISTING_SESSION", "").lower() != "true":
        for name in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"):
            if statuses.get(name) == "BLANK":
                issues.append(ValidationIssue(name, "BLANK", "Required when MT5_USE_EXISTING_SESSION=false"))

    for name, expected in {
        "ADVISOR_ONLY": "true",
        "EXECUTION_ALLOWED": "false",
        "ALLOW_ORDER" "_SEND": "false",
    }.items():
        if values.get(name, "").lower() != expected:
            issues.append(ValidationIssue(name, "INVALID_FORMAT", f"Expected {expected}"))

    return EnvSnapshot(values=values, statuses=statuses, duplicate_paths=duplicate_paths, issues=tuple(issues))


def _value(snapshot: EnvSnapshot, name: str) -> str:
    return snapshot.values.get(name, "")


def load_settings(strict: bool = True) -> AppSettings:
    snapshot = audit_environment()
    if strict and snapshot.issues:
        raise SettingsValidationError("; ".join(f"{issue.name}:{issue.message}" for issue in snapshot.issues))

    def maybe_path(name: str) -> Path | None:
        raw = _value(snapshot, name)
        return Path(raw) if raw else None

    settings = AppSettings(
        openclaw=OpenClawPaths(
            home=Path(_value(snapshot, "OPENCLAW_HOME")),
            state_dir=Path(_value(snapshot, "OPENCLAW_STATE_DIR")),
            config_path=Path(_value(snapshot, "OPENCLAW_CONFIG_PATH")),
            workspace_dir=Path(_value(snapshot, "OPENCLAW_WORKSPACE_DIR")),
            log_level=_value(snapshot, "OPENCLAW_LOG_LEVEL"),
        ),
        security=OpenClawSecurity(
            gateway_token=SecretValue(_value(snapshot, "OPENCLAW_GATEWAY_TOKEN")),
            hooks_token=SecretValue(_value(snapshot, "OPENCLAW_HOOKS_TOKEN")),
            advisor_engine_api_token=SecretValue(_value(snapshot, "ADVISOR_ENGINE_API_TOKEN")),
        ),
        providers=ProviderSelection(
            primary_provider=_value(snapshot, "AI_PRIMARY_PROVIDER"),
            primary_model=_value(snapshot, "AI_PRIMARY_MODEL"),
            fallback_provider_1=_value(snapshot, "AI_FALLBACK_PROVIDER_1"),
            fallback_model_1=_value(snapshot, "AI_FALLBACK_MODEL_1"),
            fallback_provider_2=_value(snapshot, "AI_FALLBACK_PROVIDER_2"),
            fallback_model_2=_value(snapshot, "AI_FALLBACK_MODEL_2"),
            fallback_provider_3=_value(snapshot, "AI_FALLBACK_PROVIDER_3"),
            fallback_model_3=_value(snapshot, "AI_FALLBACK_MODEL_3"),
        ),
        provider_keys=ProviderKeys(
            deepseek_api_key=SecretValue(_value(snapshot, "DEEPSEEK_API_KEY")),
            openai_api_key=SecretValue(_value(snapshot, "OPENAI_API_KEY")),
            anthropic_api_key=SecretValue(_value(snapshot, "ANTHROPIC_API_KEY")),
            gemini_api_key=SecretValue(_value(snapshot, "GEMINI_API_KEY")),
            google_api_key=SecretValue(_value(snapshot, "GOOGLE_API_KEY")),
        ),
        telegram=TelegramSettings(
            enabled=_parse_bool(_value(snapshot, "TELEGRAM_ENABLED")),
            bot_token=SecretValue(_value(snapshot, "TELEGRAM_BOT_TOKEN")),
            allowed_user_id=_value(snapshot, "TELEGRAM_ALLOWED_USER_ID"),
            target_chat_id=_value(snapshot, "TELEGRAM_TARGET_CHAT_ID"),
            group_chat_id=_value(snapshot, "TELEGRAM_GROUP_CHAT_ID"),
            thread_id=_value(snapshot, "TELEGRAM_THREAD_ID"),
            live_telegram_allowed=_parse_bool(_value(snapshot, "LIVE_TELEGRAM_ALLOWED")),
        ),
        mt5=MT5Settings(
            enabled=_parse_bool(_value(snapshot, "MT5_ENABLED")),
            terminal_path=maybe_path("MT5_TERMINAL_PATH"),
            use_existing_session=_parse_bool(_value(snapshot, "MT5_USE_EXISTING_SESSION")),
            login=_value(snapshot, "MT5_LOGIN"),
            password=SecretValue(_value(snapshot, "MT5_PASSWORD")),
            server=_value(snapshot, "MT5_SERVER"),
            xauusd_symbol=_value(snapshot, "MT5_XAUUSD_SYMBOL"),
            dxy_symbol=_value(snapshot, "MT5_DXY_SYMBOL"),
            eurusd_symbol=_value(snapshot, "MT5_EURUSD_SYMBOL"),
            audusd_symbol=_value(snapshot, "MT5_AUDUSD_SYMBOL"),
            us10y_symbol=_value(snapshot, "MT5_US10Y_SYMBOL"),
        ),
        advisor=AdvisorEngineSettings(
            advisor_only=_parse_bool(_value(snapshot, "ADVISOR_ONLY")),
            execution_allowed=_parse_bool(_value(snapshot, "EXECUTION_ALLOWED")),
            allow_order_write=_parse_bool(_value(snapshot, "ALLOW_ORDER" "_SEND")),
            host=_value(snapshot, "ADVISOR_ENGINE_HOST"),
            port=_parse_int(_value(snapshot, "ADVISOR_ENGINE_PORT")),
            base_url=_value(snapshot, "ADVISOR_ENGINE_BASE_URL"),
            timezone=_value(snapshot, "ADVISOR_TIMEZONE"),
            primary_symbol=_value(snapshot, "ADVISOR_PRIMARY_SYMBOL"),
            runtime_mode=_value(snapshot, "ADVISOR_RUNTIME_MODE"),
        ),
        hooks=HooksSettings(
            enabled=_parse_bool(_value(snapshot, "OPENCLAW_HOOKS_ENABLED")),
            path=_value(snapshot, "OPENCLAW_HOOKS_PATH"),
            gateway_host=_value(snapshot, "OPENCLAW_GATEWAY_HOST"),
            gateway_port=_parse_int(_value(snapshot, "OPENCLAW_GATEWAY_PORT")),
        ),
        storage=StorageSettings(
            data_dir=Path(_value(snapshot, "ADVISOR_DATA_DIR")),
            log_dir=Path(_value(snapshot, "ADVISOR_LOG_DIR")),
            db_path=Path(_value(snapshot, "ADVISOR_DB_PATH")),
        ),
        development=DevelopmentSettings(
            app_env=_value(snapshot, "APP_ENV"),
            dry_run=_parse_bool(_value(snapshot, "DRY_RUN")),
            shadow_mode=_parse_bool(_value(snapshot, "SHADOW_MODE")),
            live_telegram_allowed=_parse_bool(_value(snapshot, "LIVE_TELEGRAM_ALLOWED")),
            reveal_secret_values=_parse_bool(_value(snapshot, "REVEAL_SECRET_VALUES")),
        ),
    )
    return settings
