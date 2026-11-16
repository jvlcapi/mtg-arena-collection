import csv
import tempfile
import unittest
from pathlib import Path

from card_database_fixture import (
    ISLAND_ARENA_ID,
    PICARD_ARENA_ID,
    RELEASE_TO_THE_WIND_ARENA_ID,
    create_card_database,
)
from mtg_arena_collection.card_catalog import load_card_catalog
from mtg_arena_collection.collection_csv import (
    CSV_COLUMNS,
    build_collection_rows,
    find_unknown_arena_ids,
    write_collection_csv,
)

UNKNOWN_ARENA_ID = 999999


class CollectionCsvTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        database_path = create_card_database(
            Path(cls.temporary_directory.name) / "Raw_CardDatabase_test.mtga"
        )
        cls.catalog = load_card_catalog(database_path)

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()


class BuildCollectionRowsTests(CollectionCsvTestCase):
    def test_rows_are_sorted_by_name(self):
        rows = build_collection_rows(
            {RELEASE_TO_THE_WIND_ARENA_ID: 1, ISLAND_ARENA_ID: 20, PICARD_ARENA_ID: 2},
            self.catalog,
        )
        self.assertEqual(
            [row["name"] for row in rows],
            ["Captain Jean-Luc Picard", "Island", "Release to the Wind"],
        )

    def test_row_carries_quantity_and_card_details(self):
        [row] = build_collection_rows({PICARD_ARENA_ID: 2}, self.catalog)
        self.assertEqual(
            (row["quantity"], row["set_code"], row["rarity"], row["mana_cost"]),
            ("2", "TRK", "mythic", "{2}{W}"),
        )

    def test_row_carries_the_card_mechanics_separated_by_semicolons(self):
        [row] = build_collection_rows({PICARD_ARENA_ID: 2}, self.catalog)
        self.assertEqual(row["mechanics"], "bonus-para-o-time;dano-direto;remocao")

    def test_unknown_card_has_no_mechanics(self):
        [row] = build_collection_rows({UNKNOWN_ARENA_ID: 1}, self.catalog)
        self.assertEqual(row["mechanics"], "")

    def test_cards_with_zero_copies_are_skipped(self):
        rows = build_collection_rows({PICARD_ARENA_ID: 0, ISLAND_ARENA_ID: 4}, self.catalog)
        self.assertEqual([row["name"] for row in rows], ["Island"])

    def test_unknown_cards_are_kept_at_the_end_with_their_id(self):
        rows = build_collection_rows({UNKNOWN_ARENA_ID: 1, ISLAND_ARENA_ID: 4}, self.catalog)
        self.assertEqual(
            [(row["arena_id"], row["name"]) for row in rows],
            [(str(ISLAND_ARENA_ID), "Island"), (str(UNKNOWN_ARENA_ID), "")],
        )

    def test_rows_use_every_csv_column(self):
        [row] = build_collection_rows({PICARD_ARENA_ID: 1}, self.catalog)
        self.assertEqual(list(row), list(CSV_COLUMNS))


class FindUnknownArenaIdsTests(CollectionCsvTestCase):
    def test_reports_ids_missing_from_the_catalog(self):
        unknown_ids = find_unknown_arena_ids(
            {UNKNOWN_ARENA_ID: 1, PICARD_ARENA_ID: 1}, self.catalog
        )
        self.assertEqual(unknown_ids, [UNKNOWN_ARENA_ID])


class WriteCollectionCsvTests(CollectionCsvTestCase):
    def setUp(self):
        self.output_directory = tempfile.TemporaryDirectory()
        self.output_path = Path(self.output_directory.name) / "collection.csv"

    def tearDown(self):
        self.output_directory.cleanup()

    def test_csv_round_trip_keeps_multiline_rules_text(self):
        rows = build_collection_rows({PICARD_ARENA_ID: 2}, self.catalog)
        write_collection_csv(rows, self.output_path)
        with self.output_path.open(newline="", encoding="utf-8") as csv_file:
            self.assertEqual(list(csv.DictReader(csv_file)), rows)

    def test_header_follows_column_order(self):
        write_collection_csv([], self.output_path)
        header_line = self.output_path.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(header_line, ",".join(CSV_COLUMNS))

    def test_leaves_no_temporary_file_behind(self):
        write_collection_csv([], self.output_path)
        self.assertEqual(
            sorted(path.name for path in self.output_path.parent.iterdir()), ["collection.csv"]
        )

    def test_creates_missing_output_directory(self):
        nested_output_path = Path(self.output_directory.name) / "exports" / "collection.csv"
        write_collection_csv([], nested_output_path)
        self.assertTrue(nested_output_path.exists())


if __name__ == "__main__":
    unittest.main()
