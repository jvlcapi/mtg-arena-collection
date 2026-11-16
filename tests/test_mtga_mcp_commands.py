import unittest
from pathlib import Path

from command_runner_fake import RecordingCommandRunner
from mtg_arena_collection.mtga_mcp_commands import MtgaMcpCommandFailed, run_capture

MTGA_MCP_EXECUTABLE = Path("/Users/someone/Developer/mtga-mcp/.venv/bin/mtga-mcp")


class RunCaptureTests(unittest.TestCase):
    def test_runs_mtga_mcp_capture(self):
        runner = RecordingCommandRunner()
        run_capture(MTGA_MCP_EXECUTABLE, run=runner)
        self.assertEqual(runner.commands, [[str(MTGA_MCP_EXECUTABLE), "capture"]])

    def test_returns_the_capture_output_instead_of_printing_it(self):
        runner = RecordingCommandRunner(stdout="capture: logs unchanged since last run")
        self.assertEqual(
            run_capture(MTGA_MCP_EXECUTABLE, run=runner), "capture: logs unchanged since last run"
        )

    def test_failed_capture_reports_what_it_printed(self):
        runner = RecordingCommandRunner(return_codes={"default": 1}, stderr="database is locked")
        with self.assertRaisesRegex(MtgaMcpCommandFailed, "database is locked"):
            run_capture(MTGA_MCP_EXECUTABLE, run=runner)

    def test_missing_mtga_mcp_says_how_to_install_it(self):
        with self.assertRaisesRegex(MtgaMcpCommandFailed, "uv sync"):
            run_capture(MTGA_MCP_EXECUTABLE, run=RecordingCommandRunner(missing_program=True))


if __name__ == "__main__":
    unittest.main()
