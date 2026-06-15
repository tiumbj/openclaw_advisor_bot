"""CodeWorkOrder: schema and validation for blueprint-coder dispatch contracts.

A CodeWorkOrder is the sole mechanism by which super-advisor may dispatch
blueprint-coder.  It is only created when the user issues an explicit
APPLY_IMPROVEMENT command.  The human release gate remains CLOSED until a
human reviewer approves the result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CodeWorkOrderError(ValueError):
    """Raised when a CodeWorkOrder fails schema validation."""


@dataclass(frozen=True)
class CodeWorkOrder:
    """Immutable dispatch contract authorising blueprint-coder to perform code work.

    Fields
    ------
    baseline_commit : str
        Full SHA-1 of the commit that serves as the diff base for this work.
    scope : list[str]
        File paths or module names that blueprint-coder is authorised to modify.
        Must not be empty.
    intent : str
        Must equal ``"APPLY_IMPROVEMENT"`` — any other value is rejected at
        dispatch time.
    description : str
        Human-readable description of the improvement to be implemented.
    acceptance_criteria : list[str]
        Observable, testable conditions that must all pass before blueprint-coder
        marks the work order complete.  Must contain at least one criterion.
    human_release_gate_required : bool
        Must be ``True``.  Blueprint-coder cannot open the release gate itself.
    initiated_by : str
        Agent ID that created this work order (must be ``"super-advisor"``).
    task_id : str
        Unique identifier for cross-agent task tracking.
    worktree_path : str
        Absolute path of the isolated Git worktree where blueprint-coder operates.
        Must not overlap with the main working tree.
    """

    baseline_commit: str
    scope: list[str]
    intent: str
    description: str
    acceptance_criteria: list[str]
    human_release_gate_required: bool
    initiated_by: str
    task_id: str
    worktree_path: str

    def __post_init__(self) -> None:
        errors: list[str] = []
        if not self.baseline_commit or len(self.baseline_commit) < 7:
            errors.append("baseline_commit must be a non-empty git SHA (min 7 chars)")
        if not self.scope:
            errors.append("scope must contain at least one file path or module name")
        if self.intent != "APPLY_IMPROVEMENT":
            errors.append(
                f"intent must be 'APPLY_IMPROVEMENT', got {self.intent!r}"
            )
        if not self.description.strip():
            errors.append("description must be a non-empty string")
        if not self.acceptance_criteria:
            errors.append("acceptance_criteria must contain at least one criterion")
        if not self.human_release_gate_required:
            errors.append("human_release_gate_required must be True")
        if self.initiated_by != "super-advisor":
            errors.append(
                f"initiated_by must be 'super-advisor', got {self.initiated_by!r}"
            )
        if not self.task_id.strip():
            errors.append("task_id must be a non-empty string")
        if not self.worktree_path.strip():
            errors.append("worktree_path must be a non-empty absolute path")
        if errors:
            raise CodeWorkOrderError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_commit": self.baseline_commit,
            "scope": list(self.scope),
            "intent": self.intent,
            "description": self.description,
            "acceptance_criteria": list(self.acceptance_criteria),
            "human_release_gate_required": self.human_release_gate_required,
            "initiated_by": self.initiated_by,
            "task_id": self.task_id,
            "worktree_path": self.worktree_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeWorkOrder:
        missing = [
            k for k in (
                "baseline_commit", "scope", "intent", "description",
                "acceptance_criteria", "human_release_gate_required",
                "initiated_by", "task_id", "worktree_path",
            )
            if k not in data
        ]
        if missing:
            raise CodeWorkOrderError(
                f"CodeWorkOrder missing required fields: {', '.join(missing)}"
            )
        return cls(
            baseline_commit=str(data["baseline_commit"]),
            scope=list(data["scope"]),
            intent=str(data["intent"]),
            description=str(data["description"]),
            acceptance_criteria=list(data["acceptance_criteria"]),
            human_release_gate_required=bool(data["human_release_gate_required"]),
            initiated_by=str(data["initiated_by"]),
            task_id=str(data["task_id"]),
            worktree_path=str(data["worktree_path"]),
        )


_FORBIDDEN_EXEC_PATTERNS = frozenset({
    "git push",
    "git merge",
    "git rebase",
    "git reset --hard",
    "git branch -D",
    "git tag",
    "git release",
    "docker",
    "kubectl",
    "pip install",
    "pip uninstall",
    "rm -rf",
    "del /f",
})

_STATE_ENV_FORBIDDEN_PATHS = frozenset({
    "state/.env",
    "state\\\\env",
    ".env",
    "state/credentials",
    "state\\\\credentials",
})


def validate_exec_command(command: str) -> list[str]:
    """Return a list of violations if ``command`` is forbidden for blueprint-coder."""
    violations: list[str] = []
    cmd_lower = command.lower().strip()
    for pattern in _FORBIDDEN_EXEC_PATTERNS:
        if cmd_lower.startswith(pattern):
            violations.append(f"forbidden exec command: {pattern!r}")
    for path in _STATE_ENV_FORBIDDEN_PATHS:
        if path in command:
            violations.append(f"forbidden path access: {path!r}")
    return violations


def validate_file_scope(file_path: str, scope: list[str]) -> bool:
    """Return True if ``file_path`` is within the authorised scope."""
    return any(file_path.startswith(s) or file_path == s for s in scope)


FORBIDDEN_SELF_APPROVAL_AGENT_IDS = frozenset({"blueprint-coder"})


def check_self_approval(approver_agent_id: str, work_order: CodeWorkOrder) -> list[str]:
    """Return violations if blueprint-coder attempts to approve its own work order."""
    violations: list[str] = []
    if approver_agent_id in FORBIDDEN_SELF_APPROVAL_AGENT_IDS:
        violations.append(
            f"blueprint-coder (agent_id={approver_agent_id!r}) cannot approve its own "
            f"work order (task_id={work_order.task_id!r})"
        )
    return violations
