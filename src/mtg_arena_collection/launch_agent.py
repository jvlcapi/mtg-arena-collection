"""The macOS LaunchAgent that runs refresh-collection every few minutes.

Idle runs are cheap: `mtga-mcp capture` skips logs that have not changed, and the CSV is only
rewritten when a quantity changed. The agent log only gets lines for changes and failures.
"""

import os
import plistlib
import subprocess
from pathlib import Path
from typing import Callable

LAUNCH_AGENT_LABEL = "com.jvlcapi.mtg-arena-collection.refresh"
REFRESH_INTERVAL_SECONDS = 5 * 60
DEFAULT_LAUNCH_AGENT_PATH = Path.home() / "Library/LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
DEFAULT_REFRESH_LOG_PATH = Path.home() / "Library/Logs/mtg-arena-collection/refresh.log"

CommandRunner = Callable[..., subprocess.CompletedProcess]


class LaunchAgentCommandFailed(RuntimeError):
    pass


def build_launch_agent(project_directory: Path, python_executable: Path, log_path: Path) -> dict:
    project_directory = Path(project_directory)
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": [
            str(python_executable),
            "-m",
            "mtg_arena_collection",
            "refresh-collection",
        ],
        "EnvironmentVariables": {"PYTHONPATH": str(project_directory / "src")},
        "WorkingDirectory": str(project_directory),
        "StartInterval": REFRESH_INTERVAL_SECONDS,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }


def install_launch_agent(
    launch_agent: dict, launch_agent_path: Path, run: CommandRunner = subprocess.run
) -> None:
    """Writes the agent file and loads it, replacing an agent that was already loaded."""
    launch_agent_path = Path(launch_agent_path)
    Path(launch_agent["StandardOutPath"]).parent.mkdir(parents=True, exist_ok=True)
    launch_agent_path.parent.mkdir(parents=True, exist_ok=True)
    if _is_loaded(run):
        _run_launchctl(run, "bootout", _service_target())
    with launch_agent_path.open("wb") as plist_file:
        plistlib.dump(launch_agent, plist_file)
    _run_launchctl(run, "bootstrap", _user_domain(), str(launch_agent_path))


def uninstall_launch_agent(launch_agent_path: Path, run: CommandRunner = subprocess.run) -> None:
    if _is_loaded(run):
        _run_launchctl(run, "bootout", _service_target())
    Path(launch_agent_path).unlink(missing_ok=True)


def _user_domain() -> str:
    return f"gui/{os.getuid()}"


def _service_target() -> str:
    return f"{_user_domain()}/{LAUNCH_AGENT_LABEL}"


def _is_loaded(run: CommandRunner) -> bool:
    return run(["launchctl", "print", _service_target()], capture_output=True).returncode == 0


def _run_launchctl(run: CommandRunner, *arguments: str) -> None:
    result = run(["launchctl", *arguments], capture_output=True, text=True)
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip()
        raise LaunchAgentCommandFailed(
            f"`launchctl {' '.join(arguments)}` failed with exit code {result.returncode}: {output}"
        )
