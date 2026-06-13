from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.scanning import perform_security_scan


@pytest.mark.security
def test_security_scan_detects_required_vectors(sample_project: Path) -> None:
    root = sample_project
    (root / "app").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "engine" / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (root / "app" / "direct_call.py").write_text("order_send()\n", encoding="utf-8")
    (root / "app" / "const_getattr.py").write_text(
        'FORBIDDEN = "order" "_send"\ngetattr(api, FORBIDDEN)\n',
        encoding="utf-8",
    )
    (root / "app" / "bad_module.py").write_text("order_send()\n", encoding="utf-8")
    (root / "app" / "entry.py").write_text(
        "import importlib\n"
        "import app.bad_module\n"
        "module_name = 'app.bad_module'\n"
        "importlib.import_module(module_name)\n"
        "__import__(module_name)\n",
        encoding="utf-8",
    )
    (root / "docs" / "note.md").write_text(
        "Documentation mentions order_send only.\n", encoding="utf-8"
    )
    (root / "engine" / "tests" / "unit" / "test_symbols.py").write_text(
        'assert "order_send" == "order_send"\n',
        encoding="utf-8",
    )

    report = perform_security_scan(build_paths(root))

    assert report["summary"]["pass"] is False
    assert any(item["rule"] == "order_send" for item in report["source_text"])
    assert any(item["rule"] == "direct_call" for item in report["ast"])
    assert any(item["rule"] == "constant_value" for item in report["resolved_constants"])
    assert any(item["rule"] == "reachable_dependency" for item in report["import_graph"])
    assert any(item["classification"] == "DOCUMENTATION" for item in report["source_text"])
    assert any(item["classification"] == "TEST_ONLY" for item in report["source_text"])


@pytest.mark.security
def test_security_scan_passes_clean_project(sample_project: Path) -> None:
    report = perform_security_scan(build_paths(sample_project))
    assert report["summary"]["pass"] is True
