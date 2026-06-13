from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MT5_READONLY_METHODS = (
    "initialize",
    "shutdown",
    "version",
    "terminal_info",
    "account_info",
    "last_error",
    "symbols_get",
    "symbol_info",
    "symbol_select",
    "symbol_info_tick",
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_rates_range",
    "copy_ticks_from",
    "copy_ticks_range",
)


class BackendUnavailableError(RuntimeError):
    """Raised when the configured MT5 backend cannot be loaded."""


class BackendConnectionError(RuntimeError):
    """Raised when the configured MT5 backend cannot be used safely."""


@dataclass(frozen=True)
class TerminalHealth:
    enabled: bool
    connected: bool
    backend_name: str
    terminal_path: str | None
    server: str | None
    login: int | None
    ping_ms: int | None
    version: str | None
    message: str


@dataclass(frozen=True)
class DiscoveredSymbol:
    broker_symbol: str
    description: str
    path: str
    visible: bool
    point: float
    digits: int


@dataclass(frozen=True)
class ResolvedSymbol:
    logical_symbol: str
    broker_symbol: str
    aliases: tuple[str, ...]
    description: str
    point: float
    digits: int
    visible: bool


class ReadonlyMt5Backend(Protocol):
    backend_name: str

    def initialize(self) -> bool: ...

    def shutdown(self) -> None: ...

    def version(self) -> tuple[int, ...] | None: ...

    def terminal_info(self) -> object | None: ...

    def account_info(self) -> object | None: ...

    def last_error(self) -> object: ...

    def symbols_get(self) -> object | None: ...

    def symbol_info(self, symbol: str) -> object | None: ...

    def symbol_select(self, symbol: str, enable: bool) -> bool: ...

    def symbol_info_tick(self, symbol: str) -> object | None: ...

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: object,
        count: int,
    ) -> object | None: ...

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> object | None: ...

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: object,
        date_to: object,
    ) -> object | None: ...

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: object,
        count: int,
        flags: int,
    ) -> object | None: ...

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: object,
        date_to: object,
        flags: int,
    ) -> object | None: ...
