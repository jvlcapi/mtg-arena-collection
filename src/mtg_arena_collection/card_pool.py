"""The cards a deck can use in a format: the owned ones that are legal, by card name.

Legality comes from mtga-mcp's `cards` table, which `mtga-mcp import --scryfall` fills from
Scryfall by Arena id. Standard uses `legal_standard`; Historic and Historic Brawl use
`legal_historic`. A name is legal when any of its printings is. Copies of every printing add up,
and the decklist uses the printing with the most copies. Basic lands are always there.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from mtg_arena_collection.card_catalog import Card
from mtg_arena_collection.meta_decks import is_brawl_format
from mtg_arena_collection.mtga_mcp_collection import DEFAULT_MTGA_MCP_DATABASE

LEGALITY_COLUMNS = {
    "Standard": "legal_standard",
    "Historic": "legal_historic",
    "HistoricBrawl": "legal_historic",
}
LEGAL = "legal"
PLAYSET = 4
UNLIMITED_COPIES = 1_000
ANY_NUMBER_TEXT = "A deck can have any number of cards named"
TOKEN_RARITY = "token"
SCRYFALL_INSTRUCTIONS = "Run `mtga-mcp import --scryfall` first."


class CardLegalityUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PoolCard:
    card: Card
    owned_copies: int

    @property
    def name(self) -> str:
        return self.card.name


def read_legal_arena_ids(database_path: Path = DEFAULT_MTGA_MCP_DATABASE, format_name: str = "Standard") -> set[int]:
    if format_name not in LEGALITY_COLUMNS:
        raise CardLegalityUnavailable(
            f"No legality data for {format_name}; mtga-mcp only stores it for "
            f"{', '.join(LEGALITY_COLUMNS)}."
        )
    database_path = Path(database_path)
    if not database_path.exists():
        raise CardLegalityUnavailable(f"No mtga-mcp database at {database_path}. {SCRYFALL_INSTRUCTIONS}")
    connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            f"SELECT grp_id FROM cards WHERE {LEGALITY_COLUMNS[format_name]} = ?", (LEGAL,)
        ).fetchall()
    except sqlite3.OperationalError as error:
        raise CardLegalityUnavailable(
            f"The mtga-mcp database has no card legality ({error}). {SCRYFALL_INSTRUCTIONS}"
        ) from error
    finally:
        connection.close()
    if not rows:
        raise CardLegalityUnavailable(f"No card is marked legal in {format_name}. {SCRYFALL_INSTRUCTIONS}")
    return {arena_id for (arena_id,) in rows}


def build_card_pool(
    collection: dict[int, int], catalog: dict[int, Card], legal_arena_ids: set[int]
) -> dict[str, PoolCard]:
    legal_names = {catalog[arena_id].name for arena_id in legal_arena_ids if arena_id in catalog}
    copies_by_name = defaultdict(int)
    printing_by_name = {}
    for arena_id, quantity in sorted(collection.items()):
        card = catalog.get(arena_id)
        if card is None or quantity <= 0:
            continue
        if card.name not in legal_names and not is_basic_land(card):
            continue
        copies_by_name[card.name] += quantity
        most_copied = printing_by_name.get(card.name)
        if most_copied is None or quantity > most_copied[1]:
            printing_by_name[card.name] = (card, quantity)
    pool = {name: PoolCard(printing_by_name[name][0], copies) for name, copies in copies_by_name.items()}
    for card in sorted(catalog.values(), key=lambda card: card.arena_id):
        if is_basic_land(card) and card.name not in pool:
            pool[card.name] = PoolCard(card, 0)
    return pool


def copy_limit(pool_card: PoolCard, format_name: str) -> int:
    if is_basic_land(pool_card.card):
        return UNLIMITED_COPIES
    if ANY_NUMBER_TEXT in pool_card.card.rules_text:
        return pool_card.owned_copies
    return min(pool_card.owned_copies, 1 if is_brawl_format(format_name) else PLAYSET)


def is_basic_land(card: Card) -> bool:
    return card.type_line.startswith("Basic") and card.rarity != TOKEN_RARITY
