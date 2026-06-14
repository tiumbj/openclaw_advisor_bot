from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .env import load_settings
from .paths import ProjectPaths

SUPPORTED_PROVIDERS = ("openai", "claude", "gemini", "deepseek")
OPENCLAW_PROVIDER_IDS = {
    "openai": "openai",
    "claude": "anthropic",
    "gemini": "google",
    "deepseek": "deepseek",
}
PROVIDER_ENABLE_ENV = {
    "openai": "OPENAI_ENABLED",
    "claude": "CLAUDE_ENABLED",
    "gemini": "GEMINI_ENABLED",
    "deepseek": "DEEPSEEK_ENABLED",
}
PROVIDER_API_KEY_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "claude": ("ANTHROPIC_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
}
PROVIDER_MODEL_ENV = {
    "openai": "OPENAI_MODEL",
    "claude": "CLAUDE_MODEL",
    "gemini": "GEMINI_MODEL",
    "deepseek": "DEEPSEEK_MODEL",
}
PROVIDER_TIMEOUT_ENV = {
    "openai": "OPENAI_TIMEOUT_SECONDS",
    "claude": "CLAUDE_TIMEOUT_SECONDS",
    "gemini": "GEMINI_TIMEOUT_SECONDS",
    "deepseek": "DEEPSEEK_TIMEOUT_SECONDS",
}
LEGACY_PROVIDER_ENV_NAMES = (
    "AI_PRIMARY_PROVIDER",
    "AI_PRIMARY_MODEL",
    "AI_FALLBACK_PROVIDER_1",
    "AI_FALLBACK_MODEL_1",
    "AI_FALLBACK_PROVIDER_2",
    "AI_FALLBACK_MODEL_2",
    "AI_FALLBACK_PROVIDER_3",
    "AI_FALLBACK_MODEL_3",
)
ALLOWED_PROVIDER_API_KEY_NAMES = frozenset(
    name for names in PROVIDER_API_KEY_ENV.values() for name in names
)

ProviderPolicyStatus = Literal["PASS", "BLOCKED", "FAIL"]
ProviderTestStatus = Literal["PASS", "BLOCKED", "NOT_RUN"]


class ProviderPolicyError(RuntimeError):
    """Raised when provider-policy validation cannot continue."""


@dataclass(frozen=True)
class ProviderPolicyIssue:
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class ProviderPolicyReport:
    status: ProviderPolicyStatus
    reason: str
    selected_provider: str | None
    selected_openclaw_provider_id: str | None
    enabled_providers: tuple[str, ...]
    supported_providers: tuple[str, ...]
    openclaw_provider_ids: dict[str, str]
    fallback_enabled: bool
    fallback_order: tuple[str, ...]
    provider_credentials: dict[str, str]
    provider_models: dict[str, str | None]
    provider_timeouts_seconds: dict[str, int | None]
    legacy_provider_refs: tuple[str, ...]
    issues: tuple[ProviderPolicyIssue, ...]
    real_provider_test: ProviderTestStatus
    real_provider_blocker: str | None


def normalize_provider_name(raw: str) -> str:
    normalized = raw.strip().lower()
    if not normalized:
        raise ValueError("provider must not be blank")
    if normalized in SUPPORTED_PROVIDERS:
        return normalized
    alias_map = {"anthropic": "claude", "google": "gemini"}
    if normalized in alias_map:
        return alias_map[normalized]
    raise ValueError(f"unsupported provider: {raw}")


def provider_model_ref(provider: str, model: str) -> str:
    normalized_provider = normalize_provider_name(provider)
    cleaned_model = model.strip()
    if not cleaned_model:
        raise ValueError("model must not be blank")
    return f"{OPENCLAW_PROVIDER_IDS[normalized_provider]}/{cleaned_model}"


def _parse_bool(raw: str | object) -> bool:
    if isinstance(raw, bool):
        return raw
    if not isinstance(raw, str):
        return False
    return raw.strip().lower() == "true"


def _parse_int(raw: str | object) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if not isinstance(raw, str):
        raise ValueError("expected integer-like timeout")
    if not raw.strip():
        return None
    value = int(raw.strip())
    if value <= 0:
        raise ValueError("expected positive integer timeout")
    return value


def _split_csv(raw: str | object) -> tuple[str, ...]:
    if not isinstance(raw, str):
        return ()
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return tuple(values)


def _issue(field: str, code: str, message: str) -> ProviderPolicyIssue:
    return ProviderPolicyIssue(field=field, code=code, message=message)


def _legacy_provider_refs(raw_values: dict[str, str]) -> tuple[str, ...]:
    refs: list[str] = []
    for name in LEGACY_PROVIDER_ENV_NAMES:
        value = raw_values.get(name, "").strip()
        if value:
            refs.append(name)
    return tuple(refs)


def _provider_credentials(raw_values: dict[str, str], provider: str) -> tuple[str, ...]:
    return tuple(
        name for name in PROVIDER_API_KEY_ENV[provider] if raw_values.get(name, "").strip()
    )


def build_provider_policy_report(
    paths: ProjectPaths,
    env_path: Path | None = None,
) -> ProviderPolicyReport:
    settings = load_settings(paths, env_path=env_path, strict=False)
    raw_values = settings.raw_values
    issues: list[ProviderPolicyIssue] = []

    enabled_providers = tuple(
        provider
        for provider in SUPPORTED_PROVIDERS
        if _parse_bool(raw_values.get(PROVIDER_ENABLE_ENV[provider], "false"))
    )
    fallback_enabled = _parse_bool(raw_values.get("AI_PROVIDER_FALLBACK_ENABLED", "false"))
    fallback_order = _split_csv(raw_values.get("AI_PROVIDER_FALLBACK_ORDER", ""))
    real_provider_test: ProviderTestStatus = "BLOCKED"
    real_provider_blocker = "NO_AVAILABLE_AI_CREDIT"

    selected_raw = raw_values.get("AI_PROVIDER", "").strip().lower()
    selected_provider: str | None = None
    if selected_raw:
        try:
            selected_provider = normalize_provider_name(selected_raw)
        except ValueError as exc:
            issues.append(_issue("AI_PROVIDER", "unsupported_provider", str(exc)))
    elif len(enabled_providers) == 1:
        selected_provider = enabled_providers[0]

    status: ProviderPolicyStatus
    if not enabled_providers:
        status = "BLOCKED"
        reason = "NO_ENABLED_PROVIDER"
    elif len(enabled_providers) > 1 and selected_provider is None:
        status = "BLOCKED"
        reason = "MULTIPLE_ENABLED_PROVIDERS_WITHOUT_PRIMARY"
    else:
        reason = "OK"
        status = "PASS"

    if selected_provider and selected_provider not in enabled_providers:
        issues.append(
            _issue(
                "AI_PROVIDER",
                "disabled_provider_selected",
                f"selected provider {selected_provider!r} is not enabled",
            )
        )
        status = "FAIL"
        reason = "SELECTED_PROVIDER_DISABLED"

    for provider in SUPPORTED_PROVIDERS:
        enabled = provider in enabled_providers
        credential_names = PROVIDER_API_KEY_ENV[provider]
        model_name = PROVIDER_MODEL_ENV[provider]
        timeout_name = PROVIDER_TIMEOUT_ENV[provider]
        credentials = _provider_credentials(raw_values, provider)
        model = raw_values.get(model_name, "").strip()
        timeout_raw = raw_values.get(timeout_name, "").strip()

        if enabled and not credentials:
            issues.append(
                _issue(
                    "/".join(credential_names),
                    "missing_credential",
                    f"{provider} is enabled but none of {credential_names!r} is set",
                )
            )
            status = "FAIL"
        if enabled and not model:
            issues.append(
                _issue(
                    model_name,
                    "missing_model",
                    f"{provider} is enabled but {model_name} is blank",
                )
            )
            status = "FAIL"
        if model:
            expected_prefix = f"{OPENCLAW_PROVIDER_IDS[provider]}/"
            if not model.startswith(expected_prefix):
                issues.append(
                    _issue(
                        model_name,
                        "invalid_model_ref",
                        f"{model_name} must start with {expected_prefix!r}",
                    )
                )
                status = "FAIL"
        if timeout_raw:
            try:
                _parse_int(timeout_raw)
            except ValueError as exc:
                issues.append(_issue(timeout_name, "invalid_timeout", str(exc)))
                status = "FAIL"

    unsupported_provider_api_keys = tuple(
        name
        for name, value in raw_values.items()
        if name.endswith("_API_KEY")
        and name not in ALLOWED_PROVIDER_API_KEY_NAMES
        and value.strip()
    )
    if unsupported_provider_api_keys:
        issues.append(
            _issue(
                "UNSUPPORTED_PROVIDER_API_KEY",
                "unsupported_provider_api_key",
                "one or more unsupported provider API keys are set",
            )
        )
        status = "FAIL"

    if fallback_enabled:
        invalid_fallbacks = [
            provider for provider in fallback_order if provider not in SUPPORTED_PROVIDERS
        ]
        if invalid_fallbacks:
            issues.append(
                _issue(
                    "AI_PROVIDER_FALLBACK_ORDER",
                    "unsupported_fallback_provider",
                    "fallback order includes unsupported providers: "
                    + ", ".join(invalid_fallbacks),
                )
            )
            status = "FAIL"
        if len(fallback_order) != len(set(fallback_order)):
            issues.append(
                _issue(
                    "AI_PROVIDER_FALLBACK_ORDER",
                    "duplicate_fallback_provider",
                    "fallback order contains duplicate providers",
                )
            )
            status = "FAIL"
        if selected_provider and selected_provider not in fallback_order and fallback_order:
            issues.append(
                _issue(
                    "AI_PROVIDER_FALLBACK_ORDER",
                    "primary_missing_from_fallback_order",
                    "selected provider is not represented in fallback order",
                )
            )
    elif fallback_order:
        # Keep the configuration observable without enabling silent fallback behavior.
        pass

    for name in LEGACY_PROVIDER_ENV_NAMES:
        value = raw_values.get(name, "").strip()
        if value:
            issues.append(
                _issue(
                    name,
                    "legacy_provider_setting",
                    f"{name} is deprecated and must be removed",
                )
            )
            status = "FAIL"

    if selected_provider is not None:
        selected_openclaw_provider_id = OPENCLAW_PROVIDER_IDS[selected_provider]
    else:
        selected_openclaw_provider_id = None

    provider_credentials = {
        provider: "present"
        if _provider_credentials(raw_values, provider)
        else "blank"
        for provider in SUPPORTED_PROVIDERS
    }
    provider_models = {
        provider: raw_values.get(PROVIDER_MODEL_ENV[provider], "").strip() or None
        for provider in SUPPORTED_PROVIDERS
    }
    provider_timeouts_seconds: dict[str, int | None] = {}
    for provider in SUPPORTED_PROVIDERS:
        timeout_raw = raw_values.get(PROVIDER_TIMEOUT_ENV[provider], "")
        try:
            provider_timeouts_seconds[provider] = _parse_int(timeout_raw)
        except ValueError:
            provider_timeouts_seconds[provider] = None

    legacy_refs = _legacy_provider_refs(raw_values)
    return ProviderPolicyReport(
        status=status,
        reason=reason,
        selected_provider=selected_provider,
        selected_openclaw_provider_id=selected_openclaw_provider_id,
        enabled_providers=enabled_providers,
        supported_providers=SUPPORTED_PROVIDERS,
        openclaw_provider_ids=dict(OPENCLAW_PROVIDER_IDS),
        fallback_enabled=fallback_enabled,
        fallback_order=fallback_order,
        provider_credentials=provider_credentials,
        provider_models=provider_models,
        provider_timeouts_seconds=provider_timeouts_seconds,
        legacy_provider_refs=legacy_refs,
        issues=tuple(issues),
        real_provider_test=real_provider_test,
        real_provider_blocker=real_provider_blocker,
    )


def provider_policy_report_as_dict(report: ProviderPolicyReport) -> dict[str, object]:
    return {
        "status": report.status,
        "reason": report.reason,
        "selected_provider": report.selected_provider,
        "selected_openclaw_provider_id": report.selected_openclaw_provider_id,
        "enabled_providers": list(report.enabled_providers),
        "supported_providers": list(report.supported_providers),
        "openclaw_provider_ids": report.openclaw_provider_ids,
        "fallback_enabled": report.fallback_enabled,
        "fallback_order": list(report.fallback_order),
        "provider_credentials": report.provider_credentials,
        "provider_models": report.provider_models,
        "provider_timeouts_seconds": report.provider_timeouts_seconds,
        "legacy_provider_refs": list(report.legacy_provider_refs),
        "issues": [issue.__dict__ for issue in report.issues],
        "real_provider_test": report.real_provider_test,
        "real_provider_blocker": report.real_provider_blocker,
    }
