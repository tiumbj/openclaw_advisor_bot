from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from ._version import PHASE, __version__
from .agent_topology import validate_agent_topology
from .config import validate_rendered_config
from .constants import AGENT_ALLOWED_TOOLS, AGENT_SKILL_NAMES, SKILL_NAMES
from .paths import ProjectPaths


@dataclass(frozen=True)
class SkillIssue:
    skill: str
    path: str
    rule: str
    message: str


@dataclass(frozen=True)
class SkillDocument:
    name: str
    description: str
    version: str
    owner_agent: str
    purpose: str
    allowed_inputs: tuple[str, ...]
    required_input_schema: str
    output_schema: str
    allowed_tools: tuple[str, ...]
    denied_tools: tuple[str, ...]
    safety_constraints: tuple[str, ...]
    failure_behavior: str
    audit_fields: tuple[str, ...]
    tests: tuple[str, ...]
    promotion_status: str
    path: Path
    body: str


@dataclass(frozen=True)
class SkillValidationReport:
    version: str
    phase: str
    valid: bool
    skill_names: tuple[str, ...]
    issues: tuple[SkillIssue, ...]
    runtime_issues: tuple[SkillIssue, ...]


REQUIRED_FRONTMATTER_FIELDS = (
    "name",
    "description",
    "version",
    "owner_agent",
    "purpose",
    "allowed_inputs",
    "required_input_schema",
    "output_schema",
    "allowed_tools",
    "denied_tools",
    "safety_constraints",
    "failure_behavior",
    "audit_fields",
    "tests",
    "promotion_status",
)


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path} must start with YAML frontmatter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{path} must contain a closing YAML frontmatter block")
    return parts[1], parts[2]


def _as_string_sequence(value: Any, field_name: str, path: Path) -> tuple[str, ...]:
    if isinstance(value, str):
        normalized = [item.strip() for item in value.splitlines() if item.strip()]
        return tuple(normalized)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(cast(list[str], value))
    raise ValueError(f"{path} field {field_name} must be a string list")


def _parse_skill(path: Path) -> SkillDocument:
    frontmatter_text, body = _split_frontmatter(path.read_text(encoding="utf-8"), path)
    loaded = yaml.safe_load(frontmatter_text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} frontmatter must be a mapping")
    metadata = cast(dict[str, Any], loaded)
    missing = [field for field in REQUIRED_FRONTMATTER_FIELDS if field not in metadata]
    if missing:
        raise ValueError(f"{path} frontmatter missing fields: {', '.join(missing)}")

    name = metadata.get("name")
    description = metadata.get("description")
    version = metadata.get("version")
    owner_agent = metadata.get("owner_agent")
    purpose = metadata.get("purpose")
    required_input_schema = metadata.get("required_input_schema")
    output_schema = metadata.get("output_schema")
    failure_behavior = metadata.get("failure_behavior")
    promotion_status = metadata.get("promotion_status")
    if not all(
        isinstance(item, str) for item in (name, description, version, owner_agent, purpose)
    ):
        raise ValueError(
            f"{path} frontmatter must define string name, description, version, "
            "owner_agent, and purpose"
        )
    if not all(
        isinstance(item, str)
        for item in (required_input_schema, output_schema, failure_behavior, promotion_status)
    ):
        raise ValueError(f"{path} schema, behavior, and promotion fields must be strings")

    allowed_inputs = _as_string_sequence(metadata.get("allowed_inputs"), "allowed_inputs", path)
    allowed_tools = _as_string_sequence(metadata.get("allowed_tools"), "allowed_tools", path)
    denied_tools = _as_string_sequence(metadata.get("denied_tools"), "denied_tools", path)
    safety_constraints = _as_string_sequence(
        metadata.get("safety_constraints"), "safety_constraints", path
    )
    audit_fields = _as_string_sequence(metadata.get("audit_fields"), "audit_fields", path)
    tests = _as_string_sequence(metadata.get("tests"), "tests", path)
    return SkillDocument(
        name=str(name),
        description=str(description),
        version=str(version),
        owner_agent=str(owner_agent),
        purpose=str(purpose),
        allowed_inputs=allowed_inputs,
        required_input_schema=str(required_input_schema),
        output_schema=str(output_schema),
        allowed_tools=tuple(allowed_tools),
        denied_tools=tuple(denied_tools),
        safety_constraints=tuple(safety_constraints),
        failure_behavior=str(failure_behavior),
        audit_fields=tuple(audit_fields),
        tests=tuple(tests),
        promotion_status=str(promotion_status),
        path=path,
        body=body,
    )


def _has_non_negated_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if not line:
            continue
        if any(
            negation in line
            for negation in ("do not", "don't", "never", "disabled", "reject", "forbidden", "no ")
        ):
            continue
        if any(
            re.search(rf"(?<![A-Za-z0-9_]){re.escape(phrase)}(?![A-Za-z0-9_])", line)
            for phrase in phrases
        ):
            return True
    return False


def _skill_dir_map(paths: ProjectPaths) -> dict[str, Path]:
    discovered: dict[str, Path] = {}
    if not paths.skills_dir.exists():
        return discovered
    for path in paths.skills_dir.iterdir():
        skill_path = path / "SKILL.md"
        if skill_path.exists():
            discovered[path.name] = skill_path
    return discovered


def _runtime_skill_names(config: dict[str, object]) -> list[str]:
    agents = config.get("agents")
    if not isinstance(agents, dict):
        return []
    defaults = agents.get("defaults")
    if not isinstance(defaults, dict):
        return []
    skills = defaults.get("skills")
    if not isinstance(skills, list) or not all(isinstance(item, str) for item in skills):
        return []
    return cast(list[str], skills)


def validate_skills(
    paths: ProjectPaths,
    rendered_config: dict[str, object] | None = None,
) -> SkillValidationReport:
    issues: list[SkillIssue] = []
    runtime_issues: list[SkillIssue] = []
    discovered: list[SkillDocument] = []
    seen_names: set[str] = set()
    catalog_paths = _skill_dir_map(paths)
    for folder_name in SKILL_NAMES:
        skill_path = catalog_paths.get(folder_name)
        if skill_path is None:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(paths.skills_dir / folder_name / "SKILL.md"),
                    "missing_file",
                    "Skill file is missing",
                )
            )
            continue
        try:
            skill = _parse_skill(skill_path)
        except ValueError as exc:
            issues.append(SkillIssue(folder_name, str(skill_path), "frontmatter", str(exc)))
            continue
        discovered.append(skill)
        if skill.name != folder_name:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "name_mismatch",
                    f"frontmatter name must be {folder_name}",
                )
            )
        if skill.version != __version__:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "version_mismatch",
                    f"frontmatter version must be {__version__}",
                )
            )
        expected_owner = next(
            (agent_id for agent_id, names in AGENT_SKILL_NAMES.items() if folder_name in names),
            None,
        )
        if expected_owner is None:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "owner_mismatch",
                    "skill is not assigned to a blueprint owner",
                )
            )
        elif skill.owner_agent != expected_owner:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "owner_mismatch",
                    f"owner_agent must be {expected_owner}",
                )
            )
        if skill.name in seen_names:
            issues.append(
                SkillIssue(folder_name, str(skill_path), "duplicate_name", "duplicate skill name")
            )
        seen_names.add(skill.name)
        if skill.owner_agent not in AGENT_ALLOWED_TOOLS:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "owner_mismatch",
                    f"unknown owner_agent {skill.owner_agent!r}",
                )
            )
        elif list(skill.allowed_tools) != list(AGENT_ALLOWED_TOOLS[skill.owner_agent]):
            issues.append(
                SkillIssue(
                    folder_name, str(skill_path), "tool_allow_mismatch", "allowed_tools mismatch"
                )
            )
        required_denies = {
            "group:runtime",
            "group:web",
            "group:ui",
            "group:automation",
            "group:messaging",
            "group:plugins",
            "group:memory",
            "group:sessions",
            "process",
            "code_execution",
            "browser",
            "canvas",
            "gateway",
            "message",
            "subagents",
        }
        # blueprint-coder is allowed write/edit/apply_patch in its isolated worktree;
        # exec is managed via exec.mode=allowlist rather than the deny list.
        if skill.owner_agent != "blueprint-coder":
            required_denies.update({"write", "edit", "apply_patch", "exec"})
        if not required_denies.issubset(set(skill.denied_tools)):
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "tool_deny_mismatch",
                    "denied_tools must include the full safety denylist",
                )
            )
        if _has_non_negated_phrase(
            skill.body,
            ("place order", "send order", "execute trade", "close position", "buy ", "sell "),
        ):
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "execution_instruction",
                    "execution instruction detected",
                )
            )
        if _has_non_negated_phrase(skill.body, ("entry", "stop loss", "take profit", "tp", "sl")):
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "market_number_generation",
                    "market number guidance detected",
                )
            )
        if _has_non_negated_phrase(
            skill.body,
            (
                "raise score",
                "lower score",
                "change score",
                "recalculate score",
                "modify evidence score",
            ),
        ):
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "evidence_score_mutation",
                    "score mutation instruction detected",
                )
            )
        lowered = skill.body.lower()
        if "sk-" in lowered or "ghp_" in lowered or "private key" in lowered:
            issues.append(
                SkillIssue(
                    folder_name, str(skill_path), "secret_pattern", "secret-like content detected"
                )
            )
        if not skill.safety_constraints:
            issues.append(
                SkillIssue(
                    folder_name,
                    str(skill_path),
                    "missing_contract",
                    "safety_constraints must not be empty",
                )
            )
        if not skill.tests:
            issues.append(
                SkillIssue(
                    folder_name, str(skill_path), "missing_contract", "tests must not be empty"
                )
            )
        # LC-014: Semantic depth validation — body must contain required operational sections
        body_lower = skill.body.lower()
        for required_section in ("## procedure", "## decision tree", "## failure mode"):
            if required_section not in body_lower:
                issues.append(
                    SkillIssue(
                        folder_name,
                        str(skill_path),
                        "shallow_skill",
                        f"body must contain a '{required_section}' section",
                    )
                )

    if rendered_config is not None:
        config_report = validate_rendered_config(rendered_config, paths)
        if not config_report.valid:
            for config_issue in config_report.issues:
                runtime_issues.append(
                    SkillIssue(
                        "runtime-discovery",
                        paths.config_template_path.as_posix(),
                        "config_validation",
                        f"{config_issue.path}: {config_issue.message}",
                    )
                )
        topology_report = validate_agent_topology(rendered_config, paths)
        if not topology_report.valid:
            for topology_issue in topology_report.issues:
                runtime_issues.append(
                    SkillIssue(
                        "runtime-discovery",
                        paths.config_template_path.as_posix(),
                        topology_issue.rule,
                        f"{topology_issue.path}: {topology_issue.message}",
                    )
                )
        agent_names = _runtime_skill_names(rendered_config)
        expected = list(SKILL_NAMES)
        if agent_names != expected:
            runtime_issues.append(
                SkillIssue(
                    "runtime-discovery",
                    paths.config_template_path.as_posix(),
                    "runtime_skills",
                    f"configured runtime skills must equal {expected!r}",
                )
            )

    orphan_skills = sorted(set(catalog_paths).difference(SKILL_NAMES))
    for orphan in orphan_skills:
        issues.append(
            SkillIssue(
                orphan,
                str(catalog_paths[orphan]),
                "orphan_skill",
                "skill exists but is not in the blueprint catalog",
            )
        )

    return SkillValidationReport(
        version=__version__,
        phase=PHASE,
        valid=not issues and not runtime_issues,
        skill_names=tuple(skill.name for skill in discovered),
        issues=tuple(issues),
        runtime_issues=tuple(runtime_issues),
    )
