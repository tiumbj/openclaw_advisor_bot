# Blueprint Traceability

- Baseline commit: `d44da0983b38408575ceedfccb00b909862ff9f0`
- Generated UTC: `2026-06-15T00:57:20.800653Z`
- Evidence hash SHA256: `8865a7a03aa352e3d5cc5eb63dbbb18478a692f53cc8929fdb3a996f5e534128`

- `MAIN runtime orchestration` -> planner/router helpers only -> PPA-0003 -> HIGH
- `Data numerics carry realtime_class provenance` -> TickRecord/BarRecord omit realtime_class -> PPA-0004 -> HIGH
- `FRED live validation` -> unit tests only, no live credential evidence -> PPA-0009 -> MEDIUM
- `Runtime operator readiness` -> doctor warnings remain -> PPA-0008 -> MEDIUM
