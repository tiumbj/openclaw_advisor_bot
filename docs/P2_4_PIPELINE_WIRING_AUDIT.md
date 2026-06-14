# P2.4 Pipeline Wiring Audit

## Verified Current Flow

- Python evidence -> `super-advisor`
- `super-advisor` -> report validation
- `super-advisor` -> publisher skill only as a static capability

## Missing Wiring

- No `xau-strategy-auditor` runtime agent
- No `system-coder-auditor` runtime agent
- No `telegram-publisher` runtime agent
- No agent-to-agent bindings
- No explicit loop-prevention routing contract in runtime
- No separate replay or shadow pipeline

## Safety Observations

- Tool deny lists remain strict
- Gateway and messaging tools are denied in the current runtime
- No direct execution path is available
- No live Telegram delivery was attempted during this audit
