from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.providers import (
    OPENCLAW_PROVIDER_IDS,
    build_provider_policy_report,
    normalize_provider_name,
    provider_model_ref,
    provider_policy_report_as_dict,
)


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
