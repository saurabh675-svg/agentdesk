"""Focused regression tests for backend reliability fixes."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx

from app.agent_runner import AgentRunner


class AgentRunnerReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_github_summary_reports_request_failure(self) -> None:
        runner = AgentRunner.__new__(AgentRunner)
        client = MagicMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("offline"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.agent_runner.httpx.AsyncClient", return_value=client),
            patch("app.agent_runner.load_settings", return_value={}),
            patch.dict("os.environ", {"GITHUB_TOKEN": ""}),
        ):
            result = await runner._github_pr_summary("owner/repo")

        self.assertIn("GitHub PR summary failed", result)
        self.assertIn("offline", result)
        self.assertNotIn("response", result.lower())

    def test_pc_info_includes_disk_usage(self) -> None:
        runner = AgentRunner.__new__(AgentRunner)
        usage = SimpleNamespace(total=100, used=40, free=60)

        with (
            patch("app.agent_runner.shutil.disk_usage", return_value=usage),
            patch("app.agent_runner.subprocess.run", return_value=SimpleNamespace(stdout="")),
            patch("app.agent_runner.shutil.which", return_value=None),
        ):
            info = json.loads(runner._pc_info())

        self.assertEqual(info["disk"], {"total": 100, "used": 40, "free": 60})


if __name__ == "__main__":
    unittest.main()
