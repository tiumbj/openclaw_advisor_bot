# Architecture

Version: `1.2.15`
Phase: `P2.4`

OpenClaw Super Advisor remains an **alert/advisor-only** foundation.

## Agent Capability Registry

1. `workspace\agents\*\AGENT.md` is the authoring source for agent capability definitions.
2. `openclaw-advisor validate-agent-registry --write` parses those definitions into the authoritative machine-readable registry at `config\agent_capability_registry.json`.
3. The generated registry is deterministic and carries `schema_version`, `registry_version`, `registry_hash`, `agent_count`, and `skill_count`.
4. `knowledge-skill-manager` owns registry generation, validation, and stale-registry detection.
5. `super-advisor` consumes the validated registry for agent discovery, task routing, and user-facing agent-duty answers.

## Startup and Fail-Closed States

1. At startup, manager-facing commands load the generated registry and validate it against `workspace\agents\*\AGENT.md` and the rendered config metadata.
2. The runtime states are `AGENT_REGISTRY_READY`, `AGENT_REGISTRY_DEGRADED`, and `AGENT_REGISTRY_INVALID`.
3. Normal orchestration and manager discovery are allowed only when the registry is `AGENT_REGISTRY_READY`.
4. Missing, stale, malformed, or contradictory registry state fails closed; the manager does not guess agent responsibilities or silently route to generic agents.

## Control Plane

1. `config\openclaw.template.json` defines the read-only runtime shape and exposes registry metadata under `agentCapabilityRegistry`.
2. `openclaw-advisor` validates environment, skills, agent registry, rendered config, routing, and repository security boundaries.
3. `workspace\skills\*\SKILL.md` are statically validated and runtime-discovered from the config template.
4. MT5 support remains limited to the explicit read-only market-data foundation; no execution path, order bridge, broker action, or production release path is enabled in this phase.
