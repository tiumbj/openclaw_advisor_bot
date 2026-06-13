from __future__ import annotations

from dataclasses import asdict

from ._version import PHASE, __version__
from .schemas import BridgeEnvelope, EvidencePacketSchema


def bridge_contract_summary() -> dict[str, object]:
    return {
        "version": __version__,
        "phase": PHASE,
        "bridge_mode": "disabled",
        "advisor_only": True,
        "execution_allowed": False,
        "required_fields": list(asdict(BridgeEnvelope(__version__, "", "", True, False)).keys()),
        "schema_placeholder": asdict(EvidencePacketSchema()),
    }
