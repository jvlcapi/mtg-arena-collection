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
from mtg_arena_collection.collection_changes import (
    CHANGE_LOG_COLUMNS,
    ChangeLogEntry,
    CollectionChange,
    PreviousCsvUnreadable,
    append_to_change_log,
    describe_changes,
    find_collection_changes,
    read_quantities_from_csv,
    update_collection_csv,
)
from mtg_arena_collection.collection_csv import build_collection_rows, write_collection_csv

UNKNOWN_ARENA_ID = 999999
CHANGED_AT = "2026-11-09T11:05:00-03:00"


class CatalogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog_directory = tempfile.TemporaryDirectory()
        database_path = create_card_database(
            Path(cls.catalog_directory.name) / "Raw_CardDatabase_test.mtga"
        )
        cls.catalog = load_card_catalog(database_path)

    @classmethod
    def tearDownClass(cls):
        cls.catalog_directory.cleanup()

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temporary_directory.name) / "collection.csv"
        self.change_log_path = Path(self.temporary_directory.name) / "collection-changes.csv"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_csv(self, collection, catalog=None):
        rows = build_collection_rows(collection, self.catalog if catalog is None else catalog)
        write_collection_csv(rows, self.csv_path)

    def read_change_log(self):
        with self.change_log_path.open(newline="", encoding="utf-8") as change_log:
            return list(csv.reader(change_log))


class FindCollectionChangesTests(unittest.TestCase):
    def test_new_card_changes_from_zero_copies(self):
        self.assertEqual(
            find_collection_changes({}, {PICARD_ARENA_ID: 1}),
            [CollectionChange(PICARD_ARENA_ID, 0, 1)],
        )

    def test_more_copies_of_an_owned_card_is_a_change(self):
        self.assertEqual(
            find_collection_changes({PICARD_ARENA_ID: 1}, {PICARD_ARENA_ID: 2}),
            [CollectionChange(PICARD_ARENA_ID, 1, 2)],
        )

    def test_card_missing_from_the_new_collection_goes_to_zero_copies(self):
        self.assertEqual(
            find_collection_changes({PICARD_ARENA_ID: 2}, {}),
            [CollectionChange(PICARD_ARENA_ID, 2, 0)],
        )

    def test_same_quantities_are_not_changes(self):
        self.assertEqual(find_collection_changes({PICARD_ARENA_ID: 2}, {PICARD_ARENA_ID: 2}), [])

    def test_zero_copies_count_as_not_owned(self):
        self.assertEqual(find_collection_changes({}, {PICARD_ARENA_ID: 0}), [])

    def test_changes_are_sorted_by_arena_id(self):
        changes = find_collection_changes(
            {}, {RELEASE_TO_THE_WIND_ARENA_ID: 1, ISLAND_ARENA_ID: 1, PICARD_ARENA_ID: 1}
        )
        self.assertEqual(
            [change.arena_id for change in changes],
            sorted([RELEASE_TO_THE_WIND_ARENA_ID, ISLAND_ARENA_ID, PICARD_ARENA_ID]),
        )


class ReadQuantitiesFromCsvTests(CatalogTestCase):
    def test_missing_csv_means_there_is_no_previous_collection(self):
        self.assertIsNone(read_quantities_from_csv(self.csv_path))

    def test_reads_back_the_quantities_the_csv_was_written_with(self):
        self.write_csv({PICARD_ARENA_ID: 2, ISLAND_ARENA_ID: 4})
        self.assertEqual(
            read_quantities_from_csv(self.csv_path), {PICARD_ARENA_ID: 2, ISLAND_ARENA_ID: 4}
        )

    def test_csv_without_quantities_says_how_to_recover(self):
        self.csv_path.write_text("name\nIsland\n", encoding="utf-8")
        with self.assertRaisesRegex(PreviousCsvUnreadable, "Delete it"):
            read_quantities_from_csv(self.csv_path)


class DescribeChangesTests(CatalogTestCase):
    def test_entry_carries_the_card_details(self):
        [entry] = describe_changes([CollectionChange(PICARD_ARENA_ID, 1, 2)], self.catalog, CHANGED_AT)
        self.assertEqual(
            entry,
            ChangeLogEntry(CHANGED_AT, PICARD_ARENA_ID, "Captain Jean-Luc Picard", "TRK", "mythic", 1, 2),
        )

    def test_unknown_card_keeps_only_its_id(self):
        [entry] = describe_changes([CollectionChange(UNKNOWN_ARENA_ID, 0, 1)], self.catalog, CHANGED_AT)
        self.assertEqual((entry.arena_id, entry.name, entry.set_code), (UNKNOWN_ARENA_ID, "", ""))


class AppendToChangeLogTests(CatalogTestCase):
    def test_first_entries_create_the_log_with_a_header(self):
        append_to_change_log(
            describe_changes([CollectionChange(PICARD_ARENA_ID, 1, 2)], self.catalog, CHANGED_AT),
            self.change_log_path,
        )
        self.assertEqual(self.read_change_log()[0], list(CHANGE_LOG_COLUMNS))

    def test_entry_row_has_time_card_and_quantities(self):
        append_to_change_log(
            describe_changes([CollectionChange(PICARD_ARENA_ID, 1, 2)], self.catalog, CHANGED_AT),
            self.change_log_path,
        )
        self.assertEqual(
            self.read_change_log()[1],
            [CHANGED_AT, str(PICARD_ARENA_ID), "Captain Jean-Luc Picard", "TRK", "mythic", "1", "2"],
        )

    def test_later_entries_go_below_the_earlier_ones(self):
        for previous_quantity in (1, 2):
            change = CollectionChange(PICARD_ARENA_ID, previous_quantity, previous_quantity + 1)
            append_to_change_log(describe_changes([change], self.catalog, CHANGED_AT), self.change_log_path)
        self.assertEqual([row[-1] for row in self.read_change_log()], ["new_quantity", "2", "3"])


class UpdateCollectionCsvTests(CatalogTestCase):
    def load_catalog(self):
        self.catalog_loads += 1
        return self.catalog

    def setUp(self):
        super().setUp()
        self.catalog_loads = 0

    def update(self, collection, rewrite_when_unchanged=False):
        return update_collection_csv(
            collection,
            self.load_catalog,
            self.csv_path,
            self.change_log_path,
            CHANGED_AT,
            rewrite_when_unchanged=rewrite_when_unchanged,
        )

    def test_first_update_writes_the_csv_without_logging_changes(self):
        update = self.update({PICARD_ARENA_ID: 1})
        self.assertEqual(
            (update.csv_written, update.is_first_csv, update.changes, self.change_log_path.exists()),
            (True, True, [], False),
        )
        self.assertEqual(read_quantities_from_csv(self.csv_path), {PICARD_ARENA_ID: 1})

    def test_unchanged_collection_leaves_everything_alone_without_loading_the_catalog(self):
        self.write_csv({PICARD_ARENA_ID: 1})
        modified_before = self.csv_path.stat().st_mtime_ns
        update = self.update({PICARD_ARENA_ID: 1})
        self.assertEqual(
            (update.csv_written, update.changes, self.catalog_loads, self.change_log_path.exists()),
            (False, [], 0, False),
        )
        self.assertEqual(self.csv_path.stat().st_mtime_ns, modified_before)

    def test_changed_collection_rewrites_the_csv(self):
        self.write_csv({PICARD_ARENA_ID: 1})
        self.update({PICARD_ARENA_ID: 2, ISLAND_ARENA_ID: 1})
        self.assertEqual(
            read_quantities_from_csv(self.csv_path), {PICARD_ARENA_ID: 2, ISLAND_ARENA_ID: 1}
        )

    def test_changed_collection_logs_each_change(self):
        self.write_csv({PICARD_ARENA_ID: 1})
        update = self.update({PICARD_ARENA_ID: 2, ISLAND_ARENA_ID: 1})
        self.assertEqual(
            [(entry.name, entry.previous_quantity, entry.new_quantity) for entry in update.changes],
            [("Island", 0, 1), ("Captain Jean-Luc Picard", 1, 2)],
        )
        self.assertEqual(len(self.read_change_log()), 3)

    def test_rewrite_when_unchanged_refreshes_card_details(self):
        self.write_csv({PICARD_ARENA_ID: 1}, catalog={})
        update = self.update({PICARD_ARENA_ID: 1}, rewrite_when_unchanged=True)
        with self.csv_path.open(newline="", encoding="utf-8") as csv_file:
            [row] = list(csv.DictReader(csv_file))
        self.assertEqual((update.csv_written, row["name"]), (True, "Captain Jean-Luc Picard"))


if __name__ == "__main__":
    unittest.main()
