import os
import tempfile
import unittest
from pathlib import Path

from mtg_arena_collection.game_files import CardDatabaseNotFound, find_card_database


class FindCardDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.raw_downloads_directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_file(self, name: str, modified_at: int) -> Path:
        path = self.raw_downloads_directory / name
        path.write_bytes(b"")
        os.utime(path, (modified_at, modified_at))
        return path

    def test_picks_the_most_recently_downloaded_database(self):
        self.create_file("Raw_CardDatabase_old.mtga", modified_at=1_000)
        newest = self.create_file("Raw_CardDatabase_new.mtga", modified_at=2_000)
        self.assertEqual(find_card_database(self.raw_downloads_directory), newest)

    def test_ignores_other_game_downloads(self):
        self.create_file("Raw_ClientLocalization_x.mtga", modified_at=3_000)
        database = self.create_file("Raw_CardDatabase_x.mtga", modified_at=1_000)
        self.assertEqual(find_card_database(self.raw_downloads_directory), database)

    def test_explains_what_to_do_when_missing(self):
        with self.assertRaisesRegex(CardDatabaseNotFound, "Open MTG Arena"):
            find_card_database(self.raw_downloads_directory)


if __name__ == "__main__":
    unittest.main()
