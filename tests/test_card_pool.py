import sqlite3
import tempfile
import unittest
from pathlib import Path

from card_fixture import make_card
from mtg_arena_collection.card_pool import (
    CardLegalityUnavailable,
    build_card_pool,
    copy_limit,
    read_legal_arena_ids,
)

PLAINS = make_card("Plains", "Basic Land — Plains", arena_id=10, rarity="basic")
PLAINS_NEWER_PRINTING = make_card("Plains", "Basic Land — Plains", arena_id=11, rarity="basic")
SWAMP = make_card("Swamp", "Basic Land — Swamp", arena_id=12, rarity="basic")
SNOW_COVERED_ISLAND = make_card("Snow-Covered Island", "Basic Snow Land — Island", arena_id=13, rarity="basic")
HEALERS_HAWK = make_card("Healer's Hawk", "Creature — Bird", "Flying\nLifelink", arena_id=20, colors="W")
HEALERS_HAWK_PROMO = make_card("Healer's Hawk", "Creature — Bird", "Flying\nLifelink", arena_id=21, colors="W")
GOBLIN_GUIDE = make_card("Goblin Guide", "Creature — Goblin Scout", "Haste", arena_id=30, colors="R")
PERSISTENT_PETITIONERS = make_card(
    "Persistent Petitioners", "Creature — Human Advisor",
    "A deck can have any number of cards named Persistent Petitioners.", arena_id=40, colors="U")
CATALOG = {
    card.arena_id: card
    for card in (PLAINS, PLAINS_NEWER_PRINTING, SWAMP, SNOW_COVERED_ISLAND, HEALERS_HAWK,
                 HEALERS_HAWK_PROMO, GOBLIN_GUIDE, PERSISTENT_PETITIONERS)
}
EVERY_ARENA_ID = set(CATALOG)


def create_legality_database(database_path: Path, rows=(), with_cards_table=True) -> Path:
    connection = sqlite3.connect(database_path)
    try:
        if with_cards_table:
            connection.execute(
                "CREATE TABLE cards (grp_id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                "legal_standard TEXT, legal_pioneer TEXT, legal_explorer TEXT, legal_historic TEXT)"
            )
            connection.executemany(
                "INSERT INTO cards (grp_id, name, legal_standard, legal_historic) VALUES (?, ?, ?, ?)", rows
            )
        connection.commit()
    finally:
        connection.close()
    return database_path


class ReadLegalArenaIdsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "mtga.db"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_standard_uses_the_standard_legality(self):
        create_legality_database(self.database_path, [
            (20, "Healer's Hawk", "legal", "legal"),
            (30, "Goblin Guide", "not_legal", "legal"),
            (31, "Banned Card", "banned", "banned"),
        ])
        self.assertEqual(read_legal_arena_ids(self.database_path, "Standard"), {20})

    def test_historic_brawl_uses_the_historic_legality(self):
        create_legality_database(self.database_path, [
            (20, "Healer's Hawk", "legal", "legal"),
            (30, "Goblin Guide", "not_legal", "legal"),
        ])
        self.assertEqual(read_legal_arena_ids(self.database_path, "HistoricBrawl"), {20, 30})

    def test_no_card_marked_legal_says_what_to_run(self):
        create_legality_database(self.database_path, [(20, "Healer's Hawk", None, None)])
        with self.assertRaisesRegex(CardLegalityUnavailable, "import --scryfall"):
            read_legal_arena_ids(self.database_path, "Standard")

    def test_formats_without_legality_data_are_refused(self):
        create_legality_database(self.database_path)
        with self.assertRaisesRegex(CardLegalityUnavailable, "Alchemy"):
            read_legal_arena_ids(self.database_path, "Alchemy")

    def test_missing_database_says_what_to_run(self):
        with self.assertRaisesRegex(CardLegalityUnavailable, "import --scryfall"):
            read_legal_arena_ids(self.database_path, "Standard")

    def test_database_without_cards_table_says_what_to_run(self):
        create_legality_database(self.database_path, with_cards_table=False)
        with self.assertRaisesRegex(CardLegalityUnavailable, "import --scryfall"):
            read_legal_arena_ids(self.database_path, "Standard")


class BuildCardPoolTests(unittest.TestCase):
    def test_copies_of_every_printing_add_up(self):
        pool = build_card_pool({20: 1, 21: 2}, CATALOG, EVERY_ARENA_ID)
        self.assertEqual(pool["Healer's Hawk"].owned_copies, 3)

    def test_the_decklist_uses_the_printing_with_the_most_copies(self):
        pool = build_card_pool({20: 1, 21: 2}, CATALOG, EVERY_ARENA_ID)
        self.assertEqual(pool["Healer's Hawk"].card, HEALERS_HAWK_PROMO)

    def test_cards_not_legal_in_the_format_are_left_out(self):
        pool = build_card_pool({20: 1, 30: 4}, CATALOG, {20})
        self.assertNotIn("Goblin Guide", pool)

    def test_a_card_is_legal_when_any_printing_is(self):
        pool = build_card_pool({21: 2}, CATALOG, {20})
        self.assertIn("Healer's Hawk", pool)

    def test_cards_without_copies_are_left_out(self):
        pool = build_card_pool({20: 0}, CATALOG, EVERY_ARENA_ID)
        self.assertNotIn("Healer's Hawk", pool)

    def test_basic_lands_are_always_there_even_without_copies(self):
        pool = build_card_pool({}, CATALOG, set())
        self.assertEqual(sorted(name for name in pool), ["Plains", "Snow-Covered Island", "Swamp"])

    def test_owned_basic_land_printing_is_preferred(self):
        pool = build_card_pool({11: 30}, CATALOG, set())
        self.assertEqual(pool["Plains"].card, PLAINS_NEWER_PRINTING)


class CopyLimitTests(unittest.TestCase):
    def setUp(self):
        self.pool = build_card_pool({20: 1, 21: 5, 40: 9}, CATALOG, EVERY_ARENA_ID)

    def test_sixty_card_decks_take_up_to_four_owned_copies(self):
        self.assertEqual(copy_limit(self.pool["Healer's Hawk"], "Standard"), 4)

    def test_never_more_copies_than_owned(self):
        pool = build_card_pool({20: 2}, CATALOG, EVERY_ARENA_ID)
        self.assertEqual(copy_limit(pool["Healer's Hawk"], "Standard"), 2)

    def test_brawl_takes_one_copy(self):
        self.assertEqual(copy_limit(self.pool["Healer's Hawk"], "HistoricBrawl"), 1)

    def test_basic_lands_have_no_limit(self):
        self.assertGreaterEqual(copy_limit(self.pool["Plains"], "HistoricBrawl"), 99)

    def test_cards_allowing_any_number_take_every_owned_copy(self):
        self.assertEqual(copy_limit(self.pool["Persistent Petitioners"], "Standard"), 9)


if __name__ == "__main__":
    unittest.main()
