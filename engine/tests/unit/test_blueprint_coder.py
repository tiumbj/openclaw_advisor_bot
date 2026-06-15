"""Unit tests for blueprint-coder agent isolation, CodeWorkOrder schema, and routing gates.

25 tests covering:
- CodeWorkOrder schema validation (T01-T06)
- Blueprint-coder topology (T07-T09)
- Exec allowlist enforcement (T10-T13)
- Self-approval prevention (T14)
- Route allowlist (T15-T18)
- Tool permission boundaries (T19-T22)
- Intent gate (T23-T24)
- File scope enforcement (T25)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.agent_topology import (
    CODE_WORK_ORDER_ROUTE_ALLOWLIST,
    build_agent_topology,
    validate_routing,
)
from openclaw_super_advisor.code_work_order import (
    CodeWorkOrder,
    CodeWorkOrderError,
    check_self_approval,
    validate_exec_command,
    validate_file_scope,
)
from openclaw_super_advisor.constants import (
    AGENT_ALLOWED_TOOLS,
    AGENT_DENIED_TOOLS,
    AGENT_SKILL_NAMES,
)
from openclaw_super_advisor.constants import (
    BLUEPRINT_CODER_EXEC_ALLOWLIST as CONST_EXEC_ALLOWLIST,
)
from openclaw_super_advisor.paths import build_paths

# ---------------------------------------------------------------------------
# T01-T06: CodeWorkOrder schema validation
# ---------------------------------------------------------------------------

_VALID_WO = {
    "baseline_commit": "abc1234def5678",
    "scope": ["engine/src/openclaw_super_advisor/constants.py"],
    "intent": "APPLY_IMPROVEMENT",
    "description": "Add blueprint-coder to RUNTIME_AGENT_IDS",
    "acceptance_criteria": ["RUNTIME_AGENT_IDS contains blueprint-coder"],
    "human_release_gate_required": True,
    "initiated_by": "super-advisor",
    "task_id": "task-001",
    "worktree_path": "/tmp/worktree/task-001",
}


def test_code_work_order_schema_valid() -> None:
    """T01: A fully populated CodeWorkOrder round-trips through from_dict/to_dict."""
    wo = CodeWorkOrder.from_dict(_VALID_WO)
    assert wo.intent == "APPLY_IMPROVEMENT"
    assert wo.human_release_gate_required is True
    assert wo.initiated_by == "super-advisor"
    assert wo.to_dict() == _VALID_WO


def test_code_work_order_rejects_missing_baseline_commit() -> None:
    """T02: Missing baseline_commit raises CodeWorkOrderError."""
    bad = {**_VALID_WO}
    del bad["baseline_commit"]
    with pytest.raises(CodeWorkOrderError, match="baseline_commit"):
        CodeWorkOrder.from_dict(bad)


def test_code_work_order_rejects_missing_scope() -> None:
    """T03: Empty scope list raises CodeWorkOrderError."""
    bad = {**_VALID_WO, "scope": []}
    with pytest.raises(CodeWorkOrderError, match="scope"):
        CodeWorkOrder.from_dict(bad)


def test_code_work_order_rejects_wrong_intent() -> None:
    """T04: intent not equal to APPLY_IMPROVEMENT is rejected."""
    bad = {**_VALID_WO, "intent": "MARKET_ANALYSIS"}
    with pytest.raises(CodeWorkOrderError, match="APPLY_IMPROVEMENT"):
        CodeWorkOrder.from_dict(bad)


def test_code_work_order_rejects_missing_acceptance_criteria() -> None:
    """T05: Empty acceptance_criteria list raises CodeWorkOrderError."""
    bad = {**_VALID_WO, "acceptance_criteria": []}
    with pytest.raises(CodeWorkOrderError, match="acceptance_criteria"):
        CodeWorkOrder.from_dict(bad)


def test_code_work_order_human_release_gate_required() -> None:
    """T06: human_release_gate_required=False raises CodeWorkOrderError."""
    bad = {**_VALID_WO, "human_release_gate_required": False}
    with pytest.raises(CodeWorkOrderError, match="human_release_gate_required"):
        CodeWorkOrder.from_dict(bad)


# ---------------------------------------------------------------------------
# T07-T09: Blueprint-coder in topology
# ---------------------------------------------------------------------------

def test_blueprint_coder_in_topology_as_13th_agent(sample_project: Path) -> None:
    """T07: blueprint-coder is the 13th agent in the runtime topology."""
    paths = build_paths(Path(sample_project))
    agents = build_agent_topology(paths)
    agent_ids = [a.agent_id for a in agents]
    assert "blueprint-coder" in agent_ids
    assert len(agent_ids) == 13
    assert agent_ids.index("blueprint-coder") == 12  # last in the tuple


def test_blueprint_coder_has_18_skills() -> None:
    """T08: blueprint-coder owns exactly 18 skills."""
    skills = AGENT_SKILL_NAMES["blueprint-coder"]
    assert len(skills) == 18


def test_blueprint_coder_skills_include_isolated_worktree_patching() -> None:
    """T09: isolated-worktree-patching is in blueprint-coder skills."""
    assert "isolated-worktree-patching" in AGENT_SKILL_NAMES["blueprint-coder"]
    assert "release-and-rollback-planning" in AGENT_SKILL_NAMES["blueprint-coder"]
    assert "blueprint-compliance-engineering" in AGENT_SKILL_NAMES["blueprint-coder"]


# ---------------------------------------------------------------------------
# T10-T13: Exec allowlist enforcement
# ---------------------------------------------------------------------------

def test_blueprint_coder_exec_allowlist_no_push() -> None:
    """T10: git push is not in the exec allowlist."""
    assert not any("push" in cmd for cmd in CONST_EXEC_ALLOWLIST)


def test_blueprint_coder_exec_allowlist_no_merge() -> None:
    """T11: git merge is not in the exec allowlist."""
    assert not any("merge" in cmd for cmd in CONST_EXEC_ALLOWLIST)


def test_blueprint_coder_exec_allowlist_no_deploy() -> None:
    """T12: docker and kubectl are not in the exec allowlist."""
    assert not any("docker" in cmd for cmd in CONST_EXEC_ALLOWLIST)
    assert not any("kubectl" in cmd for cmd in CONST_EXEC_ALLOWLIST)


def test_validate_exec_command_rejects_push() -> None:
    """T13: validate_exec_command returns a violation for git push."""
    violations = validate_exec_command("git push origin main")
    assert violations, "git push must be detected as forbidden"
    assert any("push" in v for v in violations)


# ---------------------------------------------------------------------------
# T14: Self-approval prevention
# ---------------------------------------------------------------------------

def test_blueprint_coder_cannot_self_approve() -> None:
    """T14: blueprint-coder cannot approve its own work order."""
    wo = CodeWorkOrder.from_dict(_VALID_WO)
    violations = check_self_approval("blueprint-coder", wo)
    assert violations, "self-approval must be detected"
    assert any("blueprint-coder" in v for v in violations)


# ---------------------------------------------------------------------------
# T15-T18: Route allowlist
# ---------------------------------------------------------------------------

def test_blueprint_coder_route_allowlist_has_4_hops() -> None:
    """T15: The code-work-order route has exactly 4 hops."""
    assert len(CODE_WORK_ORDER_ROUTE_ALLOWLIST) == 4


def test_blueprint_coder_route_starts_at_super_advisor() -> None:
    """T16: The code-work-order route starts at super-advisor → blueprint-coder."""
    assert CODE_WORK_ORDER_ROUTE_ALLOWLIST[0] == ("super-advisor", "blueprint-coder")


def test_blueprint_coder_route_ends_at_super_advisor() -> None:
    """T17: The code-work-order route ends at security-compliance-agent → super-advisor."""
    assert CODE_WORK_ORDER_ROUTE_ALLOWLIST[-1] == ("security-compliance-agent", "super-advisor")


def test_blueprint_coder_route_blocked_from_telegram() -> None:
    """T18: blueprint-coder → telegram-publisher is a disallowed route."""
    bad_routes = {
        "realtime": [],
        "code-audit": [],
        "code-work-order": [
            ["super-advisor", "blueprint-coder"],
            ["blueprint-coder", "telegram-publisher"],
        ],
    }
    report = validate_routing(bad_routes)
    assert not report.valid
    assert any("disallowed_route" in issue.rule for issue in report.issues)


# ---------------------------------------------------------------------------
# T19-T22: Tool permission boundaries
# ---------------------------------------------------------------------------

def test_blueprint_coder_allowed_write_edit_patch() -> None:
    """T19: blueprint-coder's allowed tools include write, edit, apply_patch."""
    allowed = AGENT_ALLOWED_TOOLS["blueprint-coder"]
    assert "write" in allowed
    assert "edit" in allowed
    assert "apply_patch" in allowed


def test_blueprint_coder_no_secret_access(sample_project: Path) -> None:
    """T20: blueprint-coder has secret_access=none in the topology."""
    paths = build_paths(Path(sample_project))
    agents = build_agent_topology(paths)
    bc = next(a for a in agents if a.agent_id == "blueprint-coder")
    assert bc.secret_access == "none"


def test_blueprint_coder_denied_messaging() -> None:
    """T21: group:messaging is in blueprint-coder's deny list."""
    denied = AGENT_DENIED_TOOLS["blueprint-coder"]
    assert "group:messaging" in denied
    assert "message" in denied


def test_blueprint_coder_denied_subagents() -> None:
    """T22: subagents is in blueprint-coder's deny list."""
    denied = AGENT_DENIED_TOOLS["blueprint-coder"]
    assert "subagents" in denied


# ---------------------------------------------------------------------------
# T23-T24: Intent gate
# ---------------------------------------------------------------------------

def test_non_apply_improvement_intent_rejected() -> None:
    """T23: A work order with intent='REALTIME_ANALYSIS' is rejected by schema."""
    bad = {**_VALID_WO, "intent": "REALTIME_ANALYSIS"}
    with pytest.raises(CodeWorkOrderError, match="APPLY_IMPROVEMENT"):
        CodeWorkOrder.from_dict(bad)


def test_initiated_by_must_be_super_advisor() -> None:
    """T24: A work order initiated_by='xau-strategy-auditor' is rejected."""
    bad = {**_VALID_WO, "initiated_by": "xau-strategy-auditor"}
    with pytest.raises(CodeWorkOrderError, match="super-advisor"):
        CodeWorkOrder.from_dict(bad)


# ---------------------------------------------------------------------------
# T25: File scope enforcement
# ---------------------------------------------------------------------------

def test_validate_file_scope_in_scope() -> None:
    """T25a: A file within the authorised scope passes."""
    scope = ["engine/src/openclaw_super_advisor/constants.py"]
    assert validate_file_scope("engine/src/openclaw_super_advisor/constants.py", scope) is True


def test_validate_file_scope_out_of_scope() -> None:
    """T25b: A file outside the authorised scope fails."""
    scope = ["engine/src/openclaw_super_advisor/constants.py"]
    assert validate_file_scope("state/.env", scope) is False


def test_validate_exec_command_rejects_state_env() -> None:
    """T25c: Any command referencing state/.env is rejected."""
    violations = validate_exec_command("cat state/.env")
    assert violations, "state/.env access must be detected as forbidden"
