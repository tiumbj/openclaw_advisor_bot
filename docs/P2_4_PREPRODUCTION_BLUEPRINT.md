# P2.4 Master Blueprint — MAIN-Managed 24/7 Research Platform

**Schema:** `p2-4-master-blueprint-v2`
**Package version target:** `1.2.8`
**Phase:** `P2.4`
**Work package:** `WP-P2_4-MAIN-24X7-DEEP-SKILLS`
**Generated:** 2026-06-14
**Status:** SOURCE OF TRUTH — supersedes all prior P2.4 blueprint versions

---

## 1. Project Purpose

Autonomous 24/7 XAUUSD Research, Alert and Continuous-Improvement Platform.

The system runs continuously, analyses markets, generates human-readable alerts via Telegram, and improves its own research quality over time through validated experiments.

**It is advisor-only.** It never executes trades, places orders, modifies positions, or writes to any broker API.

---

## 2. Advisor-Only Invariants (Hard Locks)

These invariants MUST be enforced at every layer — config, code, skill, test, and audit:

| Invariant | Enforcement point |
|---|---|
| No `order_send`, `order_check`, `TRADE_ACTION` | AST scan, constants.FORBIDDEN_SYMBOLS |
| No `position_close`, `close_position` | AST scan |
| No `ExecutionKernel`, `execution_dispatch_bridge` | AST scan |
| `ADVISOR_ONLY=true` | env spec expected value |
| `EXECUTION_ALLOWED=false` | env spec expected value |
| `ALLOW_ORDER_SEND=false` | env spec expected value |
| No broker write path in any agent skill | Skill validator |
| Agents cannot read `state/.env` | Agent isolation |
| Agents cannot read API keys or tokens | Agent isolation |
| No auto-push, no auto-production-deploy | Release gate |

---

## 3. MAIN Agent Manager Architecture

**Agent ID:** `main-agent-manager`
**Display role:** MAIN
**Compatibility alias:** `super-advisor` (existing OpenClaw runtime entry point)

MAIN is the **sole user-facing agent**. Users interact with the system through:
- OpenClaw Control UI (loopback, token-authenticated)
- Approved CLI commands
- Telegram command channel (authenticated)

Specialist agents MUST NOT be opened as public user-facing entry points.

### MAIN Runtime Modules

| Module | Responsibility |
|---|---|
| Planner | Decompose user intent into dependency-ordered tasks |
| Scheduler | Manage recurring and one-shot job schedules (persistent) |
| Persistent Task Queue | Durable job store with lease, heartbeat, idempotency |
| Agent Router | Select specialist agent for each task type |
| Dependency Manager | Track inter-task dependencies, unblock when dependencies satisfy |
| Result Validator | Require evidence for all agent results; reject unproven claims |
| Evidence Arbiter | Resolve conflicting evidence from multiple agents |
| Conflict Resolver | Mediate inter-agent output conflicts |
| Experiment Manager | Own experiment lifecycle state machine |
| Knowledge Manager | Store approved lessons; reject unvalidated hypotheses |
| Recovery Manager | Resume pending jobs after restart; replay failed tasks |
| Incident Manager | Create and dispatch Telegram incident payloads |
| Release Gate | Require explicit human approval before code changes go to main |
| Operator Interface | Accept operator stop/pause/resume commands |

MAIN must NOT be implemented as a hardcoded function that calls agents by name. It must dynamically route based on task type, agent availability, and evidence requirements.

---

## 4. Specialist Agent Topology

### 4.1 Agent Registry

| Agent ID | Compatibility ID | Role |
|---|---|---|
| `main-agent-manager` | `super-advisor` | MAIN — sole user-facing coordinator |
| `market-data-integrity-agent` | — | MT5/FRED data quality and provenance |
| `xau-strategy-research-agent` | `xau-strategy-auditor` | XAUUSD multi-timeframe research |
| `price-action-microstructure-agent` | — | Candlestick and M1/M5 trigger analysis |
| `intermarket-macro-agent` | — | USD, US10Y, FX basket, correlation |
| `statistical-backtest-agent` | — | Sample adequacy, walk-forward, overfitting |
| `failure-root-cause-agent` | — | Alert failure, logic conflict, root-cause tree |
| `system-coder-auditor` | `system-coder-auditor` | Python audit, isolated patch only |
| `security-compliance-agent` | — | Advisor-only enforcement, secret scan |
| `telegram-publisher` | `telegram-publisher` | Thai Telegram formatting and delivery |
| `reliability-watchdog-agent` | — | Heartbeat, process health, restart |
| `knowledge-skill-manager` | — | Research knowledge and skill lifecycle |

**No two agents may share runtime responsibility.** Each specialist agent is isolated: unique workspace, agent directory, session store, memory, and tool policy.

### 4.2 Agent Isolation Requirements

Each agent MUST have:
- Unique `agent_id`
- Unique workspace path (`workspace/agents/<agent_id>/`)
- Unique `agentDir` in `state/agents/<agent_id>/agent/`
- Unique `sessionStore` in `state/agents/<agent_id>/sessions/`
- Unique `memoryDir` in `state/agents/<agent_id>/memory/`
- Explicit `allowed_tools` tuple
- Explicit `denied_tools` tuple
- Explicit `secret_access` policy
- Timeout and retry policy
- Failure behavior specification
- Versioned contract (SKILL.md files)
- Health probe

### 4.3 Prohibited Cross-Agent Behaviours

- Cross-agent memory or session access
- Unauthorized skill loading
- Agent spoofing
- Direct Agent-to-Agent bypass of MAIN
- Specialist agent answering user directly
- Agent reading `state/.env`
- Agent reading tokens or API keys
- Agent writing to production source on `main`
- Agent sending Telegram directly (only `telegram-publisher` may send)
- Agent self-approving its own experiment

---

## 5. Expert Skill Architecture

### 5.1 Skill Depth Requirements

Every skill MUST be an **executable operational contract**, not documentation. Required fields:

```
Skill ID, Skill version, Owner Agent, Domain, Purpose, Exact scope, Non-goals,
Prerequisites, Input schema, Output schema, Required evidence, Analysis method,
Step-by-step procedure, Decision tree, Quality gates, Failure modes, Edge cases,
Timeout policy, Retry policy, Allowed tools, Denied tools, Data ownership rules,
Security constraints, Interaction contracts, Escalation rules, Audit fields,
Positive test vectors, Negative test vectors, Regression tests, Promotion state,
Rollback compatibility
```

### 5.2 Analysis Skills (Market/Research)

Must additionally specify:
- Methodology with formula/logic ownership
- Timeframe compatibility matrix
- Missing-data behaviour
- Stale-data behaviour
- Contradiction handling
- Confidence limitations
- Anti-overfitting rules
- Evidence citation requirements

### 5.3 Coding/Audit Skills

Must additionally specify:
- Architecture inspection procedure
- Dependency graph analysis
- State-machine audit
- Dead code analysis
- Duplicate-path analysis
- Conflict detection checklist
- Type/schema consistency check
- Concurrency analysis
- Resource lifecycle
- Error propagation
- Transaction boundaries
- Rollback design
- Regression plan

### 5.4 Skills by Agent

**main-agent-manager:**
`advisor-safety-contract`, `environment-health`, `evidence-audit`,
`agent-orchestration-contract`, `super-potential-review`, `incident-reporting`,
`publication-policy`

**xau-strategy-research-agent (xau-strategy-auditor):**
`xauusd-market-analysis`, `multi-timeframe-structure-review`, `price-action-order-block`,
`chart-pattern-filter-review`, `candlestick-microstructure`, `strategy-logic-audit`,
`realtime-evidence-review`, `super-potential-audit`, `alert-quality-improvement`

**system-coder-auditor:**
`python-pipeline-micro-audit`, `code-architecture-review`, `logic-conflict-detection`,
`dead-code-and-duplicate-review`, `test-and-regression-design`, `blueprint-compliance-audit`,
`safe-patch-workflow`, `release-and-rollback`, `skill-improvement-proposal`

**telegram-publisher:**
`thai-telegram-publisher`, `telegram-message-contract`, `telegram-delivery-safety`,
`telegram-deduplication-throttle`, `telegram-retry-and-dead-letter`,
`telegram-security-redaction`

### 5.5 Skill Validation — Semantic Requirements

The validator MUST check beyond file existence and frontmatter fields:
- No duplicate skill logic across skills
- No shallow (placeholder) body
- Missing procedure → FAIL
- Missing evidence requirement → FAIL
- Missing failure mode → FAIL
- Owner mismatch → FAIL
- Unauthorized tools → FAIL
- Incompatible input/output → FAIL
- Orphan skill → FAIL
- Skill collision → FAIL
- Circular skill dependency → FAIL
- Version conflict → FAIL
- Runtime discovery must load all blueprint skills

---

## 6. Python Deterministic Evidence Ownership

**Python owns all numeric market values.** Agents are forbidden from:
- Calculating or modifying OHLC values
- Calculating or modifying indicator values (VWAP, Fibo, ATR, etc.)
- Calculating or modifying zones, FVG, FVP, POC, VAH, VAL
- Calculating or modifying scores, distances, headroom
- Calculating or modifying correlation coefficients
- Fabricating any numeric value

Python-owned data categories:
```
OHLC, Tick/bar data, Indicators, Zones, FVG, FVP/POC/VAH/VAL, VWAP, Fibo,
Market structure, Pattern candidates, Scores, Distances, Headroom, Session,
Intermarket metrics, Correlations, Timestamps, State, Provenance
```

---

## 7. No-Suppression Evidence Pipeline

### 7.1 Core Principle

There is NO signal suppression gate. Python sends ALL valid records to the Evidence Bus regardless of:
- Score level
- WATCH_ONLY state
- Intermarket conflict
- Setup weakness
- Headroom
- Confluence count
- Readiness state

### 7.2 Correct Pipeline

```
MT5/FRED source
→ Python deterministic analysis
→ Integrity validation (schema, symbol, timeframe, timestamp, NaN, duplicate, age)
→ Evidence Bus (non-suppressing)
→ Immutable Evidence Archive (append-only, hash-chained)
→ MAIN Agent Manager
→ Specialist Agent assignment
→ Agent evidence-based analysis (read-only)
→ MAIN result validation
→ Alert/Research/Improvement decision
→ Telegram Publisher (approved payloads only)
→ Outcome Ledger
→ Knowledge Store
→ Next cycle
```

### 7.3 Integrity Gate (REQUIRED — this is NOT suppression)

Invalid records MUST be:
1. Quarantined (not silently dropped)
2. Logged as `DATA_QUALITY_WARNING` event
3. Preserved as raw diagnostic evidence
4. Never fabricated to replace

Valid-but-degraded records MUST be sent with explicit status:
```
VALID | DELAYED | STALE | PARTIAL | CONFLICT | UNKNOWN | SOURCE_UNAVAILABLE
```

---

## 8. MT5 Data Pipeline

### 8.1 Symbols

Required logical symbols:
```
XAUUSD, EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD
```

Optional (auto-discovered or blank):
```
DXY (exact), US10Y (from MT5 if available)
```

### 8.2 Symbol Resolution

Supports broker prefix/suffix variants:
- `XAUUSD`, `XAUUSD.a`, `XAUUSDm`, `XAUUSD.pro`, `XAUUSDx`, etc.

Resolution order:
1. Exact match on `.env` override
2. Normalized auto-discovery (strip prefix/suffix, normalize case)
3. Report `missing_symbol_mapping` incident if not found

### 8.3 MT5 Environment Variables

```dotenv
MT5_XAUUSD_SYMBOL=    # blank = auto-discover
MT5_EURUSD_SYMBOL=
MT5_GBPUSD_SYMBOL=
MT5_AUDUSD_SYMBOL=
MT5_NZDUSD_SYMBOL=
MT5_USDJPY_SYMBOL=
MT5_USDCHF_SYMBOL=
MT5_USDCAD_SYMBOL=
MT5_DXY_SYMBOL=
MT5_US10Y_SYMBOL=
```

### 8.4 MT5 Safety

- Read-only: no `order_send`, no `position_close`, no write methods
- `MT5_READONLY_METHODS` allowlist enforced
- Reconnect with bounded retry and circuit breaker
- `MT5_USE_EXISTING_SESSION=true` default
- UTC normalization (broker timezone → UTC)
- Thai-time presentation layer (UTC → Asia/Bangkok)
- Stale detection with `freshness_threshold_seconds`

---

## 9. FRED Intermarket Integration

### 9.1 Environment Variables

```dotenv
FRED_ENABLED=true
FRED_API_KEY=              # user sets in state/.env; never committed
FRED_BASE_URL=https://api.stlouisfed.org
FRED_TIMEOUT_SECONDS=20
FRED_MAX_RETRIES=3
FRED_CACHE_TTL_SECONDS=3600

FRED_US10Y_SERIES_ID=DGS10
FRED_USD_BROAD_SERIES_ID=DTWEXBGS
```

### 9.2 US10Y (DGS10)

- **Internal ID:** `US10Y_DAILY`
- **Source:** FRED
- **Frequency:** DAILY (NOT intraday)
- **Unit:** Percent
- **Realtime class:** `DAILY_MACRO`
- **MUST NOT** be used as intraday realtime yield signal

### 9.3 USD Broad Index (DTWEXBGS)

- **Internal ID:** `DXY_PROXY_FRED`
- **`is_proxy = true`**
- **`is_exact_dxy = false`**
- **`usage = macro_usd_strength_context`**
- MUST NOT be labelled or presented as "DXY" without proxy qualifier

### 9.4 Source Priority

**DXY/USD strength:**
```
MT5 exact DXY (if available and valid)
→ FRED DTWEXBGS (as DXY_PROXY_FRED)
→ Python normalized major-FX basket (FX_BASKET_COMPUTED)
→ UNKNOWN
```

**US10Y:**
```
MT5 US10Y instrument (if available and valid)
→ FRED DGS10 daily
→ UNKNOWN
```

### 9.5 FRED Adapter Resilience

Must handle:
- Invalid/missing API key → `SOURCE_UNAVAILABLE` (do not crash pipeline)
- Timeout → bounded retry then circuit breaker
- Rate limit → exponential backoff with jitter
- HTTP error → log incident, continue
- Empty observations → return last-known with `stale` flag
- `"."` missing value → treat as gap, do not fabricate
- Duplicate date → use most recent
- Revised observation → accept and log
- Cache with `FRED_CACHE_TTL_SECONDS`
- Dead letter for repeated FRED failures
- FRED failure MUST NOT stop the main pipeline

---

## 10. FX Basket (DXY Proxy Computed)

Python computes normalized USD basket from:
```
EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF, USDCAD
```

Requirements:
- Normalize returns (not raw prices)
- Reverse direction for USD-as-quote pairs (EUR, GBP, AUD, NZD)
- Align timestamps (same timeframe, same bar)
- Mark missing component individually
- Mark stale component individually
- Expose each component's contribution to basket value
- Version the formula in the output provenance
- Never fabricate a fill for a missing component

---

## 11. Intermarket Research Topics

MAIN must continuously assign research on:
- XAU vs USD basket (FX_BASKET_COMPUTED)
- XAU vs exact DXY (if available)
- XAU vs DXY proxy (FRED)
- XAU vs US10Y
- XAU vs AUDUSD, EURUSD
- XAU vs risk currencies basket
- Session-specific relationships (London, New York, Asia)
- Rolling correlation (5m, 15m, 1h, 4h, 1d, 5d, 20d windows)
- Lead/lag relationships
- Regime shift detection
- Divergence patterns
- False correlation cases
- Data staleness impact on signal quality

**Data class segregation:**
```
INTRADAY_REALTIME   — MT5 live bar/tick
INTRADAY_DELAYED    — MT5 delayed or stale
DAILY_MACRO         — FRED daily series (DGS10, DTWEXBGS)
STALE               — any source past freshness threshold
UNKNOWN             — source unavailable
```

FRED daily series MUST NOT be used as intraday trade triggers.

---

## 12. Persistent 24/7 Operation

### 12.1 Job Queue Requirements

```
Persistent storage (SQLite or equivalent)
Task lease with heartbeat renewal
Idempotency key
Bounded retry with exponential backoff
Circuit breaker per task type
Timeout per task type
Max iterations per experiment
Stagnation detection (no progress after N cycles)
Duplicate-hypothesis detection
Resource limit (disk, memory thresholds)
Dead-letter queue (DLQ) for permanently failed tasks
Cancellation API (operator stop/pause)
```

### 12.2 Scheduler

```
Recurring job definitions (cron-like schedule)
Persistent schedule store
Single scheduler instance (duplicate prevention)
Job lease prevents duplicate execution
Resume on restart (load persisted schedule)
```

### 12.3 Fault Tolerance

Individual task failure MUST NOT stop the system. The system continues with remaining tasks, logs the failure, and applies DLQ policy for repeated failures.

---

## 13. Continuous Research and Learning Loop

### 13.1 Research Cycle

```
New deterministic evidence from Python
→ Archive to Evidence Bus
→ MAIN identifies research opportunity (edge or failure)
→ Specialist Agents analyze (read evidence-only)
→ Hypothesis created (with correlation ID)
→ Statistical/backtest validation
→ Baseline comparison
→ Failure/root-cause review
→ Improvement proposal
→ Isolated implementation (separate worktree)
→ Tests
→ Backtest
→ Regression
→ Security audit
→ ACCEPTED or REJECTED
→ Knowledge store update
→ Next research cycle
```

### 13.2 Edge Discovery Topics

- Conditions that improve alert quality
- Session-specific advantage
- Pattern persistence across timeframes
- Lead/lag behaviours
- Regime dependency
- Confluence value quantification
- False-positive reduction methods
- Earlier detection logic
- Better invalidation logic

### 13.3 Failure Discovery Topics

- False alerts (what triggered them)
- Missing alerts (why detection failed)
- Late alerts (delay root cause)
- Stale data propagation
- Logic conflicts
- State conflicts
- Incorrect symbol mapping
- Time alignment errors
- Overfitting
- Look-ahead bias
- Data leakage
- Duplicate alert root cause
- Agent/Python inconsistency

### 13.4 Acceptance Criteria

"OK" must be measurable. Minimum bar:
- Sample size ≥ statistical significance threshold
- Out-of-sample validation
- Walk-forward stability
- Multiple market regimes covered
- False-alert rate compared to baseline
- No regression on existing alerts
- Statistical uncertainty quantified
- Data quality verified
- Advisor-only safety confirmed
- Results reproducible from evidence alone

---

## 14. Experiment Lifecycle State Machine

```
OBSERVATION
→ HYPOTHESIS
→ EXPERIMENT_DESIGNED
→ DATA_VALIDATED
→ BACKTEST_RUNNING
→ RESULT_REVIEW
→ REJECTED | NEEDS_MORE_DATA | APPROVED_CANDIDATE
→ ISOLATED_PATCH
→ REGRESSION_TEST
→ SECURITY_REVIEW
→ RELEASE_PROPOSAL
→ HUMAN_RELEASE_GATE
→ RELEASED | REJECTED | ROLLED_BACK
```

Every state transition MUST record:
```
experiment_id, correlation_id, evidence_ids, owner_agent, start_time, end_time,
input_data_range, dataset_hash, formula_version, result, failure_reason,
reviewer, approval, rollback_reference
```

No agent may approve its own experiment. The `HUMAN_RELEASE_GATE` state requires explicit external approval.

---

## 15. Failure-Analysis Loop

`failure-root-cause-agent` continuously analyses:
- Failed alerts (what conditions led to failure)
- Logic conflicts discovered in pipeline
- Missed setup detection
- Late detection patterns
- Repeated errors (correlation → systemic cause)
- Pipeline inconsistency
- State machine mismatch

Output: root-cause tree with corrective hypothesis. Hypothesis enters `HYPOTHESIS` state in Experiment Lifecycle.

---

## 16. Outcome Ledger

Append-only, hash-chained ledger of all significant outcomes:
- Alert sent (with evidence reference)
- Alert invalidated (with reason)
- Experiment approved
- Experiment rejected
- Skill released
- Skill rolled back
- Data quality incident
- System incident
- Recovery event

Ledger MUST be verifiable (hash chain integrity check).

---

## 17. Knowledge and Memory Lifecycle

### 17.1 Knowledge Store

`knowledge-skill-manager` owns:
- Research knowledge entries (approved findings only)
- Experiment results (all states)
- Approved lessons
- Rejected hypotheses (preserved for anti-duplication)
- Skill candidate lifecycle records
- Skill version history
- Promotion proposals
- Rollback history

### 17.2 Knowledge Entry Requirements

Every entry must have:
- Source experiment ID
- Supporting evidence IDs
- Validation status
- Statistical confidence
- Date range validity
- Conditions under which it was validated

### 17.3 Agent Memory

Per-agent memory store (`AgentMemoryStore`): each agent maintains its own contextual memory. Cross-agent memory access is forbidden.

---

## 18. Skill-Improvement Lifecycle

```
Research finding → knowledge-skill-manager creates skill candidate
→ OBSERVATION state
→ CANDIDATE (when proposer produces draft)
→ TESTED (after system-coder-auditor validates implementation)
→ APPROVED_CANDIDATE (after independent review — not proposer)
→ Isolated worktree patch
→ Regression tests pass
→ Security review passes
→ RELEASE_PROPOSAL
→ HUMAN_RELEASE_GATE
→ RELEASED or REJECTED
```

`knowledge-skill-manager` MUST NOT approve its own skill proposals.

---

## 19. Safe Code-Improvement Workflow

`system-coder-auditor` default mode: `READ_ONLY_AUDIT`.
Patch mode: `ISOLATED_WORKTREE_PATCH` only.

```
Issue identified
→ Root-cause evidence packaged
→ Patch proposal submitted to MAIN
→ Isolated Git worktree created
→ Allowlisted file change only
→ Lint / type-check / tests
→ Backtest (where applicable)
→ Security scan
→ Diff audit by independent agent
→ Release proposal
→ HUMAN_RELEASE_GATE (explicit approval required)
→ Merged to main only after approval
```

**Absolutely forbidden:**
- Auto-merge to `main`
- Auto-push
- Auto-production-deploy
- Direct service control from coding agent
- Reading secrets or `.env`
- Modifying runtime token
- Modifying `main` without gate

---

## 20. Telegram Alert Pipeline

### 20.1 Alert Flow

```
MAIN validates evidence → approves alert payload
→ telegram-publisher receives payload only
→ Format in Thai (human-readable)
→ Redact any sensitive fields
→ Deduplication check (evidence_id + timeframe window)
→ Throttle check
→ Send via Telegram Bot API
→ Record delivery result
→ Dead letter on repeated failure
→ MAIN receives delivery confirmation
→ Outcome Ledger entry
```

### 20.2 Rules

- Only `telegram-publisher` may call Telegram API
- No market analysis inside telegram-publisher
- No numeric fabrication inside telegram-publisher
- No direct Telegram calls from any other agent

---

## 21. System-Health Telegram Alerts

System events that generate Telegram notifications:

```
SYSTEM_STARTED, SYSTEM_RECOVERED, SYSTEM_SHUTTING_DOWN, SYSTEM_OFFLINE_DETECTED,
GATEWAY_FAILED, PYTHON_ENGINE_FAILED, QUEUE_STALLED, DATA_STALE,
MT5_DISCONNECTED, FRED_UNAVAILABLE, DISK_LOW, DATABASE_LOCKED,
EXPERIMENT_FAILED, SECURITY_INCIDENT
```

Each alert MUST include:
- Severity (CRITICAL, WARNING, INFO)
- Thai and UTC timestamp
- Affected component
- Root cause (if known)
- Current impact
- Recovery action taken or required
- Correlation ID
- Deduplication key
- Throttle state (no flooding)

---

## 22. Windows Auto-Start

System starts automatically when Windows boots.

### 22.1 Startup Order

```
1. Load canonical env (state/.env)
2. Validate token / config
3. Start OpenClaw Gateway
4. Start Python Engine
5. Start MAIN Agent Manager
6. Start Scheduler
7. Start Queue Workers
8. Start Watchdog
9. Validate MT5 connection
10. Validate FRED (non-blocking; failure allowed)
11. Resume pending jobs from queue
12. Send SYSTEM_RECOVERED Telegram alert
```

### 22.2 Startup Safety

Must prevent:
- Duplicate service instances (PID file or Windows service lock)
- Duplicate worker processes
- Duplicate scheduler instances
- Stale PID files from previous crash
- Port collision (check before bind)
- Token drift (re-validate token from env on startup)
- Split-brain state (check queue for in-flight tasks before resuming)

### 22.3 Implementation

Windows Task Scheduler (`scripts/startup/Register-StartupTask.ps1`) or Windows Service wrapper. Must be idempotent (safe to run multiple times).

---

## 23. Watchdog and Restart Recovery

`reliability-watchdog-agent` monitors:
- Gateway HTTP health endpoint
- Python Engine process health
- Queue worker heartbeats
- Disk space (configurable threshold)
- Database lock / WAL file health
- MAIN agent session health
- MT5 connection state

On failure:
1. Log incident
2. Attempt restart (bounded retry)
3. Send `GATEWAY_FAILED` / `PYTHON_ENGINE_FAILED` Telegram alert
4. If restart fails → escalate to `SYSTEM_INCIDENT` event
5. Continue monitoring remaining healthy components

---

## 24. Checkpoint and Resume

Active jobs MUST checkpoint progress periodically. On restart:
1. Load all jobs in `IN_PROGRESS` or `LEASED` state
2. Check lease expiry
3. Reset expired leases to `QUEUED`
4. Resume execution from last checkpoint

Checkpoint granularity: per-phase within each experiment stage. Do NOT re-run completed phases.

---

## 25. Graceful Shutdown

On Windows shutdown signal (CTRL_SHUTDOWN_EVENT or service stop):
1. Stop accepting new jobs
2. Checkpoint all active jobs
3. Flush Evidence Archive and Outcome Ledger
4. Release all queue leases
5. Send `SYSTEM_SHUTTING_DOWN` Telegram alert
6. Stop Queue Workers
7. Stop Scheduler
8. Stop MAIN Agent Manager
9. Stop Python Engine
10. Stop OpenClaw Gateway (last)

---

## 26. External Heartbeat Design

Local process emits a signed heartbeat every 1–5 minutes to an external monitor endpoint. If the monitor sees no heartbeat for `missed_heartbeat_threshold` intervals, it sends `SYSTEM_OFFLINE_DETECTED` Telegram alert.

**Why external:** The local process cannot send Telegram after a power failure. External monitoring is required for offline detection.

### 26.1 Heartbeat Schema

```json
{
  "schema_version": "heartbeat-v1",
  "system_id": "<unique-system-id>",
  "emitted_at_utc": "<ISO-8601>",
  "sequence": <integer>,
  "component_health": {
    "gateway": "OK|DEGRADED|FAILED",
    "python_engine": "OK|DEGRADED|FAILED",
    "queue": "OK|DEGRADED|FAILED",
    "mt5": "OK|DEGRADED|UNAVAILABLE"
  },
  "signature": "<hmac-sha256>"
}
```

### 26.2 Implementation Scope for P2.4

P2.4 MUST deliver:
- Local signed heartbeat emitter (Python module)
- Heartbeat schema (dataclass + validation)
- External monitor reference implementation (deployable adapter — can be a standalone script)
- Missed-heartbeat contract (threshold, incident payload schema)
- Telegram incident payload for offline detection

If no external host is configured, the system logs a `HEARTBEAT_EXTERNAL_NOT_CONFIGURED` warning but does not fail.

---

## 27. Backup and Restore

### 27.1 What is backed up

All non-secret operational data:
- Source code and config (excluding `.env`, tokens)
- Workspace and skills
- Evidence archive
- Outcome ledger
- Knowledge store
- Skill candidate records
- Docs

### 27.2 What is excluded

Absolutely excluded from backup:
- `state/.env`
- Any file matching secret patterns
- `.venv`, `__pycache__`, `.git`, `node_modules`
- `data/backups` (do not nest backups)
- `state/npm`

### 27.3 Verification

Every backup creates a SHA-256 manifest. Verification re-hashes all files and compares. Restore drill extracts to temp directory, verifies integrity, then cleans up.

---

## 28. Security Boundaries

| Boundary | Enforcement |
|---|---|
| Advisor-only | FORBIDDEN_SYMBOLS AST scan |
| No secret in source | SECRET_PATTERNS regex scan + git history scan |
| No runtime state in git | FORBIDDEN_TRACKED_PATHS scan |
| No cross-agent memory | Agent isolation contract |
| No Telegram from non-publisher | Tool denylist |
| No code write from non-coder | Tool denylist + worktree isolation |
| No auto-deploy | Release gate (human approval required) |
| No fabricated numerics | Python ownership contract + agent skill scan |
| Backup excludes secrets | `_should_exclude` method |
| FRED API key not logged | Redaction in heartbeat and logs |

---

## 29. Test Strategy

### 29.1 Test Categories

| Category | Path | Description |
|---|---|---|
| Unit | `engine/tests/unit/` | Individual module contracts |
| Integration | `engine/tests/integration/` | CLI and multi-module flows |
| Security | `engine/tests/security/` | Forbidden symbol scan, secret scan |
| Live | `engine/tests/live/` | Requires live MT5/FRED (excluded from CI) |

### 29.2 Required New Tests (P2.4 WP-MAIN-24X7)

See Section 29 of this document for the full list of required tests organized by subsystem.

Tests MUST NOT mock the database unless the test is explicitly testing the mock boundary. Prefer real SQLite in temp directory.

---

## 30. CI Strategy

CI runs on every push to `main`:
1. `python -m pip check` — dependency integrity
2. `python -m ruff check .` — lint
3. `python -m mypy engine/src` — type check
4. `python -m pytest -m "not live" -q --no-cov` — all non-live tests
5. `python -m build` — package build

CI MUST NOT run live tests (MT5, FRED with real key, paid AI providers).

---

## 31. Audit Evidence Requirements

The audit evidence bundle MUST be published at:
```
artifacts/p2_4_main_24x7_audit_readiness/
```

Contents: see `AUDIT_MANIFEST.json` template in the same directory.

No secret may appear in any evidence file.

---

## 32. P2.4 Closure Gates

All gates MUST be PASS before P2.4 can close. See `P2_4_BLUEPRINT_COMPLIANCE_MATRIX.md` for the full evaluation.

```
Blueprint updated before implementation                     REQUIRED
Blueprint Markdown/JSON consistency                         REQUIRED
MAIN Agent Manager runtime                                  REQUIRED
MAIN is sole user-facing agent                              REQUIRED
Specialist Agent runtime behaviour                          REQUIRED
Agent isolation (12 agents)                                 REQUIRED
Expert Skill depth (all skills)                             REQUIRED
Skill runtime discovery                                     REQUIRED
Semantic Skill validation                                   REQUIRED
Python numeric ownership                                    REQUIRED
No-suppression evidence pipeline                            REQUIRED
Integrity quarantine                                        REQUIRED
MT5 read-only multi-symbol pipeline (8 symbols)             REQUIRED
FRED adapter (resilient, non-blocking)                      REQUIRED
DGS10 daily classification                                  REQUIRED
DTWEXBGS proxy classification                               REQUIRED
FX basket (7-pair normalized)                               REQUIRED
Persistent scheduler                                        REQUIRED
Persistent queue                                            REQUIRED
Checkpoint/resume                                           REQUIRED
24/7 research cycle (MAIN-orchestrated)                     REQUIRED
Experiment lifecycle state machine                          REQUIRED
Failure-analysis loop                                       REQUIRED
Safe isolated code improvement                              REQUIRED
Windows auto-start                                          REQUIRED
Watchdog                                                    REQUIRED
Graceful shutdown                                           REQUIRED
Recovery notification (SYSTEM_RECOVERED)                    REQUIRED
External heartbeat implementation contract                  REQUIRED
Telegram incident pipeline                                  REQUIRED
Gateway/token regression                                    REQUIRED
Browser MAIN E2E                                            REQUIRED
Evidence archive (hash-chained)                             REQUIRED
Outcome ledger (hash-chained)                               REQUIRED
Knowledge/skill lifecycle                                   REQUIRED
Backup/restore                                              REQUIRED
Advisor-only enforcement                                    REQUIRED
No broker write                                             REQUIRED
No MT5 order_send                                           REQUIRED
Secret scan (source + history)                              REQUIRED
Logic conflict matrix                                       REQUIRED
Post-patch re-audit                                         REQUIRED
Lint/type/tests/build all pass                              REQUIRED
Audit evidence bundle published                             REQUIRED
Blueprint coverage                                          100%
FAIL count                                                  0
PARTIAL count                                               0
NOT_IMPLEMENTED count                                       0
NOT_RUN count                                               0
```

**P2.4 closes as:** `READY FOR PRE-PRODUCTION AUDIT — NOT PRODUCTION APPROVED`

Production approval requires a separate pre-production audit phase.

---

*End of P2.4 Master Blueprint v2*
