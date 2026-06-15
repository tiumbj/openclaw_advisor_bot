from __future__ import annotations

import html
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib import parse, request

from .events import canonical_json, sha256_hex

PublicationEventType = Literal[
    "SUPER_POTENTIAL_CONFIRMED",
    "SUPER_POTENTIAL_INVALIDATED",
    "DATA_QUALITY_WARNING",
    "SYSTEM_INCIDENT",
    "SYSTEM_RECOVERED",
]

ALLOWED_MARKET_PUBLICATION_EVENTS: tuple[str, ...] = (
    "SUPER_POTENTIAL_CONFIRMED",
    "SUPER_POTENTIAL_INVALIDATED",
    "DATA_QUALITY_WARNING",
    "SYSTEM_INCIDENT",
    "SYSTEM_RECOVERED",
)
FORBIDDEN_MARKET_PUBLICATION_EVENTS: tuple[str, ...] = (
    "SUPER_POTENTIAL_CANDIDATE_INTERNAL",
    "SYSTEM_HEALTH",
)
TELEGRAM_LIMIT = 4096


class TelegramPolicyError(RuntimeError):
    pass


class TelegramDeliveryError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True)
class ApprovedPublicationPayload:
    event_type: PublicationEventType
    severity: str
    symbol: str
    timeframe: str
    status: str
    headline: str
    market_context: str
    trigger_reasons: tuple[str, ...]
    key_levels: tuple[str, ...]
    invalidation: str
    data_quality: str
    event_time_utc: str
    evidence_ids: tuple[str, ...]
    correlation_id: str
    dedup_key: str
    expires_at_utc: str
    setup_id: str
    trigger_version: str
    direction: str = "WATCH"
    provenance: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class TelegramDeliveryRequest:
    formatted_thai_text: str
    parse_mode: str
    reply_to_message_id: int | None
    dedup_key: str
    priority: str
    redaction_status: str
    target_kind: Literal["market", "operator"]
    correlation_id: str


@dataclass(frozen=True)
class TelegramBotIdentity:
    bot_id: int
    username: str
    first_name: str


@dataclass(frozen=True)
class OperatorInboundMessage:
    update_id: int
    user_id: str
    chat_id: str
    message_id: int
    text: str
    correlation_id: str


@dataclass(frozen=True)
class OperatorReply:
    chat_id: str
    reply_to_message_id: int
    text: str
    correlation_id: str


class MarketAlertDedupStore:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, float]:
        if not self.state_path.exists():
            return {}
        return {
            str(key): float(value)
            for key, value in json.loads(self.state_path.read_text(encoding="utf-8")).items()
        }

    def seen(self, key: str, now: float | None = None) -> bool:
        now = now or time.time()
        values = self._load()
        expiry = values.get(key)
        return expiry is not None and expiry > now

    def mark(self, key: str, ttl_seconds: int, now: float | None = None) -> None:
        now = now or time.time()
        values = self._load()
        values[key] = now + ttl_seconds
        self.state_path.write_text(canonical_json(values), encoding="utf-8")


class TelegramPublisher:
    """Formatter and safety gate for market/system publications.

    This class intentionally has no Telegram token and never calls Bot API.
    """

    def __init__(self, dedup_store: MarketAlertDedupStore, *, cooldown_seconds: int = 3600) -> None:
        self.dedup_store = dedup_store
        self.cooldown_seconds = cooldown_seconds

    def format_market(self, payload: ApprovedPublicationPayload) -> TelegramDeliveryRequest:
        self._validate_payload(payload)
        if self.dedup_store.seen(payload.dedup_key):
            raise TelegramPolicyError("duplicate market publication rejected")
        status_text = {
            "CONFIRMED": "ยืนยันแล้ว",
            "INVALIDATED": "ถูกยกเลิก",
            "WARNING": "เตือนคุณภาพข้อมูล",
            "INCIDENT": "เหตุขัดข้อง",
            "RECOVERED": "ระบบกลับมาทำงาน",
        }.get(payload.status, payload.status)
        lines = [
            f"XAUUSD | {html.escape(payload.headline)}",
            f"สถานะ: {html.escape(status_text)}",
            f"เวลา: {html.escape(payload.event_time_utc)}",
            f"TF: {html.escape(payload.timeframe)}",
            f"ทิศทาง: {html.escape(payload.direction)}",
            "เหตุผลหลัก: " + html.escape("; ".join(payload.trigger_reasons)),
            "โซนสำคัญ: " + html.escape("; ".join(payload.key_levels)),
            "เงื่อนไขยกเลิก: " + html.escape(payload.invalidation),
            "คุณภาพข้อมูล: " + html.escape(payload.data_quality),
            f"ID: {html.escape(payload.correlation_id[:12])}",
        ]
        message = "\n".join(lines)
        if len(message) > TELEGRAM_LIMIT:
            raise TelegramPolicyError("formatted message exceeds Telegram limit")
        self.dedup_store.mark(payload.dedup_key, self.cooldown_seconds)
        return TelegramDeliveryRequest(
            formatted_thai_text=message,
            parse_mode="HTML",
            reply_to_message_id=None,
            dedup_key=payload.dedup_key,
            priority=self._priority(payload),
            redaction_status="REDACTED",
            target_kind="market",
            correlation_id=payload.correlation_id,
        )

    def _validate_payload(self, payload: ApprovedPublicationPayload) -> None:
        if payload.event_type in FORBIDDEN_MARKET_PUBLICATION_EVENTS:
            raise TelegramPolicyError(f"event type {payload.event_type} must not be published")
        if payload.event_type not in ALLOWED_MARKET_PUBLICATION_EVENTS:
            raise TelegramPolicyError(f"unsupported publication event type {payload.event_type}")
        if parse_utc(payload.expires_at_utc) <= datetime.now(tz=UTC):
            raise TelegramPolicyError("expired publication payload rejected")
        if not payload.evidence_ids:
            raise TelegramPolicyError("publication requires evidence_ids")
        if not payload.provenance:
            raise TelegramPolicyError("publication requires provenance")
        expected_key = (
            f"{payload.event_type}:{payload.symbol}:{payload.timeframe}:"
            f"{payload.setup_id}:{payload.trigger_version}"
        )
        if payload.dedup_key != expected_key:
            raise TelegramPolicyError("dedup_key does not match market publication contract")

    def _priority(self, payload: ApprovedPublicationPayload) -> str:
        if payload.severity.upper() in {"CRITICAL", "HIGH"}:
            return "HIGH"
        if payload.event_type in {"SUPER_POTENTIAL_CONFIRMED", "SUPER_POTENTIAL_INVALIDATED"}:
            return "NORMAL"
        return "LOW"


class TelegramOperatorTransport:
    def __init__(
        self,
        *,
        token: str,
        owner_user_id: str,
        allowed_chat_ids: tuple[str, ...],
        http_post: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        if not token:
            raise TelegramPolicyError("operator bot token is required")
        if not owner_user_id or not allowed_chat_ids:
            raise TelegramPolicyError("operator owner and allowed chats are required")
        self._token = token
        self.owner_user_id = owner_user_id
        self.allowed_chat_ids = allowed_chat_ids
        self._http_post = http_post or _telegram_post

    def receive_update(self, update: Mapping[str, Any]) -> OperatorInboundMessage:
        message = update.get("message")
        if not isinstance(message, Mapping):
            raise TelegramPolicyError("operator update has no message")
        sender = message.get("from")
        chat = message.get("chat")
        if not isinstance(sender, Mapping) or not isinstance(chat, Mapping):
            raise TelegramPolicyError("operator update missing sender/chat")
        user_id = str(sender.get("id", ""))
        chat_id = str(chat.get("id", ""))
        if user_id != self.owner_user_id or chat_id not in self.allowed_chat_ids:
            raise TelegramPolicyError("unauthorized operator Telegram update")
        message_id = int(message.get("message_id", 0))
        return OperatorInboundMessage(
            update_id=int(update.get("update_id", 0)),
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            text=str(message.get("text", "")),
            correlation_id=sha256_hex(f"{chat_id}:{message_id}")[:24],
        )

    def send_reply(self, reply: OperatorReply) -> Mapping[str, Any]:
        if reply.chat_id not in self.allowed_chat_ids:
            raise TelegramPolicyError("operator reply target is not trusted inbound chat")
        return self._http_post(
            self._token,
            {
                "chat_id": reply.chat_id,
                "text": reply.text,
                "reply_to_message_id": reply.reply_to_message_id,
            },
        )

    def send_market_alert(self, _: TelegramDeliveryRequest) -> Mapping[str, Any]:
        raise TelegramPolicyError("operator bot cannot send proactive market alerts")


class TelegramMarketTransport:
    def __init__(
        self,
        *,
        token: str,
        target_chat_id: str,
        target_thread_id: str = "",
        http_post: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        if not token or not target_chat_id:
            raise TelegramPolicyError("market bot token and target chat are required")
        self._token = token
        self.target_chat_id = target_chat_id
        self.target_thread_id = target_thread_id
        self._http_post = http_post or _telegram_post

    def send_alert(self, delivery: TelegramDeliveryRequest) -> Mapping[str, Any]:
        if delivery.target_kind != "market":
            raise TelegramPolicyError("market transport accepts only market delivery requests")
        payload: dict[str, Any] = {
            "chat_id": self.target_chat_id,
            "text": delivery.formatted_thai_text,
            "parse_mode": delivery.parse_mode,
            "disable_web_page_preview": True,
        }
        if self.target_thread_id:
            payload["message_thread_id"] = self.target_thread_id
        return self._http_post(self._token, payload)

    def receive_update(self, _: Mapping[str, Any]) -> None:
        raise TelegramPolicyError("market bot inbound is disabled")

    def send_reply(self, _: OperatorReply) -> None:
        raise TelegramPolicyError("market bot cannot answer operator messages")


def validate_dual_bot_contract(values: Mapping[str, str]) -> tuple[str, ...]:
    issues: list[str] = []
    operator_enabled = values.get("OPENCLAW_TELEGRAM_OPERATOR_ENABLED", "false").lower() == "true"
    market_enabled = values.get("OPENCLAW_TELEGRAM_MARKET_ENABLED", "false").lower() == "true"
    operator_token = values.get("OPENCLAW_TELEGRAM_OPERATOR_BOT_TOKEN", "")
    market_token = values.get("OPENCLAW_TELEGRAM_MARKET_BOT_TOKEN", "")
    if operator_enabled:
        for name in (
            "OPENCLAW_TELEGRAM_OPERATOR_BOT_TOKEN",
            "OPENCLAW_TELEGRAM_OPERATOR_OWNER_USER_ID",
            "OPENCLAW_TELEGRAM_OPERATOR_ALLOWED_CHAT_IDS",
        ):
            if not values.get(name, ""):
                issues.append(f"{name}: required when operator bot is enabled")
    if market_enabled:
        for name in (
            "OPENCLAW_TELEGRAM_MARKET_BOT_TOKEN",
            "OPENCLAW_TELEGRAM_MARKET_TARGET_CHAT_ID",
        ):
            if not values.get(name, ""):
                issues.append(f"{name}: required when market bot is enabled")
    if operator_token and market_token and operator_token == market_token:
        issues.append("OPENCLAW_TELEGRAM_BOT_TOKENS: operator and market tokens must be distinct")
    if (
        values.get("OPENCLAW_TELEGRAM_MARKET_INBOUND_ENABLED", "false").lower() == "true"
        and market_enabled
    ):
        issues.append("OPENCLAW_TELEGRAM_MARKET_INBOUND_ENABLED: market inbound must stay disabled")
    if (
        values.get("OPENCLAW_TELEGRAM_OPERATOR_MODE", "polling") == "polling"
        and values.get("OPENCLAW_TELEGRAM_OPERATOR_WEBHOOK_ENABLED", "false").lower() == "true"
    ):
        issues.append("OPENCLAW_TELEGRAM_OPERATOR_MODE: polling and webhook cannot both be enabled")
    return tuple(issues)


def _telegram_post(token: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    encoded = parse.urlencode({key: value for key, value in payload.items() if value is not None})
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    req = request.Request(endpoint, data=encoded.encode("utf-8"), method="POST")
    with request.urlopen(req, timeout=15) as response:
        data = cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
    if not data.get("ok"):
        raise TelegramDeliveryError("Telegram Bot API rejected sendMessage")
    return data


def redacted_transport_evidence(identity: TelegramBotIdentity) -> dict[str, Any]:
    return {
        "bot_id_hash": sha256_hex(str(identity.bot_id))[:12],
        "username": identity.username,
        "first_name": identity.first_name,
        "verified_at_utc": utc_now(),
    }


__all__ = [
    "ALLOWED_MARKET_PUBLICATION_EVENTS",
    "ApprovedPublicationPayload",
    "MarketAlertDedupStore",
    "OperatorInboundMessage",
    "OperatorReply",
    "TelegramBotIdentity",
    "TelegramDeliveryRequest",
    "TelegramMarketTransport",
    "TelegramOperatorTransport",
    "TelegramPolicyError",
    "TelegramPublisher",
    "asdict",
    "redacted_transport_evidence",
    "validate_dual_bot_contract",
]
