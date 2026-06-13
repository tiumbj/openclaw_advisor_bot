from __future__ import annotations

from dataclasses import asdict, dataclass

from .config import load_agent_policy, validate_config_paths
from .constants import CANONICAL_ENV_PATH, CONFIG_PATH, LEGACY_ARCHIVE_PATH, STATE_DIR, WORKSPACE_DIR
from .env import audit_environment, load_settings


@dataclass(frozen=True)
class HealthReport:
    state_dir: str
    config_path: str
    workspace_path: str
    canonical_env_path: str
    legacy_archive_path: str
    env_status: dict[str, str]
    env_issues: tuple[dict[str, str], ...]
    agent_id: str
    allowed_tools: tuple[str, ...]


def run_health_check() -> HealthReport:
    validate_config_paths()
    env_snapshot = audit_environment()
    settings = load_settings(strict=False)
    agent_policy = load_agent_policy()
    return HealthReport(
        state_dir=str(STATE_DIR),
        config_path=str(CONFIG_PATH),
        workspace_path=str(WORKSPACE_DIR),
        canonical_env_path=str(CANONICAL_ENV_PATH),
        legacy_archive_path=str(LEGACY_ARCHIVE_PATH),
        env_status={name: env_snapshot.status(name) for name in env_snapshot.values},
        env_issues=tuple(
            {"name": issue.name, "status": issue.status, "message": issue.message}
            for issue in env_snapshot.issues
        ),
        agent_id=agent_policy.agent_id,
        allowed_tools=agent_policy.allowed_tools,
    )


def run_health_check_as_dict() -> dict[str, object]:
    return asdict(run_health_check())
