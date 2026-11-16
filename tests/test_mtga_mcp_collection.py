import sqlite3
import tempfile
import unittest
from pathlib import Path

from mtg_arena_collection.mtga_mcp_collection import (
    MtgaMcpCollectionUnavailable,
    read_mtga_mcp_collection,
)


def create_mtga_mcp_database(database_path: Path, collection_rows=None, with_collection_table=True) -> Path:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("CREATE TABLE cards (grp_id INTEGER PRIMARY KEY, name TEXT)")
        if with_collection_table:
            connection.execute(
                "CREATE TABLE collection (grp_id INTEGER PRIMARY KEY, count INTEGER NOT NULL)"
            )
            connection.executemany("INSERT INTO collection VALUES (?, ?)", collection_rows or [])
        connection.commit()
    finally:
        connection.close()
    return database_path


class ReadMtgaMcpCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "mtga.db"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_reads_quantity_by_arena_id(self):
        create_mtga_mcp_database(self.database_path, [(106584, 2), (66709, 4)])
        self.assertEqual(read_mtga_mcp_collection(self.database_path), {106584: 2, 66709: 4})

    def test_leaves_the_database_untouched(self):
        create_mtga_mcp_database(self.database_path, [(106584, 2)])
        modified_before = self.database_path.stat().st_mtime_ns
        read_mtga_mcp_collection(self.database_path)
        self.assertEqual(self.database_path.stat().st_mtime_ns, modified_before)

    def test_missing_database_says_what_to_run(self):
        with self.assertRaisesRegex(MtgaMcpCollectionUnavailable, "mtga-mcp capture"):
            read_mtga_mcp_collection(self.database_path)

    def test_database_without_collection_table_says_what_to_run(self):
        create_mtga_mcp_database(self.database_path, with_collection_table=False)
        with self.assertRaisesRegex(MtgaMcpCollectionUnavailable, "mtga-mcp capture"):
            read_mtga_mcp_collection(self.database_path)

    def test_empty_collection_says_what_to_run(self):
        create_mtga_mcp_database(self.database_path, [])
        with self.assertRaisesRegex(MtgaMcpCollectionUnavailable, "mtga-mcp capture"):
            read_mtga_mcp_collection(self.database_path)


if __name__ == "__main__":
    unittest.main()
