import sqlite3
import tempfile
import unittest
from pathlib import Path

from mtg_arena_collection.meta_decks import MetaDeckCard, MetaDecksUnavailable, read_meta_decks

DECKS_TABLE = """
CREATE TABLE decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, format TEXT, best_of INTEGER,
    tier TEXT, meta_share REAL, win_rate REAL, source TEXT, source_url TEXT,
    imported_at TEXT NOT NULL, dup_of INTEGER REFERENCES decks(id)
)
"""
DECK_CARDS_TABLE = """
CREATE TABLE deck_cards (
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE, card_name TEXT NOT NULL,
    set_code TEXT, quantity INTEGER NOT NULL, board TEXT NOT NULL DEFAULT 'main', grp_id INTEGER
)
"""

MONO_RED_FROM_THE_META_LIST = {
    "name": "Mono Red", "format": "Standard", "meta_share": 0.07,
    "cards": [("Lightning Strike", 4, "main", 1001), ("Mountain", 20, "main", 1002),
              ("Abrade", 2, "side", 1003)],
}
IZZET_FROM_THE_TOP_RESULTS = {
    "name": "Izzet", "format": "Standard", "source": "aetherhub", "win_rate": 0.61,
    "cards": [("Opt", 4, "main", 1004)],
}
PLAYERS_OWN_DECK = {
    "name": "My Goblins", "format": "Standard", "source": "player_log", "best_of": None,
    "cards": [("Goblin Guide", 4, "main", 1005)],
}
BEST_OF_THREE_DECK = {
    "name": "Traditional Izzet", "format": "Standard", "best_of": 3, "meta_share": 0.02,
    "cards": [("Opt", 4, "main", 1004)],
}
SYTHIS_BRAWL_DECK = {
    "name": "Sythis, Harvest&#x27;s Hand", "format": "HistoricBrawl", "meta_share": 0.01,
    "cards": [("Sythis, Harvest's Hand", 1, "side", 2001), ("Forest", 30, "main", 2002),
              ("Sterling Grove", 1, "main", 2003)],
}


def create_deck_database(database_path: Path, decks=(), with_deck_tables=True) -> Path:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE cards (grp_id INTEGER PRIMARY KEY, name TEXT)")
        if with_deck_tables:
            connection.execute(DECKS_TABLE)
            connection.execute(DECK_CARDS_TABLE)
            for deck in decks:
                insert_deck(connection, deck)
        connection.commit()
    finally:
        connection.close()
    return database_path


def insert_deck(connection: sqlite3.Connection, deck: dict) -> int:
    cursor = connection.execute(
        "INSERT INTO decks (name, format, best_of, meta_share, win_rate, source, imported_at, dup_of) "
        "VALUES (?, ?, ?, ?, ?, ?, '2026-11-09', ?)",
        (deck["name"], deck["format"], deck.get("best_of", 1), deck.get("meta_share"),
         deck.get("win_rate"), deck.get("source", "aetherhub-meta"), deck.get("dup_of")),
    )
    connection.executemany(
        "INSERT INTO deck_cards (deck_id, card_name, quantity, board, grp_id) VALUES (?, ?, ?, ?, ?)",
        [(cursor.lastrowid, *card) for card in deck["cards"]],
    )
    return cursor.lastrowid


class ReadMetaDecksTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "mtga.db"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def read_names(self, *decks, formats=None):
        create_deck_database(self.database_path, decks)
        return [deck.name for deck in read_meta_decks(self.database_path, formats)]

    def test_reads_decks_from_deck_sites_and_leaves_out_the_players_own(self):
        names = self.read_names(MONO_RED_FROM_THE_META_LIST, IZZET_FROM_THE_TOP_RESULTS, PLAYERS_OWN_DECK)
        self.assertEqual(names, ["Mono Red", "Izzet"])

    def test_keeps_the_meta_share_and_the_win_rate(self):
        create_deck_database(self.database_path, [MONO_RED_FROM_THE_META_LIST, IZZET_FROM_THE_TOP_RESULTS])
        mono_red, izzet = read_meta_decks(self.database_path)
        self.assertEqual(
            [(mono_red.meta_share, mono_red.win_rate), (izzet.meta_share, izzet.win_rate)],
            [(0.07, None), (None, 0.61)],
        )

    def test_main_deck_leaves_out_the_sideboard(self):
        create_deck_database(self.database_path, [MONO_RED_FROM_THE_META_LIST])
        [mono_red] = read_meta_decks(self.database_path)
        self.assertEqual(
            mono_red.main,
            (MetaDeckCard("Lightning Strike", 4, 1001), MetaDeckCard("Mountain", 20, 1002)),
        )

    def test_leaves_out_near_duplicates(self):
        create_deck_database(self.database_path, [MONO_RED_FROM_THE_META_LIST])
        connection = sqlite3.connect(self.database_path)
        insert_deck(connection, {**MONO_RED_FROM_THE_META_LIST, "name": "Mono Red Copy", "dup_of": 1})
        connection.commit()
        connection.close()
        self.assertEqual([deck.name for deck in read_meta_decks(self.database_path)], ["Mono Red"])

    def test_leaves_out_best_of_three_lists(self):
        names = self.read_names(IZZET_FROM_THE_TOP_RESULTS, BEST_OF_THREE_DECK)
        self.assertEqual(names, ["Izzet"])

    def test_brawl_commander_comes_from_the_side_board(self):
        create_deck_database(self.database_path, [SYTHIS_BRAWL_DECK])
        [sythis] = read_meta_decks(self.database_path)
        self.assertEqual(
            (sythis.commander, [card.name for card in sythis.main]),
            (MetaDeckCard("Sythis, Harvest's Hand", 1, 2001), ["Forest", "Sterling Grove"]),
        )

    def test_decks_outside_brawl_have_no_commander(self):
        create_deck_database(self.database_path, [MONO_RED_FROM_THE_META_LIST])
        [mono_red] = read_meta_decks(self.database_path)
        self.assertIsNone(mono_red.commander)

    def test_html_entities_in_names_are_decoded(self):
        self.assertEqual(self.read_names(SYTHIS_BRAWL_DECK), ["Sythis, Harvest's Hand"])

    def test_reads_only_the_formats_asked_for(self):
        names = self.read_names(MONO_RED_FROM_THE_META_LIST, SYTHIS_BRAWL_DECK, formats={"HistoricBrawl"})
        self.assertEqual(names, ["Sythis, Harvest's Hand"])

    def test_leaves_the_database_untouched(self):
        create_deck_database(self.database_path, [MONO_RED_FROM_THE_META_LIST])
        modified_before = self.database_path.stat().st_mtime_ns
        read_meta_decks(self.database_path)
        self.assertEqual(self.database_path.stat().st_mtime_ns, modified_before)

    def test_missing_database_says_what_to_run(self):
        with self.assertRaisesRegex(MetaDecksUnavailable, "bulk-import"):
            read_meta_decks(self.database_path)

    def test_database_without_deck_tables_says_what_to_run(self):
        create_deck_database(self.database_path, with_deck_tables=False)
        with self.assertRaisesRegex(MetaDecksUnavailable, "bulk-import"):
            read_meta_decks(self.database_path)

    def test_database_with_only_the_players_decks_says_what_to_run(self):
        create_deck_database(self.database_path, [PLAYERS_OWN_DECK])
        with self.assertRaisesRegex(MetaDecksUnavailable, "bulk-import"):
            read_meta_decks(self.database_path)


if __name__ == "__main__":
    unittest.main()
