import json
import tempfile
import unittest
from pathlib import Path

from mtg_arena_collection.meta_lessons import (
    ROLE_TAGS,
    FormatLessons,
    GroupSummary,
    LandCountFit,
    PlayedTogether,
)
from mtg_arena_collection.meta_lessons_report import (
    format_meta_lessons_report,
    meta_lessons_as_json,
    write_meta_lessons,
)

GENERATED_AT = "2026-11-09T20:00:00-03:00"


def make_summary(label, deck_count=3, weight_share=0.5):
    return GroupSummary(
        label=label, deck_count=deck_count, weight_share=weight_share, land_count=22.5,
        creature_count=20.0, average_mana_value=2.25, curve=(10.2, 12.0, 8.0, 4.0, 2.0, 1.0),
        role_counts={tag: 1.0 for tag in ROLE_TAGS},
        most_played_cards=(("Lightning Strike", 1.0), ("Goblin Guide", 0.75)),
    )


def make_lessons(format_name="Standard", unknown_card_names=()):
    return FormatLessons(
        format_name=format_name, main_deck_size=60, land_count_fit=LandCountFit(20.0, 1.0123456),
        all_decks=make_summary("todos", deck_count=67, weight_share=1.0),
        by_speed=(make_summary("rapido"),),
        by_mechanic=(make_summary("ganho-de-vida"),),
        mechanics_played_together=(PlayedTogether("ganho-de-vida", "ganho-de-vida-recompensa", 8, 3.6),),
        cards_played_together=(PlayedTogether("Aerial Boost", "Bushwhack", 3, 5.0),
                               PlayedTogether("Cut Down", "Duress", 7, 2.1)),
        card_presence={"Lightning Strike": 0.5},
        unknown_card_names=unknown_card_names,
    )


class FormatMetaLessonsReportTests(unittest.TestCase):
    def setUp(self):
        self.report = format_meta_lessons_report([make_lessons()], GENERATED_AT)

    def test_each_format_has_a_section_with_its_deck_count(self):
        self.assertIn("## Standard (67 decks)", self.report)

    def test_historic_brawl_gets_its_spaced_name(self):
        report = format_meta_lessons_report([make_lessons("HistoricBrawl")], GENERATED_AT)
        self.assertIn("## Historic Brawl (67 decks)", report)

    def test_land_count_line_uses_decimal_commas_and_gives_examples(self):
        self.assertIn("terrenos ≈ 20,0 + 1,01 × custo médio das mágicas", self.report)
        self.assertIn("custo médio 1,5 → 21,5 terrenos", self.report)

    def test_speed_table_starts_with_every_deck(self):
        self.assertIn(
            "| Todos | 67 | 100% | 22,5 | 20,0 | 2,25 | 10/12/8/4/2/1 | 1,0 | 1,0 | 1,0 | 1,0 |\n"
            "| Rápido (custo médio abaixo de 2) | 3 | 50% |",
            self.report,
        )

    def test_mechanic_table_lists_each_group(self):
        self.assertIn("| ganho-de-vida | 3 | 50% | 22,5 |", self.report)

    def test_most_played_cards_come_with_the_share_of_decks(self):
        self.assertIn("- **ganho-de-vida**: Lightning Strike (100%), Goblin Guide (75%)", self.report)

    def test_mechanic_pairs_show_how_many_times_more_than_chance(self):
        self.assertIn("| ganho-de-vida | ganho-de-vida-recompensa | 8 | 3,6 |", self.report)

    def test_card_pairs_show_the_most_frequent_first(self):
        self.assertLess(
            self.report.index("| Cut Down | Duress | 7 | 2,1 |"),
            self.report.index("| Aerial Boost | Bushwhack | 3 | 5,0 |"),
        )

    def test_cards_missing_from_the_catalog_are_named(self):
        report = format_meta_lessons_report([make_lessons(unknown_card_names=("Mystery Card",))], GENERATED_AT)
        self.assertIn("Mystery Card", report)

    def test_no_note_about_missing_cards_when_every_card_was_found(self):
        self.assertNotIn("fora do catálogo", self.report)


class MetaLessonsAsJsonTests(unittest.TestCase):
    def test_keeps_every_format_with_rounded_numbers(self):
        data = json.loads(meta_lessons_as_json([make_lessons()], GENERATED_AT))
        [standard] = data["formats"]
        self.assertEqual(
            (data["generated_at"], standard["format_name"], standard["land_count_fit"]["slope"]),
            (GENERATED_AT, "Standard", 1.012),
        )


class WriteMetaLessonsTests(unittest.TestCase):
    def test_writes_the_report_and_the_json_without_leftovers(self):
        with tempfile.TemporaryDirectory() as directory:
            output_directory = Path(directory) / "meta-lessons"
            report_path, json_path = write_meta_lessons([make_lessons()], output_directory, GENERATED_AT)
            self.assertEqual(
                sorted(path.name for path in output_directory.iterdir()),
                sorted([report_path.name, json_path.name]),
            )


if __name__ == "__main__":
    unittest.main()
