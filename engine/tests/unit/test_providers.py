from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.providers import (
    OPENCLAW_PROVIDER_IDS,
    build_provider_policy_report,
    normalize_provider_name,
    provider_model_ref,
    provider_policy_report_as_dict,
    _legacy_provider_refs,
    _parse_bool,
    _parse_int,
    _provider_credentials,
    _split_csv,
)


def _provider_env_text(sample_project: Path) -> str:
    return (sample_project / ".env.example").read_text(encoding="utf-8")


def test_provider_name_and_model_reference_helpers() -> None:
    assert normalize_provider_name(" OpenAI ") == "openai"
    assert normalize_provider_name("google") == "gemini"
    assert provider_model_ref("deepseek", " chat ") == "deepseek/chat"
    assert _parse_bool(True) is True
    assert _parse_bool(" TRUE ") is True
    assert _parse_bool("nope") is False
    assert _parse_bool(123) is False
    assert _parse_int(None) is None
    assert _parse_int(7) == 7
    assert _parse_int(" 7 ") == 7
    assert _parse_int(" ") is None
    assert _split_csv(None) == ()
    assert _split_csv(" OpenAI, gemini , , claude ") == ("openai", "gemini", "claude")
    assert _provider_credentials({"GOOGLE_API_KEY": "secret"}, "gemini") == (
        "GOOGLE_API_KEY",
    )
    assert _legacy_provider_refs(
        {
            "AI_PRIMARY_PROVIDER": "groq",
            "AI_PRIMARY_MODEL": "compound",
            "GROQ_API_KEY": "secret-groq",
        }
    ) == (
        "AI_PRIMARY_PROVIDER=groq",
        "AI_PRIMARY_MODEL=compound",
        "GROQ_API_KEY=<redacted>",
    )

    with pytest.raises(ValueError, match="provider must not be blank"):
        normalize_provider_name(" ")
    with pytest.raises(ValueError, match="unsupported provider"):
        normalize_provider_name("groq")
    with pytest.raises(ValueError, match="expected positive integer timeout"):
        _parse_int("0")
    with pytest.raises(ValueError, match="expected integer-like timeout"):
        _parse_int(object())
    with pytest.raises(ValueError, match="model must not be blank"):
        provider_model_ref("openai", " ")


def test_provider_policy_blocks_when_nothing_is_enabled(sample_project: Path) -> None:
    report = build_provider_policy_report(
        build_paths(sample_project),
        env_path=sample_project / ".env.example",
    )
    assert report.status == "BLOCKED"
    assert report.reason == "NO_ENABLED_PROVIDER"
    assert report.enabled_providers == ()
    assert report.selected_provider is None
    assert report.real_provider_test == "BLOCKED"
    assert report.real_provider_blocker == "NO_AVAILABLE_AI_CREDIT"


def test_provider_policy_passes_with_one_enabled_provider(sample_project: Path) -> None:
    env_path = sample_project / "state" / "provider.env"
    env_path.write_text(
        (sample_project / ".env.example")
        .read_text(encoding="utf-8")
        .replace("OPENAI_ENABLED=false", "OPENAI_ENABLED=true")
        .replace("AI_PROVIDER=", "AI_PROVIDER=openai")
        .replace("OPENAI_MODEL=", "OPENAI_MODEL=openai/gpt-5.3-chat-latest")
        .replace("OPENAI_TIMEOUT_SECONDS=", "OPENAI_TIMEOUT_SECONDS=60")
        .replace("OPENAI_API_KEY=", "OPENAI_API_KEY=secret-openai"),
        encoding="utf-8",
    )
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "PASS"
    assert report.reason == "OK"
    assert report.selected_provider == "openai"
    assert report.selected_openclaw_provider_id == OPENCLAW_PROVIDER_IDS["openai"]
    assert report.provider_credentials["openai"] == "present"
    assert report.provider_models["openai"] == "openai/gpt-5.3-chat-latest"
    assert report.provider_timeouts_seconds["openai"] == 60


def test_provider_policy_accepts_google_api_key_alias(sample_project: Path) -> None:
    env_path = sample_project / "state" / "provider-gemini.env"
    env_path.write_text(
        _provider_env_text(sample_project)
        .replace("OPENAI_ENABLED=false", "OPENAI_ENABLED=true")
        .replace("GEMINI_ENABLED=false", "GEMINI_ENABLED=true")
        .replace("AI_PROVIDER=", "AI_PROVIDER=openai")
        .replace("OPENAI_MODEL=", "OPENAI_MODEL=openai/gpt-5.3-chat-latest")
        .replace("GEMINI_MODEL=", "GEMINI_MODEL=google/gemini-2.5-pro")
        .replace("OPENAI_TIMEOUT_SECONDS=", "OPENAI_TIMEOUT_SECONDS=60")
        .replace("GOOGLE_API_KEY=", "GOOGLE_API_KEY=secret-gemini")
        .replace("OPENAI_API_KEY=", "OPENAI_API_KEY=secret-openai"),
        encoding="utf-8",
    )
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "PASS"
    assert report.selected_provider == "openai"
    assert report.provider_credentials["gemini"] == "present"
    assert report.provider_models["gemini"] == "google/gemini-2.5-pro"


def test_provider_policy_blocks_multiple_enabled_without_primary(
    sample_project: Path,
) -> None:
    env_path = sample_project / "state" / "provider-multiple.env"
    env_path.write_text(
        _provider_env_text(sample_project)
        .replace("OPENAI_ENABLED=false", "OPENAI_ENABLED=true")
        .replace("CLAUDE_ENABLED=false", "CLAUDE_ENABLED=true")
        .replace("OPENAI_MODEL=", "OPENAI_MODEL=openai/gpt-5.3-chat-latest")
        .replace("CLAUDE_MODEL=", "CLAUDE_MODEL=anthropic/claude-3.7-sonnet")
        .replace("OPENAI_API_KEY=", "OPENAI_API_KEY=secret-openai")
        .replace("ANTHROPIC_API_KEY=", "ANTHROPIC_API_KEY=secret-claude"),
        encoding="utf-8",
    )
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "BLOCKED"
    assert report.reason == "MULTIPLE_ENABLED_PROVIDERS_WITHOUT_PRIMARY"
    assert report.enabled_providers == ("openai", "claude")


def test_provider_policy_rejects_disabled_primary_and_legacy_refs(
    sample_project: Path,
) -> None:
    env_path = sample_project / "state" / "provider-disabled.env"
    env_path.write_text(
        _provider_env_text(sample_project)
        .replace("AI_PROVIDER=", "AI_PROVIDER=claude")
        .replace("OPENAI_ENABLED=false", "OPENAI_ENABLED=true")
        .replace("OPENAI_MODEL=", "OPENAI_MODEL=openai/gpt-5.3-chat-latest")
        .replace("OPENAI_API_KEY=", "OPENAI_API_KEY=secret-openai")
        + "\n"
        + "\n".join(
            [
                "AI_PRIMARY_PROVIDER=groq",
                "AI_PRIMARY_MODEL=compound",
                "AI_FALLBACK_PROVIDER_1=groq",
                "AI_FALLBACK_MODEL_1=compound",
                "GROQ_API_KEY=secret-groq",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "FAIL"
    assert report.reason == "SELECTED_PROVIDER_DISABLED"
    assert any(issue.code == "disabled_provider_selected" for issue in report.issues)
    assert any(issue.code == "legacy_provider_setting" for issue in report.issues)
    assert any(issue.field == "GROQ_API_KEY" for issue in report.issues)


def test_provider_policy_reports_invalid_fallback_order(sample_project: Path) -> None:
    env_path = sample_project / "state" / "provider-fallback.env"
    env_path.write_text(
        _provider_env_text(sample_project)
        .replace("OPENAI_ENABLED=false", "OPENAI_ENABLED=true")
        .replace("AI_PROVIDER=", "AI_PROVIDER=openai")
        .replace("AI_PROVIDER_FALLBACK_ENABLED=false", "AI_PROVIDER_FALLBACK_ENABLED=true")
        .replace(
            "AI_PROVIDER_FALLBACK_ORDER=openai,claude,gemini,deepseek",
            "AI_PROVIDER_FALLBACK_ORDER=claude,deepseek,groq,claude",
        )
        .replace("OPENAI_MODEL=", "OPENAI_MODEL=openai/gpt-5.3-chat-latest")
        .replace("OPENAI_API_KEY=", "OPENAI_API_KEY=secret-openai"),
        encoding="utf-8",
    )
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "FAIL"
    assert any(issue.code == "unsupported_fallback_provider" for issue in report.issues)
    assert any(issue.code == "duplicate_fallback_provider" for issue in report.issues)
    assert any(issue.code == "primary_missing_from_fallback_order" for issue in report.issues)


def test_provider_policy_reports_missing_fields_invalid_model_and_timeout(
    sample_project: Path,
) -> None:
    env_path = sample_project / "state" / "provider-invalid.env"
    env_path.write_text(
        _provider_env_text(sample_project)
        .replace("OPENAI_ENABLED=false", "OPENAI_ENABLED=true")
        .replace("AI_PROVIDER=", "AI_PROVIDER=openai")
        .replace("OPENAI_MODEL=", "OPENAI_MODEL=gpt-5.3-chat-latest")
        .replace("OPENAI_TIMEOUT_SECONDS=", "OPENAI_TIMEOUT_SECONDS=0"),
        encoding="utf-8",
    )
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "FAIL"
    assert any(issue.code == "missing_credential" for issue in report.issues)
    assert any(issue.code == "invalid_model_ref" for issue in report.issues)
    assert any(issue.code == "invalid_timeout" for issue in report.issues)


def test_provider_policy_rejects_groq_and_unknown_provider(sample_project: Path) -> None:
    env_path = sample_project / "state" / "provider-groq.env"
    env_text = (sample_project / ".env.example").read_text(encoding="utf-8").replace(
        "AI_PROVIDER=", "AI_PROVIDER=groq"
    )
    env_path.write_text(env_text + "\nGROQ_API_KEY=secret-groq\n", encoding="utf-8")
    report = build_provider_policy_report(build_paths(sample_project), env_path=env_path)
    assert report.status == "FAIL"
    assert any(issue.code == "unsupported_provider" for issue in report.issues)
    assert any(issue.field == "GROQ_API_KEY" for issue in report.issues)
    payload = provider_policy_report_as_dict(report)
    assert payload["status"] == "FAIL"
    assert normalize_provider_name("anthropic") == "claude"
    assert provider_model_ref("gemini", "gemini-2.5-pro") == "google/gemini-2.5-pro"
