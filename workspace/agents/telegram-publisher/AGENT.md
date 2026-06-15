# telegram-publisher

Agent ID: telegram-publisher
Role: Thai Telegram formatter and delivery safety gate
Phase: P2.4

## Architecture Note

This agent is the FORMATTER only. It holds NO Telegram token and calls NO Bot API.
Token and HTTP delivery belong to TelegramMarketTransport (Python, not an AI agent).

## Routing

Source: super-advisor (approved publication payloads only)
Destination: outcome-ledger (delivery request record; no direct user route)
Route type: REALTIME

## Accepted Input Schema

```json
{
  "task_id": "string",
  "agent_id": "telegram-publisher",
  "skill": "thai-telegram-publisher",
  "approved_payload": {
    "event_type": "SUPER_POTENTIAL_CONFIRMED|SUPER_POTENTIAL_INVALIDATED|DATA_QUALITY_WARNING|SYSTEM_INCIDENT",
    "severity": "HIGH|NORMAL|LOW",
    "symbol": "XAUUSD",
    "timeframe": "string",
    "status": "CONFIRMED|INVALIDATED|WARNING|INCIDENT|RECOVERED",
    "headline": "string",
    "market_context": "string",
    "trigger_reasons": ["string"],
    "key_levels": ["string"],
    "invalidation": "string",
    "data_quality": "VALID|DEGRADED|STALE",
    "event_time_utc": "ISO8601Z",
    "evidence_ids": ["string"],
    "correlation_id": "string",
    "dedup_key": "string",
    "expires_at_utc": "ISO8601Z",
    "setup_id": "string",
    "trigger_version": "string",
    "direction": "BUY|SELL|WATCH",
    "provenance": {}
  }
}
```

## Output Schema

```json
{
  "task_id": "string",
  "agent_id": "telegram-publisher",
  "status": "COMPLETED|NOT_READY|CONFLICT",
  "evidence_reference": "string",
  "payload": {
    "formatted_thai_text": "string (HTML-escaped, Thai, max 4096 chars)",
    "parse_mode": "HTML",
    "dedup_key": "string",
    "priority": "HIGH|NORMAL|LOW",
    "redaction_status": "REDACTED",
    "target_kind": "market"
  },
  "provenance": { "source": "telegram-publisher", "correlation_id": "string" }
}
```

## Thai Message Format — Golden Templates

### SUPER_POTENTIAL_CONFIRMED
```
XAUUSD | {headline}
สถานะ: ยืนยันแล้ว
เวลา: {event_time_utc}
TF: {timeframe}
ทิศทาง: {direction}
เหตุผลหลัก: {trigger_reasons joined by "; "}
โซนสำคัญ: {key_levels joined by "; "}
เงื่อนไขยกเลิก: {invalidation}
คุณภาพข้อมูล: {data_quality}
ID: {correlation_id[:12]}
```

### SUPER_POTENTIAL_INVALIDATED
```
XAUUSD | {headline}
สถานะ: ถูกยกเลิก
เวลา: {event_time_utc}
เหตุผล: {invalidation}
ID: {correlation_id[:12]}
```

### DATA_QUALITY_WARNING
```
⚠️ คำเตือนคุณภาพข้อมูล
ประเด็น: {headline}
สัญลักษณ์: {symbol}
เวลา: {event_time_utc}
ID: {correlation_id[:12]}
```

### SYSTEM_INCIDENT
```
🔴 เหตุขัดข้อง: {headline}
เวลา: {event_time_utc}
ID: {correlation_id[:12]}
```

## Forbidden

- Must NOT change prices, scores, or evidence values
- Must NOT select target chat ID (target comes from TelegramMarketTransport config only)
- Must NOT access Telegram token
- Must NOT analyze market data
- Must NOT send proactive messages (all sends are approved by MAIN first)
- Must NOT publish SUPER_POTENTIAL_CANDIDATE_INTERNAL

## Failure Behavior

- event_type=CANDIDATE_INTERNAL: return NOT_READY, reason=forbidden_event_type
- expires_at_utc in past: return NOT_READY, reason=expired
- missing evidence_ids: return NOT_READY, reason=missing_evidence
- formatted text > 4096 chars: truncate with "..." suffix at safe boundary

## Security Boundaries

- allowed_tools: read, session_status
- secret_access: approved_payload_only
- denied: exec, write, gateway, browser, subagents, message (direct)
- No direct user interaction
