import tempfile
import unittest
from pathlib import Path

from card_database_fixture import (
    ISLAND_ARENA_ID,
    PICARD_ARENA_ID,
    RELEASE_TO_THE_WIND_ARENA_ID,
    SIMIC_GOLD_CARD_ARENA_ID,
    create_card_database,
)
from mtg_arena_collection.card_catalog import load_card_catalog


class LoadCardCatalogTests(unittest.TestCase):
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

    def test_loads_every_card(self):
        self.assertEqual(len(self.catalog), 4)

    def test_name_has_no_markup(self):
        self.assertEqual(self.catalog[PICARD_ARENA_ID].name, "Captain Jean-Luc Picard")

    def test_portuguese_name_has_no_markup(self):
        self.assertEqual(
            self.catalog[PICARD_ARENA_ID].portuguese_name, "Capitão Jean-Luc Picard"
        )

    def test_missing_portuguese_name_is_empty(self):
        self.assertEqual(self.catalog[SIMIC_GOLD_CARD_ARENA_ID].portuguese_name, "")

    def test_rebalanced_card_name_has_the_alchemy_prefix(self):
        self.assertEqual(self.catalog[SIMIC_GOLD_CARD_ARENA_ID].name, "A-Simic Test Card")

    def test_original_card_name_has_no_alchemy_prefix(self):
        self.assertEqual(self.catalog[RELEASE_TO_THE_WIND_ARENA_ID].name, "Release to the Wind")

    def test_type_line_joins_types_and_subtypes(self):
        self.assertEqual(
            self.catalog[PICARD_ARENA_ID].type_line, "Legendary Creature — Human Officer"
        )

    def test_type_line_without_subtypes(self):
        self.assertEqual(self.catalog[RELEASE_TO_THE_WIND_ARENA_ID].type_line, "Instant")

    def test_rarity_name(self):
        self.assertEqual(self.catalog[PICARD_ARENA_ID].rarity, "mythic")

    def test_basic_land_rarity(self):
        self.assertEqual(self.catalog[ISLAND_ARENA_ID].rarity, "basic")

    def test_colors_use_wubrg_letters(self):
        self.assertEqual(self.catalog[SIMIC_GOLD_CARD_ARENA_ID].colors, "UG")

    def test_colorless_card_has_no_colors(self):
        self.assertEqual(self.catalog[ISLAND_ARENA_ID].colors, "")

    def test_mana_cost_uses_brace_symbols(self):
        self.assertEqual(self.catalog[SIMIC_GOLD_CARD_ARENA_ID].mana_cost, "{1}{U/G}{U/G}")

    def test_mana_value(self):
        self.assertEqual(self.catalog[SIMIC_GOLD_CARD_ARENA_ID].mana_value, 3)

    def test_set_and_collector_number(self):
        card = self.catalog[PICARD_ARENA_ID]
        self.assertEqual((card.set_code, card.collector_number), ("TRK", "7"))

    def test_power_and_toughness(self):
        card = self.catalog[PICARD_ARENA_ID]
        self.assertEqual((card.power, card.toughness), ("2", "3"))

    def test_rules_text_lists_each_ability_on_its_own_line(self):
        self.assertEqual(
            self.catalog[PICARD_ARENA_ID].rules_text,
            "Other creatures you control get +1/+1.\n"
            "{1}, {T}: Captain Jean-Luc Picard deals 1 damage to any target.",
        )

    def test_rules_text_keeps_reminder_text_without_markup(self):
        self.assertEqual(
            self.catalog[RELEASE_TO_THE_WIND_ARENA_ID].rules_text,
            "Exile target nonland permanent. (You may cast it this turn.)",
        )

    def test_digital_flags(self):
        card = self.catalog[SIMIC_GOLD_CARD_ARENA_ID]
        self.assertEqual((card.is_digital_only, card.is_rebalanced), (True, True))

    def test_digital_release_set(self):
        self.assertEqual(self.catalog[SIMIC_GOLD_CARD_ARENA_ID].digital_release_set, "Y24-OTJ")


if __name__ == "__main__":
    unittest.main()
