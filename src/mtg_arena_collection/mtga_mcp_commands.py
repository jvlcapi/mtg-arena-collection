"""Runs `mtga-mcp capture` (github.com/fkadriver/mtga-mcp), which reads the game logs.

It goes through the console script in mtga-mcp's virtual environment instead of `uv run`, so
nothing gets synced or downloaded when the scheduled refresh runs.
"""

import subprocess
from pathlib import Path
from typing import Callable

DEFAULT_MTGA_MCP_EXECUTABLE = Path.home() / "Developer/mtga-mcp/.venv/bin/mtga-mcp"

CommandRunner = Callable[..., subprocess.CompletedProcess]


class MtgaMcpCommandFailed(RuntimeError):
    pass


def run_capture(
    mtga_mcp_executable: Path = DEFAULT_MTGA_MCP_EXECUTABLE, run: CommandRunner = subprocess.run
) -> str:
    """Adds the cards granted in the game logs to mtga-mcp's collection; returns its output."""
    try:
        result = run([str(mtga_mcp_executable), "capture"], capture_output=True, text=True)
    except FileNotFoundError as error:
        raise MtgaMcpCommandFailed(
            f"mtga-mcp is not installed at {mtga_mcp_executable}. "
            "Run `uv sync` in the mtga-mcp folder."
        ) from error
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip()
        raise MtgaMcpCommandFailed(
            f"`mtga-mcp capture` failed with exit code {result.returncode}: {output}"
        )
    return result.stdout
