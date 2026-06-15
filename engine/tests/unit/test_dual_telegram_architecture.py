from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from openclaw_super_advisor.env import audit_environment
from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.telegram import (
    ApprovedPublicationPayload,
    MarketAlertDedupStore,
    OperatorReply,
    TelegramMarketTransport,
    TelegramOperatorTransport,
    TelegramPolicyError,
    TelegramPublisher,
    validate_dual_bot_contract,
)


def _future(seconds: int = 3600) -> str:
    return (datetime.now(tz=UTC) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _past() -> str:
    return (datetime.now(tz=UTC) - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")


def _payload(**overrides: Any) -> ApprovedPublicationPayload:
    base = ApprovedPublicationPayload(
        event_type="SUPER_POTENTIAL_CONFIRMED",
        severity="HIGH",
        symbol="XAUUSD",
        timeframe="M15",
        status="CONFIRMED",
        headline="SUPER POTENTIAL",
        market_context="Python evidence package",
        trigger_reasons=("EMA alignment", "RSI confirmation"),
        key_levels=("support 2300", "resistance 2320"),
        invalidation="close below 2295",
        data_quality="VALID",
        event_time_utc="2026-06-15T00:00:00Z",
        evidence_ids=("ev-1", "ev-2"),
        correlation_id="corr-1234567890",
        dedup_key="SUPER_POTENTIAL_CONFIRMED:XAUUSD:M15:setup-1:trigger-v1",
        expires_at_utc=_future(),
        setup_id="setup-1",
        trigger_version="trigger-v1",
        direction="BUY",
        provenance={"source": "python-signal-engine"},
    )
    return replace(base, **overrides)


def test_market_publisher_formats_thai_snapshot_and_marks_dedup(tmp_path: Path) -> None:
    publisher = TelegramPublisher(MarketAlertDedupStore(tmp_path / "dedup.json"))

    delivery = publisher.format_market(_payload())

    assert delivery.target_kind == "market"
    assert delivery.parse_mode == "HTML"
    assert delivery.priority == "HIGH"
    assert "XAUUSD | SUPER POTENTIAL" in delivery.formatted_thai_text
    assert "สถานะ: ยืนยันแล้ว" in delivery.formatted_thai_text
    assert "ทิศทาง: BUY" in delivery.formatted_thai_text
    assert "หลักฐาน" not in delivery.formatted_thai_text
    with pytest.raises(TelegramPolicyError, match="duplicate"):
        publisher.format_market(_payload())


def test_market_publisher_rejects_expired_missing_provenance_and_wrong_dedup(
    tmp_path: Path,
) -> None:
    publisher = TelegramPublisher(MarketAlertDedupStore(tmp_path / "dedup.json"))

    with pytest.raises(TelegramPolicyError, match="expired"):
        publisher.format_market(_payload(expires_at_utc=_past()))
    with pytest.raises(TelegramPolicyError, match="provenance"):
        publisher.format_market(_payload(provenance={}))
    with pytest.raises(TelegramPolicyError, match="dedup_key"):
        publisher.format_market(_payload(dedup_key="manual"))


def test_operator_transport_accepts_only_authorized_user_and_replies_same_chat() -> None:
    sent: list[dict[str, Any]] = []

    def post(_: str, payload: dict[str, Any]) -> dict[str, Any]:
        sent.append(payload)
        return {"ok": True}

    transport = TelegramOperatorTransport(
        token="operator-token",
        owner_user_id="111",
        allowed_chat_ids=("222",),
        http_post=post,
    )
    inbound = transport.receive_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 7,
                "from": {"id": 111},
                "chat": {"id": 222},
                "text": "วิเคราะห์ XAUUSD",
            },
        }
    )
    assert inbound.text == "วิเคราะห์ XAUUSD"

    transport.send_reply(
        OperatorReply(
            chat_id=inbound.chat_id,
            reply_to_message_id=inbound.message_id,
            text="รับทราบ",
            correlation_id=inbound.correlation_id,
        )
    )
    assert sent == [{"chat_id": "222", "text": "รับทราบ", "reply_to_message_id": 7}]

    with pytest.raises(TelegramPolicyError, match="unauthorized"):
        transport.receive_update(
            {
                "message": {
                    "message_id": 8,
                    "from": {"id": 333},
                    "chat": {"id": 222},
                    "text": "hello",
                },
            }
        )


def test_market_and_operator_transports_are_isolated(tmp_path: Path) -> None:
    publisher = TelegramPublisher(MarketAlertDedupStore(tmp_path / "dedup.json"))
    delivery = publisher.format_market(_payload())
    operator = TelegramOperatorTransport(
        token="operator-token",
        owner_user_id="111",
        allowed_chat_ids=("222",),
        http_post=lambda _token, payload: {"ok": True, "payload": payload},
    )
    market = TelegramMarketTransport(
        token="market-token",
        target_chat_id="-100",
        http_post=lambda _token, payload: {"ok": True, "payload": payload},
    )

    with pytest.raises(TelegramPolicyError, match="operator bot cannot"):
        operator.send_market_alert(delivery)
    with pytest.raises(TelegramPolicyError, match="market bot inbound"):
        market.receive_update({"message": {"text": "question"}})
    with pytest.raises(TelegramPolicyError, match="market bot cannot answer"):
        market.send_reply(OperatorReply("222", 1, "reply", "corr"))

    result = market.send_alert(delivery)
    assert result["payload"]["chat_id"] == "-100"


def test_dual_bot_env_contract_rejects_duplicate_tokens() -> None:
    issues = validate_dual_bot_contract(
        {
            "OPENCLAW_TELEGRAM_OPERATOR_ENABLED": "true",
            "OPENCLAW_TELEGRAM_OPERATOR_BOT_TOKEN": "same",
            "OPENCLAW_TELEGRAM_OPERATOR_OWNER_USER_ID": "111",
            "OPENCLAW_TELEGRAM_OPERATOR_ALLOWED_CHAT_IDS": "222",
            "OPENCLAW_TELEGRAM_MARKET_ENABLED": "true",
            "OPENCLAW_TELEGRAM_MARKET_BOT_TOKEN": "same",
            "OPENCLAW_TELEGRAM_MARKET_TARGET_CHAT_ID": "-100",
        }
    )

    assert any("distinct" in issue for issue in issues)


def test_environment_audit_reports_dual_bot_contract_issues(sample_project: Path) -> None:
    paths = build_paths(sample_project)
    env_path = paths.runtime_env_path
    text = env_path.read_text(encoding="utf-8")
    replacements = {
        "OPENCLAW_TELEGRAM_OPERATOR_ENABLED=false": (
            "OPENCLAW_TELEGRAM_OPERATOR_ENABLED=true"
        ),
        "OPENCLAW_TELEGRAM_MARKET_ENABLED=false": "OPENCLAW_TELEGRAM_MARKET_ENABLED=true",
        "OPENCLAW_TELEGRAM_OPERATOR_BOT_TOKEN=": "OPENCLAW_TELEGRAM_OPERATOR_BOT_TOKEN=same",
        "OPENCLAW_TELEGRAM_MARKET_BOT_TOKEN=": "OPENCLAW_TELEGRAM_MARKET_BOT_TOKEN=same",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    env_path.write_text(text, encoding="utf-8")

    report = audit_environment(paths)

    assert not report.valid
    assert any(issue.name == "OPENCLAW_TELEGRAM_BOT_TOKENS" for issue in report.issues)
