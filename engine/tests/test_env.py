from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(r"C:\Data\OpenClawSuperAdvisor")
sys.path.insert(0, str(ROOT / "engine" / "src"))

from openclaw_super_advisor.constants import ENGINE_DIR, ROOT_DIR
from openclaw_super_advisor.env import (
    DuplicateEnvError,
    SecretValue,
    audit_environment,
    detect_duplicate_env_files,
    load_settings,
)


class EnvLoaderTests(unittest.TestCase):
    def test_audits_canonical_env(self) -> None:
        snapshot = audit_environment()
        self.assertEqual(snapshot.status("OPENAI_API_KEY"), "BLANK")
        self.assertEqual(snapshot.status("OPENCLAW_HOME"), "PRESENT")

    def test_detects_prohibited_env(self) -> None:
        rogue_env = ENGINE_DIR / ".env"
        rogue_env.write_text("SHOULD_NOT_EXIST=\n", encoding="utf-8")
        try:
            self.assertIn(rogue_env, detect_duplicate_env_files())
            with self.assertRaises(DuplicateEnvError):
                audit_environment()
        finally:
            rogue_env.unlink(missing_ok=True)

    def test_load_settings_allows_blank_tokens_in_non_strict_mode(self) -> None:
        settings = load_settings(strict=False)
        self.assertIsInstance(settings.security.gateway_token, SecretValue)
        self.assertTrue(settings.security.gateway_token.is_blank())
        self.assertTrue(settings.advisor.advisor_only)
        self.assertFalse(settings.advisor.execution_allowed)

    def test_root_has_no_top_level_env(self) -> None:
        self.assertFalse((ROOT_DIR / ".env").exists())


if __name__ == "__main__":
    unittest.main()
