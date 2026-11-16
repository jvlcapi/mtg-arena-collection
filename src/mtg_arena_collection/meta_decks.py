"""Reads the meta decks that mtga-mcp (github.com/fkadriver/mtga-mcp) imported from deck sites.

`mtga-mcp deck bulk-import` saves each deck in `decks`, with the meta share or the win rate the
site showed, and its cards in `deck_cards` (board `main` or `side`). Decks read from the player's
own game log (source `player_log`), near-duplicates (`dup_of`) and Best-of-3 lists are left out.
In Brawl formats the commander is the one card on the side board.
"""

import html
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from mtg_arena_collection.mtga_mcp_collection import DEFAULT_MTGA_MCP_DATABASE

PLAYER_LOG_SOURCE = "player_log"
BEST_OF_ONE = 1
IMPORT_INSTRUCTIONS = (
    "Import them with mtga-mcp first, for example: "
    "mtga-mcp deck bulk-import --source aetherhub-meta --format Standard --best-of 1"
)
DECKS_QUERY = """
SELECT id, name, format, source, meta_share, win_rate FROM decks
WHERE source IS NOT ? AND dup_of IS NULL AND best_of = ?
ORDER BY format, id
"""
DECK_CARDS_QUERY = "SELECT deck_id, card_name, quantity, board, grp_id FROM deck_cards ORDER BY rowid"
MAIN_BOARD = "main"


class MetaDecksUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class MetaDeckCard:
    name: str
    quantity: int
    arena_id: int | None = None


@dataclass(frozen=True)
class MetaDeck:
    deck_id: int
    name: str
    format_name: str
    source: str
    meta_share: float | None
    win_rate: float | None
    main: tuple[MetaDeckCard, ...]
    commander: MetaDeckCard | None = None


def read_meta_decks(
    database_path: Path = DEFAULT_MTGA_MCP_DATABASE, formats: set[str] | None = None
) -> list[MetaDeck]:
    deck_rows, card_rows = _read_rows(Path(database_path))
    cards_by_deck = defaultdict(lambda: {"main": [], "side": []})
    for deck_id, card_name, quantity, board, arena_id in card_rows:
        board_cards = cards_by_deck[deck_id]["main" if board == MAIN_BOARD else "side"]
        board_cards.append(MetaDeckCard(html.unescape(card_name), quantity, arena_id))
    decks = [
        _build_deck(row, cards_by_deck[row[0]])
        for row in deck_rows
        if formats is None or row[2] in formats
    ]
    if not decks:
        wanted = f" for {', '.join(sorted(formats))}" if formats else ""
        raise MetaDecksUnavailable(f"The mtga-mcp database has no meta decks{wanted}. {IMPORT_INSTRUCTIONS}")
    return decks


def is_brawl_format(format_name: str) -> bool:
    return format_name.endswith("Brawl")


def _read_rows(database_path: Path) -> tuple[list, list]:
    if not database_path.exists():
        raise MetaDecksUnavailable(f"No mtga-mcp database at {database_path}. {IMPORT_INSTRUCTIONS}")
    connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        deck_rows = connection.execute(DECKS_QUERY, (PLAYER_LOG_SOURCE, BEST_OF_ONE)).fetchall()
        card_rows = connection.execute(DECK_CARDS_QUERY).fetchall()
    except sqlite3.OperationalError as error:
        raise MetaDecksUnavailable(
            f"The mtga-mcp database has no decks yet ({error}). {IMPORT_INSTRUCTIONS}"
        ) from error
    finally:
        connection.close()
    return deck_rows, card_rows


def _build_deck(deck_row: tuple, cards: dict[str, list[MetaDeckCard]]) -> MetaDeck:
    deck_id, name, format_name, source, meta_share, win_rate = deck_row
    side_board = cards["side"]
    has_commander = is_brawl_format(format_name) and len(side_board) == 1
    return MetaDeck(
        deck_id=deck_id,
        name=html.unescape(name),
        format_name=format_name,
        source=source,
        meta_share=meta_share,
        win_rate=win_rate,
        main=tuple(cards["main"]),
        commander=side_board[0] if has_commander else None,
    )
