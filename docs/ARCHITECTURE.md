# Architecture

Version: `1.2.1`  
Phase: `P2.1`

OpenClaw Super Advisor remains an **alert/advisor-only** foundation.

1. `config\openclaw.template.json` defines the read-only runtime shape.
2. `openclaw-advisor` validates environment, skills, rendered config, and repository security boundaries.
3. `workspace\skills\*\SKILL.md` are statically validated and runtime-discovered from the config template.
4. MT5 support is limited to the explicit read-only market-data foundation; no execution path,
   order bridge, broker action, or Telegram trading alert flow is enabled in this phase.
