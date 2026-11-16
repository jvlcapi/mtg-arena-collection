#!/bin/bash
# Turns the collection in mtga-mcp's database into exports/collection.csv, without reading the logs.
# Extra arguments go to the importer, for example: --output ~/Desktop/colecao.csv
set -euo pipefail

project_directory="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$project_directory/src" exec python3 -m mtg_arena_collection import-from-mtga-mcp "$@"
