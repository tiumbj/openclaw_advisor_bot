from __future__ import annotations

from pathlib import Path

from openclaw_super_advisor.env import (
    DuplicateEnvError,
    SecretValue,
    audit_environment,
    load_settings,
)
from openclaw_super_advisor.paths import build_paths


def test_audit_environment_uses_portable_paths(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    report = audit_environment(paths)
    assert report.status("OPENCLAW_HOME") == "PRESENT"
    assert report.status("OPENAI_API_KEY") == "BLANK"
    assert report.valid


def test_detects_duplicate_env_file(sample_project: Path) -> None:
    rogue_env = sample_project / ".env"
    rogue_env.write_text("SHOULD_NOT_EXIST=true\n", encoding="utf-8")
    paths = build_paths(sample_project)
    try:
        try:
            audit_environment(paths)
        except DuplicateEnvError:
            pass
        else:
            raise AssertionError("Expected duplicate env detection")
    finally:
        rogue_env.unlink()


def test_load_settings_redacts_secrets(sample_project: Path) -> None:
    env_path = sample_project / "state" / ".env"
    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            "OPENCLAW_GATEWAY_TOKEN=", "OPENCLAW_GATEWAY_TOKEN=secret-token"
        ),
        encoding="utf-8",
    )
    settings = load_settings(build_paths(sample_project), strict=False)
    token = settings.secrets["OPENCLAW_GATEWAY_TOKEN"]
    assert isinstance(token, SecretValue)
    assert token.redacted().startswith("<redacted:")
    assert settings.render_context()["OPENCLAW_GATEWAY_TOKEN"] == "secret-token"
