from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_super_advisor.paths import build_paths
from openclaw_super_advisor.scanning import (
    _module_constants,
    _module_name,
    _resolve_string,
    _should_ignore_source_text_hit,
    perform_security_scan,
    scan_ast,
    scan_ast_for_file,
    scan_import_graph,
    scan_paths_for_secrets,
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
    assert _should_ignore_source_text_hit(Path("constants.py"), '"order_send",', "order_send")

    report = perform_security_scan(build_paths(root))
    assert any(item["rule"] == "getattr_constant" for item in report["resolved_constants"])


@pytest.mark.security
def test_scanning_helper_functions_cover_remaining_branches(sample_project: Path) -> None:
    root = sample_project
    pkg = root / "pkg"
    pkg.mkdir(exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (root / "helper_direct.py").write_text("order_send()\n", encoding="utf-8")
    (root / "helper_attr.py").write_text("api.order_send()\n", encoding="utf-8")
    (root / "helper_getattr.py").write_text(
        'NAME = "order_send"\ngetattr(api, NAME)\n',
        encoding="utf-8",
    )
    (root / "helper_import_from.py").write_text(
        "from helper_direct import value\n",
        encoding="utf-8",
    )

    paths = build_paths(root)
    assert _module_name(root, pkg / "__init__.py") == "pkg"
    assert scan_ast(paths)
    assert scan_ast_for_file(root / "helper_direct.py")
    assert scan_import_graph(paths)
    assert scan_paths_for_secrets([root / "missing.txt"], "working_tree") == []
