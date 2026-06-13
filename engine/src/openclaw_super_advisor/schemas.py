from __future__ import annotations

from dataclasses import dataclass

from ._version import __version__


@dataclass(frozen=True)
class EvidencePacketSchema:
    schema_version: str = __version__
    advisor_only: bool = True
    execution_allowed: bool = False


@dataclass(frozen=True)
class BridgeEnvelope:
    schema_version: str
    event_id: str
    timestamp_utc: str
    advisor_only: bool
    execution_allowed: bool
