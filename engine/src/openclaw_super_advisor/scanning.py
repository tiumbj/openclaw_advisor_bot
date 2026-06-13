from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ._version import PHASE, __version__
from .constants import FORBIDDEN_SYMBOLS, FORBIDDEN_TRACKED_PATHS
from .paths import ProjectPaths

SOURCE_EXTENSIONS = {".py", ".json", ".toml", ".yml", ".yaml", ".md", ".txt"}
PYTHON_EXTENSIONS = {".py"}
SECRET_PATTERNS = {
    "openai_key": re.compile(r"sk-proj-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "telegram_bot_token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{20,}\b"),
    "github_pat": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "jwt_like": re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "archive",
    "logs",
    "data",
    "htmlcov",
    "state",
}
FORBIDDEN_REGEXES = {
    pattern: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(pattern)}(?![A-Za-z0-9_])")
    for pattern in FORBIDDEN_SYMBOLS
}


@dataclass(frozen=True)
class ScanFinding:
    detector: str
    rule: str
    file: str
    line: int
    classification: str
    detail: str


@dataclass(frozen=True)
class SecretFinding:
    scope: str
    file: str
    line: int
    secret_type: str
    redacted_fingerprint: str
    commit: str | None = None


def _iter_files(paths: ProjectPaths) -> list[Path]:
    discovered: list[Path] = []
    for path in paths.root_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        discovered.append(path)
    return discovered


def _classify_path(path: Path) -> str:
    lowered_parts = {part.lower() for part in path.parts}
    if "tests" in lowered_parts:
        return "TEST_ONLY"
    if "docs" in lowered_parts:
        return "DOCUMENTATION"
    if path.suffix.lower() in {".md", ".txt"}:
        return "DOCUMENTATION"
    return "ACTIVE_SOURCE"


def _fingerprint(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def scan_source_text(paths: ProjectPaths) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for path in _iter_files(paths):
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN_SYMBOLS:
                if _should_ignore_source_text_hit(path, line, pattern):
                    continue
                if FORBIDDEN_REGEXES[pattern].search(line):
                    findings.append(
                        ScanFinding(
                            detector="source_text",
                            rule=pattern,
                            file=str(path),
                            line=line_number,
                            classification=_classify_path(path),
                            detail=pattern,
                        )
                    )
    return findings


def _should_ignore_source_text_hit(path: Path, line: str, pattern: str) -> bool:
    if path.name == "constants.py" and pattern in line and '"' in line:
        return True
    return False


def _resolve_string(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_string(node.left, constants)
        right = _resolve_string(node.right, constants)
        if left is not None and right is not None:
            return left + right
    return None


def _module_constants(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in cast(list[ast.stmt], getattr(tree, "body", [])):
        if isinstance(node, ast.Assign):
            value = _resolve_string(node.value, constants)
            if value is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value
    return constants


def scan_ast(paths: ProjectPaths) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for path in _iter_files(paths):
        if path.suffix.lower() not in PYTHON_EXTENSIONS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        constants = _module_constants(tree)
        classification = _classify_path(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            line_number = getattr(node, "lineno", 1)
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_SYMBOLS:
                findings.append(
                    ScanFinding(
                        "ast", "direct_call", str(path), line_number, classification, node.func.id
                    )
                )
            if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_SYMBOLS:
                findings.append(
                    ScanFinding(
                        "ast",
                        "attribute_call",
                        str(path),
                        line_number,
                        classification,
                        node.func.attr,
                    )
                )
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
            ):
                name = _resolve_string(node.args[1], constants)
                if name in FORBIDDEN_SYMBOLS:
                    findings.append(
                        ScanFinding(
                            "ast",
                            "getattr",
                            str(path),
                            line_number,
                            classification,
                            name,
                        )
                    )
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
                and node.func.attr == "import_module"
                and node.args
            ):
                module_name = _resolve_string(node.args[0], constants)
                if module_name is not None:
                    findings.append(
                        ScanFinding(
                            "ast",
                            "importlib",
                            str(path),
                            line_number,
                            classification,
                            module_name,
                        )
                    )
            if isinstance(node.func, ast.Name) and node.func.id == "__import__" and node.args:
                module_name = _resolve_string(node.args[0], constants)
                if module_name is not None:
                    findings.append(
                        ScanFinding(
                            "ast",
                            "builtin_import",
                            str(path),
                            line_number,
                            classification,
                            module_name,
                        )
                    )
    return findings


def scan_resolved_constants(paths: ProjectPaths) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for path in _iter_files(paths):
        if path.suffix.lower() not in PYTHON_EXTENSIONS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        constants = _module_constants(tree)
        classification = _classify_path(path)
        for node in cast(list[ast.stmt], getattr(tree, "body", [])):
            if not isinstance(node, ast.Assign):
                continue
            value = _resolve_string(node.value, constants)
            if value in FORBIDDEN_SYMBOLS:
                findings.append(
                    ScanFinding(
                        detector="resolved_constants",
                        rule="constant_value",
                        file=str(path),
                        line=getattr(node, "lineno", 1),
                        classification=classification,
                        detail=value,
                    )
                )
        for walk_node in ast.walk(tree):
            if not isinstance(walk_node, ast.Call):
                continue
            line_number = getattr(walk_node, "lineno", 1)
            if (
                isinstance(walk_node.func, ast.Name)
                and walk_node.func.id == "getattr"
                and len(walk_node.args) >= 2
            ):
                name = _resolve_string(walk_node.args[1], constants)
                if name in FORBIDDEN_SYMBOLS:
                    findings.append(
                        ScanFinding(
                            "resolved_constants",
                            "getattr_constant",
                            str(path),
                            line_number,
                            classification,
                            name,
                        )
                    )
            if (
                isinstance(walk_node.func, ast.Attribute)
                and isinstance(walk_node.func.value, ast.Name)
                and walk_node.func.value.id == "importlib"
                and walk_node.func.attr == "import_module"
                and walk_node.args
            ):
                module_name = _resolve_string(walk_node.args[0], constants)
                if module_name:
                    findings.append(
                        ScanFinding(
                            "resolved_constants",
                            "importlib_constant",
                            str(path),
                            line_number,
                            classification,
                            module_name,
                        )
                    )
            if (
                isinstance(walk_node.func, ast.Name)
                and walk_node.func.id == "__import__"
                and walk_node.args
            ):
                module_name = _resolve_string(walk_node.args[0], constants)
                if module_name:
                    findings.append(
                        ScanFinding(
                            "resolved_constants",
                            "builtin_import_constant",
                            str(path),
                            line_number,
                            classification,
                            module_name,
                        )
                    )
    return findings


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_import(module_name: str) -> str | None:
    if module_name.startswith("."):
        return None
    return module_name


def scan_import_graph(paths: ProjectPaths) -> list[ScanFinding]:
    python_files = [path for path in _iter_files(paths) if path.suffix.lower() in PYTHON_EXTENSIONS]
    module_to_path = {_module_name(paths.root_dir, path): path for path in python_files}
    graph: dict[str, set[str]] = {name: set() for name in module_to_path}
    flagged_modules: set[str] = set()
    for module_name, path in module_to_path.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(finding.detail in FORBIDDEN_SYMBOLS for finding in scan_ast_for_file(path, tree)):
            flagged_modules.add(module_name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    if target in module_to_path:
                        graph[module_name].add(target)
            elif isinstance(node, ast.ImportFrom) and node.module:
                resolved_target = _resolve_import(node.module)
                if resolved_target in module_to_path:
                    graph[module_name].add(resolved_target)
    indegree: dict[str, int] = {name: 0 for name in module_to_path}
    for targets in graph.values():
        for target in targets:
            indegree[target] += 1
    roots = [name for name, count in indegree.items() if count == 0 and "tests." not in name]
    findings: list[ScanFinding] = []
    for root_name in roots:
        stack = [root_name]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if current in flagged_modules and current != root_name:
                path = module_to_path[current]
                findings.append(
                    ScanFinding(
                        detector="import_graph",
                        rule="reachable_dependency",
                        file=str(path),
                        line=1,
                        classification=_classify_path(path),
                        detail=f"reachable from {root_name}",
                    )
                )
            stack.extend(sorted(graph.get(current, set())))
    return findings


def scan_ast_for_file(path: Path, tree: ast.AST | None = None) -> list[ScanFinding]:
    working_tree = tree or ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants = _module_constants(working_tree)
    classification = _classify_path(path)
    findings: list[ScanFinding] = []
    for node in ast.walk(working_tree):
        if not isinstance(node, ast.Call):
            continue
        line_number = getattr(node, "lineno", 1)
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_SYMBOLS:
            findings.append(
                ScanFinding(
                    "ast",
                    "direct_call",
                    str(path),
                    line_number,
                    classification,
                    node.func.id,
                )
            )
        if isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_SYMBOLS:
            findings.append(
                ScanFinding(
                    "ast",
                    "attribute_call",
                    str(path),
                    line_number,
                    classification,
                    node.func.attr,
                )
            )
        if isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
            name = _resolve_string(node.args[1], constants)
            if name in FORBIDDEN_SYMBOLS:
                findings.append(
                    ScanFinding(
                        "ast",
                        "getattr",
                        str(path),
                        line_number,
                        classification,
                        name,
                    )
                )
    return findings


def scan_paths_for_secrets(paths_to_scan: list[Path], scope: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in paths_to_scan:
        if not path.exists() or not path.is_file():
            continue
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        if _classify_path(path) == "TEST_ONLY":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for secret_type, pattern in SECRET_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            scope=scope,
                            file=str(path),
                            line=line_number,
                            secret_type=secret_type,
                            redacted_fingerprint=_fingerprint(match.group(0)),
                        )
                    )
    return findings


def scan_git_history(paths: ProjectPaths) -> list[SecretFinding]:
    command = [
        "git",
        "-C",
        str(paths.root_dir),
        "log",
        "--all",
        "-p",
        "--no-color",
        "--format=COMMIT:%H",
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    findings: list[SecretFinding] = []
    current_commit: str | None = None
    current_file = "<unknown>"
    current_line = 0
    for line in result.stdout.splitlines():
        if line.startswith("COMMIT:"):
            current_commit = line.removeprefix("COMMIT:")
            current_file = "<unknown>"
            current_line = 0
            continue
        if line.startswith("+++ b/"):
            current_file = line.removeprefix("+++ b/")
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            current_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") or line.startswith("-"):
            content = line[1:]
            if _classify_path(paths.root_dir / current_file) == "TEST_ONLY":
                current_line += 1
                continue
            for secret_type, pattern in SECRET_PATTERNS.items():
                match = pattern.search(content)
                if match:
                    findings.append(
                        SecretFinding(
                            scope="history",
                            file=current_file,
                            line=current_line,
                            secret_type=secret_type,
                            redacted_fingerprint=_fingerprint(match.group(0)),
                            commit=current_commit,
                        )
                    )
            current_line += 1
    return findings


def staged_paths(paths: ProjectPaths) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(paths.root_dir), "diff", "--cached", "--name-only"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    discovered: list[Path] = []
    for line in result.stdout.splitlines():
        if line.strip():
            discovered.append(paths.root_dir / line.strip())
    return discovered


def tracked_runtime_state_violations(paths: ProjectPaths) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(paths.root_dir), "ls-files"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    tracked = result.stdout.splitlines()
    violations: list[str] = []
    for tracked_path in tracked:
        normalized = tracked_path.replace("/", "\\")
        for forbidden in FORBIDDEN_TRACKED_PATHS:
            if normalized == forbidden or normalized.startswith(forbidden + "\\"):
                violations.append(normalized)
                break
    return sorted(violations)


def perform_security_scan(paths: ProjectPaths, include_history: bool = False) -> dict[str, object]:
    source_findings = scan_source_text(paths)
    ast_findings = scan_ast(paths)
    constant_findings = scan_resolved_constants(paths)
    import_graph_findings = scan_import_graph(paths)
    working_tree_secrets = scan_paths_for_secrets(_iter_files(paths), "working_tree")
    staged_secrets = scan_paths_for_secrets(staged_paths(paths), "staged")
    history_secrets = scan_git_history(paths) if include_history else []
    tracked_runtime_state = tracked_runtime_state_violations(paths)
    active_source_violations = [
        finding
        for finding in [*source_findings, *ast_findings, *constant_findings, *import_graph_findings]
        if finding.classification == "ACTIVE_SOURCE"
    ]
    return {
        "version": __version__,
        "phase": PHASE,
        "summary": {
            "pass": not active_source_violations
            and not working_tree_secrets
            and not staged_secrets
            and not history_secrets
            and not tracked_runtime_state,
            "active_source_violations": len(active_source_violations),
            "documentation_hits": sum(
                1 for finding in source_findings if finding.classification == "DOCUMENTATION"
            ),
            "test_hits": sum(
                1 for finding in source_findings if finding.classification == "TEST_ONLY"
            ),
        },
        "source_text": [finding.__dict__ for finding in source_findings],
        "ast": [finding.__dict__ for finding in ast_findings],
        "resolved_constants": [finding.__dict__ for finding in constant_findings],
        "import_graph": [finding.__dict__ for finding in import_graph_findings],
        "secrets": {
            "working_tree": [finding.__dict__ for finding in working_tree_secrets],
            "staged": [finding.__dict__ for finding in staged_secrets],
            "history": [finding.__dict__ for finding in history_secrets],
        },
        "runtime_state_tracking": {
            "tracked_forbidden_paths": tracked_runtime_state,
        },
    }


def write_scan_report(path: Path, report: dict[str, object]) -> None:
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
