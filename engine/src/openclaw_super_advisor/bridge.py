from __future__ import annotations

from dataclasses import asdict

from .schemas import BridgeEnvelope, EvidencePacketSchema


def bridge_contract_summary() -> dict[str, object]:
    return {
        "bridge_mode": "disabled",
        "advisor_only": True,
        "execution_allowed": False,
        "required_fields": list(asdict(BridgeEnvelope("", "", "", True, False)).keys()),
        "schema_placeholder": asdict(EvidencePacketSchema()),
    }
