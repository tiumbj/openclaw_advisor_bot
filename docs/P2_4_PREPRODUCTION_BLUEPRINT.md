# P2.4 Pre-production Blueprint

## 1. Current Architecture

- Package version: `1.2.5`
- Current validated phase: `P2.4`
- Runtime agent registry contains one configured agent: `super-advisor`
- Routing bindings are empty
- Gateway bind target is loopback on port `18789`
- Control UI is disabled
- Shell env fallback is disabled in the rendered config
- Supported providers are restricted to `openai`, `claude`, `gemini`, and `deepseek`
- Unsupported providers are removed from the tracked provider policy and must stay unsupported
- Current runtime skills discovered for `super-advisor`: 7 ready workspace skills
- Learning, backup, and self-improvement layers are not implemented as separate production subsystems yet

## 2. Confirmed Defects

- `openclaw status --json` reports the gateway as listening but auth mismatched with the current shell environment
- `openclaw models status --json` still reflects historical provider credentials in shell env diagnostics outside git
- The repository now reports package version `1.2.5`
- Only `super-advisor` exists; the requested `xau-strategy-auditor`, `system-coder-auditor`, and `telegram-publisher` agents do not exist as isolated runtime agents
- No routing bindings exist, so agent-to-agent routing is not actually wired
- No separate immutable evidence archive, outcome ledger, agent memory store, or skill candidate store exists yet
- No backup/restore commands, integrity verification, retention policy, or restore drill exists yet
- No controlled self-improvement dry run exists yet

## 3. Target Architecture

- Keep the system advisor-only
- Preserve read-only MT5 access
- Keep the four-provider allowlist only
- Separate provider policy from live provider smoke testing
- Add isolated agents with unique workspaces, agent directories, and session stores
- Add explicit skill allowlists and tool policies per agent
- Add structured routing for evidence review, strategy review, code audit, and publication
- Add immutable evidence archive, append-only outcome ledger, per-agent memory, and skill candidate lifecycle storage
- Add backup and restore routines for all non-secret operational data
- Add controlled self-improvement proposal and isolated patch workflow only

## 4. Agent Topology

- `super-advisor`
  - Coordinator, safety policy, evidence validation, final publication decision, incident coordination
  - No numeric calculation authority
  - No source-code modification authority
- `xau-strategy-auditor`
  - Read-only XAUUSD strategy review, multi-timeframe reasoning, chart pattern audit, alert-quality review
  - No Telegram tool
  - No direct MT5 tool
- `system-coder-auditor`
  - Read-only code audit by default
  - Isolated worktree patch mode only
  - No direct access to runtime secrets
- `telegram-publisher`
  - Thai formatting and delivery of approved payloads only
  - No market analysis or score authority
  - No code-write authority

## 5. Skill Matrix

- `super-advisor`
  - Required: `advisor-safety-contract`, `environment-health`, `evidence-audit`, `agent-orchestration-contract`, `super-potential-review`, `incident-reporting`, `publication-policy`
- `xau-strategy-auditor`
  - Required: `xauusd-market-analysis`, `multi-timeframe-structure-review`, `price-action-order-block`, `chart-pattern-filter-review`, `candlestick-microstructure`, `strategy-logic-audit`, `realtime-evidence-review`, `super-potential-audit`, `alert-quality-improvement`
- `system-coder-auditor`
  - Required: `python-pipeline-micro-audit`, `code-architecture-review`, `logic-conflict-detection`, `dead-code-and-duplicate-review`, `test-and-regression-design`, `blueprint-compliance-audit`, `safe-patch-workflow`, `release-and-rollback`, `skill-improvement-proposal`
- `telegram-publisher`
  - Required: `thai-telegram-publisher`, `telegram-message-contract`, `telegram-delivery-safety`, `telegram-deduplication-throttle`, `telegram-retry-and-dead-letter`, `telegram-security-redaction`

## 6. Tool Matrix

- `super-advisor`
  - Allowed: read approved evidence, session status, internal agent invocation, approved publisher invocation, incident logging
  - Denied: shell, source write, raw MT5, direct Telegram message, credential access, browser, arbitrary HTTP
- `xau-strategy-auditor`
  - Allowed: read approved evidence packet, read strategy specification, return structured review
  - Denied: write, shell, Telegram, MT5, credential access, direct code mutation
- `system-coder-auditor`
  - Allowed in read-only mode: read source bundle, read tests, read dependency graph
  - Controlled patch mode: isolated worktree only, allowlisted development commands
  - Denied: direct write to `main`, push without release gate, runtime `.env`, Telegram, MT5, broker, production state, service control
- `telegram-publisher`
  - Allowed: read approved publication payload, Telegram send tool, delivery-result logging
  - Denied: market analysis, source write, shell, provider configuration, MT5, internal score modification

## 7. Message Routing

- Python deterministic pipeline -> structured evidence packet -> `super-advisor`
- `super-advisor` -> `xau-strategy-auditor` -> structured review
- `super-advisor` -> final policy -> `telegram-publisher`
- `telegram-publisher` -> Telegram delivery
- Code-audit flow must stay separate from realtime signal generation
- Telegram publisher must not invoke the XAU analyst
- Circular routing must be rejected

## 8. Data Ownership

- Python owns numeric market values, score values, and all calculation outputs
- Agents may only review or relay evidence; they may not invent or alter numbers
- Missing values must stay `UNKNOWN`
- Telegram formatting may not fabricate prices, targets, or probabilities

## 9. Event Schemas

- `SYSTEM_HEALTH`
- `DATA_QUALITY_WARNING`
- `SUPER_POTENTIAL_CANDIDATE_INTERNAL`
- `SUPER_POTENTIAL_CONFIRMED`
- `SUPER_POTENTIAL_INVALIDATED`
- `SYSTEM_INCIDENT`

## 10. Persistence And Backup

- Immutable evidence archive: redacted structured records with SHA-256 and provenance metadata
- Outcome ledger: append-only candidate/publication/outcome history
- Agent memory: per-agent `MEMORY.md` and dated memory notes
- Skill candidate store: observation -> candidate -> tested -> rejected/approved -> released/rolled back
- Backup must include manifests, ledger, memory, skill versions, config templates, evaluation results, and release metadata

## 11. Security Boundaries

- Advisor-only contract remains active
- No execution, broker writes, or trade lifecycle control
- No secret values in reports or memory
- No unrestricted self-modification
- No direct write to `main`
- No automatic deployment

## 12. Test Plan

- Report artifact integrity tests
- Provider policy tests
- Agent registry and skill discovery tests
- Routing/binding tests
- Telegram formatting snapshot tests
- Backup/restore tests
- Self-improvement dry-run tests
- Secret-scan tests
- CI verification

## 13. Rollback Plan

- Keep a rollback commit before agent/routing/backup changes
- Use isolated worktree patches for experimental coder changes
- Validate before merge
- Remove only the last experimental patch on failure
- Preserve the original safety contract and all working provider policy tests

## 14. Files To Change

- `engine/src/openclaw_super_advisor/_version.py`
- `engine/src/openclaw_super_advisor/cli.py`
- `engine/src/openclaw_super_advisor/config.py`
- `engine/src/openclaw_super_advisor/env.py`
- `engine/src/openclaw_super_advisor/providers.py`
- `engine/src/openclaw_super_advisor/skills.py`
- `config/openclaw.template.json`
- `workspace/skills/*/SKILL.md`
- `state/openclaw.json`
- `state/agents/*`
- `docs/*P2_4*`
- `engine/tests/*`

## 15. Expected Risks

- Gateway auth mismatch may continue to block live provider verification until the runtime token source is reconciled
- Additional agent topology may expose new validation failures if skills or tool policies are inconsistent
- Backup and memory foundations may need more storage layout work than the current repo contains
- Telegram dry-run may need channel-specific credential alignment before any live smoke test
