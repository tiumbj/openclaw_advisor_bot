from __future__ import annotations

import json

from .health import run_health_check_as_dict


if __name__ == "__main__":
    print(json.dumps(run_health_check_as_dict(), ensure_ascii=True, indent=2))
