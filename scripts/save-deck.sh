#!/bin/bash
# Saves a decklist in MTG Arena's import format under decks/<format>/<colors>/<archetype>/.
# Reads the list from standard input, so after Export in MTG Arena:
#   pbpaste | ./scripts/save-deck.sh --name "Krenko Goblins" --format "Historic Brawl" --archetype Goblins
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection save-deck "$@"
