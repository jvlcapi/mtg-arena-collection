#!/bin/bash
# Adds the cards granted in the game logs (mtga-mcp capture) and updates exports/collection.csv.
# The scheduled refresh runs the same command; it prints nothing when nothing changed.
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection refresh-collection "$@"
