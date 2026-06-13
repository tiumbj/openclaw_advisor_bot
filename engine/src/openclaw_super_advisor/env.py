from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from .paths import ProjectPaths

EnvStatus = Literal["PRESENT", "MISSING", "BLANK", "INVALID_FORMAT"]


class DuplicateEnvError(RuntimeError):
    """Raised when a non-canonical runtime env file exists."""


class CanonicalEnvMissingError(RuntimeError):
    """Raised when the selected env file does not exist."""


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
class EnvAuditReport:
    env_path: Path
    values: dict[str, str]
    statuses: dict[str, EnvStatus]
    duplicate_paths: tuple[Path, ...]
    issues: tuple[ValidationIssue, ...]

    def status(self, name: str) -> EnvStatus:
        return self.statuses.get(name, "MISSING")

    @property
    def valid(self) -> bool:
        return not self.issues and not self.duplicate_paths


@dataclass(frozen=True)
class AppSettings:
    env_path: Path
    raw_values: dict[str, str]
    parsed_values: dict[str, object]
    secrets: dict[str, SecretValue]

    def render_context(self) -> dict[str, str]:
        return dict(self.raw_values)


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    parser: Callable[[str], object]
    allow_blank: bool = True
    expected: str | None = None


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


def _parse_bool(raw: str) -> bool:
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("expected true or false")


def _parse_int(raw: str) -> int:
    return int(raw)


def _parse_string(raw: str) -> str:
    return raw


def _parse_path(raw: str) -> Path:
    return Path(raw)


def _parse_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("expected absolute http(s) URL")
    return raw


def _secret(raw: str) -> SecretValue:
    return SecretValue(raw)


def build_env_specs(paths: ProjectPaths) -> tuple[EnvVarSpec, ...]:
    return (
        EnvVarSpec(
            "OPENCLAW_HOME",
            _parse_path,
            allow_blank=False,
            expected=str(paths.root_dir),
        ),
        EnvVarSpec(
            "OPENCLAW_STATE_DIR", _parse_path, allow_blank=False, expected=str(paths.state_dir)
        ),
        EnvVarSpec(
            "OPENCLAW_CONFIG_PATH",
            _parse_path,
            allow_blank=False,
            expected=str(paths.runtime_config_path),
        ),
        EnvVarSpec(
            "OPENCLAW_WORKSPACE_DIR",
            _parse_path,
            allow_blank=False,
            expected=str(paths.workspace_dir),
        ),
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
        EnvVarSpec("ADVISOR_ONLY", _parse_bool, allow_blank=False, expected="true"),
        EnvVarSpec("EXECUTION_ALLOWED", _parse_bool, allow_blank=False, expected="false"),
        EnvVarSpec("ALLOW_ORDER_SEND", _parse_bool, allow_blank=False, expected="false"),
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
        EnvVarSpec("ADVISOR_DATA_DIR", _parse_path, allow_blank=False),
        EnvVarSpec("ADVISOR_LOG_DIR", _parse_path, allow_blank=False),
        EnvVarSpec("ADVISOR_DB_PATH", _parse_path, allow_blank=False),
        EnvVarSpec("APP_ENV", _parse_string, allow_blank=False),
        EnvVarSpec("DRY_RUN", _parse_bool, allow_blank=False),
        EnvVarSpec("SHADOW_MODE", _parse_bool, allow_blank=False),
        EnvVarSpec(
            "LIVE_TELEGRAM_ALLOWED",
            _parse_bool,
            allow_blank=False,
            expected="false",
        ),
        EnvVarSpec(
            "REVEAL_SECRET_VALUES",
            _parse_bool,
            allow_blank=False,
            expected="false",
        ),
    )


def detect_duplicate_env_files(
    paths: ProjectPaths,
    env_path: Path | None = None,
) -> tuple[Path, ...]:
    selected_path = (env_path or paths.runtime_env_path).resolve()
    allowed_paths = {selected_path, paths.runtime_env_path.resolve()}
    duplicates: list[Path] = []
    for path in paths.root_dir.rglob(".env"):
        resolved = path.resolve()
        if resolved not in allowed_paths:
            duplicates.append(resolved)
    return tuple(sorted(duplicates))


def _validate_expected(spec: EnvVarSpec, raw: str, parsed: object, base_dir: Path) -> None:
    if spec.expected is None:
        return
    if isinstance(parsed, Path):
        actual_path = parsed if parsed.is_absolute() else (base_dir / parsed)
        if actual_path.resolve() != Path(spec.expected).resolve():
            raise ValueError(f"expected {spec.expected}")
        return
    if raw.lower() != spec.expected.lower():
        raise ValueError(f"expected {spec.expected}")


def audit_environment(paths: ProjectPaths, env_path: Path | None = None) -> EnvAuditReport:
    selected_env_path = (env_path or paths.runtime_env_path).resolve()
    if not selected_env_path.exists():
        raise CanonicalEnvMissingError(f"Missing env file: {selected_env_path}")
    duplicate_paths = detect_duplicate_env_files(paths, selected_env_path)
    if duplicate_paths:
        raise DuplicateEnvError(
            "Found prohibited env files: " + ", ".join(str(path) for path in duplicate_paths)
        )
    values = _parse_env_file(selected_env_path)
    statuses: dict[str, EnvStatus] = {}
    issues: list[ValidationIssue] = []
    for spec in build_env_specs(paths):
        raw = values.get(spec.name)
        if raw is None:
            statuses[spec.name] = "MISSING"
            issues.append(ValidationIssue(spec.name, "MISSING", "Variable is missing"))
            continue
        if raw == "":
            statuses[spec.name] = "BLANK"
            if not spec.allow_blank:
                issues.append(ValidationIssue(spec.name, "BLANK", "Required variable is blank"))
            continue
        try:
            parsed = spec.parser(raw)
            _validate_expected(spec, raw, parsed, paths.root_dir)
            statuses[spec.name] = "PRESENT"
        except ValueError as exc:
            statuses[spec.name] = "INVALID_FORMAT"
            issues.append(ValidationIssue(spec.name, "INVALID_FORMAT", str(exc)))

    if values.get("TELEGRAM_ENABLED", "false").lower() == "true":
        for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TARGET_CHAT_ID"):
            if statuses.get(name) == "BLANK":
                issues.append(ValidationIssue(name, "BLANK", "Required when TELEGRAM_ENABLED=true"))

    if (
        values.get("MT5_ENABLED", "false").lower() == "true"
        and values.get("MT5_USE_EXISTING_SESSION", "true").lower() != "true"
    ):
        for name in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"):
            if statuses.get(name) == "BLANK":
                issues.append(
                    ValidationIssue(
                        name,
                        "BLANK",
                        "Required when MT5_ENABLED=true and MT5_USE_EXISTING_SESSION=false",
                    )
                )

    token_names = ("OPENCLAW_GATEWAY_TOKEN", "OPENCLAW_HOOKS_TOKEN", "ADVISOR_ENGINE_API_TOKEN")
    non_blank_tokens = {name: values.get(name, "") for name in token_names if values.get(name, "")}
    if len(set(non_blank_tokens.values())) != len(non_blank_tokens):
        issues.append(
            ValidationIssue(
                "OPENCLAW_TOKENS",
                "INVALID_FORMAT",
                "Gateway, hooks, and engine tokens must be distinct when present",
            )
        )

    return EnvAuditReport(
        env_path=selected_env_path,
        values=values,
        statuses=statuses,
        duplicate_paths=duplicate_paths,
        issues=tuple(issues),
    )


def load_settings(
    paths: ProjectPaths,
    env_path: Path | None = None,
    strict: bool = True,
) -> AppSettings:
    report = audit_environment(paths, env_path=env_path)
    if strict and report.issues:
        message = "; ".join(f"{issue.name}: {issue.message}" for issue in report.issues)
        raise SettingsValidationError(message)
    parsed_values: dict[str, object] = {}
    secrets: dict[str, SecretValue] = {}
    for spec in build_env_specs(paths):
        raw = report.values.get(spec.name, "")
        if raw == "":
            parsed_values[spec.name] = raw
            if spec.parser is _secret:
                secrets[spec.name] = SecretValue(raw)
            continue
        parsed = spec.parser(raw)
        parsed_values[spec.name] = parsed
        if isinstance(parsed, SecretValue):
            secrets[spec.name] = parsed
    return AppSettings(
        env_path=report.env_path,
        raw_values=dict(report.values),
        parsed_values=parsed_values,
        secrets=secrets,
    )
