from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.paths import build_paths, is_project_root, resolve_project_root


def _make_project_root(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "workspace" / "skills").mkdir(parents=True)
    (root / "engine" / "src" / "openclaw_super_advisor").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'clone'\n", encoding="utf-8")
    (root / "config" / "openclaw.template.json").write_text("{}", encoding="utf-8")


def test_resolve_project_root_prefers_current_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clone = tmp_path / "audit-clone"
    _make_project_root(clone)
    monkeypatch.chdir(clone)
    monkeypatch.delenv("OPENCLAW_ADVISOR_ROOT", raising=False)

    assert is_project_root(clone)
    assert resolve_project_root() == clone.resolve()
    assert build_paths().root_dir == clone.resolve()


def test_resolve_project_root_honors_explicit_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clone = tmp_path / "explicit-clone"
    _make_project_root(clone)
    monkeypatch.setenv("OPENCLAW_ADVISOR_ROOT", str(clone))

    assert resolve_project_root() == clone.resolve()


def test_resolve_project_root_rejects_invalid_explicit_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not an OpenClaw advisor checkout"):
        resolve_project_root(tmp_path / "missing")
