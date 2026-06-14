# HEARTBEAT

Health reporting must be factual and bounded. If the environment, schema, or bridge is not ready, report the failure plainly and do not simulate success.

## External Heartbeat Design (Blueprint §26)

### Purpose
The external heartbeat proves the advisor system is alive to an external monitor (UptimeRobot, Betterstack, or custom endpoint). A missed heartbeat triggers a Telegram SYSTEM_OFFLINE alert.

### Schema (ExternalHeartbeat)

Fields: `schema_version`, `system_id`, `emitted_at_utc`, `sequence`, `component_health` (gateway/python_engine/queue/mt5 each UP|DOWN|UNKNOWN), `signature` (HMAC-SHA256-hex).

### Signing
`signature = HMAC-SHA256(secret=EXTERNAL_HEARTBEAT_SECRET, message=schema_version+system_id+emitted_at_utc+str(sequence))`

### Emission Rules
- Emitted every `HEARTBEAT_INTERVAL_SECONDS` (default: 60)
- If `EXTERNAL_HEARTBEAT_ENDPOINT` is not set → `HEARTBEAT_EXTERNAL_NOT_CONFIGURED` status, no HTTP call
- On HTTP failure → log warning, continue; do NOT raise; do NOT stop the engine
- API key / secret must never appear in logs, reports, or error messages

### Missed-Heartbeat Contract
- External monitor waits 2 × interval before declaring OFFLINE
- On OFFLINE detection: Telegram SYSTEM_OFFLINE event with component health snapshot
- On recovery: Telegram SYSTEM_RECOVERED event

### Implementation
- `engine/src/openclaw_super_advisor/runtime/heartbeat.py`
- Classes: `ExternalHeartbeat`, `ComponentHealth`, `HeartbeatEmitter`
- `HeartbeatEmitter.emit()` — non-blocking; posts to endpoint or logs NOT_CONFIGURED
