"""Puts the steps that keep the collection CSV up to date in the right order."""

from typing import Callable

from mtg_arena_collection.collection_changes import CollectionUpdate


def refresh_collection(
    run_capture: Callable[[], object], update_csv: Callable[[], CollectionUpdate]
) -> CollectionUpdate:
    """Adds the cards granted in the game logs to mtga-mcp's collection, then updates the CSV."""
    run_capture()
    return update_csv()
