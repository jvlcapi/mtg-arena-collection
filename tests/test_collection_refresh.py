import unittest

from mtg_arena_collection.collection_changes import CollectionUpdate
from mtg_arena_collection.collection_refresh import refresh_collection
from mtg_arena_collection.mtga_mcp_commands import MtgaMcpCommandFailed


class RefreshCollectionTests(unittest.TestCase):
    def setUp(self):
        self.steps = []
        self.update = CollectionUpdate(csv_written=False, is_first_csv=False)

    def run_capture(self):
        self.steps.append("capture")

    def update_csv(self):
        self.steps.append("update")
        return self.update

    def test_captures_the_game_logs_before_updating_the_csv(self):
        refresh_collection(self.run_capture, self.update_csv)
        self.assertEqual(self.steps, ["capture", "update"])

    def test_returns_what_the_csv_update_did(self):
        self.assertIs(refresh_collection(self.run_capture, self.update_csv), self.update)

    def test_failed_capture_leaves_the_csv_alone(self):
        def failing_capture():
            raise MtgaMcpCommandFailed("capture failed")

        with self.assertRaises(MtgaMcpCommandFailed):
            refresh_collection(failing_capture, self.update_csv)
        self.assertEqual(self.steps, [])


if __name__ == "__main__":
    unittest.main()
