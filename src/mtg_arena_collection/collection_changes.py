"""Finds what changed since the last CSV, rewrites it and keeps a log of the changes."""

import csv
from dataclasses import astuple, dataclass, field
from pathlib import Path
from typing import Callable

from mtg_arena_collection.card_catalog import Card
from mtg_arena_collection.collection_csv import build_collection_rows, write_collection_csv

CHANGE_LOG_COLUMNS = (
    "changed_at",
    "arena_id",
    "name",
    "set_code",
    "rarity",
    "previous_quantity",
    "new_quantity",
)


class PreviousCsvUnreadable(RuntimeError):
    pass


@dataclass(frozen=True)
class CollectionChange:
    arena_id: int
    previous_quantity: int
    new_quantity: int


@dataclass(frozen=True)
class ChangeLogEntry:
    changed_at: str
    arena_id: int
    name: str
    set_code: str
    rarity: str
    previous_quantity: int
    new_quantity: int


@dataclass
class CollectionUpdate:
    csv_written: bool
    is_first_csv: bool
    changes: list[ChangeLogEntry] = field(default_factory=list)


def read_quantities_from_csv(csv_path: Path) -> dict[int, int] | None:
    """Quantities by Arena id in a CSV this project wrote, or None when there is no CSV yet."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return None
    try:
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            return {
                int(row["arena_id"]): int(row["quantity"]) for row in csv.DictReader(csv_file)
            }
    except (KeyError, ValueError) as error:
        raise PreviousCsvUnreadable(
            f"Could not read the quantities in {csv_path} ({error!r}). "
            "Delete it to write it again from the mtga-mcp collection."
        ) from error


def find_collection_changes(
    previous: dict[int, int], current: dict[int, int]
) -> list[CollectionChange]:
    changes = []
    for arena_id in sorted(previous.keys() | current.keys()):
        previous_quantity = previous.get(arena_id, 0)
        new_quantity = current.get(arena_id, 0)
        if previous_quantity != new_quantity:
            changes.append(CollectionChange(arena_id, previous_quantity, new_quantity))
    return changes


def describe_changes(
    changes: list[CollectionChange], catalog: dict[int, Card], changed_at: str
) -> list[ChangeLogEntry]:
    entries = []
    for change in changes:
        card = catalog.get(change.arena_id)
        entries.append(
            ChangeLogEntry(
                changed_at=changed_at,
                arena_id=change.arena_id,
                name=card.name if card else "",
                set_code=card.set_code if card else "",
                rarity=card.rarity if card else "",
                previous_quantity=change.previous_quantity,
                new_quantity=change.new_quantity,
            )
        )
    return entries


def append_to_change_log(entries: list[ChangeLogEntry], change_log_path: Path) -> None:
    change_log_path = Path(change_log_path)
    change_log_path.parent.mkdir(parents=True, exist_ok=True)
    is_new_log = not change_log_path.exists()
    with change_log_path.open("a", newline="", encoding="utf-8") as change_log:
        writer = csv.writer(change_log)
        if is_new_log:
            writer.writerow(CHANGE_LOG_COLUMNS)
        writer.writerows(astuple(entry) for entry in entries)


def update_collection_csv(
    collection: dict[int, int],
    load_catalog: Callable[[], dict[int, Card]],
    csv_path: Path,
    change_log_path: Path,
    changed_at: str,
    *,
    rewrite_when_unchanged: bool = False,
) -> CollectionUpdate:
    """Rewrites the CSV when quantities changed (or when asked to) and logs each change.

    The catalog is only loaded when the CSV gets written, so an unchanged collection is cheap.
    """
    previous = read_quantities_from_csv(csv_path)
    changes = [] if previous is None else find_collection_changes(previous, collection)
    if previous is not None and not changes and not rewrite_when_unchanged:
        return CollectionUpdate(csv_written=False, is_first_csv=False)

    catalog = load_catalog()
    write_collection_csv(build_collection_rows(collection, catalog), csv_path)
    entries = describe_changes(changes, catalog, changed_at)
    if entries:
        append_to_change_log(entries, change_log_path)
    return CollectionUpdate(csv_written=True, is_first_csv=previous is None, changes=entries)
