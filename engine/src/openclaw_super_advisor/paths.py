from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root_dir: Path
    config_dir: Path
    state_dir: Path
    workspace_dir: Path
    docs_dir: Path
    engine_dir: Path
    skills_dir: Path
    canonical_env_example_path: Path
    runtime_env_path: Path
    config_template_path: Path
    runtime_config_path: Path
    config_schema_path: Path


def installed_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def is_project_root(path: Path) -> bool:
    """Return whether a path looks like an OpenClaw advisor checkout."""
    return (
        (path / "config" / "openclaw.template.json").is_file()
        and (path / "workspace" / "skills").is_dir()
        and (
            (path / "pyproject.toml").is_file()
            or (path / ".env.example").is_file()
            or (path / "state" / ".env").is_file()
        )
    )


def resolve_project_root(project_root: str | Path | None = None) -> Path:
    if project_root is not None:
        root = Path(project_root).resolve()
        if not is_project_root(root):
            raise ValueError(f"project_root is not an OpenClaw advisor checkout: {root}")
        return root
    override = os.environ.get("OPENCLAW_ADVISOR_ROOT")
    if override:
        root = Path(override).resolve()
        if not is_project_root(root):
            raise ValueError(f"OPENCLAW_ADVISOR_ROOT is not an OpenClaw advisor checkout: {root}")
        return root
    cwd = Path.cwd().resolve()
    if is_project_root(cwd):
        return cwd
    installed = installed_project_root()
    if is_project_root(installed):
        return installed
    raise ValueError(
        "unable to resolve OpenClaw advisor project root; set OPENCLAW_ADVISOR_ROOT "
        "or pass --project-root"
    )


def build_paths(project_root: str | Path | None = None) -> ProjectPaths:
    root_dir = resolve_project_root(project_root)
    config_dir = root_dir / "config"
    state_dir = root_dir / "state"
    workspace_dir = root_dir / "workspace"
    return ProjectPaths(
        root_dir=root_dir,
        config_dir=config_dir,
        state_dir=state_dir,
        workspace_dir=workspace_dir,
        docs_dir=root_dir / "docs",
        engine_dir=root_dir / "engine",
        skills_dir=workspace_dir / "skills",
        canonical_env_example_path=root_dir / ".env.example",
        runtime_env_path=state_dir / ".env",
        config_template_path=config_dir / "openclaw.template.json",
        runtime_config_path=state_dir / "openclaw.json",
        config_schema_path=config_dir / "settings.schema.json",
    )
