from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from ._version import PHASE, __version__


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "version": __version__,
            "phase": PHASE,
        }
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("openclaw_super_advisor")
    logger.handlers.clear()
    logger.setLevel(level.upper())
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger
