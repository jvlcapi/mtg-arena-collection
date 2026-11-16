#!/bin/bash
# Learns from the meta decks mtga-mcp imported: land count, curve, roles, and the mechanics and
# cards that show up together. Writes exports/meta-lessons/meta-lessons.md (report in Portuguese)
# and meta-lessons.json (for the deck designer).
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection learn-from-meta "$@"
