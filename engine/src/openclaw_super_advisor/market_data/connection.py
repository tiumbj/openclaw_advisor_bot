from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from .backend import BackendConnectionError, ReadonlyMt5Backend

T = TypeVar("T")


class BoundedRetryRunner:
    def __init__(
        self, backend: ReadonlyMt5Backend, max_attempts: int, backoff_seconds: int
    ) -> None:
        self.backend = backend
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds

    def run(self, operation: Callable[[], T]) -> T:
        last_error: BackendConnectionError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                if not self.backend.initialize():
                    raise BackendConnectionError(
                        f"backend initialize failed: {self.backend.last_error()!r}"
                    )
                return operation()
            except BackendConnectionError as exc:
                last_error = exc
                self.backend.shutdown()
                if attempt == self.max_attempts:
                    break
                time.sleep(self.backoff_seconds * attempt)
        if last_error is None:
            raise BackendConnectionError(
                "market-data operation failed without an explicit backend error"
            )
        raise last_error
