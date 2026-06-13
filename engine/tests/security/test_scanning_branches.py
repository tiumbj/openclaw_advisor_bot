from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.scanning import (
    _module_constants,
    _resolve_string,
    perform_security_scan,
)


@pytest.mark.security
def test_scanning_covers_constant_and_import_branches(sample_project: Path) -> None:
    root = sample_project
    (root / ".venv").mkdir(exist_ok=True)
    (root / ".venv" / "ignored.py").write_text("order_send()\n", encoding="utf-8")
    (root / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "entry_from.py").write_text("from helper import VALUE\n", encoding="utf-8")
    (root / "concat.py").write_text(
        'NAME = "order" + "_send"\ngetattr(api, NAME)\n',
        encoding="utf-8",
    )
    tree = __import__("ast").parse('NAME = "order" + "_send"\nOTHER = something\n')
    constants = _module_constants(tree)
    assert constants["NAME"] == "order_send"
    second_assignment = tree.body[1]
    assert _resolve_string(second_assignment.value, constants) is None  # type: ignore[attr-defined]

    report = perform_security_scan(build_paths(root))
    assert any(item["rule"] == "getattr_constant" for item in report["resolved_constants"])
