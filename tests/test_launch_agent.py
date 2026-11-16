import os
import plistlib
import tempfile
import unittest
from pathlib import Path

from command_runner_fake import RecordingCommandRunner
from mtg_arena_collection.launch_agent import (
    LAUNCH_AGENT_LABEL,
    LaunchAgentCommandFailed,
    build_launch_agent,
    install_launch_agent,
    uninstall_launch_agent,
)

PROJECT_DIRECTORY = Path("/Users/someone/Developer/mtg-arena-collection")
PYTHON_EXECUTABLE = Path("/opt/homebrew/bin/python3")
NOT_LOADED = {("launchctl", "print"): 113}
USER_DOMAIN = f"gui/{os.getuid()}"
SERVICE = f"{USER_DOMAIN}/{LAUNCH_AGENT_LABEL}"


class BuildLaunchAgentTests(unittest.TestCase):
    def setUp(self):
        self.log_path = Path("/Users/someone/Library/Logs/mtg-arena-collection/refresh.log")
        self.launch_agent = build_launch_agent(PROJECT_DIRECTORY, PYTHON_EXECUTABLE, self.log_path)

    def test_runs_the_refresh_command_with_the_given_python(self):
        self.assertEqual(
            self.launch_agent["ProgramArguments"],
            [str(PYTHON_EXECUTABLE), "-m", "mtg_arena_collection", "refresh-collection"],
        )

    def test_points_python_at_the_project_code(self):
        self.assertEqual(
            self.launch_agent["EnvironmentVariables"]["PYTHONPATH"], str(PROJECT_DIRECTORY / "src")
        )

    def test_runs_every_five_minutes_and_once_when_loaded(self):
        self.assertEqual(
            (self.launch_agent["StartInterval"], self.launch_agent["RunAtLoad"]), (300, True)
        )

    def test_sends_output_and_errors_to_the_refresh_log(self):
        self.assertEqual(
            (self.launch_agent["StandardOutPath"], self.launch_agent["StandardErrorPath"]),
            (str(self.log_path), str(self.log_path)),
        )

    def test_runs_as_a_background_job(self):
        self.assertEqual(self.launch_agent["ProcessType"], "Background")


class LaunchAgentFilesTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.launch_agent_path = directory / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
        self.log_path = directory / "Logs" / "mtg-arena-collection" / "refresh.log"
        self.launch_agent = build_launch_agent(PROJECT_DIRECTORY, PYTHON_EXECUTABLE, self.log_path)

    def tearDown(self):
        self.temporary_directory.cleanup()


class InstallLaunchAgentTests(LaunchAgentFilesTestCase):
    def install(self, runner):
        install_launch_agent(self.launch_agent, self.launch_agent_path, run=runner)

    def test_writes_the_launch_agent_file(self):
        self.install(RecordingCommandRunner(return_codes=NOT_LOADED))
        with self.launch_agent_path.open("rb") as plist_file:
            self.assertEqual(plistlib.load(plist_file), self.launch_agent)

    def test_creates_the_log_folder(self):
        self.install(RecordingCommandRunner(return_codes=NOT_LOADED))
        self.assertTrue(self.log_path.parent.is_dir())

    def test_loads_an_agent_that_was_not_loaded(self):
        runner = RecordingCommandRunner(return_codes=NOT_LOADED)
        self.install(runner)
        self.assertEqual(
            runner.commands,
            [
                ["launchctl", "print", SERVICE],
                ["launchctl", "bootstrap", USER_DOMAIN, str(self.launch_agent_path)],
            ],
        )

    def test_replaces_an_agent_that_was_already_loaded(self):
        runner = RecordingCommandRunner()
        self.install(runner)
        self.assertEqual(
            runner.commands[1:],
            [
                ["launchctl", "bootout", SERVICE],
                ["launchctl", "bootstrap", USER_DOMAIN, str(self.launch_agent_path)],
            ],
        )

    def test_failed_launchctl_reports_its_message(self):
        runner = RecordingCommandRunner(
            return_codes={**NOT_LOADED, ("launchctl", "bootstrap"): 5},
            stderr="Bootstrap failed: 5: Input/output error",
        )
        with self.assertRaisesRegex(LaunchAgentCommandFailed, "Input/output error"):
            self.install(runner)


class UninstallLaunchAgentTests(LaunchAgentFilesTestCase):
    def write_launch_agent_file(self):
        self.launch_agent_path.parent.mkdir(parents=True)
        with self.launch_agent_path.open("wb") as plist_file:
            plistlib.dump(self.launch_agent, plist_file)

    def test_unloads_a_loaded_agent(self):
        self.write_launch_agent_file()
        runner = RecordingCommandRunner()
        uninstall_launch_agent(self.launch_agent_path, run=runner)
        self.assertEqual(runner.commands[1:], [["launchctl", "bootout", SERVICE]])

    def test_removes_the_launch_agent_file(self):
        self.write_launch_agent_file()
        uninstall_launch_agent(self.launch_agent_path, run=RecordingCommandRunner(return_codes=NOT_LOADED))
        self.assertFalse(self.launch_agent_path.exists())

    def test_nothing_installed_is_not_an_error(self):
        runner = RecordingCommandRunner(return_codes=NOT_LOADED)
        uninstall_launch_agent(self.launch_agent_path, run=runner)
        self.assertEqual(runner.commands, [["launchctl", "print", SERVICE]])


if __name__ == "__main__":
    unittest.main()
