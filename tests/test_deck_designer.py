import unittest

from card_fixture import make_card
from mtg_arena_collection.arena_deck_files import DeckCard
from mtg_arena_collection.card_mechanics import MechanicTagger
from mtg_arena_collection.card_pool import PoolCard
from mtg_arena_collection.deck_designer import (
    DeckNotDesigned,
    Engine,
    archetype_title,
    best_engine_for_commander,
    build_mana_base,
    design_deck,
    designed_deck_name,
    engine_card_copies,
    suggest_engines,
    to_arena_decklist,
)
from mtg_arena_collection.meta_lessons import (
    ROLE_TAGS,
    FormatLessons,
    GroupSummary,
    LandCountFit,
    PlayedTogether,
)

PLAINS = make_card("Plains", "Basic Land — Plains", arena_id=1, rarity="basic")
MOUNTAIN = make_card("Mountain", "Basic Land — Mountain", arena_id=2, rarity="basic")
INSPIRING_VANTAGE = make_card(
    "Inspiring Vantage", "Land", "{T}: Add {R} or {W}.", arena_id=3, color_identity="RW")
WATERY_GRAVE = make_card(
    "Watery Grave", "Land — Island Swamp", "{T}: Add {U} or {B}.", arena_id=4, color_identity="UB")
MANA_CONFLUENCE = make_card(
    "Mana Confluence", "Land", "{T}, Pay 1 life: Add one mana of any color.", arena_id=5)


def white_card(name, type_line, rules_text="", mana_value=1, arena_id=0):
    mana_cost = "{W}" if mana_value == 1 else f"{{{mana_value - 1}}}{{W}}"
    return make_card(name, type_line, rules_text, mana_cost=mana_cost, arena_id=arena_id,
                     mana_value=mana_value, colors="W")


HEALERS_HAWK = white_card("Healer's Hawk", "Creature — Bird", "Flying\nLifelink", arena_id=10)
SOUL_WARDEN = white_card(
    "Soul Warden", "Creature — Human Cleric", "Whenever another creature enters, you gain 1 life.",
    arena_id=11)
AJANIS_PRIDEMATE = white_card(
    "Ajani's Pridemate", "Creature — Cat Soldier",
    "Whenever you gain life, put a +1/+1 counter on this creature.", mana_value=2, arena_id=12)
SAVANNAH_LIONS = white_card("Savannah Lions", "Creature — Cat", arena_id=13)
BANISHING_LIGHT = white_card(
    "Banishing Light", "Enchantment",
    "When this enchantment enters, exile target nonland permanent an opponent controls until this "
    "enchantment leaves the battlefield.", mana_value=3, arena_id=14)
ALPHA_SQUIRE = white_card("Alpha Squire", "Creature — Human Soldier", arena_id=15)
BETA_SQUIRE = white_card("Beta Squire", "Creature — Human Soldier", arena_id=16)
ANCIENT_WURM = white_card("Ancient Wurm", "Creature — Wurm", mana_value=6, arena_id=17)
ZEALOUS_BEAR = white_card("Zealous Bear", "Creature — Bear", mana_value=2, arena_id=18)
GOBLIN_GUIDE = make_card(
    "Goblin Guide", "Creature — Goblin Scout", "Haste", mana_cost="{R}", arena_id=20, mana_value=1,
    colors="R")
KRENKO = make_card(
    "Krenko, Mob Boss", "Legendary Creature — Goblin Warrior",
    "{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control.",
    mana_cost="{2}{R}{R}", arena_id=21, mana_value=4, colors="R")
GOBLIN_CHIEFTAIN = make_card(
    "Goblin Chieftain", "Creature — Goblin",
    "Other Goblin creatures you control get +1/+1 and have haste.",
    mana_cost="{1}{R}{R}", arena_id=22, mana_value=3, colors="R")
GOBLIN_RECRUITS = [
    make_card(f"Goblin Recruit {number}", "Creature — Goblin", mana_cost="{R}", arena_id=100 + number,
              mana_value=1, colors="R")
    for number in range(12)
]
EVERY_CARD = [
    PLAINS, MOUNTAIN, INSPIRING_VANTAGE, WATERY_GRAVE, MANA_CONFLUENCE, HEALERS_HAWK, SOUL_WARDEN,
    AJANIS_PRIDEMATE, SAVANNAH_LIONS, BANISHING_LIGHT, ALPHA_SQUIRE, BETA_SQUIRE, ANCIENT_WURM,
    ZEALOUS_BEAR, GOBLIN_GUIDE, KRENKO, GOBLIN_CHIEFTAIN, *GOBLIN_RECRUITS,
]
TAGGER = MechanicTagger.from_catalog({card.arena_id: card for card in EVERY_CARD})
LIFEGAIN_IN_WHITE = Engine("ganho-de-vida", frozenset("W"))


def make_pool(*cards_and_copies):
    pool = {card.name: PoolCard(card, 0) for card in (PLAINS, MOUNTAIN)}
    pool.update({card.name: PoolCard(card, copies) for card, copies in cards_and_copies})
    return pool


def make_reference(label="todos", land_count=4.0, creature_count=6.0, curve=(3.0, 3.0, 0.0, 0.0, 0.0, 0.0),
                   role_counts=None):
    return GroupSummary(
        label=label, deck_count=10, weight_share=0.3, land_count=land_count,
        creature_count=creature_count, average_mana_value=1.5, curve=curve,
        role_counts={tag: 0.0 for tag in ROLE_TAGS} | (role_counts or {}), most_played_cards=(),
    )


def make_lessons(format_name="Standard", main_deck_size=10, all_decks=None, by_mechanic=(),
                 card_pairs=(), card_presence=None):
    return FormatLessons(
        format_name=format_name, main_deck_size=main_deck_size, land_count_fit=LandCountFit(4.0, 0.0),
        all_decks=all_decks or make_reference(), by_speed=(), by_mechanic=tuple(by_mechanic),
        mechanics_played_together=(), cards_played_together=tuple(card_pairs),
        card_presence=card_presence or {}, unknown_card_names=(),
    )


def nonland_copies(deck):
    return {pool_card.name: copies for pool_card, copies in deck.nonland_cards}


def land_copies(deck):
    return {pool_card.name: copies for pool_card, copies in deck.lands}


class DesignDeckTests(unittest.TestCase):
    def test_engine_and_partner_cards_come_before_plain_ones(self):
        pool = make_pool((HEALERS_HAWK, 4), (AJANIS_PRIDEMATE, 4), (SAVANNAH_LIONS, 4))
        deck = design_deck(pool, make_lessons(), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(set(nonland_copies(deck)), {"Healer's Hawk", "Ajani's Pridemate"})

    def test_cards_outside_the_engine_colors_are_left_out(self):
        pool = make_pool((HEALERS_HAWK, 4), (SAVANNAH_LIONS, 4), (GOBLIN_GUIDE, 4))
        lessons = make_lessons(card_presence={"Goblin Guide": 1.0})
        deck = design_deck(pool, lessons, LIFEGAIN_IN_WHITE, TAGGER)
        self.assertNotIn("Goblin Guide", nonland_copies(deck))

    def test_never_more_copies_than_owned_or_four(self):
        pool = make_pool((HEALERS_HAWK, 2), (SAVANNAH_LIONS, 9))
        deck = design_deck(pool, make_lessons(), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(nonland_copies(deck), {"Healer's Hawk": 2, "Savannah Lions": 4})

    def test_required_cards_are_always_in(self):
        pool = make_pool((HEALERS_HAWK, 4), (SOUL_WARDEN, 4), (SAVANNAH_LIONS, 2))
        engine = Engine("ganho-de-vida", frozenset("W"), required_cards=("Savannah Lions",))
        self.assertEqual(nonland_copies(design_deck(pool, make_lessons(), engine, TAGGER))["Savannah Lions"], 2)

    def test_required_card_outside_the_pool_is_refused(self):
        engine = Engine("ganho-de-vida", frozenset("W"), required_cards=("Black Lotus",))
        with self.assertRaisesRegex(DeckNotDesigned, "Black Lotus"):
            design_deck(make_pool((HEALERS_HAWK, 4)), make_lessons(), engine, TAGGER)

    def test_required_card_outside_the_deck_colors_is_refused(self):
        engine = Engine("ganho-de-vida", frozenset("W"), required_cards=("Goblin Guide",))
        with self.assertRaisesRegex(DeckNotDesigned, "Goblin Guide"):
            design_deck(make_pool((HEALERS_HAWK, 4), (GOBLIN_GUIDE, 4)), make_lessons(), engine, TAGGER)

    def test_engine_card_copies_count_the_mechanic_and_its_partners(self):
        pool = make_pool((HEALERS_HAWK, 2), (AJANIS_PRIDEMATE, 1), (SAVANNAH_LIONS, 4))
        deck = design_deck(pool, make_lessons(), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(engine_card_copies(deck, TAGGER), 3)

    def test_land_count_follows_the_reference(self):
        pool = make_pool((HEALERS_HAWK, 4), (SOUL_WARDEN, 4), (SAVANNAH_LIONS, 4))
        deck = design_deck(pool, make_lessons(), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual((sum(land_copies(deck).values()), sum(nonland_copies(deck).values())), (4, 6))

    def test_the_meta_group_of_the_engine_mechanic_is_the_reference(self):
        lifegain_group = make_reference("ganho-de-vida", land_count=3.0, curve=(4.0, 3.0, 0.0, 0.0, 0.0, 0.0))
        pool = make_pool((HEALERS_HAWK, 4), (SOUL_WARDEN, 4), (SAVANNAH_LIONS, 4))
        deck = design_deck(pool, make_lessons(by_mechanic=[lifegain_group]), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual((deck.reference.label, sum(land_copies(deck).values())), ("ganho-de-vida", 3))

    def test_roles_below_their_target_are_filled(self):
        reference = make_reference(creature_count=4.0, curve=(4.0, 0.0, 2.0, 0.0, 0.0, 0.0),
                                   role_counts={"remocao": 2.0})
        pool = make_pool((HEALERS_HAWK, 4), (SOUL_WARDEN, 4), (AJANIS_PRIDEMATE, 4), (BANISHING_LIGHT, 2))
        deck = design_deck(pool, make_lessons(all_decks=reference), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(nonland_copies(deck).get("Banishing Light"), 2)

    def test_mana_values_below_the_target_curve_come_first(self):
        reference = make_reference(curve=(0.0, 6.0, 0.0, 0.0, 0.0, 0.0))
        pool = make_pool((ANCIENT_WURM, 4), (ZEALOUS_BEAR, 4))
        deck = design_deck(pool, make_lessons(all_decks=reference), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(nonland_copies(deck), {"Zealous Bear": 4, "Ancient Wurm": 2})

    def test_cards_the_meta_plays_more_come_first(self):
        pool = make_pool((ALPHA_SQUIRE, 4), (BETA_SQUIRE, 4))
        deck = design_deck(pool, make_lessons(card_presence={"Beta Squire": 0.5}), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(nonland_copies(deck), {"Beta Squire": 4, "Alpha Squire": 2})

    def test_cards_the_meta_plays_with_the_ones_already_in_come_first(self):
        pool = make_pool((HEALERS_HAWK, 2), (ALPHA_SQUIRE, 4), (BETA_SQUIRE, 4))
        lessons = make_lessons(card_pairs=[PlayedTogether("Beta Squire", "Healer's Hawk", 3, 2.5)])
        deck = design_deck(pool, lessons, LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(nonland_copies(deck), {"Healer's Hawk": 2, "Beta Squire": 4})

    def test_slots_the_collection_cannot_fill_become_basic_lands(self):
        deck = design_deck(make_pool((HEALERS_HAWK, 2)), make_lessons(), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual((deck.unfilled_slots, land_copies(deck)), (4, {"Plains": 8}))


class DesignBrawlDeckTests(unittest.TestCase):
    def setUp(self):
        self.pool = make_pool((KRENKO, 1), (GOBLIN_CHIEFTAIN, 1), (HEALERS_HAWK, 1),
                              *[(recruit, 3) for recruit in GOBLIN_RECRUITS])
        self.lessons = make_lessons(format_name="HistoricBrawl")
        engine = Engine("tribo:goblin", frozenset("RW"), commander="Krenko, Mob Boss")
        self.deck = design_deck(self.pool, self.lessons, engine, TAGGER)

    def test_commander_stays_apart_from_the_main_deck(self):
        self.assertEqual(
            (self.deck.commander.name, "Krenko, Mob Boss" in nonland_copies(self.deck)),
            ("Krenko, Mob Boss", False),
        )

    def test_brawl_decks_take_one_copy_of_each_card(self):
        self.assertEqual(set(nonland_copies(self.deck).values()), {1})

    def test_colors_come_from_the_commander(self):
        self.assertEqual(
            (self.deck.engine.colors, "Healer's Hawk" in nonland_copies(self.deck)), (frozenset("R"), False)
        )

    def test_commander_outside_the_pool_is_refused(self):
        engine = Engine("fichas", frozenset("R"), commander="Krenko, Tin Street Kingpin")
        with self.assertRaisesRegex(DeckNotDesigned, "Tin Street"):
            design_deck(self.pool, self.lessons, engine, TAGGER)


class BuildManaBaseTests(unittest.TestCase):
    def test_basic_lands_split_by_the_colored_mana_symbols(self):
        double_white = make_card("Double White", "Creature — Human", mana_cost="{W}{W}", colors="W")
        single_red = make_card("Single Red", "Creature — Human", mana_cost="{R}", colors="R")
        nonland_cards = ((PoolCard(double_white, 4), 4), (PoolCard(single_red, 2), 2))
        lands = build_mana_base(make_pool(), frozenset("RW"), 10, nonland_cards, "Standard")
        self.assertEqual({card.name: copies for card, copies in lands}, {"Plains": 8, "Mountain": 2})

    def test_lands_making_both_colors_come_first_up_to_half(self):
        pool = make_pool((INSPIRING_VANTAGE, 4), (WATERY_GRAVE, 4))
        nonland_cards = ((PoolCard(HEALERS_HAWK, 4), 4), (PoolCard(GOBLIN_GUIDE, 4), 4))
        lands = build_mana_base(pool, frozenset("RW"), 6, nonland_cards, "Standard")
        self.assertEqual(
            {card.name: copies for card, copies in lands},
            {"Inspiring Vantage": 3, "Plains": 2, "Mountain": 1},
        )

    def test_lands_making_any_color_fix_too(self):
        pool = make_pool((MANA_CONFLUENCE, 2))
        nonland_cards = ((PoolCard(HEALERS_HAWK, 4), 4), (PoolCard(GOBLIN_GUIDE, 4), 4))
        lands = build_mana_base(pool, frozenset("RW"), 10, nonland_cards, "Standard")
        self.assertEqual({card.name: copies for card, copies in lands}["Mana Confluence"], 2)

    def test_one_color_decks_use_basic_lands_only(self):
        pool = make_pool((INSPIRING_VANTAGE, 4))
        lands = build_mana_base(pool, frozenset("W"), 10, ((PoolCard(HEALERS_HAWK, 4), 4),), "Standard")
        self.assertEqual({card.name: copies for card, copies in lands}, {"Plains": 10})


class SuggestEnginesTests(unittest.TestCase):
    def test_suggests_the_mechanic_and_colors_with_the_most_owned_cards_first(self):
        pool = make_pool((HEALERS_HAWK, 4), (SOUL_WARDEN, 4), (AJANIS_PRIDEMATE, 4), (GOBLIN_GUIDE, 1))
        lessons = make_lessons(by_mechanic=[make_reference("ganho-de-vida")])
        engines = suggest_engines(pool, lessons, TAGGER, count=2)
        self.assertEqual(engines, [LIFEGAIN_IN_WHITE, Engine("marcadores", frozenset("W"))])

    def test_one_color_wins_when_it_already_fills_the_deck(self):
        vampire = make_card("Lifelink Vampire", "Creature — Vampire", "Lifelink", mana_cost="{B}",
                            arena_id=30, mana_value=1, colors="B")
        pool = make_pool((HEALERS_HAWK, 4), (SOUL_WARDEN, 4), (AJANIS_PRIDEMATE, 4), (vampire, 4))
        [engine] = suggest_engines(pool, make_lessons(), TAGGER, count=1)
        self.assertEqual(engine.colors, frozenset("W"))

    def test_mechanics_need_enough_cards(self):
        self.assertEqual(suggest_engines(make_pool((GOBLIN_GUIDE, 1)), make_lessons(), TAGGER, count=3), [])

    def test_brawl_engines_are_owned_legendary_commanders(self):
        pool = make_pool((KRENKO, 1), (GOBLIN_CHIEFTAIN, 1), *[(recruit, 1) for recruit in GOBLIN_RECRUITS])
        engines = suggest_engines(pool, make_lessons(format_name="HistoricBrawl"), TAGGER, count=1)
        self.assertEqual(engines, [Engine("tribo:goblin", frozenset("R"), commander="Krenko, Mob Boss")])


class BestEngineForCommanderTests(unittest.TestCase):
    def setUp(self):
        self.pool = make_pool((KRENKO, 1), (GOBLIN_CHIEFTAIN, 1), *[(recruit, 1) for recruit in GOBLIN_RECRUITS])
        self.lessons = make_lessons(format_name="HistoricBrawl")

    def test_picks_the_commander_mechanic_with_the_most_cards(self):
        engine = best_engine_for_commander(self.pool, self.lessons, TAGGER, "Krenko, Mob Boss")
        self.assertEqual(engine, Engine("tribo:goblin", frozenset("R"), commander="Krenko, Mob Boss"))

    def test_commander_without_enough_engine_cards_is_refused(self):
        pool = make_pool((KRENKO, 1))
        with self.assertRaisesRegex(DeckNotDesigned, "Krenko"):
            best_engine_for_commander(pool, self.lessons, TAGGER, "Krenko, Mob Boss")


class NamingTests(unittest.TestCase):
    def test_tribes_are_named_by_the_plural_type(self):
        self.assertEqual(archetype_title("tribo:elf"), "Elves")

    def test_mechanics_are_named_by_their_words(self):
        self.assertEqual(archetype_title("ganho-de-vida"), "Ganho de vida")

    def test_sixty_card_decks_are_named_by_colors_and_mechanic(self):
        deck = design_deck(make_pool((HEALERS_HAWK, 4)), make_lessons(), LIFEGAIN_IN_WHITE, TAGGER)
        self.assertEqual(designed_deck_name(deck), "Mono White Ganho de vida (designer)")

    def test_brawl_decks_are_named_by_the_commander(self):
        pool = make_pool((KRENKO, 1), *[(recruit, 1) for recruit in GOBLIN_RECRUITS])
        engine = Engine("tribo:goblin", frozenset("R"), commander="Krenko, Mob Boss")
        deck = design_deck(pool, make_lessons(format_name="HistoricBrawl"), engine, TAGGER)
        self.assertEqual(designed_deck_name(deck), "Krenko Goblins (designer)")


class ToArenaDecklistTests(unittest.TestCase):
    def test_decklist_has_the_commander_and_the_printings(self):
        pool = make_pool((KRENKO, 1), (GOBLIN_RECRUITS[0], 1))
        engine = Engine("tribo:goblin", frozenset("R"), commander="Krenko, Mob Boss")
        decklist = to_arena_decklist(design_deck(pool, make_lessons(format_name="HistoricBrawl"), engine, TAGGER))
        self.assertEqual(
            (decklist.commander, decklist.main[0]),
            (DeckCard(1, "Krenko, Mob Boss", "TST", "1"), DeckCard(1, "Goblin Recruit 0", "TST", "1")),
        )


if __name__ == "__main__":
    unittest.main()
