#!/bin/bash
# Removes the launchd schedule created by scripts/install-automatic-refresh.sh.
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection uninstall-automatic-refresh "$@"
