from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from ._version import PHASE, __version__
from .config import validate_rendered_config
from .constants import SKILL_NAMES
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


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path} must start with YAML frontmatter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{path} must contain a closing YAML frontmatter block")
    return parts[1], parts[2]


def _parse_skill(path: Path) -> SkillDocument:
    frontmatter_text, body = _split_frontmatter(path.read_text(encoding="utf-8"), path)
    loaded = yaml.safe_load(frontmatter_text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} frontmatter must be a mapping")
    metadata = cast(dict[str, object], loaded)
    name = metadata.get("name")
    description = metadata.get("description")
    version = metadata.get("version")
    if (
        not isinstance(name, str)
        or not isinstance(description, str)
        or not isinstance(version, str)
    ):
        raise ValueError(
            f"{path} frontmatter must define string name, description, and version"
        )
    return SkillDocument(name=name, description=description, version=version, path=path, body=body)


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


def validate_skills(
    paths: ProjectPaths,
    rendered_config: dict[str, object] | None = None,
) -> SkillValidationReport:
    issues: list[SkillIssue] = []
    runtime_issues: list[SkillIssue] = []
    discovered: list[SkillDocument] = []
    seen_names: set[str] = set()
    for folder_name in SKILL_NAMES:
        skill_path = paths.skills_dir / folder_name / "SKILL.md"
        if not skill_path.exists():
            issues.append(
                SkillIssue(folder_name, str(skill_path), "missing_file", "Skill file is missing")
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
        if skill.name in seen_names:
            issues.append(
                SkillIssue(folder_name, str(skill_path), "duplicate_name", "duplicate skill name")
            )
        seen_names.add(skill.name)
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
                    folder_name,
                    str(skill_path),
                    "secret_pattern",
                    "secret-like content detected",
                )
            )

    if rendered_config is not None:
        config_report = validate_rendered_config(rendered_config, paths)
        if not config_report.valid:
            for item in config_report.issues:
                runtime_issues.append(
                    SkillIssue(
                        "runtime-discovery",
                        paths.config_template_path.as_posix(),
                        "config_validation",
                        f"{item.path}: {item.message}",
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

    return SkillValidationReport(
        version=__version__,
        phase=PHASE,
        valid=not issues and not runtime_issues,
        skill_names=tuple(skill.name for skill in discovered),
        issues=tuple(issues),
        runtime_issues=tuple(runtime_issues),
    )


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
