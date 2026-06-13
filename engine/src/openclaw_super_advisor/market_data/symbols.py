from __future__ import annotations

from .backend import DiscoveredSymbol, ResolvedSymbol
from .normalization import utc_now
from .schemas import QualityIncident


def normalized_symbol_name(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def resolve_symbols(
    targets: tuple[tuple[str, tuple[str, ...]], ...],
    discovered: list[DiscoveredSymbol],
) -> tuple[list[ResolvedSymbol], list[QualityIncident]]:
    lookup: dict[str, list[DiscoveredSymbol]] = {}
    for symbol in discovered:
        candidates = {symbol.broker_symbol, symbol.description}
        for candidate in candidates:
            key = normalized_symbol_name(candidate)
            lookup.setdefault(key, []).append(symbol)

    resolved: list[ResolvedSymbol] = []
    incidents: list[QualityIncident] = []
    for logical_symbol, aliases in targets:
        match_candidates = (logical_symbol, *aliases)
        matches: list[DiscoveredSymbol] = []
        for candidate in match_candidates:
            matches.extend(lookup.get(normalized_symbol_name(candidate), []))
        unique_matches = {item.broker_symbol: item for item in matches if item.broker_symbol}
        if not unique_matches:
            incidents.append(
                QualityIncident(
                    event_kind="missing_symbol_mapping",
                    logical_symbol=logical_symbol,
                    timeframe=None,
                    detail="configured symbol could not be resolved from broker discovery",
                    observed_at_utc=utc_now(),
                    incident_key=f"missing_symbol_mapping:{logical_symbol}",
                )
            )
            continue
        if len(unique_matches) > 1:
            incidents.append(
                QualityIncident(
                    event_kind="ambiguous_symbol_mapping",
                    logical_symbol=logical_symbol,
                    timeframe=None,
                    detail="configured symbol resolved to multiple broker symbols",
                    observed_at_utc=utc_now(),
                    incident_key=f"ambiguous_symbol_mapping:{logical_symbol}",
                )
            )
            continue
        symbol = next(iter(unique_matches.values()))
        resolved.append(
            ResolvedSymbol(
                logical_symbol=logical_symbol,
                broker_symbol=symbol.broker_symbol,
                aliases=aliases,
                description=symbol.description,
                point=symbol.point,
                digits=symbol.digits,
                visible=symbol.visible,
            )
        )
    return resolved, incidents
