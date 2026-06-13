from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(r"C:\Data\OpenClawSuperAdvisor")
STATE = ROOT / "state"
WORKSPACE = ROOT / "workspace"
CONFIG = STATE / "openclaw.json"
ARCHIVE = Path(r"C:\Data\OpenClaw_PreReset_Audit_20260613\OpenClawBot_Legacy.zip")
FORBIDDEN_SYMBOLS = (
    "order" "_send",
    "TRADE" "_ACTION",
    "Execution" "Kernel",
    "execution" "_dispatch_bridge",
    "position" "_close",
)
SKILL_DIRS = (
    "advisor-safety-contract",
    "environment-health",
    "python-engine-bridge",
    "evidence-audit",
    "super-potential-review",
    "thai-telegram-publisher",
    "incident-reporting",
)


def run_openclaw(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_HOME": str(ROOT),
            "OPENCLAW_STATE_DIR": str(STATE),
            "OPENCLAW_CONFIG_PATH": str(CONFIG),
            "OPENCLAW_WORKSPACE_DIR": str(WORKSPACE),
        }
    )
    cli = shutil.which("openclaw.cmd") or shutil.which("openclaw") or r"C:\Users\Teera\AppData\Roaming\npm\openclaw.cmd"
    return subprocess.run(
        [cli, *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


class CleanRoomTests(unittest.TestCase):
    def test_old_project_absent(self) -> None:
        self.assertFalse(Path(r"C:\Data\OpenClawBot").exists())

    def test_old_gateway_task_absent(self) -> None:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'OpenClawBot|OpenClaw|Gateway' -or $_.Description -match 'OpenClawBot|OpenClaw|Gateway' }).Count",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.stdout.strip() or "0", "0")

    def test_locked_paths_exist(self) -> None:
        self.assertTrue(STATE.exists())
        self.assertTrue(CONFIG.exists())
        self.assertTrue(WORKSPACE.exists())

    def test_only_one_env_exists(self) -> None:
        env_files = [path for path in ROOT.rglob(".env")]
        self.assertEqual(env_files, [STATE / ".env"])

    def test_provider_keys_not_stored_in_workspace(self) -> None:
        self.assertFalse((WORKSPACE / ".env").exists())

    def test_only_super_advisor_agent_exists(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        agents = config["agents"]["list"]
        self.assertEqual([agent["id"] for agent in agents], ["super-advisor"])

    def test_no_old_session_loaded(self) -> None:
        self.assertFalse(Path(r"C:\Users\Teera\.openclaw").exists())

    def test_no_execution_module_exists(self) -> None:
        hits: list[str] = []
        for path in ROOT.rglob("*.py"):
            if "execution" in path.stem.lower():
                hits.append(str(path))
        self.assertEqual(hits, [])

    def test_forbidden_trading_symbols_absent(self) -> None:
        hits: list[str] = []
        for extension in ("*.py", "*.json", "*.toml", "*.ps1"):
            for path in ROOT.rglob(extension):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    for symbol in FORBIDDEN_SYMBOLS:
                        if symbol in text:
                            hits.append(f"{path}:{symbol}")
        self.assertEqual(hits, [])

    def test_agent_tool_permissions_are_minimal(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        agent = config["agents"]["list"][0]
        self.assertEqual(agent["tools"]["allow"], ["read", "session_status"])
        self.assertEqual(agent["tools"]["exec"]["mode"], "deny")

    def test_skills_exist(self) -> None:
        for name in SKILL_DIRS:
            self.assertTrue((WORKSPACE / "skills" / name / "SKILL.md").exists(), msg=name)

    def test_config_validates_against_live_schema(self) -> None:
        result = run_openclaw("config", "validate", "--json")
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])

    def test_env_health_reports_status_only(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "engine" / "src"))
        from openclaw_super_advisor.health import run_health_check

        report = run_health_check()
        self.assertTrue(set(report.env_status.values()).issubset({"PRESENT", "MISSING", "BLANK", "INVALID_FORMAT"}))

    def test_env_is_ignored_by_git(self) -> None:
        ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("state/.env", ignore_text)

    def test_legacy_archive_is_outside_runtime(self) -> None:
        self.assertTrue(ARCHIVE.exists())
        self.assertFalse(str(ARCHIVE).startswith(str(ROOT)))


if __name__ == "__main__":
    unittest.main()
