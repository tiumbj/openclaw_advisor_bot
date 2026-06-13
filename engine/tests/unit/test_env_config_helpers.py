from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from openclaw_super_advisor.config import (
    ConfigValidationError,
    _as_list,
    _as_object,
    _replace_raw_placeholder,
    _replace_string_placeholder,
    render_config,
    validate_rendered_config,
)
from openclaw_super_advisor.env import (
    CanonicalEnvMissingError,
    SecretValue,
    SettingsValidationError,
    _parse_bool,
    _parse_env_file,
    _parse_url,
    audit_environment,
    load_settings,
)
from openclaw_super_advisor.paths import build_paths, installed_project_root, resolve_project_root


def test_env_private_helpers_and_error_paths(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = build_paths(sample_project)
    missing_path = sample_project / "missing.env"
    with pytest.raises(CanonicalEnvMissingError):
        audit_environment(paths, env_path=missing_path)

    invalid_env = sample_project / "state" / ".env"
    invalid_env.write_text("BROKEN_LINE\n", encoding="utf-8")
    with pytest.raises(ValueError):
        _parse_env_file(invalid_env)

    assert _parse_bool("true") is True
    assert _parse_bool("false") is False
    with pytest.raises(ValueError):
        _parse_bool("maybe")
    with pytest.raises(ValueError):
        _parse_url("not-a-url")

    monkeypatch.setenv("OPENCLAW_ADVISOR_ROOT", str(sample_project))
    assert resolve_project_root() == sample_project.resolve()
    assert resolve_project_root(sample_project) == sample_project.resolve()
    assert installed_project_root().exists()


def test_env_cross_field_validation_and_strict_settings(sample_project: Path) -> None:
    env_path = sample_project / "state" / ".env"
    env_text = env_path.read_text(encoding="utf-8")
    env_text = env_text.replace("TELEGRAM_ENABLED=false", "TELEGRAM_ENABLED=true")
    env_text = env_text.replace("MT5_ENABLED=false", "MT5_ENABLED=true")
    env_text = env_text.replace("MT5_USE_EXISTING_SESSION=true", "MT5_USE_EXISTING_SESSION=false")
    env_text = env_text.replace(
        "ADVISOR_ENGINE_BASE_URL=http://127.0.0.1:8765",
        "ADVISOR_ENGINE_BASE_URL=bad-url",
    )
    env_text = env_text.replace("OPENCLAW_GATEWAY_TOKEN=", "OPENCLAW_GATEWAY_TOKEN=same")
    env_text = env_text.replace("OPENCLAW_HOOKS_TOKEN=", "OPENCLAW_HOOKS_TOKEN=same")
    env_text = env_text.replace("ADVISOR_ENGINE_API_TOKEN=", "ADVISOR_ENGINE_API_TOKEN=same")
    env_path.write_text(env_text, encoding="utf-8")

    report = audit_environment(build_paths(sample_project))
    names = {issue.name for issue in report.issues}
    assert "ADVISOR_ENGINE_BASE_URL" in names
    assert "TELEGRAM_BOT_TOKEN" in names
    assert "MT5_LOGIN" in names
    assert "OPENCLAW_TOKENS" in names
    assert report.status("UNKNOWN_VALUE") == "MISSING"

    with pytest.raises(SettingsValidationError):
        load_settings(build_paths(sample_project), strict=True)

    blank_secret = SecretValue("")
    assert blank_secret.redacted() == "<blank>"
    assert repr(blank_secret) == "<blank>"


def test_config_helpers_and_validation_errors(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    rendered = render_config(paths, env_path=paths.canonical_env_example_path)
    validation = validate_rendered_config(rendered, paths)
    assert validation.valid

    re_match = re.match(r'"{{([A-Z0-9_]+)}}"', '"{{OPENCLAW_HOME}}"')
    assert re_match is not None
    assert (
        json.loads(_replace_string_placeholder(re_match, {"OPENCLAW_HOME": "C:\\Demo"}))
        == "C:\\Demo"
    )

    raw_match = re.match(r"\{\{([A-Z0-9_]+)\}\}", "{{OPENCLAW_GATEWAY_PORT}}")
    assert raw_match is not None
    assert _replace_raw_placeholder(raw_match, {"OPENCLAW_GATEWAY_PORT": "18789"}) == "18789"
    string_missing = re.match(r'"{{([A-Z0-9_]+)}}"', '"{{MISSING_VALUE}}"')
    assert string_missing is not None
    with pytest.raises(ConfigValidationError):
        _replace_string_placeholder(string_missing, {})

    with pytest.raises(ConfigValidationError):
        _as_object([], "demo")
    with pytest.raises(ConfigValidationError):
        _as_list({}, "demo")
    with pytest.raises(ConfigValidationError):
        _replace_raw_placeholder(raw_match, {})

    broken = dict(rendered)
    broken["skills"] = []
    broken["tools"] = dict(rendered["tools"])
    broken["tools"]["allow"] = ["read"]  # type: ignore[index]
    broken["tools"]["deny"] = []  # type: ignore[index]
    invalid = validate_rendered_config(broken, paths)
    assert not invalid.valid

    malformed = dict(rendered)
    malformed["agents"] = {"defaults": rendered["agents"]["defaults"], "list": []}  # type: ignore[index]
    assert not validate_rendered_config(malformed, paths).valid

    not_object = json.loads("[]")
    with pytest.raises(ConfigValidationError):
        validate_rendered_config(not_object, paths)  # type: ignore[arg-type]

    template_path = sample_project / "config" / "openclaw.template.json"
    template_path.write_text('{"demo": {{MISSING_VALUE}}}\n', encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        render_config(paths, env_path=paths.canonical_env_example_path)
    template_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        render_config(paths, env_path=paths.canonical_env_example_path)


def test_app_settings_parsed_values(sample_project: Path) -> None:
    settings = load_settings(
        build_paths(sample_project),
        env_path=sample_project / "state" / ".env",
        strict=False,
    )
    assert settings.parsed_values["OPENCLAW_GATEWAY_PORT"] == 18789
    assert settings.parsed_values["ADVISOR_ONLY"] is True
    assert ast.literal_eval("True") is True


def test_env_reports_missing_and_invalid_exact_values(sample_project: Path) -> None:
    env_path = sample_project / "state" / ".env"
    env_text = env_path.read_text(encoding="utf-8")
    env_text = env_text.replace(
        f"OPENCLAW_HOME={sample_project}",
        "OPENCLAW_HOME=",
    )
    env_text = env_text.replace("ADVISOR_ONLY=true", "ADVISOR_ONLY=false")
    env_text = env_text.replace(
        f"OPENCLAW_STATE_DIR={sample_project / 'state'}",
        "OPENCLAW_STATE_DIR=C:\\Wrong",
    )
    env_text = env_text.replace("OPENCLAW_GATEWAY_HOST=127.0.0.1", "")
    env_path.write_text(env_text, encoding="utf-8")

    report = audit_environment(build_paths(sample_project))
    issues = {issue.name for issue in report.issues}
    assert "OPENCLAW_HOME" in issues
    assert "ADVISOR_ONLY" in issues
    assert "OPENCLAW_STATE_DIR" in issues
    assert "OPENCLAW_GATEWAY_HOST" in issues
