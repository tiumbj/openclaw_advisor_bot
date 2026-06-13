from __future__ import annotations

import unittest

from openclaw_super_advisor.health import run_health_check


class HealthCheckTests(unittest.TestCase):
    def test_health_report_is_read_only(self) -> None:
        report = run_health_check()
        self.assertEqual(report.agent_id, "super-advisor")
        self.assertEqual(tuple(report.allowed_tools), ("read", "session_status"))
        self.assertEqual(report.env_status["TELEGRAM_BOT_TOKEN"], "BLANK")


if __name__ == "__main__":
    unittest.main()
