import unittest

from card_fixture import make_card
from mtg_arena_collection.card_mechanics import MechanicTagger
from mtg_arena_collection.card_pool import PoolCard
from mtg_arena_collection.deck_designer import DesignedDeck, Engine
from mtg_arena_collection.designed_deck_summary import describe_designed_deck
from mtg_arena_collection.meta_lessons import ROLE_TAGS, GroupSummary

PLAINS = make_card("Plains", "Basic Land — Plains", arena_id=1, rarity="basic")
HEALERS_HAWK = make_card(
    "Healer's Hawk", "Creature — Bird", "Flying\nLifelink", mana_cost="{W}", arena_id=10, mana_value=1,
    colors="W")
BANISHING_LIGHT = make_card(
    "Banishing Light", "Enchantment",
    "When this enchantment enters, exile target nonland permanent an opponent controls until this "
    "enchantment leaves the battlefield.", mana_cost="{2}{W}", arena_id=11, mana_value=3, colors="W")
LINVALA = make_card(
    "Linvala, Shield of Sea Gate", "Legendary Creature — Angel Wizard", "Flying", mana_cost="{1}{W}{U}",
    arena_id=12, mana_value=3, colors="WU")
CATALOG = {card.arena_id: card for card in (PLAINS, HEALERS_HAWK, BANISHING_LIGHT, LINVALA)}
TAGGER = MechanicTagger.from_catalog(CATALOG)
DECK_PATH = "decks/standard/mono-white/ganho-de-vida/mono-white-ganho-de-vida-designer.txt"


def make_reference(label="ganho-de-vida", deck_count=20):
    return GroupSummary(
        label=label, deck_count=deck_count, weight_share=0.28, land_count=22.2, creature_count=18.6,
        average_mana_value=2.31, curve=(11.0, 13.0, 8.0, 4.0, 1.0, 1.0),
        role_counts={tag: 0.5 for tag in ROLE_TAGS}, most_played_cards=(),
    )


def make_designed_deck(reference=None, unfilled_slots=0, commander=None):
    return DesignedDeck(
        format_name="Standard", engine=Engine("ganho-de-vida", frozenset("W")),
        reference=reference or make_reference(), commander=commander,
        nonland_cards=((PoolCard(HEALERS_HAWK, 4), 4), (PoolCard(BANISHING_LIGHT, 2), 2)),
        lands=((PoolCard(PLAINS, 0), 4),), unfilled_slots=unfilled_slots,
    )


def describe(deck):
    return describe_designed_deck(deck, DECK_PATH, CATALOG, TAGGER)


class DescribeDesignedDeckTests(unittest.TestCase):
    def test_starts_with_the_name_and_the_file(self):
        self.assertTrue(describe(make_designed_deck()).startswith(f"Mono White Ganho de vida (designer): {DECK_PATH}\n"))

    def test_names_the_engine_and_the_meta_decks_it_was_compared_with(self):
        self.assertIn(
            "Motor: ganho-de-vida, com 4 cópias de cartas do motor. "
            "Comparado com os 20 decks do meta construídos em volta de ganho-de-vida.",
            describe(make_designed_deck()),
        )

    def test_without_a_meta_group_it_compares_with_every_deck_of_the_format(self):
        description = describe(make_designed_deck(reference=make_reference("todos", deck_count=67)))
        self.assertIn("Comparado com todos os 67 decks do formato.", description)

    def test_counts_come_next_to_the_meta_numbers(self):
        self.assertIn(
            "Terrenos 4 (meta 22,2) · Criaturas 4 (meta 18,6) · Custo médio 1,67 (meta 2,31)",
            describe(make_designed_deck()),
        )

    def test_curve_comes_next_to_the_meta_curve(self):
        self.assertIn("Curva 1/2/3/4/5/6+: 4/0/2/0/0/0 (meta 11/13/8/4/1/1)", describe(make_designed_deck()))

    def test_roles_come_next_to_the_meta_roles(self):
        self.assertIn("Remoção 2 (meta 0,5) · Compra 0 (meta 0,5)", describe(make_designed_deck()))

    def test_slots_without_cards_are_reported(self):
        self.assertIn("3 vagas sem carta viraram terrenos básicos", describe(make_designed_deck(unfilled_slots=3)))

    def test_brawl_decks_name_the_commander(self):
        description = describe(make_designed_deck(commander=PoolCard(LINVALA, 1)))
        self.assertIn("Comandante: Linvala, Shield of Sea Gate.", description)


if __name__ == "__main__":
    unittest.main()
