from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..events import canonical_json, sha256_hex, utc_now
from .planner import AgentTask, DependencyPlan, MainPlanner
from .registry_runtime import RegistrySnapshot
from .router import AgentRouter

Dispatcher = Callable[[AgentTask], Mapping[str, Any]]


@dataclass(frozen=True)
class AgentCapability:
    agent_id: str
    skills: tuple[str, ...]
    available: bool = True


@dataclass(frozen=True)
class RuntimeRequest:
    request_id: str
    plan: DependencyPlan
    idempotency_key: str
    action: str = "analyze"
    timeout_seconds: float = 30.0
    max_hops: int = 50
    human_release_gate_open: bool = False


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    agent_id: str
    status: str
    evidence_reference: str
    payload: dict[str, Any]
    provenance: dict[str, Any]
    retryable: bool = False


@dataclass(frozen=True)
class RuntimeReport:
    request_id: str
    status: str
    completed_task_ids: tuple[str, ...]
    failed_task_ids: tuple[str, ...]
    conflict_task_ids: tuple[str, ...]
    dispatch_count: int
    checkpoint_path: str
    audit_log_path: str


@dataclass(frozen=True)
class MainRuntimeQueryReport:
    query_type: str
    response: dict[str, Any]


@dataclass
class RuntimeCheckpoint:
    request_id: str
    idempotency_key: str
    status: str
    completed: dict[str, TaskResult] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    dispatched_idempotency_keys: set[str] = field(default_factory=set)
    paused: bool = False
    stopped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "completed": {key: asdict(value) for key, value in self.completed.items()},
            "failed": self.failed,
            "dispatched_idempotency_keys": sorted(self.dispatched_idempotency_keys),
            "paused": self.paused,
            "stopped": self.stopped,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RuntimeCheckpoint:
        completed_payload = payload.get("completed", {})
        completed: dict[str, TaskResult] = {}
        if isinstance(completed_payload, dict):
            for task_id, item in completed_payload.items():
                if isinstance(item, dict):
                    completed[str(task_id)] = TaskResult(
                        task_id=str(item["task_id"]),
                        agent_id=str(item["agent_id"]),
                        status=str(item["status"]),
                        evidence_reference=str(item["evidence_reference"]),
                        payload=dict(item["payload"]),
                        provenance=dict(item["provenance"]),
                        retryable=bool(item.get("retryable", False)),
                    )
        return cls(
            request_id=str(payload["request_id"]),
            idempotency_key=str(payload["idempotency_key"]),
            status=str(payload["status"]),
            completed=completed,
            failed={str(k): str(v) for k, v in dict(payload.get("failed", {})).items()},
            dispatched_idempotency_keys=set(
                str(item) for item in list(payload.get("dispatched_idempotency_keys", []))
            ),
            paused=bool(payload.get("paused", False)),
            stopped=bool(payload.get("stopped", False)),
        )


class RuntimeValidationError(RuntimeError):
    pass


class HumanReleaseGateClosedError(RuntimeValidationError):
    pass


class MainRuntimeManager:
    def __init__(
        self,
        capabilities: tuple[AgentCapability, ...],
        checkpoint_dir: Path,
        dispatcher: Dispatcher,
        *,
        registry_snapshot: RegistrySnapshot | None = None,
        planner: MainPlanner | None = None,
        router: AgentRouter | None = None,
        max_retries: int = 2,
    ) -> None:
        self.capabilities = {item.agent_id: item for item in capabilities}
        self.checkpoint_dir = checkpoint_dir
        self.dispatcher = dispatcher
        self.max_retries = max_retries
        self.registry_snapshot = registry_snapshot
        self.planner = planner
        self.router = router
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path = self.checkpoint_dir / "main-runtime-audit.ndjson"

    @classmethod
    def from_registry_snapshot(
        cls,
        registry_snapshot: RegistrySnapshot,
        checkpoint_dir: Path,
        dispatcher: Dispatcher,
        *,
        max_retries: int = 2,
    ) -> MainRuntimeManager:
        capabilities = tuple(
            AgentCapability(
                agent.agent_id,
                agent.owned_skills,
                agent.current_availability == "AVAILABLE",
            )
            for agent in registry_snapshot.list_available_agents()
            if agent.agent_id != "super-advisor"
        )
        planner = MainPlanner(registry_snapshot)
        router = AgentRouter(registry_snapshot)
        return cls(
            capabilities,
            checkpoint_dir,
            dispatcher,
            registry_snapshot=registry_snapshot,
            planner=planner,
            router=router,
            max_retries=max_retries,
        )

    @property
    def registry_state(self) -> str:
        if self.registry_snapshot is None:
            return "AGENT_REGISTRY_INVALID"
        return self.registry_snapshot.state

    @property
    def registry_loaded_by_main_runtime(self) -> bool:
        return bool(
            self.registry_snapshot is not None
            and self.registry_snapshot.loaded_by_main_runtime
            and self.planner is not None
            and self.router is not None
        )

    def plan_request(
        self,
        plan_id: str,
        request_type: str,
        tasks: list[AgentTask],
        *,
        available_inputs: dict[str, dict[str, Any]] | None = None,
    ) -> DependencyPlan:
        if self.registry_state != "AGENT_REGISTRY_READY":
            raise RuntimeValidationError(
                "MAIN planner is unavailable because the registry is not ready"
            )
        if self.planner is None:
            raise RuntimeValidationError(
                "MAIN planner is unavailable because the registry is not loaded"
            )
        return self.planner.build_plan(
            plan_id,
            request_type,
            tasks,
            available_inputs=available_inputs,
        )

    def route_plan(
        self,
        plan: DependencyPlan,
        payloads: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if self.registry_state != "AGENT_REGISTRY_READY":
            raise RuntimeValidationError(
                "MAIN router is unavailable because the registry is not ready"
            )
        if self.router is None:
            raise RuntimeValidationError(
                "MAIN router is unavailable because the registry is not loaded"
            )
        return [item.__dict__ for item in self.router.route_all(plan, payloads)]

    def handle_manager_query(self, query: str) -> MainRuntimeQueryReport:
        if self.registry_snapshot is None:
            return MainRuntimeQueryReport(
                query_type="registry_unavailable",
                response={"error": "MAIN runtime registry snapshot is unavailable"},
            )
        if self.registry_state != "AGENT_REGISTRY_READY":
            return MainRuntimeQueryReport(
                query_type="registry_unavailable",
                response={
                    "registry_state": self.registry_state,
                    "registry_definition_hash": self.registry_snapshot.definition_hash,
                    "registry_schema_version": self.registry_snapshot.schema_version,
                    "error": "; ".join(self.registry_snapshot.validation_errors)
                    or "registry is not ready",
                },
            )
        normalized = query.strip().lower()
        if "อะไรก็ได้" in normalized or "ใกล้เคียง" in normalized:
            return MainRuntimeQueryReport(
                query_type="routing_explanation",
                response={
                    "registry_schema_version": self.registry_snapshot.schema_version,
                    "registry_definition_hash": self.registry_snapshot.definition_hash,
                    "task_type": "unknown_task_type",
                    "selected_agent": None,
                    "rejected_candidates": [],
                    "required_review_chain": [],
                    "forbidden_actions": [],
                    "error": "query classification is too ambiguous for contract-safe routing",
                },
            )
        if any(token in normalized for token in ("code", "review", "ตรวจ")):
            task_type = "code_review"
        else:
            task_type = ""
        if any(token in normalized for token in ("มี agent", "หน้าที่", "ห้ามทำอะไร", "agent")):
            if task_type:
                pass
            else:
                agents = [
                    {
                        "agent_id": agent.agent_id,
                        "display_name": agent.display_name,
                        "role_summary": agent.role_summary,
                        "primary_responsibilities": list(agent.primary_responsibilities),
                        "forbidden_actions": list(agent.forbidden_actions),
                        "current_availability": agent.current_availability,
                        "definition_source": agent.definition_source,
                        "definition_version": agent.definition_version,
                    }
                    for agent in self.registry_snapshot.agents
                ]
                return MainRuntimeQueryReport(
                    query_type="agent_catalog_query",
                    response={
                        "registry_schema_version": self.registry_snapshot.schema_version,
                        "registry_definition_hash": self.registry_snapshot.definition_hash,
                        "registry_source": self.registry_snapshot.source_path,
                        "source": "main_runtime_registry_snapshot",
                        "agents": agents,
                    },
                )
        if not task_type:
            return MainRuntimeQueryReport(
                query_type="unclassified",
                response={
                    "registry_schema_version": self.registry_snapshot.schema_version,
                    "registry_definition_hash": self.registry_snapshot.definition_hash,
                    "error": "query could not be classified against the validated registry",
                },
            )
        task = AgentTask(
            task_id="query-route-1",
            agent_id="system-coder-auditor",
            skill="python-pipeline-micro-audit",
            depends_on=(),
            input_schema={"type": "object"},
            task_type=task_type,
            requested_action="audit",
        )
        plan = self.plan_request(
            "query-plan-1",
            task_type,
            [task],
            available_inputs={
                task.task_id: {
                    "task_id": task.task_id,
                    "audit_scope": "production-grade code review",
                    "source_files": ["engine/src"],
                }
            },
        )
        decision = plan.planning_decisions[0]
        return MainRuntimeQueryReport(
            query_type="routing_explanation",
            response={
                "registry_schema_version": self.registry_snapshot.schema_version,
                "registry_definition_hash": self.registry_snapshot.definition_hash,
                "registry_source": self.registry_snapshot.source_path,
                "selected_agent": decision.selected_agent,
                "reason_for_selection": decision.selection_reason,
                "matched_accepted_task_type": decision.matched_accepted_task_type,
                "rejected_candidates": list(decision.rejected_candidate_agents),
                "required_review_chain": list(decision.required_reviewers),
                "forbidden_actions": list(decision.forbidden_actions),
                "human_release_gate_required": decision.human_release_gate_required,
            },
        )

    def execute(self, request: RuntimeRequest) -> RuntimeReport:
        if self.registry_state != "AGENT_REGISTRY_READY":
            raise RuntimeValidationError("MAIN runtime registry is not ready")
        if request.action in {"release", "deploy"} and not request.human_release_gate_open:
            raise HumanReleaseGateClosedError("HUMAN_RELEASE_GATE is CLOSED")
        ordered = self._validate_and_order_plan(request.plan, request.max_hops)
        checkpoint = self._load_checkpoint(request)
        if checkpoint.paused:
            return self._report(request, checkpoint, "PAUSED")
        if checkpoint.stopped:
            return self._report(request, checkpoint, "STOPPED")
        deadline = time.monotonic() + request.timeout_seconds
        for task in ordered:
            if task.task_id in checkpoint.completed:
                continue
            if time.monotonic() > deadline:
                checkpoint.status = "TIMEOUT"
                self._save_checkpoint(request, checkpoint)
                return self._report(request, checkpoint, "TIMEOUT")
            dispatch_key = f"{request.idempotency_key}:{task.task_id}"
            if dispatch_key in checkpoint.dispatched_idempotency_keys:
                continue
            result = self._dispatch_with_retry(task)
            checkpoint.dispatched_idempotency_keys.add(dispatch_key)
            validation_error = self._validate_result(task, result)
            if validation_error:
                checkpoint.failed[task.task_id] = validation_error
                checkpoint.status = "FAILED"
                self._append_audit_event("task_failed", task.task_id, validation_error)
                self._save_checkpoint(request, checkpoint)
                return self._report(request, checkpoint, "FAILED")
            checkpoint.completed[task.task_id] = result
            self._append_audit_event("task_completed", task.task_id, result.evidence_reference)
            conflicts = self._detect_conflicts(checkpoint.completed)
            if conflicts:
                for task_id in conflicts:
                    checkpoint.failed[task_id] = "conflict_detected"
                checkpoint.status = "CONFLICT"
                self._save_checkpoint(request, checkpoint)
                return self._report(request, checkpoint, "CONFLICT")
            self._save_checkpoint(request, checkpoint)
        checkpoint.status = "COMPLETED"
        self._save_checkpoint(request, checkpoint)
        return self._report(request, checkpoint, "COMPLETED")

    def pause(self, request: RuntimeRequest) -> None:
        checkpoint = self._load_checkpoint(request)
        checkpoint.paused = True
        checkpoint.status = "PAUSED"
        self._save_checkpoint(request, checkpoint)

    def resume(self, request: RuntimeRequest) -> RuntimeReport:
        checkpoint = self._load_checkpoint(request)
        checkpoint.paused = False
        checkpoint.status = "RUNNING"
        self._save_checkpoint(request, checkpoint)
        return self.execute(request)

    def stop(self, request: RuntimeRequest) -> None:
        checkpoint = self._load_checkpoint(request)
        checkpoint.stopped = True
        checkpoint.status = "STOPPED"
        self._save_checkpoint(request, checkpoint)

    def recover(self, request: RuntimeRequest) -> RuntimeReport:
        return self.execute(request)

    def _dispatch_with_retry(self, task: AgentTask) -> TaskResult:
        attempts = 0
        last_error = "unknown dispatch failure"
        while attempts <= self.max_retries:
            attempts += 1
            try:
                payload = dict(self.dispatcher(task))
                result = TaskResult(
                    task_id=str(payload["task_id"]),
                    agent_id=str(payload["agent_id"]),
                    status=str(payload["status"]),
                    evidence_reference=str(payload["evidence_reference"]),
                    payload=dict(payload.get("payload", {})),
                    provenance=dict(payload.get("provenance", {})),
                    retryable=bool(payload.get("retryable", False)),
                )
                if result.status == "RETRYABLE_FAILURE" and result.retryable:
                    last_error = "retryable failure result"
                    continue
                return result
            except (KeyError, TypeError, ValueError) as exc:
                last_error = str(exc)
                break
            except RuntimeError as exc:
                last_error = str(exc)
                if attempts > self.max_retries:
                    break
        return TaskResult(
            task_id=task.task_id,
            agent_id=task.agent_id,
            status="FAILED",
            evidence_reference="",
            payload={"error": last_error},
            provenance={},
        )

    def _validate_result(self, task: AgentTask, result: TaskResult) -> str:
        if result.task_id != task.task_id:
            return "result task_id mismatch"
        if result.agent_id != task.agent_id:
            return "result agent_id mismatch"
        if result.status not in {"COMPLETED", "WATCH", "LOW_SCORE", "NOT_READY", "CONFLICT"}:
            return "unsupported result status"
        if not result.evidence_reference:
            return "missing evidence_reference"
        if not result.provenance:
            return "missing provenance"
        if result.payload.get("fabricated_numeric_evidence") is True:
            return "fabricated numeric evidence rejected"
        return ""

    def _validate_and_order_plan(
        self, plan: DependencyPlan, max_hops: int
    ) -> tuple[AgentTask, ...]:
        if len(plan.tasks) > max_hops:
            raise RuntimeValidationError("plan exceeds max_hops")
        task_by_id: dict[str, AgentTask] = {}
        for task in plan.tasks:
            if task.task_id in task_by_id:
                raise RuntimeValidationError(f"duplicate task_id: {task.task_id}")
            task_by_id[task.task_id] = task
            capability = self.capabilities.get(task.agent_id)
            if capability is None or not capability.available:
                raise RuntimeValidationError(f"unavailable capability: {task.agent_id}")
            if task.skill not in capability.skills:
                raise RuntimeValidationError(
                    f"agent {task.agent_id} does not provide skill {task.skill}"
                )
        for task in plan.tasks:
            for dependency in task.depends_on:
                if dependency not in task_by_id:
                    raise RuntimeValidationError(f"unknown dependency: {dependency}")
        ordered: list[AgentTask] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                raise RuntimeValidationError("dependency cycle detected")
            visiting.add(task_id)
            task = task_by_id[task_id]
            for dependency in task.depends_on:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)
            ordered.append(task)

        for task in plan.tasks:
            visit(task.task_id)
        return tuple(ordered)

    def _detect_conflicts(self, completed: Mapping[str, TaskResult]) -> tuple[str, ...]:
        values: dict[str, Any] = {}
        conflicts: list[str] = []
        for task_id, result in completed.items():
            for key, value in result.payload.items():
                if key.startswith("evidence.") and key in values and values[key] != value:
                    conflicts.append(task_id)
                values[key] = value
        return tuple(conflicts)

    def _checkpoint_path(self, request: RuntimeRequest) -> Path:
        safe_key = sha256_hex(request.idempotency_key)[:24]
        return self.checkpoint_dir / f"{request.request_id}-{safe_key}.json"

    def _load_checkpoint(self, request: RuntimeRequest) -> RuntimeCheckpoint:
        path = self._checkpoint_path(request)
        if not path.exists():
            return RuntimeCheckpoint(
                request_id=request.request_id,
                idempotency_key=request.idempotency_key,
                status="RUNNING",
            )
        return RuntimeCheckpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _save_checkpoint(self, request: RuntimeRequest, checkpoint: RuntimeCheckpoint) -> None:
        path = self._checkpoint_path(request)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(canonical_json(checkpoint.to_dict()), encoding="utf-8")
        tmp.replace(path)

    def _append_audit_event(self, event_type: str, task_id: str, detail: str) -> None:
        previous_hash = ""
        if self.audit_log_path.exists():
            lines = [
                line
                for line in self.audit_log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if lines:
                previous_hash = str(json.loads(lines[-1])["record_hash"])
        event = {
            "created_at_utc": utc_now(),
            "event_type": event_type,
            "task_id": task_id,
            "detail": detail,
            "previous_hash": previous_hash,
            "record_hash": "",
        }
        event["record_hash"] = sha256_hex(canonical_json(event))
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(event) + "\n")

    def _report(
        self,
        request: RuntimeRequest,
        checkpoint: RuntimeCheckpoint,
        status: str,
    ) -> RuntimeReport:
        failed_ids = tuple(sorted(checkpoint.failed))
        conflict_ids = tuple(
            task_id
            for task_id, reason in sorted(checkpoint.failed.items())
            if reason == "conflict_detected"
        )
        return RuntimeReport(
            request_id=request.request_id,
            status=status,
            completed_task_ids=tuple(sorted(checkpoint.completed)),
            failed_task_ids=failed_ids,
            conflict_task_ids=conflict_ids,
            dispatch_count=len(checkpoint.dispatched_idempotency_keys),
            checkpoint_path=str(self._checkpoint_path(request)),
            audit_log_path=str(self.audit_log_path),
        )
