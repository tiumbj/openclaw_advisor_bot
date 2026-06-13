from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


def atomic_write(target_path: Path, writer: Callable[[Path], None]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".tmp-{target_path.name}")
    try:
        writer(temp_path)
        os.replace(temp_path, target_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise
