import unittest

from card_fixture import make_card
from mtg_arena_collection.card_mechanics import MechanicTagger
from mtg_arena_collection.meta_decks import MetaDeck, MetaDeckCard
from mtg_arena_collection.meta_lessons import (
    CardLookup,
    PlayedTogether,
    card_presence,
    cards_played_together,
    deck_weights,
    fit_land_count,
    learn_from_meta,
    mechanics_played_together,
    profile_deck,
    speed_band_of,
    summarize_group,
)

MOUNTAIN = make_card("Mountain", "Basic Land — Mountain", arena_id=10, rarity="basic")
PLAINS = make_card("Plains", "Basic Land — Plains", arena_id=11, rarity="basic")
ORNITHOPTER = make_card("Ornithopter", "Artifact Creature — Thopter", "Flying", arena_id=20)
GOBLIN_GUIDE = make_card(
    "Goblin Guide", "Creature — Goblin Scout", "Haste", arena_id=21, mana_value=1, colors="R")
LIGHTNING_STRIKE = make_card(
    "Lightning Strike", "Instant", "Lightning Strike deals 3 damage to any target.",
    arena_id=22, mana_value=2, colors="R")
KRENKO = make_card(
    "Krenko, Mob Boss", "Legendary Creature — Goblin Warrior",
    "{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control.",
    arena_id=23, mana_value=4, colors="R")
SHIVAN_DRAGON = make_card(
    "Shivan Dragon", "Creature — Dragon", "Flying\n{R}: This creature gets +1/+0 until end of turn.",
    arena_id=24, mana_value=6, colors="R")
HEALERS_HAWK = make_card(
    "Healer's Hawk", "Creature — Bird", "Flying\nLifelink", arena_id=30, mana_value=1, colors="W")
AJANIS_PRIDEMATE = make_card(
    "Ajani's Pridemate", "Creature — Cat Soldier",
    "Whenever you gain life, put a +1/+1 counter on this creature.",
    arena_id=31, mana_value=2, colors="W")
SAVANNAH_LIONS = make_card("Savannah Lions", "Creature — Cat", arena_id=32, mana_value=1, colors="W")
CEASE_DESIST = make_card("Cease // Desist", "Instant // Sorcery", arena_id=40, mana_value=1, colors="G")
REVENGE = make_card("Revenge", "Sorcery", arena_id=41, mana_value=5, colors="B")
REVIVAL_REVENGE = make_card("Revival // Revenge", "Sorcery // Sorcery", arena_id=42, mana_value=2)
ANGEL_TOKEN = make_card("Angel of Sanctions", "Token Creature — Zombie Angel", arena_id=50, rarity="token")
ANGEL_OF_SANCTIONS = make_card("Angel of Sanctions", "Creature — Angel", arena_id=51, mana_value=5)

CATALOG = {
    card.arena_id: card
    for card in (
        MOUNTAIN, PLAINS, ORNITHOPTER, GOBLIN_GUIDE, LIGHTNING_STRIKE, KRENKO, SHIVAN_DRAGON,
        HEALERS_HAWK, AJANIS_PRIDEMATE, SAVANNAH_LIONS, CEASE_DESIST, REVENGE, REVIVAL_REVENGE,
        ANGEL_OF_SANCTIONS, ANGEL_TOKEN,
    )
}
CARD_LOOKUP = CardLookup(CATALOG)
TAGGER = MechanicTagger.from_catalog(CATALOG)


def make_deck(*cards, deck_id=1, format_name="Standard", commander=None, meta_share=None,
              win_rate=None, source="aetherhub-meta", extra_lines=()):
    main = tuple(MetaDeckCard(card.name, quantity, card.arena_id) for card, quantity in cards)
    return MetaDeck(
        deck_id=deck_id, name="Deck", format_name=format_name, source=source,
        meta_share=meta_share, win_rate=win_rate, main=main + tuple(extra_lines),
        commander=MetaDeckCard(commander.name, 1, commander.arena_id) if commander else None,
    )


def make_profile(*cards, weight=1.0, **deck_details):
    return profile_deck(make_deck(*cards, **deck_details), weight, CARD_LOOKUP, TAGGER)


class CardLookupTests(unittest.TestCase):
    def test_finds_the_card_by_arena_id_first(self):
        self.assertEqual(CARD_LOOKUP.find(MetaDeckCard("Old Name", 4, GOBLIN_GUIDE.arena_id)), GOBLIN_GUIDE)

    def test_finds_the_card_by_name_without_arena_id(self):
        self.assertEqual(CARD_LOOKUP.find(MetaDeckCard("Goblin Guide", 4)), GOBLIN_GUIDE)

    def test_finds_split_cards_by_the_first_face(self):
        self.assertEqual(CARD_LOOKUP.find(MetaDeckCard("Cease", 1)), CEASE_DESIST)

    def test_full_names_win_over_face_names(self):
        self.assertEqual(CARD_LOOKUP.find(MetaDeckCard("Revenge", 1)), REVENGE)

    def test_tokens_named_like_a_card_are_not_found_by_name(self):
        self.assertEqual(CARD_LOOKUP.find(MetaDeckCard("Angel of Sanctions", 1)), ANGEL_OF_SANCTIONS)

    def test_unknown_cards_are_not_found(self):
        self.assertIsNone(CARD_LOOKUP.find(MetaDeckCard("Mystery Card", 1)))


class ProfileDeckTests(unittest.TestCase):
    def test_counts_lands_creatures_and_nonland_cards(self):
        profile = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 20), (LIGHTNING_STRIKE, 20))
        self.assertEqual(
            (profile.card_count, profile.land_count, profile.creature_count, profile.nonland_count),
            (60, 20, 20, 40),
        )

    def test_average_mana_value_counts_only_nonland_cards(self):
        profile = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 20), (LIGHTNING_STRIKE, 20))
        self.assertEqual(profile.average_mana_value, 1.5)

    def test_curve_puts_zero_with_one_and_six_or_more_together(self):
        profile = make_profile(
            (ORNITHOPTER, 2), (GOBLIN_GUIDE, 4), (LIGHTNING_STRIKE, 4), (KRENKO, 1), (SHIVAN_DRAGON, 3)
        )
        self.assertEqual(profile.curve, (6, 4, 0, 1, 0, 3))

    def test_tag_counts_add_up_the_copies_of_nonland_cards(self):
        profile = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 4), (LIGHTNING_STRIKE, 4))
        self.assertEqual(profile.tag_counts, {"impeto": 4, "remocao": 4, "dano-direto": 4})

    def test_themes_are_tags_on_at_least_a_quarter_of_the_nonland_cards(self):
        profile = make_profile((PLAINS, 24), (HEALERS_HAWK, 9), (AJANIS_PRIDEMATE, 8), (SAVANNAH_LIONS, 19))
        self.assertEqual(profile.themes(), {"ganho-de-vida", "evasao"})

    def test_brawl_commander_tags_are_themes_too(self):
        profile = make_profile(
            (MOUNTAIN, 40), (GOBLIN_GUIDE, 59), format_name="HistoricBrawl", commander=KRENKO
        )
        self.assertTrue({"fichas", "tribo:goblin"} <= profile.themes())

    def test_brawl_colors_come_from_the_commander(self):
        profile = make_profile((MOUNTAIN, 99), format_name="HistoricBrawl", commander=KRENKO)
        self.assertEqual(profile.colors, {"R"})

    def test_colors_come_from_the_nonland_cards(self):
        profile = make_profile((PLAINS, 20), (HEALERS_HAWK, 20), (LIGHTNING_STRIKE, 20))
        self.assertEqual(profile.colors, {"W", "R"})

    def test_nonland_cards_keep_their_color_identity(self):
        profile = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 4), (ORNITHOPTER, 4))
        self.assertEqual(profile.nonland_card_colors, {"Goblin Guide": {"R"}, "Ornithopter": set()})

    def test_cards_missing_from_the_catalog_are_listed_and_left_out(self):
        profile = make_profile((MOUNTAIN, 20), extra_lines=[MetaDeckCard("Mystery Card", 4)])
        self.assertEqual((profile.unknown_card_names, profile.card_count), (("Mystery Card",), 20))


class DeckWeightsTests(unittest.TestCase):
    def test_meta_list_decks_weigh_their_share_over_the_list_average(self):
        decks = [make_deck(deck_id=1, meta_share=0.375), make_deck(deck_id=2, meta_share=0.125)]
        self.assertEqual(deck_weights(decks), {1: 1.5, 2: 0.5})

    def test_top_result_decks_weigh_their_win_rate_over_the_list_average(self):
        decks = [
            make_deck(deck_id=1, win_rate=0.75, source="aetherhub"),
            make_deck(deck_id=2, win_rate=0.25, source="aetherhub"),
        ]
        self.assertEqual(deck_weights(decks), {1: 1.5, 2: 0.5})

    def test_each_format_and_source_is_its_own_list(self):
        decks = [
            make_deck(deck_id=1, meta_share=0.375),
            make_deck(deck_id=2, meta_share=0.125, format_name="Historic"),
            make_deck(deck_id=3, win_rate=0.5, source="aetherhub"),
        ]
        self.assertEqual(deck_weights(decks), {1: 1.0, 2: 1.0, 3: 1.0})

    def test_decks_without_share_or_win_rate_weigh_one(self):
        self.assertEqual(deck_weights([make_deck(deck_id=1)]), {1: 1.0})


class FitLandCountTests(unittest.TestCase):
    def test_line_goes_through_the_decks(self):
        cheap = make_profile((MOUNTAIN, 22), (LIGHTNING_STRIKE, 38))
        expensive = make_profile((MOUNTAIN, 26), (KRENKO, 34))
        fit = fit_land_count([cheap, expensive])
        self.assertEqual((fit.intercept, fit.slope), (18.0, 2.0))

    def test_decks_with_little_weight_barely_move_the_line(self):
        decks = [
            make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 40)),
            make_profile((MOUNTAIN, 22), (LIGHTNING_STRIKE, 38)),
            make_profile((MOUNTAIN, 40), (KRENKO, 20), weight=0.000001),
        ]
        self.assertAlmostEqual(fit_land_count(decks).slope, 2.0, places=2)

    def test_decks_with_the_same_average_cost_get_their_average_land_count(self):
        decks = [make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 40)), make_profile((MOUNTAIN, 24), (GOBLIN_GUIDE, 36))]
        fit = fit_land_count(decks)
        self.assertEqual((fit.intercept, fit.slope, fit.land_count_for(1.0)), (22.0, 0.0, 22.0))


class SummarizeGroupTests(unittest.TestCase):
    def test_averages_are_weighted(self):
        heavy = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 40), weight=3.0)
        light = make_profile((MOUNTAIN, 24), (GOBLIN_GUIDE, 36), weight=1.0)
        self.assertEqual(summarize_group("todos", [heavy, light], 4.0).land_count, 21.0)

    def test_counts_are_scaled_to_sixty_cards(self):
        long_list = make_profile((MOUNTAIN, 24), (GOBLIN_GUIDE, 40))
        self.assertEqual(summarize_group("todos", [long_list], 1.0).land_count, 22.5)

    def test_historic_brawl_counts_are_scaled_to_ninety_nine_cards(self):
        short_list = make_profile((MOUNTAIN, 49), (GOBLIN_GUIDE, 49), format_name="HistoricBrawl")
        self.assertEqual(summarize_group("todos", [short_list], 1.0).land_count, 49.5)

    def test_weight_share_is_the_groups_part_of_the_format(self):
        profile = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 40))
        self.assertEqual(summarize_group("impeto", [profile], 4.0).weight_share, 0.25)

    def test_role_counts_follow_the_role_tags(self):
        profile = make_profile((MOUNTAIN, 20), (LIGHTNING_STRIKE, 40))
        role_counts = summarize_group("todos", [profile], 1.0).role_counts
        self.assertEqual((role_counts["remocao"], role_counts["compra"]), (40.0, 0.0))

    def test_curve_is_scaled_and_weighted(self):
        heavy = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 40), weight=3.0)
        light = make_profile((MOUNTAIN, 20), (LIGHTNING_STRIKE, 40), weight=1.0)
        self.assertEqual(summarize_group("todos", [heavy, light], 4.0).curve, (30.0, 10.0, 0.0, 0.0, 0.0, 0.0))

    def test_most_played_cards_come_with_the_weighted_share_of_decks_playing_them(self):
        first = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 20), (LIGHTNING_STRIKE, 20), weight=3.0)
        second = make_profile((MOUNTAIN, 20), (LIGHTNING_STRIKE, 40), weight=1.0)
        self.assertEqual(
            summarize_group("todos", [first, second], 4.0).most_played_cards,
            (("Lightning Strike", 1.0), ("Goblin Guide", 0.75)),
        )


class CardPresenceTests(unittest.TestCase):
    def test_presence_is_the_weighted_share_of_decks_playing_each_card(self):
        first = make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 20), (LIGHTNING_STRIKE, 20), weight=3.0)
        second = make_profile((MOUNTAIN, 20), (LIGHTNING_STRIKE, 40), weight=1.0)
        self.assertEqual(card_presence([first, second]), {"Lightning Strike": 1.0, "Goblin Guide": 0.75})


class SpeedBandTests(unittest.TestCase):
    def test_bands_split_at_average_mana_value_two_and_three(self):
        self.assertEqual(
            [speed_band_of(average) for average in (1.99, 2.0, 2.99, 3.0)],
            ["rapido", "medio", "medio", "lento"],
        )


def goblin_decks(count, weight=1.0):
    return [make_profile((MOUNTAIN, 20), (GOBLIN_GUIDE, 20), (KRENKO, 20), weight=weight) for _ in range(count)]


def burn_decks(count, weight=1.0):
    return [make_profile((MOUNTAIN, 20), (LIGHTNING_STRIKE, 40), weight=weight) for _ in range(count)]


def lifegain_decks(count):
    return [
        make_profile((PLAINS, 24), (HEALERS_HAWK, 12), (AJANIS_PRIDEMATE, 12), (SAVANNAH_LIONS, 12))
        for _ in range(count)
    ]


class CardsPlayedTogetherTests(unittest.TestCase):
    def test_pairs_count_how_many_times_more_than_chance_they_share_decks(self):
        pairs = cards_played_together(goblin_decks(3) + burn_decks(3))
        self.assertEqual(pairs, [PlayedTogether("Goblin Guide", "Krenko, Mob Boss", 3, 2.0)])

    def test_chance_only_counts_the_decks_whose_colors_could_play_both_cards(self):
        white_decks = [make_profile((PLAINS, 20), (HEALERS_HAWK, 40)) for _ in range(6)]
        pairs = cards_played_together(goblin_decks(3) + burn_decks(3) + white_decks)
        self.assertEqual([pair.times_more_than_chance for pair in pairs], [2.0])

    def test_heavier_decks_count_more(self):
        pairs = cards_played_together(goblin_decks(3) + burn_decks(3, weight=3.0))
        self.assertEqual([pair.times_more_than_chance for pair in pairs], [4.0])

    def test_pairs_need_three_decks(self):
        self.assertEqual(cards_played_together(goblin_decks(2) + burn_decks(4)), [])


class MechanicsPlayedTogetherTests(unittest.TestCase):
    def test_pairs_come_from_the_themes_of_each_deck(self):
        haste_decks = [make_profile((MOUNTAIN, 24), (GOBLIN_GUIDE, 36)) for _ in range(3)]
        pairs = mechanics_played_together(lifegain_decks(3) + haste_decks)
        self.assertIn(PlayedTogether("ganho-de-vida", "ganho-de-vida-recompensa", 3, 2.0), pairs)

    def test_mechanics_in_every_deck_are_not_more_than_chance(self):
        self.assertEqual(mechanics_played_together(lifegain_decks(3)), [])


class LearnFromMetaTests(unittest.TestCase):
    def test_formats_come_in_the_order_standard_historic_and_historic_brawl(self):
        decks = [
            make_deck((MOUNTAIN, 99), deck_id=1, format_name="HistoricBrawl", commander=KRENKO),
            make_deck((MOUNTAIN, 20), (GOBLIN_GUIDE, 40), deck_id=2, format_name="Historic"),
            make_deck((MOUNTAIN, 20), (GOBLIN_GUIDE, 40), deck_id=3),
        ]
        lessons = learn_from_meta(decks, CATALOG, TAGGER)
        self.assertEqual([lesson.format_name for lesson in lessons], ["Standard", "Historic", "HistoricBrawl"])

    def test_mechanic_groups_need_three_decks(self):
        lifegain = [
            make_deck((PLAINS, 24), (HEALERS_HAWK, 12), (AJANIS_PRIDEMATE, 12), (SAVANNAH_LIONS, 12), deck_id=number)
            for number in (1, 2, 3)
        ]
        haste = [make_deck((MOUNTAIN, 24), (GOBLIN_GUIDE, 36), deck_id=number) for number in (4, 5)]
        [standard] = learn_from_meta(lifegain + haste, CATALOG, TAGGER)
        labels = {summary.label for summary in standard.by_mechanic}
        self.assertEqual(("ganho-de-vida" in labels, "impeto" in labels), (True, False))

    def test_speed_bands_and_all_decks_cover_every_deck(self):
        decks = [
            make_deck((MOUNTAIN, 20), (GOBLIN_GUIDE, 40), deck_id=1),
            make_deck((MOUNTAIN, 26), (KRENKO, 34), deck_id=2),
        ]
        [standard] = learn_from_meta(decks, CATALOG, TAGGER)
        self.assertEqual(
            (standard.all_decks.deck_count, [(band.label, band.deck_count) for band in standard.by_speed]),
            (2, [("rapido", 1), ("lento", 1)]),
        )


if __name__ == "__main__":
    unittest.main()
