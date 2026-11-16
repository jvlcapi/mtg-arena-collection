#!/bin/bash
# Schedules refresh-collection every 5 minutes with launchd (and runs it once right away).
# Remove it with scripts/uninstall-automatic-refresh.sh.
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection install-automatic-refresh "$@"
