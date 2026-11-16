"""Turns a collection ({arena_id: quantity}) into CSV rows with the card details."""

import csv
import os
from dataclasses import asdict
from pathlib import Path

from mtg_arena_collection.card_catalog import Card
from mtg_arena_collection.card_mechanics import MechanicTagger

CSV_COLUMNS = (
    "quantity",
    "name",
    "portuguese_name",
    "set_code",
    "collector_number",
    "rarity",
    "mana_cost",
    "mana_value",
    "colors",
    "color_identity",
    "type_line",
    "power",
    "toughness",
    "rules_text",
    "mechanics",
    "arena_id",
    "digital_release_set",
    "is_digital_only",
    "is_rebalanced",
)


def build_collection_rows(
    collection: dict[int, int], catalog: dict[int, Card], tagger: MechanicTagger | None = None
) -> list[dict[str, str]]:
    tagger = tagger or MechanicTagger.from_catalog(catalog)
    rows = []
    for arena_id, quantity in collection.items():
        if quantity <= 0:
            continue
        card = catalog.get(arena_id)
        card_details = asdict(card) if card else {"arena_id": arena_id}
        row = {column: _as_text(card_details.get(column, "")) for column in CSV_COLUMNS}
        row["quantity"] = str(quantity)
        row["mechanics"] = ";".join(tagger.tags_for(card)) if card else ""
        rows.append(row)
    return sorted(rows, key=_sort_key)


def find_unknown_arena_ids(collection: dict[int, int], catalog: dict[int, Card]) -> list[int]:
    return sorted(arena_id for arena_id in collection if arena_id not in catalog)


def write_collection_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.partial")
    with temporary_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary_path, output_path)


def _as_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _sort_key(row: dict[str, str]) -> tuple:
    is_unknown_card = row["name"] == ""
    return (is_unknown_card, row["name"].casefold(), row["set_code"], int(row["arena_id"]))
