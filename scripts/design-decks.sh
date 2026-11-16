#!/bin/bash
# Designs decks from the owned cards around an engine and saves them in decks/, for example:
#   ./scripts/design-decks.sh --format Standard
#   ./scripts/design-decks.sh --format Standard --mechanic ganho-de-vida --colors W
#   ./scripts/design-decks.sh --format HistoricBrawl --commander "Krenko, Mob Boss"
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection design-decks "$@"
