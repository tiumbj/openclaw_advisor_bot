# P2.4 Logic and Code Conflict Matrix

**Generated:** 2026-06-14
**Baseline HEAD:** `5e247b2846d33b7a164478ac0061cec5a4a949d3`
**Blueprint version:** `p2-4-master-blueprint-v2`
**Audit scope:** Full codebase vs Blueprint v2

---

## Summary

| Severity | Count |
|---|---|
| CRITICAL | 9 |
| HIGH | 11 |
| MEDIUM | 8 |
| LOW | 3 |
| **Total** | **31** |

---

## Findings

### LC-001 — CRITICAL: Agent topology has 4 agents; Blueprint requires 12

- **Component:** `engine/src/openclaw_super_advisor/constants.py`
- **Files:** `constants.py`, `agent_topology.py`
- **Expected:** 12 runtime agents (main-agent-manager + 11 specialists)
- **Actual:** 4 agents (super-advisor, xau-strategy-auditor, system-coder-auditor, telegram-publisher)
- **Root cause:** Original P2.4 blueprint only defined 4 agents. New blueprint v2 expands to 12.
- **Pipeline impact:** MAIN orchestration, intermarket analysis, statistical backtest, failure analysis, watchdog, security compliance, and knowledge management all lack runtime agents
- **Blueprint requirement:** §4 Specialist Agent Topology
- **Remediation:** Add 8 new agents to `RUNTIME_AGENT_IDS`, `AGENT_SKILL_NAMES`, `AGENT_ALLOWED_TOOLS`, `AGENT_DENIED_TOOLS` in constants.py; add to `build_agent_topology()` in agent_topology.py
- **Test required:** `test_only_main_is_user_facing`, `test_agent_topology_has_12_agents`
- **Status:** OPEN

### LC-002 — CRITICAL: No FRED integration anywhere in codebase

- **Component:** Entire engine
- **Files:** `engine/src/openclaw_super_advisor/env.py` (no FRED vars), no FRED adapter module
- **Expected:** FRED adapter with DGS10 and DTWEXBGS support, resilient error handling, daily classification
- **Actual:** Zero FRED code exists. env.py has no `FRED_*` variables.
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** No US10Y daily data. No USD broad index from FRED. Intermarket analysis is incomplete.
- **Blueprint requirement:** §9 FRED Intermarket Integration
- **Remediation:** Create `engine/src/openclaw_super_advisor/market_data/fred_adapter.py`; add `FRED_*` env vars to `env.py` and `.env.example`
- **Test required:** `test_fred_dgs10_daily_classification`, `test_fred_dtwexbgs_is_marked_proxy`, `test_fred_missing_dot_value`, `test_fred_failure_does_not_stop_pipeline`
- **Status:** OPEN

### LC-003 — CRITICAL: No FX basket calculator

- **Component:** Entire engine
- **Files:** None (module does not exist)
- **Expected:** 7-pair normalized FX basket computing USD strength as `FX_BASKET_COMPUTED`
- **Actual:** No FX basket code exists
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** No computed USD strength when MT5 DXY and FRED DTWEXBGS are unavailable
- **Blueprint requirement:** §10 FX Basket
- **Remediation:** Create `engine/src/openclaw_super_advisor/market_data/fx_basket.py`
- **Test required:** `test_fx_basket_direction_normalization`, `test_fx_basket_timestamp_alignment`
- **Status:** OPEN

### LC-004 — CRITICAL: No persistent job queue or scheduler

- **Component:** Entire engine
- **Files:** None (modules do not exist)
- **Expected:** SQLite-backed persistent task queue with lease/heartbeat/idempotency; persistent scheduler with single-instance enforcement
- **Actual:** No scheduler, no task queue, no job persistence in any module
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** System cannot run 24/7 continuously. No recovery from crash. No recurring research cycle.
- **Blueprint requirement:** §12 Persistent 24/7 Operation
- **Remediation:** Create `engine/src/openclaw_super_advisor/scheduler/job_queue.py` and `scheduler/scheduler.py`
- **Test required:** `test_scheduler_persists_jobs`, `test_worker_recovers_leased_job`, `test_circuit_breaker_opens`, `test_checkpoint_resume`
- **Status:** OPEN

### LC-005 — CRITICAL: No experiment lifecycle state machine

- **Component:** `engine/src/openclaw_super_advisor/persistence/__init__.py`
- **Files:** `persistence/__init__.py` — has `SkillCandidateStore` but not a full experiment lifecycle
- **Expected:** 16-state experiment state machine with `experiment_id`, `correlation_id`, `evidence_ids`, dataset hash, formula version, human release gate
- **Actual:** `SkillCandidateStore` has 7 states (OBSERVATION → CANDIDATE → TESTED → APPROVED → RELEASED → REJECTED → ROLLED_BACK); missing HYPOTHESIS, EXPERIMENT_DESIGNED, DATA_VALIDATED, BACKTEST_RUNNING, RESULT_REVIEW, NEEDS_MORE_DATA, APPROVED_CANDIDATE, ISOLATED_PATCH, REGRESSION_TEST, SECURITY_REVIEW, RELEASE_PROPOSAL, HUMAN_RELEASE_GATE
- **Root cause:** Prior design merged skill lifecycle and experiment lifecycle
- **Pipeline impact:** No continuous research cycle can be orchestrated. No backtest tracking.
- **Blueprint requirement:** §14 Experiment Lifecycle State Machine
- **Remediation:** Create `engine/src/openclaw_super_advisor/research/experiment.py` with full 16-state machine
- **Test required:** `test_experiment_state_transitions`, `test_human_gate_required`, `test_agent_cannot_self_approve`
- **Status:** OPEN

### LC-006 — CRITICAL: No Windows auto-start scripts

- **Component:** `scripts/` directory
- **Files:** No startup registration scripts exist
- **Expected:** `scripts/startup/Register-StartupTask.ps1`, startup order enforcement, duplicate-instance prevention
- **Actual:** `scripts/` contains OpenClaw gateway scripts only; no Windows auto-start for the Python engine, MAIN, scheduler, or watchdog
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** System requires manual start after reboot; not 24/7
- **Blueprint requirement:** §22 Windows Auto-Start
- **Remediation:** Create `scripts/startup/Register-StartupTask.ps1` and `scripts/startup/Start-AdvisorStack.ps1`
- **Test required:** `test_duplicate_service_rejected`
- **Status:** OPEN

### LC-007 — CRITICAL: No external heartbeat emitter

- **Component:** `engine/src/openclaw_super_advisor/runtime/heartbeat.py`
- **Files:** `heartbeat.py` — `build_heartbeat()` only builds a `HeartbeatRecord`; nothing emits it externally
- **Expected:** Local signed heartbeat emitter; external monitor reference implementation; missed-heartbeat contract; Telegram offline alert schema
- **Actual:** `build_heartbeat()` creates a record but there is no emission loop, no signing, no external target, no monitor adapter
- **Root cause:** Heartbeat was scaffolded but not completed
- **Pipeline impact:** Power-failure detection is impossible without external heartbeat emission
- **Blueprint requirement:** §26 External Heartbeat Design
- **Remediation:** Extend `heartbeat.py` with `HeartbeatEmitter` class; create `heartbeat_monitor_adapter.py`
- **Test required:** `test_external_heartbeat_schema`, `test_missed_heartbeat_incident`
- **Status:** OPEN

### LC-008 — CRITICAL: No graceful shutdown handler

- **Component:** Entire engine
- **Files:** No Windows shutdown signal handler in any module
- **Expected:** `CTRL_SHUTDOWN_EVENT` or service stop handler: checkpoint jobs → flush archive/ledger → send SYSTEM_SHUTTING_DOWN → stop workers in order
- **Actual:** Python engine has no shutdown signal handling; no `SYSTEM_SHUTTING_DOWN` event
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** Crash on Windows shutdown; evidence archive may be corrupted; jobs lost
- **Blueprint requirement:** §25 Graceful Shutdown
- **Remediation:** Create `engine/src/openclaw_super_advisor/runtime/shutdown.py`
- **Test required:** `test_graceful_shutdown_checkpoints_jobs`, `test_shutdown_telegram_payload`
- **Status:** OPEN

### LC-009 — CRITICAL: AGENTS.md is stale (version P2.1 / 1.2.1)

- **Component:** `workspace/AGENTS.md`
- **Files:** `workspace/AGENTS.md` line 3: `Version: 1.2.1`, line 4: `Phase: P2.1`
- **Expected:** Version 1.2.7+, Phase P2.4, all 12 agents listed, MAIN as sole user-facing entry
- **Actual:** Version 1.2.1, Phase P2.1, only 3 invariants listed, no multi-agent topology
- **Root cause:** AGENTS.md was never updated after P2.1
- **Pipeline impact:** OpenClaw runtime loads workspace/AGENTS.md as the agent system prompt. Stale content means MAIN runs with wrong identity and invariants.
- **Blueprint requirement:** §3 MAIN Agent Manager, §4 Agent Topology
- **Remediation:** Rewrite `workspace/AGENTS.md` with current phase, all 12 agents, MAIN identity, and complete invariants
- **Test required:** Part of blueprint compliance test
- **Status:** OPEN

### LC-010 — HIGH: MT5 env specs missing 5 symbols

- **Component:** `engine/src/openclaw_super_advisor/env.py`
- **Files:** `env.py` lines 190-195
- **Expected:** 10 MT5 symbol env vars (XAUUSD, EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD, DXY, US10Y)
- **Actual:** 5 MT5 symbol vars present (XAUUSD, DXY, EURUSD, AUDUSD, US10Y); missing GBPUSD, NZDUSD, USDJPY, USDCHF, USDCAD
- **Root cause:** Initial implementation only covered XAUUSD and a few FX pairs
- **Pipeline impact:** FX basket cannot use all 7 required pairs from env override; GBPUSD, NZDUSD, USDJPY, USDCHF, USDCAD always auto-discovered
- **Blueprint requirement:** §8.3 MT5 Environment Variables
- **Remediation:** Add 5 missing `EnvVarSpec` entries to `env.py`; add to `.env.example`
- **Test required:** `test_mt5_symbol_auto_discovery`, `test_mt5_symbol_suffix_mapping`
- **Status:** OPEN

### LC-011 — HIGH: bridge.py contains `schema_placeholder` in production source

- **Component:** `engine/src/openclaw_super_advisor/bridge.py`
- **Files:** `bridge.py` line 17: `"schema_placeholder": asdict(EvidencePacketSchema())`
- **Expected:** Real schema field name, not `schema_placeholder`
- **Actual:** Placeholder key in production code suggests incomplete EvidencePacketSchema
- **Root cause:** bridge.py was partially scaffolded
- **Pipeline impact:** Evidence packets sent to MAIN may have incorrect schema; downstream schema validation may fail
- **Blueprint requirement:** §7 No-Suppression Evidence Pipeline
- **Remediation:** Read bridge.py fully and replace `schema_placeholder` with the actual EvidencePacketSchema structure
- **Test required:** Evidence schema validation test
- **Status:** OPEN

### LC-012 — HIGH: Dead code in agent_topology.py — `if route_issues: pass`

- **Component:** `engine/src/openclaw_super_advisor/agent_topology.py`
- **Files:** `agent_topology.py` line 329
- **Expected:** Either route_issues processing or no block at all
- **Actual:** `if route_issues: pass` — route issues are computed in `validate_agent_topology()` but the block does nothing; the issues are never included in the report
- **Root cause:** Incomplete implementation — route validation was started but the pass statement was left in
- **Pipeline impact:** Route validation issues in `validate_agent_topology()` are silently ignored
- **Blueprint requirement:** §4 Agent isolation; routing validation
- **Remediation:** Remove the `if route_issues: pass` block or complete the route issue processing
- **Test required:** `test_routing_validation_issues_surface`
- **Status:** OPEN

### LC-013 — HIGH: No data class segregation (INTRADAY_REALTIME vs DAILY_MACRO)

- **Component:** `engine/src/openclaw_super_advisor/market_data/`
- **Files:** `schemas.py` — `TickRecord`, `BarRecord` have `data_quality` but no `realtime_class` field
- **Expected:** Each data record carries its realtime class: INTRADAY_REALTIME, INTRADAY_DELAYED, DAILY_MACRO, STALE, UNKNOWN
- **Actual:** `data_quality` field exists but no `realtime_class` concept exists in any schema
- **Root cause:** Daily/intraday distinction not modelled in the schema
- **Pipeline impact:** FRED daily series could be misused as intraday trigger; no way to enforce the DAILY_MACRO classification
- **Blueprint requirement:** §11 Intermarket Research Topics (data class segregation)
- **Remediation:** Add `realtime_class` to evidence schemas; classify FRED series as DAILY_MACRO at ingestion
- **Test required:** `test_fred_dgs10_daily_classification`
- **Status:** OPEN

### LC-014 — HIGH: Skill validator checks frontmatter only — no semantic depth check

- **Component:** `engine/src/openclaw_super_advisor/skills.py`
- **Files:** `skills.py` — `validate_skills()` checks frontmatter fields but not body depth
- **Expected:** Validator detects shallow skills, missing decision tree, missing analysis procedure, missing quality gates
- **Actual:** Body is only checked for forbidden phrases (order_send, stop loss, etc.) and secret patterns; no check for procedural depth
- **Root cause:** Validator was designed for correctness but not depth
- **Pipeline impact:** Shallow skills pass validation; agents run with inadequate operational contracts
- **Blueprint requirement:** §5 Expert Skill Architecture — §5.5 Semantic Requirements
- **Remediation:** Add depth validation to `validate_skills()`: check for minimum required sections in body
- **Test required:** `test_skill_not_shallow_placeholder`, `test_skill_has_analysis_procedure`, `test_skill_has_failure_modes`
- **Status:** OPEN

### LC-015 — HIGH: No reliability-watchdog-agent or process health monitoring

- **Component:** Entire engine
- **Files:** No watchdog module exists
- **Expected:** Watchdog polls gateway health, Python engine health, queue worker heartbeats, disk, DB
- **Actual:** `build_heartbeat()` creates a record but there's no watchdog loop that monitors components and triggers restart
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** Component failures are not automatically detected and recovered
- **Blueprint requirement:** §23 Watchdog and Restart Recovery
- **Remediation:** Create `engine/src/openclaw_super_advisor/runtime/watchdog.py`
- **Test required:** `test_watchdog_detects_gateway_failure`
- **Status:** OPEN

### LC-016 — HIGH: No TelegramPublisher system event types

- **Component:** `engine/src/openclaw_super_advisor/persistence/__init__.py`
- **Files:** `persistence/__init__.py` — `TelegramPublisher.format_thai()` has no system event formatting
- **Expected:** 14 system event types (SYSTEM_STARTED, GATEWAY_FAILED, etc.) with severity, Thai timestamp, component, root cause
- **Actual:** `format_thai()` only formats a generic `title`/`body`/`evidence_id` payload with no event type routing
- **Root cause:** Only market alert payload was designed; system events not modelled
- **Pipeline impact:** Watchdog and incident manager cannot send typed system alerts
- **Blueprint requirement:** §21 System-Health Telegram Alerts
- **Remediation:** Add `format_system_event()` and system event type schema to `TelegramPublisher`
- **Test required:** `test_system_recovered_telegram_payload`, `test_shutdown_telegram_payload`
- **Status:** OPEN

### LC-017 — HIGH: No continuous research cycle orchestrator

- **Component:** Entire engine
- **Files:** No research cycle module
- **Expected:** MAIN orchestrates continuous: evidence → hypothesis → experiment → backtest → review → knowledge update
- **Actual:** No research cycle implementation. Each component (evidence archive, ledger, skill candidate) exists in isolation.
- **Root cause:** Not implemented in prior phases
- **Pipeline impact:** System accumulates data but does not autonomously research or improve
- **Blueprint requirement:** §13 Continuous Research and Learning Loop
- **Remediation:** Create `engine/src/openclaw_super_advisor/research/research_cycle.py`
- **Test required:** `test_main_creates_dependency_plan`, `test_main_assigns_correct_agent`
- **Status:** OPEN

### LC-018 — HIGH: No security-compliance-agent

- **Component:** Agent topology
- **Files:** `constants.py` — not in RUNTIME_AGENT_IDS
- **Expected:** Dedicated agent for advisor-only enforcement, secret scan, privilege audit
- **Actual:** Security scanning is done by Python CLI tools only; no runtime security agent
- **Root cause:** Not in original 4-agent design
- **Pipeline impact:** No ongoing security compliance monitoring during runtime
- **Blueprint requirement:** §4.1 Agent Registry
- **Remediation:** Add security-compliance-agent to constants.py; create workspace directory and skill set
- **Test required:** Part of agent topology test
- **Status:** OPEN

### LC-019 — HIGH: No knowledge-skill-manager agent runtime behavior

- **Component:** Agent topology, `persistence/__init__.py`
- **Files:** `SkillCandidateStore` exists but no knowledge-skill-manager agent entry
- **Expected:** Dedicated agent managing research knowledge, experiment records, approved lessons, skill lifecycle
- **Actual:** SkillCandidateStore is a Python class; there's no agent in the topology that owns it
- **Root cause:** Not in original 4-agent design
- **Blueprint requirement:** §17 Knowledge and Memory Lifecycle
- **Remediation:** Add knowledge-skill-manager to agent topology; wire SkillCandidateStore as its backing store
- **Status:** OPEN

### LC-020 — HIGH: MAIN (super-advisor) has no Planner/Router/Queue/Recovery runtime modules

- **Component:** `agent_topology.py`
- **Files:** `agent_topology.py` — super-advisor is defined as a static `AgentContract` with no runtime module references
- **Expected:** MAIN has 14 runtime modules (Planner, Scheduler, PersistentTaskQueue, AgentRouter, etc.)
- **Actual:** super-advisor is just an `AgentContract` dataclass with name, skills, and tool policy
- **Root cause:** Agent contracts were designed as static declarations; runtime behaviour modules are separate
- **Pipeline impact:** MAIN cannot orchestrate multi-agent workflows dynamically
- **Blueprint requirement:** §3 MAIN Agent Manager Architecture
- **Remediation:** Create `engine/src/openclaw_super_advisor/main_agent/` package with module stubs for each MAIN runtime module
- **Status:** OPEN

### LC-021 — MEDIUM: `.env.example` missing FRED and 5 MT5 symbol vars

- **Component:** `.env.example`
- **Files:** `.env.example`
- **Expected:** All FRED_* and all 10 MT5 symbol vars in the example file
- **Actual:** Missing FRED section entirely; missing GBPUSD, NZDUSD, USDJPY, USDCHF, USDCAD MT5 vars
- **Root cause:** env.py gaps propagate to .env.example
- **Remediation:** Update `.env.example` to include all new env vars
- **Status:** OPEN

### LC-022 — MEDIUM: `providers.py` line 304 has dead `pass` block

- **Component:** `engine/src/openclaw_super_advisor/providers.py`
- **Files:** `providers.py` line 304
- **Expected:** No unreachable code
- **Actual:** `pass` statement in a branch that does nothing
- **Root cause:** Incomplete implementation
- **Remediation:** Remove or complete the pass block
- **Status:** OPEN

### LC-023 — MEDIUM: No `market-data-integrity-agent` despite dedicated blueprint section

- **Component:** Agent topology
- **Files:** `constants.py` — not in RUNTIME_AGENT_IDS
- **Expected:** Agent for MT5/FRED data quality, missing bars, timezone alignment, provenance
- **Actual:** Data quality is handled by Python quality functions; no dedicated agent
- **Blueprint requirement:** §4 Agent Topology — market-data-integrity-agent
- **Remediation:** Add to constants.py; create workspace and skills
- **Status:** OPEN

### LC-024 — MEDIUM: No `intermarket-macro-agent`

- **Component:** Agent topology
- **Files:** Not in RUNTIME_AGENT_IDS
- **Expected:** Agent for USD basket, correlation, lead/lag, regime classification
- **Actual:** No intermarket analysis agent
- **Blueprint requirement:** §4.4 intermarket-macro-agent
- **Remediation:** Add to constants.py; create workspace and skills
- **Status:** OPEN

### LC-025 — MEDIUM: No `statistical-backtest-agent`

- **Component:** Agent topology
- **Files:** Not in RUNTIME_AGENT_IDS
- **Expected:** Agent for sample adequacy, walk-forward, overfitting detection
- **Actual:** No statistical backtest agent
- **Blueprint requirement:** §4.5 statistical-backtest-agent
- **Remediation:** Add to constants.py; create workspace and skills
- **Status:** OPEN

### LC-026 — MEDIUM: No `price-action-microstructure-agent`

- **Component:** Agent topology
- **Files:** Not in RUNTIME_AGENT_IDS
- **Expected:** Agent for candlestick structure, M1/M5 trigger, microstructure analysis
- **Actual:** No microstructure agent
- **Blueprint requirement:** §4.3 price-action-microstructure-agent
- **Remediation:** Add to constants.py; create workspace and skills
- **Status:** OPEN

### LC-027 — MEDIUM: No `failure-root-cause-agent`

- **Component:** Agent topology
- **Files:** Not in RUNTIME_AGENT_IDS
- **Expected:** Agent for alert failure analysis, root-cause tree, corrective hypothesis
- **Actual:** No failure analysis agent
- **Blueprint requirement:** §15 Failure-Analysis Loop
- **Remediation:** Add to constants.py; create workspace and skills
- **Status:** OPEN

### LC-028 — MEDIUM: Heartbeat schema lacks `signature` and `component_health`

- **Component:** `engine/src/openclaw_super_advisor/market_data/schemas.py`
- **Files:** `schemas.py` — `HeartbeatRecord` has `collector_name`, `status`, `detail`
- **Expected:** Heartbeat schema with `schema_version`, `system_id`, `emitted_at_utc`, `sequence`, `component_health`, `signature`
- **Actual:** `HeartbeatRecord` is a simpler internal data record, not the external heartbeat schema
- **Blueprint requirement:** §26.1 Heartbeat Schema
- **Remediation:** Create `ExternalHeartbeat` dataclass in `runtime/heartbeat.py` with full schema
- **Status:** OPEN

### LC-029 — LOW: `workspace/agents/` only has `.gitkeep` files for specialist agents

- **Component:** `workspace/agents/`
- **Files:** `workspace/agents/system-coder-auditor/.gitkeep`, etc.
- **Expected:** Real agent configuration in workspace directories for all 12 agents
- **Actual:** Directories have only `.gitkeep`; no actual agent config
- **Root cause:** Workspace directories were scaffolded without content
- **Remediation:** Not critical for runtime if agents are declared in constants.py; but need directories for all 12 agents
- **Status:** OPEN

### LC-030 — LOW: No `HEARTBEAT.md` content (workspace file exists but may be empty)

- **Component:** `workspace/HEARTBEAT.md`
- **Expected:** Heartbeat design documentation for the agent system
- **Actual:** File exists (27 bytes — nearly empty based on file listing)
- **Remediation:** Document external heartbeat design in HEARTBEAT.md
- **Status:** OPEN

### LC-031 — LOW: Skills for new 8 agents do not exist

- **Component:** `workspace/skills/`
- **Expected:** Skill files for market-data-integrity-agent, price-action-microstructure-agent, intermarket-macro-agent, statistical-backtest-agent, failure-root-cause-agent, security-compliance-agent, reliability-watchdog-agent, knowledge-skill-manager
- **Actual:** Only skills for super-advisor, xau-strategy-auditor, system-coder-auditor, and telegram-publisher exist
- **Root cause:** New agents not previously in design
- **Remediation:** Create skill files as part of agent implementation — tracked in LC-001 remediation
- **Status:** OPEN

---

## Remediation Priority

| Priority | Findings | Blocker |
|---|---|---|
| 1 | LC-009 (AGENTS.md) | MAIN identity wrong in runtime |
| 2 | LC-001 (agent topology 4→12) | All specialist agents missing |
| 3 | LC-010 (MT5 env vars) | FX basket incomplete |
| 4 | LC-002 (FRED adapter) | No US10Y/DXY daily data |
| 5 | LC-003 (FX basket) | USD strength proxy incomplete |
| 6 | LC-004 (scheduler/queue) | No 24/7 operation |
| 7 | LC-005 (experiment lifecycle) | No continuous research |
| 8 | LC-006 (Windows auto-start) | Manual restart required |
| 9 | LC-007 (external heartbeat) | No offline detection |
| 10 | LC-008 (graceful shutdown) | Data loss on reboot |
| 11 | LC-011–LC-031 | Various correctness issues |
