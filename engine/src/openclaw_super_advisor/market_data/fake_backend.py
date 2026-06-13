from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class FakeMt5Scenario:
    initialize_success: bool = True
    visible_symbols: set[str] = field(default_factory=set)
    last_error_value: tuple[int, str] = (0, "ok")
    symbols: list[object] = field(default_factory=list)
    ticks_by_symbol: dict[str, list[object]] = field(default_factory=dict)
    bars_by_symbol_and_timeframe: dict[tuple[str, int], list[object]] = field(default_factory=dict)
    latest_tick_by_symbol: dict[str, object] = field(default_factory=dict)
    terminal_info_payload: object | None = None
    account_info_payload: object | None = None
    version_payload: tuple[int, ...] | None = (5, 0, 0)
    fail_once: bool = False
    _failed: bool = False


class FakeMt5Backend:
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440
    COPY_TICKS_ALL = 0

    def __init__(self, scenario: FakeMt5Scenario | None = None) -> None:
        self.backend_name = "fake-mt5"
        self.scenario = scenario or FakeMt5Scenario()
        self.connected = False

    def initialize(self) -> bool:
        if self.scenario.fail_once and not self.scenario._failed:
            self.scenario._failed = True
            self.scenario.last_error_value = (1001, "temporary initialize failure")
            self.connected = False
            return False
        self.connected = self.scenario.initialize_success
        return self.connected

    def shutdown(self) -> None:
        self.connected = False

    def version(self) -> tuple[int, ...] | None:
        return self.scenario.version_payload

    def terminal_info(self) -> object | None:
        if self.scenario.terminal_info_payload is not None:
            return self.scenario.terminal_info_payload
        return {"path": "C:\\MT5\\terminal64.exe"}

    def account_info(self) -> object | None:
        if self.scenario.account_info_payload is not None:
            return self.scenario.account_info_payload
        return {"server": "demo-server", "login": 123456}

    def last_error(self) -> object:
        return self.scenario.last_error_value

    def symbols_get(self) -> object | None:
        return self.scenario.symbols

    def symbol_info(self, symbol: str) -> object | None:
        for item in self.scenario.symbols:
            if isinstance(item, dict) and item.get("name") == symbol:
                return item
        return None

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        if enable:
            self.scenario.visible_symbols.add(symbol)
        return True

    def symbol_info_tick(self, symbol: str) -> object | None:
        return self.scenario.latest_tick_by_symbol.get(symbol)

    def copy_rates_from(
        self, symbol: str, timeframe: int, date_from: object, count: int
    ) -> object | None:
        _ = date_from
        payload = self.scenario.bars_by_symbol_and_timeframe.get((symbol, timeframe), [])
        return payload[:count]

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> object | None:
        payload = self.scenario.bars_by_symbol_and_timeframe.get((symbol, timeframe), [])
        return payload[start_pos : start_pos + count]

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: object,
        date_to: object,
    ) -> object | None:
        _ = (date_from, date_to)
        return self.scenario.bars_by_symbol_and_timeframe.get((symbol, timeframe), [])

    def copy_ticks_from(
        self, symbol: str, date_from: object, count: int, flags: int
    ) -> object | None:
        _ = (date_from, flags)
        payload = self.scenario.ticks_by_symbol.get(symbol, [])
        return payload[:count]

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: object,
        date_to: object,
        flags: int,
    ) -> object | None:
        _ = (date_from, date_to, flags)
        return self.scenario.ticks_by_symbol.get(symbol, [])


def build_default_scenario() -> FakeMt5Scenario:
    return FakeMt5Scenario(
        symbols=[
            {
                "name": "XAUUSD.",
                "description": "Gold",
                "path": "Metals",
                "visible": False,
                "point": 0.01,
                "digits": 2,
            },
            {
                "name": "DXY",
                "description": "Dollar Index",
                "path": "Indices",
                "visible": True,
                "point": 0.01,
                "digits": 2,
            },
        ],
        ticks_by_symbol={
            "XAUUSD.": [
                {
                    "time": int(datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC).timestamp()),
                    "time_msc": 1767225720000,
                    "bid": 2600.0,
                    "ask": 2600.2,
                    "last": 2600.1,
                    "volume": 9.0,
                    "volume_real": 9.0,
                    "flags": 1,
                }
            ]
        },
        latest_tick_by_symbol={
            "XAUUSD.": {
                "time": int(datetime(2026, 1, 1, 0, 3, 0, tzinfo=UTC).timestamp()),
                "time_msc": 1767225780000,
                "bid": 2600.1,
                "ask": 2600.3,
                "last": 2600.2,
                "volume": 10.0,
                "volume_real": 10.0,
                "flags": 1,
            }
        },
        bars_by_symbol_and_timeframe={
            ("XAUUSD.", FakeMt5Backend.TIMEFRAME_H1): [
                {
                    "time": int(datetime(2025, 12, 31, 23, 0, tzinfo=UTC).timestamp()),
                    "open": 2598.0,
                    "high": 2601.0,
                    "low": 2597.0,
                    "close": 2600.0,
                    "tick_volume": 100,
                    "spread": 10,
                    "real_volume": 0,
                }
            ]
        },
    )
