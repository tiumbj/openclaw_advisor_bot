from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, cast

import yaml

from ._version import __version__
from .agent_topology import CODE_WORK_ORDER_ROUTE_ALLOWLIST
from .constants import (
    AGENT_ALLOWED_TOOLS,
    AGENT_DENIED_TOOLS,
    AGENT_SKILL_NAMES,
    RUNTIME_AGENT_IDS,
)
from .events import canonical_json, sha256_hex
from .paths import ProjectPaths

AGENT_REGISTRY_SCHEMA_VERSION = "1.0.0"
AGENT_REGISTRY_READY = "AGENT_REGISTRY_READY"
AGENT_REGISTRY_DEGRADED = "AGENT_REGISTRY_DEGRADED"
AGENT_REGISTRY_INVALID = "AGENT_REGISTRY_INVALID"

REQUIRED_AGENT_FIELDS = (
    "agent_id",
    "display_name",
    "role_summary",
    "primary_responsibilities",
    "accepted_task_types",
    "required_input_schema",
    "output_contract",
    "allowed_actions",
    "forbidden_actions",
    "allowed_tools",
    "forbidden_tools",
    "upstream_routes",
    "downstream_routes",
    "required_reviewers",
    "escalation_target",
    "human_release_gate_required",
    "may_modify_code",
    "may_commit",
    "may_push",
    "may_deploy",
    "may_publish_telegram",
    "may_access_browser",
    "may_access_secrets",
    "self_approval_allowed",
    "definition_source",
    "definition_version",
    "definition_hash",
)
OPTIONAL_AGENT_FIELDS = ("owned_skills",)
REQUIRED_REGISTRY_FIELDS = (
    "schema_version",
    "registry_version",
    "registry_hash",
    "generated_from",
    "generated_path",
    "generated_by",
    "agent_count",
    "skill_count",
    "agents",
)


@dataclass(frozen=True)
class AgentRegistryIssue:
    path: str
    rule: str
    message: str


@dataclass(frozen=True)
class AgentCapabilityRecord:
    agent_id: str
    display_name: str
    role_summary: str
    primary_responsibilities: tuple[str, ...]
    accepted_task_types: tuple[str, ...]
    required_input_schema: dict[str, Any]
    output_contract: dict[str, Any]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    upstream_routes: tuple[str, ...]
    downstream_routes: tuple[str, ...]
    required_reviewers: tuple[str, ...]
    escalation_target: str
    human_release_gate_required: bool
    may_modify_code: bool
    may_commit: bool
    may_push: bool
    may_deploy: bool
    may_publish_telegram: bool
    may_access_browser: bool
    may_access_secrets: bool
    self_approval_allowed: bool
    definition_source: str
    definition_version: str
    definition_hash: str
    owned_skills: tuple[str, ...]
    current_availability: str = "AVAILABLE"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "primary_responsibilities": list(self.primary_responsibilities),
            "accepted_task_types": list(self.accepted_task_types),
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
            "allowed_tools": list(self.allowed_tools),
            "forbidden_tools": list(self.forbidden_tools),
            "upstream_routes": list(self.upstream_routes),
            "downstream_routes": list(self.downstream_routes),
            "required_reviewers": list(self.required_reviewers),
            "owned_skills": list(self.owned_skills),
        }


@dataclass(frozen=True)
class AgentCapabilityRegistry:
    schema_version: str
    registry_version: str
    registry_hash: str
    generated_from: str
    generated_path: str
    generated_by: str
    agent_count: int
    skill_count: int
    agents: tuple[AgentCapabilityRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "registry_version": self.registry_version,
            "registry_hash": self.registry_hash,
            "generated_from": self.generated_from,
            "generated_path": self.generated_path,
            "generated_by": self.generated_by,
            "agent_count": self.agent_count,
            "skill_count": self.skill_count,
            "agents": [agent.to_dict() for agent in self.agents],
        }

    def get_agent_capability(self, agent_id: str) -> AgentCapabilityRecord:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        raise KeyError(agent_id)

    def list_available_agents(self) -> tuple[AgentCapabilityRecord, ...]:
        return tuple(agent for agent in self.agents if agent.current_availability == "AVAILABLE")

    def find_agents_for_task(self, task_type: str) -> tuple[AgentCapabilityRecord, ...]:
        return tuple(agent for agent in self.agents if task_type in agent.accepted_task_types)

    def validate_agent_route(
        self, source_agent: str, target_agent: str, task_type: str
    ) -> tuple[bool, str]:
        try:
            source = self.get_agent_capability(source_agent)
            target = self.get_agent_capability(target_agent)
        except KeyError as exc:
            return False, f"unknown agent id {exc.args[0]!r}"
        if target_agent not in source.downstream_routes:
            return False, f"{source_agent!r} is not allowed to route to {target_agent!r}"
        if task_type not in target.accepted_task_types:
            return False, f"{target_agent!r} does not accept task_type {task_type!r}"
        return True, "route_allowed"


@dataclass(frozen=True)
class AgentRegistryValidationReport:
    valid: bool
    status: str
    registry: AgentCapabilityRegistry | None
    issues: tuple[AgentRegistryIssue, ...]
    missing_agent_count: int
    duplicate_agent_count: int
    registry_config_mismatch_count: int


@dataclass(frozen=True)
class RoutingDecision:
    selected_agent: str | None
    reason_for_selection: str
    rejected_candidates: tuple[dict[str, str], ...]
    required_review_chain: tuple[str, ...]
    safety_restrictions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_agent": self.selected_agent,
            "reason_for_selection": self.reason_for_selection,
            "rejected_candidates": list(self.rejected_candidates),
            "required_review_chain": list(self.required_review_chain),
            "safety_restrictions": list(self.safety_restrictions),
        }


@dataclass(frozen=True)
class ManagerQueryResponse:
    query: str
    source: str
    registry_version: str
    registry_hash: str
    agents: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "source": self.source,
            "registry_version": self.registry_version,
            "registry_hash": self.registry_hash,
            "agents": list(self.agents),
        }


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path} must start with YAML frontmatter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{path} must contain a closing YAML frontmatter block")
    return parts[1], parts[2]


def _as_string(value: Any, field_name: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} field {field_name} must be a non-empty string")
    return value.strip()


def _as_bool(value: Any, field_name: str, path: Path) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path} field {field_name} must be a boolean")
    return value


def _as_string_tuple(value: Any, field_name: str, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path} field {field_name} must be a non-empty string list")
    return tuple(item.strip() for item in cast(list[str], value) if item.strip())


def _as_object(value: Any, field_name: str, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} field {field_name} must be an object")
    return cast(dict[str, Any], value)


def _agent_definition_hash(metadata: dict[str, Any]) -> str:
    sanitized = dict(metadata)
    sanitized.pop("definition_hash", None)
    sanitized.pop("definition_source", None)
    return sha256_hex(canonical_json(sanitized))


def _registry_payload_hash(payload: dict[str, Any]) -> str:
    return sha256_hex(
        canonical_json(
            {
                "schema_version": payload.get("schema_version"),
                "registry_version": payload.get("registry_version"),
                "generated_from": payload.get("generated_from"),
                "generated_path": payload.get("generated_path"),
                "generated_by": payload.get("generated_by"),
                "agent_count": payload.get("agent_count"),
                "skill_count": payload.get("skill_count"),
                "agents": payload.get("agents"),
            }
        )
    )


def _safe_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def parse_agent_markdown(path: Path) -> AgentCapabilityRecord:
    frontmatter_text, _ = _split_frontmatter(path.read_text(encoding="utf-8"), path)
    loaded = yaml.safe_load(frontmatter_text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} frontmatter must be a mapping")
    metadata = cast(dict[str, Any], loaded)
    allowed_fields = set(REQUIRED_AGENT_FIELDS).union(OPTIONAL_AGENT_FIELDS).difference(
        {"definition_source", "definition_hash"}
    )
    unknown_fields = sorted(set(metadata).difference(allowed_fields))
    if unknown_fields:
        raise ValueError(f"{path} frontmatter has unknown fields: {', '.join(unknown_fields)}")
    missing = [
        field
        for field in REQUIRED_AGENT_FIELDS
        if field not in {"definition_source", "definition_hash"} and field not in metadata
    ]
    if missing:
        raise ValueError(f"{path} frontmatter missing fields: {', '.join(missing)}")
    metadata["definition_source"] = str(path).replace("\\", "/")
    metadata["definition_hash"] = _agent_definition_hash(metadata)
    owned_skills = tuple(cast(list[str], metadata.get("owned_skills", [])))
    return AgentCapabilityRecord(
        agent_id=_as_string(metadata.get("agent_id"), "agent_id", path),
        display_name=_as_string(metadata.get("display_name"), "display_name", path),
        role_summary=_as_string(metadata.get("role_summary"), "role_summary", path),
        primary_responsibilities=_as_string_tuple(
            metadata.get("primary_responsibilities"), "primary_responsibilities", path
        ),
        accepted_task_types=_as_string_tuple(
            metadata.get("accepted_task_types"), "accepted_task_types", path
        ),
        required_input_schema=_as_object(
            metadata.get("required_input_schema"), "required_input_schema", path
        ),
        output_contract=_as_object(metadata.get("output_contract"), "output_contract", path),
        allowed_actions=_as_string_tuple(metadata.get("allowed_actions"), "allowed_actions", path),
        forbidden_actions=_as_string_tuple(
            metadata.get("forbidden_actions"), "forbidden_actions", path
        ),
        allowed_tools=_as_string_tuple(metadata.get("allowed_tools"), "allowed_tools", path),
        forbidden_tools=_as_string_tuple(metadata.get("forbidden_tools"), "forbidden_tools", path),
        upstream_routes=_as_string_tuple(metadata.get("upstream_routes"), "upstream_routes", path),
        downstream_routes=_as_string_tuple(
            metadata.get("downstream_routes"), "downstream_routes", path
        ),
        required_reviewers=_as_string_tuple(
            metadata.get("required_reviewers"), "required_reviewers", path
        ),
        escalation_target=_as_string(metadata.get("escalation_target"), "escalation_target", path),
        human_release_gate_required=_as_bool(
            metadata.get("human_release_gate_required"), "human_release_gate_required", path
        ),
        may_modify_code=_as_bool(metadata.get("may_modify_code"), "may_modify_code", path),
        may_commit=_as_bool(metadata.get("may_commit"), "may_commit", path),
        may_push=_as_bool(metadata.get("may_push"), "may_push", path),
        may_deploy=_as_bool(metadata.get("may_deploy"), "may_deploy", path),
        may_publish_telegram=_as_bool(
            metadata.get("may_publish_telegram"), "may_publish_telegram", path
        ),
        may_access_browser=_as_bool(metadata.get("may_access_browser"), "may_access_browser", path),
        may_access_secrets=_as_bool(metadata.get("may_access_secrets"), "may_access_secrets", path),
        self_approval_allowed=_as_bool(
            metadata.get("self_approval_allowed"), "self_approval_allowed", path
        ),
        definition_source=str(path).replace("\\", "/"),
        definition_version=_as_string(
            metadata.get("definition_version"), "definition_version", path
        ),
        definition_hash=cast(str, metadata["definition_hash"]),
        owned_skills=owned_skills,
    )


def build_agent_registry(paths: ProjectPaths) -> AgentCapabilityRegistry:
    agents: list[AgentCapabilityRecord] = []
    for agent_id in RUNTIME_AGENT_IDS:
        agent_path = paths.agents_dir / agent_id / "AGENT.md"
        agents.append(parse_agent_markdown(agent_path))
    payload = {
        "schema_version": AGENT_REGISTRY_SCHEMA_VERSION,
        "registry_version": __version__,
        "generated_from": str(paths.agents_dir).replace("\\", "/"),
        "generated_path": str(paths.agent_registry_path).replace("\\", "/"),
        "generated_by": "openclaw-advisor validate-agent-registry --write",
        "agent_count": len(agents),
        "skill_count": sum(len(agent.owned_skills) for agent in agents),
        "agents": [agent.to_dict() for agent in agents],
    }
    registry_hash = sha256_hex(canonical_json(payload))
    return AgentCapabilityRegistry(
        schema_version=AGENT_REGISTRY_SCHEMA_VERSION,
        registry_version=__version__,
        registry_hash=registry_hash,
        generated_from=str(paths.agents_dir).replace("\\", "/"),
        generated_path=str(paths.agent_registry_path).replace("\\", "/"),
        generated_by="openclaw-advisor validate-agent-registry --write",
        agent_count=len(agents),
        skill_count=sum(len(agent.owned_skills) for agent in agents),
        agents=tuple(agents),
    )


def _expected_review_chain() -> tuple[str, ...]:
    return (*tuple(source for source, _ in CODE_WORK_ORDER_ROUTE_ALLOWLIST), "super-advisor")


def _validate_generated_registry_payload(
    payload: Any,
    *,
    paths: ProjectPaths,
    expected_registry: AgentCapabilityRegistry,
) -> tuple[AgentRegistryIssue, ...]:
    issues: list[AgentRegistryIssue] = []
    if not isinstance(payload, dict):
        return (
            AgentRegistryIssue(
                str(paths.agent_registry_path),
                "malformed_json",
                "generated registry must decode to an object",
            ),
        )
    missing_fields = [field for field in REQUIRED_REGISTRY_FIELDS if field not in payload]
    for field in missing_fields:
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.{field}",
                "missing_field",
                f"generated registry field {field!r} is required",
            )
        )
    schema_version = payload.get("schema_version")
    if schema_version in (None, ""):
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.schema_version",
                "missing_schema_version",
                "generated registry schema_version is required",
            )
        )
    elif schema_version != AGENT_REGISTRY_SCHEMA_VERSION:
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.schema_version",
                "unsupported_schema_version",
                "generated registry schema_version is unsupported",
            )
        )
    registry_hash = payload.get("registry_hash")
    if not isinstance(registry_hash, str) or not registry_hash.strip():
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.registry_hash",
                "missing_registry_hash",
                "generated registry registry_hash is required",
            )
        )
    elif registry_hash != _registry_payload_hash(cast(dict[str, Any], payload)):
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.registry_hash",
                "invalid_registry_hash",
                "generated registry registry_hash does not match its content",
            )
        )
    agents_payload = payload.get("agents")
    if not isinstance(agents_payload, list):
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.agents",
                "malformed_agents",
                "generated registry agents must be a list",
            )
        )
        agents_payload = []
    if payload.get("agent_count") != len(agents_payload):
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.agent_count",
                "agent_count_mismatch",
                "generated registry agent_count must match the number of agents",
            )
        )
    generated_agent_ids: list[str] = []
    expected_agent_ids = {agent.agent_id for agent in expected_registry.agents}
    for index, item in enumerate(agents_payload):
        if not isinstance(item, dict):
            issues.append(
                AgentRegistryIssue(
                    f"{paths.agent_registry_path}.agents[{index}]",
                    "malformed_agent",
                    "generated registry agent entries must be objects",
                )
            )
            continue
        agent_id = item.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id.strip():
            issues.append(
                AgentRegistryIssue(
                    f"{paths.agent_registry_path}.agents[{index}].agent_id",
                    "missing_agent_id",
                    "generated registry agent_id is required",
                )
            )
            continue
        generated_agent_ids.append(agent_id)
        for field_name in ("primary_responsibilities", "accepted_task_types", "required_reviewers"):
            field_value = item.get(field_name)
            if field_value is None:
                issues.append(
                    AgentRegistryIssue(
                        f"{paths.agent_registry_path}.agents[{index}].{field_name}",
                        "missing_field",
                        f"generated registry field {field_name!r} is required for {agent_id!r}",
                    )
                )
                continue
            if not isinstance(field_value, list) or not field_value:
                issues.append(
                    AgentRegistryIssue(
                        f"{paths.agent_registry_path}.agents[{index}].{field_name}",
                        "empty_field",
                        f"generated registry field {field_name!r} must be a non-empty list",
                    )
                )
        definition_source = item.get("definition_source")
        if not isinstance(definition_source, str) or not definition_source.strip():
            issues.append(
                AgentRegistryIssue(
                    f"{paths.agent_registry_path}.agents[{index}].definition_source",
                    "missing_definition_source",
                    "generated registry definition_source is required",
                )
            )
        else:
            source_path = Path(definition_source)
            if ".." in source_path.parts:
                issues.append(
                    AgentRegistryIssue(
                        f"{paths.agent_registry_path}.agents[{index}].definition_source",
                        "path_traversal",
                        "generated registry definition_source may not contain parent traversal",
                    )
                )
            elif not _safe_relative_to(source_path, paths.agents_dir):
                issues.append(
                    AgentRegistryIssue(
                        f"{paths.agent_registry_path}.agents[{index}].definition_source",
                        "invalid_definition_source",
                        "generated registry definition_source must stay within workspace/agents",
                    )
                )
        upstream_routes = item.get("upstream_routes", [])
        downstream_routes = item.get("downstream_routes", [])
        required_reviewers = item.get("required_reviewers", [])
        escalation_target = item.get("escalation_target")
        if isinstance(downstream_routes, list) and agent_id in downstream_routes:
            issues.append(
                AgentRegistryIssue(
                    f"{paths.agent_registry_path}.agents[{index}].downstream_routes",
                    "forbidden_self_route",
                    "generated registry agent may not route to itself",
                )
            )
        if (
            agent_id != "super-advisor"
            and isinstance(required_reviewers, list)
            and agent_id in required_reviewers
        ):
            issues.append(
                AgentRegistryIssue(
                    f"{paths.agent_registry_path}.agents[{index}].required_reviewers",
                    "self_approval_reviewer_chain",
                    "generated registry reviewer chain may not self-approve",
                )
            )
        if isinstance(item.get("allowed_actions"), list) and isinstance(
            item.get("forbidden_actions"), list
        ):
            allowed = {str(value).strip().lower() for value in item["allowed_actions"]}
            forbidden = {str(value).strip().lower() for value in item["forbidden_actions"]}
            if allowed.intersection(forbidden):
                issues.append(
                    AgentRegistryIssue(
                        f"{paths.agent_registry_path}.agents[{index}]",
                        "contradictory_actions",
                        "generated registry allowed_actions and forbidden_actions conflict",
                    )
                )
        for route_kind, route_targets in (
            ("upstream_routes", upstream_routes),
            ("downstream_routes", downstream_routes),
            ("required_reviewers", required_reviewers),
        ):
            if isinstance(route_targets, list):
                for target in route_targets:
                    if target not in expected_agent_ids:
                        issues.append(
                            AgentRegistryIssue(
                                f"{paths.agent_registry_path}.agents[{index}].{route_kind}",
                                "unknown_route_agent",
                                f"generated registry references unknown agent {target!r}",
                            )
                        )
        if escalation_target not in expected_agent_ids:
            issues.append(
                AgentRegistryIssue(
                    f"{paths.agent_registry_path}.agents[{index}].escalation_target",
                    "unknown_escalation_target",
                    "generated registry escalation_target must reference a known agent",
                )
            )
    if len(generated_agent_ids) != len(set(generated_agent_ids)):
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.agents",
                "duplicate_agent",
                "generated registry contains duplicate agent ids",
            )
        )
    if "super-advisor" not in generated_agent_ids:
        issues.append(
            AgentRegistryIssue(
                f"{paths.agent_registry_path}.agents",
                "missing_super_advisor",
                "generated registry must include super-advisor",
            )
        )
    if set(generated_agent_ids) != expected_agent_ids:
        issues.append(
            AgentRegistryIssue(
                str(paths.agent_registry_path),
                "registry_agent_set_mismatch",
                "generated registry agent set does not match AGENT.md definitions",
            )
        )
    if cast(dict[str, Any], payload) != expected_registry.to_dict():
        issues.append(
            AgentRegistryIssue(
                str(paths.agent_registry_path),
                "stale_registry",
                "generated registry does not match AGENT.md definitions",
            )
        )
    return tuple(issues)


def validate_agent_registry(
    paths: ProjectPaths,
    *,
    rendered_config: dict[str, object] | None = None,
    require_generated_file: bool = False,
) -> AgentRegistryValidationReport:
    issues: list[AgentRegistryIssue] = []
    registry = None
    duplicate_agent_count = 0
    mismatch_count = 0
    try:
        registry = build_agent_registry(paths)
    except (FileNotFoundError, ValueError) as exc:
        issues.append(AgentRegistryIssue("agent_registry", "parse_error", str(exc)))
        return AgentRegistryValidationReport(
            valid=False,
            status=AGENT_REGISTRY_INVALID,
            registry=None,
            issues=tuple(issues),
            missing_agent_count=len(RUNTIME_AGENT_IDS),
            duplicate_agent_count=0,
            registry_config_mismatch_count=0,
        )

    seen: set[str] = set()
    for index, agent in enumerate(registry.agents):
        if agent.agent_id in seen:
            duplicate_agent_count += 1
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].agent_id",
                    "duplicate_agent",
                    f"duplicate agent id {agent.agent_id!r}",
                )
            )
        seen.add(agent.agent_id)
        if not agent.primary_responsibilities:
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].primary_responsibilities",
                    "missing",
                    "primary responsibilities are required",
                )
            )
        if agent.allowed_tools != AGENT_ALLOWED_TOOLS.get(agent.agent_id, ()):
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].allowed_tools",
                    "tool_allow_mismatch",
                    "registry allowed_tools must match runtime constants",
                )
            )
        if agent.definition_version != __version__:
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].definition_version",
                    "version_mismatch",
                    f"definition_version must be {__version__}",
                )
            )
        if agent.forbidden_tools != AGENT_DENIED_TOOLS.get(agent.agent_id, ()):
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].forbidden_tools",
                    "tool_deny_mismatch",
                    "registry forbidden_tools must match runtime constants",
                )
            )
        if agent.owned_skills != AGENT_SKILL_NAMES.get(agent.agent_id, ()):
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].owned_skills",
                    "skill_catalog_mismatch",
                    "registry owned_skills must match runtime skill ownership",
                )
            )
        if agent.agent_id in {
            "system-coder-auditor",
            "security-compliance-agent",
            "blueprint-coder",
        }:
            if agent.self_approval_allowed:
                issues.append(
                    AgentRegistryIssue(
                        f"agents[{index}].self_approval_allowed",
                        "forbidden",
                        f"{agent.agent_id} cannot self-approve",
                    )
                )
        if agent.agent_id == "blueprint-coder" and not agent.may_modify_code:
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].may_modify_code",
                    "missing_capability",
                    "blueprint-coder must be the code-modifying agent",
                )
            )
        if agent.may_push and not agent.may_commit:
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}]",
                    "contradictory_permissions",
                    "may_push cannot be true when may_commit is false",
                )
            )
        if agent.may_deploy and not agent.may_push:
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}]",
                    "contradictory_permissions",
                    "may_deploy cannot be true when may_push is false",
                )
            )
        if agent.may_publish_telegram and agent.agent_id != "telegram-publisher":
            issues.append(
                AgentRegistryIssue(
                    f"agents[{index}].may_publish_telegram",
                    "forbidden",
                    "only telegram-publisher may publish Telegram content",
                )
            )

    expected_ids = set(RUNTIME_AGENT_IDS)
    missing_agent_count = len(expected_ids.difference(seen))
    for source in registry.agents:
        for route_kind, route_targets in (
            ("upstream_routes", source.upstream_routes),
            ("downstream_routes", source.downstream_routes),
            ("required_reviewers", source.required_reviewers),
        ):
            for target in route_targets:
                if target not in expected_ids:
                    issues.append(
                        AgentRegistryIssue(
                            f"{source.agent_id}.{route_kind}",
                            "unknown_agent",
                            f"unknown route target {target!r}",
                        )
                    )
        if source.escalation_target not in expected_ids:
            issues.append(
                AgentRegistryIssue(
                    f"{source.agent_id}.escalation_target",
                    "unknown_agent",
                    f"unknown escalation_target {source.escalation_target!r}",
                )
            )

    if registry.get_agent_capability("blueprint-coder").required_reviewers != (
        "system-coder-auditor",
        "security-compliance-agent",
        "super-advisor",
    ):
        issues.append(
            AgentRegistryIssue(
                "blueprint-coder.required_reviewers",
                "review_chain_mismatch",
                (
                    "blueprint-coder must route through system-coder-auditor, "
                    "security-compliance-agent, and super-advisor"
                ),
            )
        )

    if require_generated_file:
        if not paths.agent_registry_path.exists():
            issues.append(
                AgentRegistryIssue(
                    str(paths.agent_registry_path),
                    "missing_file",
                    "generated agent registry file is missing",
                )
            )
        else:
            try:
                generated_payload = json.loads(
                    paths.agent_registry_path.read_text(encoding="utf-8")
                )
            except JSONDecodeError:
                issues.append(
                    AgentRegistryIssue(
                        str(paths.agent_registry_path),
                        "malformed_json",
                        "generated agent registry file is not valid JSON",
                    )
                )
            else:
                issues.extend(
                    _validate_generated_registry_payload(
                        generated_payload,
                        paths=paths,
                        expected_registry=registry,
                    )
                )

    if rendered_config is not None:
        registry_meta = rendered_config.get("agentCapabilityRegistry")
        if not isinstance(registry_meta, dict):
            mismatch_count += 1
            issues.append(
                AgentRegistryIssue(
                    "agentCapabilityRegistry",
                    "missing",
                    "rendered config must expose agentCapabilityRegistry metadata",
                )
            )
        else:
            if registry_meta.get("registryHash") != registry.registry_hash:
                mismatch_count += 1
                issues.append(
                    AgentRegistryIssue(
                        "agentCapabilityRegistry.registryHash",
                        "mismatch",
                        "rendered config registryHash must match the validated registry",
                    )
                )
            if registry_meta.get("agentCount") != registry.agent_count:
                mismatch_count += 1
                issues.append(
                    AgentRegistryIssue(
                        "agentCapabilityRegistry.agentCount",
                        "mismatch",
                        "rendered config agentCount must match the validated registry",
                    )
                )
        agents_section = rendered_config.get("agents")
        if isinstance(agents_section, dict):
            agent_list = agents_section.get("list")
            if isinstance(agent_list, list):
                config_agents = {
                    str(item.get("id")): cast(dict[str, Any], item)
                    for item in agent_list
                    if isinstance(item, dict)
                }
                for agent in registry.agents:
                    config_agent = config_agents.get(agent.agent_id)
                    if config_agent is None:
                        mismatch_count += 1
                        issues.append(
                            AgentRegistryIssue(
                                f"agents.list.{agent.agent_id}",
                                "missing",
                                "rendered config is missing a registered agent",
                            )
                        )
                        continue
                    if tuple(config_agent.get("skills", [])) != agent.owned_skills:
                        mismatch_count += 1
                        issues.append(
                            AgentRegistryIssue(
                                f"agents.list.{agent.agent_id}.skills",
                                "mismatch",
                                "rendered config skills must match the registry",
                            )
                        )
                    tools = config_agent.get("tools", {})
                    if (
                        isinstance(tools, dict)
                        and tuple(tools.get("allow", [])) != agent.allowed_tools
                    ):
                        mismatch_count += 1
                        issues.append(
                            AgentRegistryIssue(
                                f"agents.list.{agent.agent_id}.tools.allow",
                                "mismatch",
                                "rendered config tool allowlist must match the registry",
                            )
                        )
        else:
            mismatch_count += 1
            issues.append(
                AgentRegistryIssue(
                    "agents",
                    "missing",
                    "rendered config agents section is required for registry validation",
                )
            )

    status = AGENT_REGISTRY_READY
    if issues:
        degraded_rules = {"missing_file", "stale_registry"}
        status = (
            AGENT_REGISTRY_DEGRADED
            if all(issue.rule in degraded_rules for issue in issues)
            else AGENT_REGISTRY_INVALID
        )
    return AgentRegistryValidationReport(
        valid=not issues,
        status=status,
        registry=registry,
        issues=tuple(issues),
        missing_agent_count=missing_agent_count,
        duplicate_agent_count=duplicate_agent_count,
        registry_config_mismatch_count=mismatch_count,
    )


class ManagerRegistryRuntime:
    def __init__(self, registry: AgentCapabilityRegistry, status: str) -> None:
        self._registry = registry
        self.status = status

    @classmethod
    def load(
        cls, paths: ProjectPaths, rendered_config: dict[str, object]
    ) -> ManagerRegistryRuntime:
        report = validate_agent_registry(
            paths,
            rendered_config=rendered_config,
            require_generated_file=True,
        )
        if not report.valid or report.registry is None:
            raise RuntimeError(
                "agent registry is not ready: "
                + "; ".join(f"{issue.path}: {issue.message}" for issue in report.issues)
            )
        return cls(report.registry, report.status)

    def get_agent_registry(self) -> AgentCapabilityRegistry:
        return self._registry

    def get_agent_capability(self, agent_id: str) -> AgentCapabilityRecord:
        return self._registry.get_agent_capability(agent_id)

    def list_available_agents(self) -> tuple[AgentCapabilityRecord, ...]:
        return self._registry.list_available_agents()

    def find_agents_for_task(self, task_type: str) -> tuple[AgentCapabilityRecord, ...]:
        return self._registry.find_agents_for_task(task_type)

    def validate_agent_route(
        self, source_agent: str, target_agent: str, task_type: str
    ) -> tuple[bool, str]:
        return self._registry.validate_agent_route(source_agent, target_agent, task_type)

    def route_task(self, task_type: str, *, source_agent: str = "super-advisor") -> RoutingDecision:
        rejected: list[dict[str, str]] = []
        for candidate in self.list_available_agents():
            if task_type not in candidate.accepted_task_types:
                rejected.append(
                    {"agent_id": candidate.agent_id, "reason": "task_type_not_accepted"}
                )
                continue
            allowed, reason = self.validate_agent_route(source_agent, candidate.agent_id, task_type)
            if not allowed:
                rejected.append({"agent_id": candidate.agent_id, "reason": reason})
                continue
            safety = tuple(candidate.forbidden_actions[:3]) + tuple(
                f"allowed_tools={','.join(candidate.allowed_tools)}",
            )
            return RoutingDecision(
                selected_agent=candidate.agent_id,
                reason_for_selection=(
                    f"{candidate.agent_id} accepts task_type {task_type!r} and is reachable from "
                    f"{source_agent!r} under the validated registry"
                ),
                rejected_candidates=tuple(rejected),
                required_review_chain=candidate.required_reviewers,
                safety_restrictions=safety,
            )
        return RoutingDecision(
            selected_agent=None,
            reason_for_selection=f"no validated agent accepted task_type {task_type!r}",
            rejected_candidates=tuple(rejected),
            required_review_chain=(),
            safety_restrictions=("fail_closed",),
        )

    def answer_agent_duties_query(self, query: str) -> ManagerQueryResponse:
        agents = tuple(
            {
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "role_summary": agent.role_summary,
                "primary_responsibilities": list(agent.primary_responsibilities),
                "forbidden_actions": list(agent.forbidden_actions),
                "current_availability": agent.current_availability,
                "registry_definition_source": agent.definition_source,
                "registry_version": agent.definition_version,
                "registry_schema_version": self._registry.schema_version,
                "registry_definition_hash": self._registry.registry_hash,
            }
            for agent in self._registry.agents
        )
        return ManagerQueryResponse(
            query=query,
            source="validated_agent_capability_registry",
            registry_version=self._registry.registry_version,
            registry_hash=self._registry.registry_hash,
            agents=agents,
        )

    def handle_manager_query(self, query: str) -> dict[str, Any]:
        normalized = query.strip().lower()
        if any(token in normalized for token in ("code", "review", "ตรวจ")):
            decision = self.route_task("code_review")
            return {
                "query_type": "routing_explanation",
                "response": {
                    "registry_version": self._registry.registry_version,
                    "registry_hash": self._registry.registry_hash,
                    "task_type": "code_review",
                    **decision.to_dict(),
                    "human_release_gate_required": self.get_agent_capability(
                        decision.selected_agent or "system-coder-auditor"
                    ).human_release_gate_required
                    if decision.selected_agent
                    else True,
                    "forbidden_actions": list(
                        self.get_agent_capability(decision.selected_agent).forbidden_actions
                    )
                    if decision.selected_agent
                    else [],
                },
            }
        if "อะไรก็ได้" in normalized or "ใกล้เคียง" in normalized:
            decision = self.route_task("unknown_task_type")
            return {
                "query_type": "routing_explanation",
                "response": {
                    "registry_version": self._registry.registry_version,
                    "registry_hash": self._registry.registry_hash,
                    "task_type": "unknown_task_type",
                    **decision.to_dict(),
                },
            }
        if any(token in normalized for token in ("agent", "หน้าที่", "มี agent", "ห้ามทำอะไร")):
            return {
                "query_type": "agent_catalog_query",
                "response": self.answer_agent_duties_query(query).to_dict(),
            }
        return {
            "query_type": "unclassified",
            "response": {
                "registry_version": self._registry.registry_version,
                "registry_hash": self._registry.registry_hash,
                "error": "query could not be classified against the validated registry",
            },
        }
