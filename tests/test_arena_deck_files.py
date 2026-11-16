import tempfile
import unittest
from pathlib import Path

from card_database_fixture import create_card_database
from mtg_arena_collection.arena_deck_files import (
    ArenaDecklist,
    DeckCard,
    DeckFolder,
    color_combination_name,
    deck_file_path,
    decklist_colors,
    format_arena_decklist,
    index_cards_by_name,
    parse_arena_decklist,
    save_arena_deck,
)
from mtg_arena_collection.card_catalog import load_card_catalog

SHOCK = DeckCard(4, "Shock", "M19", "156")
MOUNTAIN = DeckCard(20, "Mountain", "KTK", "256")
KRENKO = DeckCard(1, "Krenko, Mob Boss", "FDN", "204")
LURRUS = DeckCard(1, "Lurrus of the Dream-Den", "IKO", "226")
ABRADE = DeckCard(2, "Abrade", "FDN", "188")


def lines_of(decklist):
    return format_arena_decklist(decklist).split("\n")


class FormatArenaDecklistTests(unittest.TestCase):
    def test_starts_with_the_deck_name_in_the_about_section(self):
        decklist = ArenaDecklist("Mono Red Burn", main=(SHOCK,))
        self.assertEqual(lines_of(decklist)[:2], ["About", "Name Mono Red Burn"])

    def test_card_line_has_quantity_name_set_code_and_collector_number(self):
        self.assertIn("4 Shock (M19) 156", lines_of(ArenaDecklist("Burn", main=(SHOCK,))))

    def test_card_without_a_printing_has_only_quantity_and_name(self):
        self.assertIn("4 Shock", lines_of(ArenaDecklist("Burn", main=(DeckCard(4, "Shock"),))))

    def test_collector_number_loses_leading_zeros(self):
        decklist = ArenaDecklist("Burn", main=(DeckCard(4, "Shock", "M19", "007"),))
        self.assertIn("4 Shock (M19) 7", lines_of(decklist))

    def test_printing_with_letters_in_the_collector_number_is_left_out(self):
        decklist = ArenaDecklist("Burn", main=(DeckCard(4, "Shock", "M19", "156a"),))
        self.assertIn("4 Shock", lines_of(decklist))

    def test_collector_number_zero_means_unknown_and_is_left_out(self):
        decklist = ArenaDecklist("Goblins", main=(DeckCard(1, "Splinter Twin", "SPG", "0"),))
        self.assertIn("1 Splinter Twin", lines_of(decklist))

    def test_sections_come_in_arena_order_separated_by_blank_lines(self):
        decklist = ArenaDecklist(
            "Krenko Goblins", main=(SHOCK, MOUNTAIN), sideboard=(ABRADE,),
            commander=KRENKO, companion=LURRUS,
        )
        self.assertEqual(
            format_arena_decklist(decklist),
            "About\nName Krenko Goblins\n\n"
            "Commander\n1 Krenko, Mob Boss (FDN) 204\n\n"
            "Companion\n1 Lurrus of the Dream-Den (IKO) 226\n\n"
            "Deck\n4 Shock (M19) 156\n20 Mountain (KTK) 256\n\n"
            "Sideboard\n2 Abrade (FDN) 188\n1 Lurrus of the Dream-Den (IKO) 226\n",
        )

    def test_deck_without_extra_sections_has_only_about_and_deck(self):
        self.assertEqual(
            format_arena_decklist(ArenaDecklist("Burn", main=(SHOCK,))),
            "About\nName Burn\n\nDeck\n4 Shock (M19) 156\n",
        )

    def test_companion_already_in_the_sideboard_is_not_listed_twice(self):
        decklist = ArenaDecklist("Burn", main=(SHOCK,), sideboard=(LURRUS,), companion=LURRUS)
        self.assertEqual(lines_of(decklist).count("1 Lurrus of the Dream-Den (IKO) 226"), 2)


class ParseArenaDecklistTests(unittest.TestCase):
    def test_reads_back_what_was_written(self):
        decklist = ArenaDecklist(
            "Krenko Goblins", main=(SHOCK, MOUNTAIN), sideboard=(ABRADE,), commander=KRENKO,
        )
        self.assertEqual(parse_arena_decklist(format_arena_decklist(decklist)), decklist)

    def test_reads_lines_without_a_printing(self):
        parsed = parse_arena_decklist("Deck\n4 Shock\n")
        self.assertEqual(parsed.main, (DeckCard(4, "Shock"),))

    def test_list_without_a_name_gets_an_empty_name(self):
        self.assertEqual(parse_arena_decklist("Deck\n4 Shock\n").name, "")

    def test_card_names_with_parentheses_keep_them(self):
        parsed = parse_arena_decklist("Deck\n1 Sword of Body and Mind (Promo)\n")
        self.assertEqual(parsed.main, (DeckCard(1, "Sword of Body and Mind (Promo)"),))


class ColorCombinationNameTests(unittest.TestCase):
    def test_single_color_is_mono(self):
        self.assertEqual(color_combination_name("R"), "mono-red")

    def test_two_colors_use_the_guild_name(self):
        self.assertEqual(
            [color_combination_name(colors) for colors in ("WU", "UR", "RG", "WR", "BG", "UG")],
            ["azorius", "izzet", "gruul", "boros", "golgari", "simic"],
        )

    def test_order_of_the_letters_does_not_matter(self):
        self.assertEqual(color_combination_name("RU"), "izzet")

    def test_three_colors_use_the_shard_or_wedge_name(self):
        self.assertEqual(
            [color_combination_name(colors) for colors in ("WUB", "BRG", "WRG", "URG", "WBR")],
            ["esper", "jund", "naya", "temur", "mardu"],
        )

    def test_four_colors_name_the_missing_one(self):
        self.assertEqual(color_combination_name("UBRG"), "four-color-no-white")

    def test_all_five_and_none(self):
        self.assertEqual(
            (color_combination_name("WUBRG"), color_combination_name("")), ("five-color", "colorless")
        )


class DecklistColorsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog_directory = tempfile.TemporaryDirectory()
        database_path = create_card_database(
            Path(cls.catalog_directory.name) / "Raw_CardDatabase_test.mtga"
        )
        cls.cards_by_name = index_cards_by_name(load_card_catalog(database_path))

    @classmethod
    def tearDownClass(cls):
        cls.catalog_directory.cleanup()

    def colors_of(self, *names, commander=None):
        return decklist_colors(
            ArenaDecklist("Deck", main=tuple(DeckCard(1, name) for name in names),
                          commander=DeckCard(1, commander) if commander else None),
            self.cards_by_name,
        )

    def test_colors_come_from_the_spells_in_wubrg_order(self):
        self.assertEqual(self.colors_of("A-Simic Test Card", "Captain Jean-Luc Picard"), "WUG")

    def test_basic_lands_add_no_color(self):
        self.assertEqual(self.colors_of("Release to the Wind", "Island"), "U")

    def test_cards_missing_from_the_catalog_are_ignored(self):
        self.assertEqual(self.colors_of("Release to the Wind", "Card From The Future"), "U")

    def test_commander_color_identity_decides_for_brawl(self):
        self.assertEqual(
            self.colors_of("Island", commander="Captain Jean-Luc Picard"), "W"
        )


class DeckFilePathTests(unittest.TestCase):
    def test_path_is_format_colors_archetype_and_deck_name(self):
        path = deck_file_path(
            Path("decks"), "Krenko Goblins", DeckFolder("Historic Brawl", "R", "Goblins")
        )
        self.assertEqual(path, Path("decks/historic-brawl/mono-red/goblins/krenko-goblins.txt"))

    def test_folder_names_lose_accents_and_punctuation(self):
        path = deck_file_path(Path("decks"), "Izzet: Mágicas!", DeckFolder("Standard", "UR", "Mágicas"))
        self.assertEqual(path, Path("decks/standard/izzet/magicas/izzet-magicas.txt"))

    def test_format_written_as_one_word_is_split(self):
        path = deck_file_path(Path("decks"), "Krenko", DeckFolder("HistoricBrawl", "R", "Goblins"))
        self.assertEqual(path.parts[1], "historic-brawl")


class SaveArenaDeckTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.decks_directory = Path(self.temporary_directory.name) / "decks"
        self.folder = DeckFolder("Standard", "R", "Burn")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_writes_the_decklist_in_its_folder(self):
        decklist = ArenaDecklist("Mono Red Burn", main=(SHOCK, MOUNTAIN))
        path = save_arena_deck(self.decks_directory, decklist, self.folder)
        self.assertEqual(path.read_text(encoding="utf-8"), format_arena_decklist(decklist))

    def test_saving_again_replaces_the_file(self):
        save_arena_deck(self.decks_directory, ArenaDecklist("Mono Red Burn", main=(SHOCK,)), self.folder)
        newer = ArenaDecklist("Mono Red Burn", main=(SHOCK, MOUNTAIN))
        path = save_arena_deck(self.decks_directory, newer, self.folder)
        self.assertEqual(parse_arena_decklist(path.read_text(encoding="utf-8")), newer)

    def test_leaves_no_temporary_file_behind(self):
        path = save_arena_deck(self.decks_directory, ArenaDecklist("Burn", main=(SHOCK,)), self.folder)
        self.assertEqual([file.name for file in path.parent.iterdir()], [path.name])


if __name__ == "__main__":
    unittest.main()
