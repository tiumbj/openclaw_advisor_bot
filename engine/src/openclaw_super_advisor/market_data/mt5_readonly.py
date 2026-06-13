from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .backend import BackendConnectionError, BackendUnavailableError

try:
    import MetaTrader5 as MetaTrader5Module
except ImportError:
    META_TRADER5_MODULE = None
else:
    META_TRADER5_MODULE = MetaTrader5Module


@dataclass
class MetaTrader5ReadonlyAdapter:
    terminal_path: Path | None
    login: str
    password: str
    server: str
    use_existing_session: bool
    timeout_ms: int = 10_000
    backend_name: str = "mt5-readonly"

    _connected: bool = False

    def _module(self) -> Any:
        if META_TRADER5_MODULE is None:
            raise BackendUnavailableError("MetaTrader5 package is not installed")
        return META_TRADER5_MODULE

    def initialize(self) -> bool:
        if self._connected:
            return True
        module = self._module()
        kwargs: dict[str, object] = {"timeout": self.timeout_ms}
        if self.terminal_path is not None:
            kwargs["path"] = str(self.terminal_path)
        if not self.use_existing_session:
            if not (self.login and self.password and self.server):
                raise BackendConnectionError(
                    "MT5 login, password, and server are required when "
                    "MT5_USE_EXISTING_SESSION=false"
                )
            kwargs["login"] = int(self.login)
            kwargs["password"] = self.password
            kwargs["server"] = self.server
        if not bool(module.initialize(**kwargs)):
            raise BackendConnectionError(f"MetaTrader5 initialize failed: {module.last_error()!r}")
        self._connected = True
        return True

    def shutdown(self) -> None:
        if self._connected:
            self._module().shutdown()
        self._connected = False

    def version(self) -> tuple[int, ...] | None:
        self.initialize()
        version = self._module().version()
        return None if version is None else tuple(int(part) for part in version)

    def terminal_info(self) -> object | None:
        self.initialize()
        return cast(object | None, self._module().terminal_info())

    def account_info(self) -> object | None:
        self.initialize()
        return cast(object | None, self._module().account_info())

    def last_error(self) -> object:
        return self._module().last_error()

    def symbols_get(self) -> object | None:
        self.initialize()
        return cast(object | None, self._module().symbols_get())

    def symbol_info(self, symbol: str) -> object | None:
        self.initialize()
        return cast(object | None, self._module().symbol_info(symbol))

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        self.initialize()
        return bool(self._module().symbol_select(symbol, enable))

    def symbol_info_tick(self, symbol: str) -> object | None:
        self.initialize()
        return cast(object | None, self._module().symbol_info_tick(symbol))

    def copy_rates_from(
        self,
        symbol: str,
        timeframe: int,
        date_from: object,
        count: int,
    ) -> object | None:
        self.initialize()
        return cast(
            object | None,
            self._module().copy_rates_from(symbol, timeframe, date_from, count),
        )

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: int,
        start_pos: int,
        count: int,
    ) -> object | None:
        self.initialize()
        return cast(
            object | None,
            self._module().copy_rates_from_pos(symbol, timeframe, start_pos, count),
        )

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: int,
        date_from: object,
        date_to: object,
    ) -> object | None:
        self.initialize()
        return cast(
            object | None,
            self._module().copy_rates_range(symbol, timeframe, date_from, date_to),
        )

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: object,
        count: int,
        flags: int,
    ) -> object | None:
        self.initialize()
        return cast(
            object | None,
            self._module().copy_ticks_from(symbol, date_from, count, flags),
        )

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: object,
        date_to: object,
        flags: int,
    ) -> object | None:
        self.initialize()
        return cast(
            object | None,
            self._module().copy_ticks_range(symbol, date_from, date_to, flags),
        )
