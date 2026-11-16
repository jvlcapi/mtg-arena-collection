import unittest

from card_fixture import make_card
from mtg_arena_collection.card_mechanics import (
    ENABLER_AND_PAYOFF_PAIRS,
    MECHANIC_DESCRIPTIONS,
    MechanicTagger,
    partner_mechanics_of,
)


CARDS = {
    "Ajani's Pridemate": make_card(
        "Ajani's Pridemate", "Creature — Cat Soldier",
        "Whenever you gain life, put a +1/+1 counter on this creature."),
    "Healer's Hawk": make_card("Healer's Hawk", "Creature — Bird", "Flying\nLifelink"),
    "Krenko, Mob Boss": make_card(
        "Krenko, Mob Boss", "Legendary Creature — Goblin Warrior",
        "{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control."),
    "Woe Strider": make_card(
        "Woe Strider", "Creature — Horror",
        "When this creature enters, create a 0/1 white Goat creature token.\n"
        "Sacrifice another creature: Scry 1.\n"
        "Escape—{3}{B}{B}, Exile four other cards from your graveyard.\n"
        "This creature escapes with two +1/+1 counters on it."),
    "Luminous Broodmoth": make_card(
        "Luminous Broodmoth", "Creature — Insect",
        "Flying\nWhenever a creature you control without flying dies, return it to the battlefield "
        "under its owner's control with a flying counter on it."),
    "Lightning Strike": make_card(
        "Lightning Strike", "Instant", "Lightning Strike deals 3 damage to any target."),
    "Opt": make_card("Opt", "Instant", "Scry 1.\nDraw a card."),
    "Llanowar Elves": make_card("Llanowar Elves", "Creature — Elf Druid", "{T}: Add {G}."),
    "Forest Shrine": make_card("Forest Shrine", "Land", "{T}: Add {G}."),
    "Banishing Light": make_card(
        "Banishing Light", "Enchantment",
        "When this enchantment enters, exile target nonland permanent an opponent controls until "
        "this enchantment leaves the battlefield."),
    "Tolarian Terror": make_card(
        "Tolarian Terror", "Creature — Serpent",
        "This spell costs {1} less to cast for each instant and sorcery card in your graveyard.\n"
        "Ward {2}"),
    "Inspiring Overseer": make_card(
        "Inspiring Overseer", "Creature — Angel Cleric",
        "Flying\nWhen this creature enters, you gain 1 life and draw a card."),
    "Spell Pierce": make_card(
        "Spell Pierce", "Instant", "Counter target noncreature spell unless its controller pays {2}."),
    "Revival // Revenge": make_card(
        "Revival // Revenge", "Sorcery",
        "Return target creature card with mana value 3 or less from your graveyard to the battlefield.\n"
        "Double your life total. Target opponent loses half their life, rounded up."),
    "Vito, Thorn of the Dusk Rose": make_card(
        "Vito, Thorn of the Dusk Rose", "Legendary Creature — Vampire Cleric",
        "Whenever you gain life, target opponent loses that much life.\n"
        "{3}{B}{B}: Creatures you control gain lifelink until end of turn."),
    "Goblin Bombardment": make_card(
        "Goblin Bombardment", "Enchantment",
        "Sacrifice a creature: This enchantment deals 1 damage to any target."),
    "Settle the Wreckage": make_card(
        "Settle the Wreckage", "Instant",
        "Exile all attacking creatures target player controls. That player may search their library "
        "for that many basic land cards, put those cards onto the battlefield tapped, then shuffle."),
    "Wall of Omens": make_card(
        "Wall of Omens", "Creature — Wall", "Defender\nWhen Wall of Omens enters, draw a card."),
    "Elvish Archdruid": make_card(
        "Elvish Archdruid", "Creature — Elf Druid",
        "Other Elves you control get +1/+1.\n{T}: Add {G} for each Elf you control."),
    "Lost Shade": make_card(
        "Lost Shade", "Instant", "Return target card from the shade of your graveyard to your hand."),
    "Glorious Anthem": make_card(
        "Glorious Anthem", "Enchantment", "Creatures you control get +1/+1."),
    "Bloodthirsty Blade": make_card(
        "Bloodthirsty Blade", "Artifact — Equipment",
        "Whenever another creature you control dies, create a Treasure token."),
    "Duress": make_card(
        "Duress", "Sorcery",
        "Target opponent reveals their hand. You choose a noncreature, nonland card from it. "
        "That player discards that card."),
    "Sleight of Hand": make_card(
        "Sleight of Hand", "Sorcery",
        "Look at the top two cards of your library. Put one of them into your hand and the other on "
        "the bottom of your library."),
}

TAGGER = MechanicTagger(creature_types={
    "Cat", "Soldier", "Bird", "Goblin", "Warrior", "Horror", "Goat", "Insect", "Elf", "Druid",
    "Serpent", "Angel", "Cleric", "Vampire", "Wall", "Shade",
})


def tags_of(name):
    return set(TAGGER.tags_for(CARDS[name]))


class LifegainTests(unittest.TestCase):
    def test_lifelink_gains_life(self):
        self.assertIn("ganho-de-vida", tags_of("Healer's Hawk"))

    def test_gaining_a_number_of_life_gains_life(self):
        self.assertIn("ganho-de-vida", tags_of("Inspiring Overseer"))

    def test_whenever_you_gain_life_is_a_payoff(self):
        self.assertIn("ganho-de-vida-recompensa", tags_of("Ajani's Pridemate"))

    def test_payoff_alone_is_not_a_source(self):
        self.assertNotIn("ganho-de-vida", tags_of("Ajani's Pridemate"))


class CreaturesAndTokensTests(unittest.TestCase):
    def test_creature_tokens(self):
        self.assertIn("fichas", tags_of("Woe Strider"))

    def test_treasure_is_an_artifact_token_not_a_creature_token(self):
        self.assertEqual(
            {"fichas-de-artefato", "fichas"} & tags_of("Bloodthirsty Blade"), {"fichas-de-artefato"}
        )

    def test_counters(self):
        self.assertIn("marcadores", tags_of("Ajani's Pridemate"))

    def test_anthem_pumps_the_team(self):
        self.assertIn("bonus-para-o-time", tags_of("Glorious Anthem"))


class SacrificeAndGraveyardTests(unittest.TestCase):
    def test_sacrifice_outlet(self):
        self.assertIn("sacrificio", tags_of("Goblin Bombardment"))

    def test_death_trigger(self):
        self.assertIn("morte-recompensa", tags_of("Luminous Broodmoth"))

    def test_returning_a_creature_to_the_battlefield(self):
        self.assertEqual({"reanimar", "cemiterio"} & tags_of("Revival // Revenge"), {"reanimar", "cemiterio"})

    def test_escape_uses_the_graveyard(self):
        self.assertIn("cemiterio", tags_of("Woe Strider"))


class SpellsTests(unittest.TestCase):
    def test_instants_and_sorceries_in_the_graveyard_are_a_spells_payoff(self):
        self.assertIn("magicas", tags_of("Tolarian Terror"))

    def test_counterspell(self):
        self.assertIn("anula", tags_of("Spell Pierce"))

    def test_card_draw(self):
        self.assertIn("compra", tags_of("Opt"))

    def test_scry_alone_is_not_card_draw(self):
        self.assertNotIn("compra", tags_of("Woe Strider"))

    def test_putting_a_looked_at_card_into_your_hand_is_card_draw(self):
        self.assertIn("compra", tags_of("Sleight of Hand"))

    def test_choosing_a_card_the_opponent_discards(self):
        self.assertIn("descarte", tags_of("Duress"))


class InteractionTests(unittest.TestCase):
    def test_damage_to_any_target_is_removal_and_reaches_players(self):
        self.assertEqual({"remocao", "dano-direto"} & tags_of("Lightning Strike"), {"remocao", "dano-direto"})

    def test_exiling_a_permanent_is_removal(self):
        self.assertIn("remocao", tags_of("Banishing Light"))

    def test_exiling_all_attackers_is_a_board_wipe(self):
        self.assertIn("limpa-mesa", tags_of("Settle the Wreckage"))

    def test_life_loss_for_an_opponent_reaches_players(self):
        self.assertIn("dano-direto", tags_of("Vito, Thorn of the Dusk Rose"))

    def test_ward_protects(self):
        self.assertIn("protecao", tags_of("Tolarian Terror"))

    def test_flying_is_evasion(self):
        self.assertIn("evasao", tags_of("Healer's Hawk"))

    def test_enters_trigger(self):
        self.assertIn("entrada", tags_of("Banishing Light"))


class ManaTests(unittest.TestCase):
    def test_mana_creature_ramps(self):
        self.assertIn("rampa", tags_of("Llanowar Elves"))

    def test_lands_that_tap_for_mana_are_not_ramp(self):
        self.assertNotIn("rampa", tags_of("Forest Shrine"))


class TribeTests(unittest.TestCase):
    def test_caring_about_a_creature_type_tags_the_tribe(self):
        self.assertIn("tribo:goblin", tags_of("Krenko, Mob Boss"))

    def test_irregular_plural_is_recognized(self):
        self.assertIn("tribo:elf", tags_of("Elvish Archdruid"))

    def test_the_card_own_name_does_not_count(self):
        self.assertNotIn("tribo:wall", tags_of("Wall of Omens"))

    def test_lowercase_words_are_not_creature_types(self):
        self.assertNotIn("tribo:shade", tags_of("Lost Shade"))

    def test_creature_types_come_from_the_catalog_type_lines(self):
        tagger = MechanicTagger.from_catalog({card.arena_id: card for card in (CARDS["Krenko, Mob Boss"],)})
        self.assertEqual(tagger.creature_types, {"Goblin", "Warrior"})

    def test_subtypes_that_also_name_noncreature_cards_are_not_tribes(self):
        goldhound = make_card("Goldhound", "Artifact Creature — Treasure Dog", "First strike", arena_id=2)
        treasure = make_card("Treasure", "Token Artifact — Treasure", "{T}, Sacrifice this token: Add one mana.",
                             arena_id=3)
        tagger = MechanicTagger.from_catalog({card.arena_id: card for card in (goldhound, treasure)})
        self.assertEqual(tagger.creature_types, {"Dog"})


class DescriptionTests(unittest.TestCase):
    def test_every_mechanic_tag_has_a_description(self):
        found = set().union(*(set(TAGGER.tags_for(card)) for card in CARDS.values()))
        self.assertEqual({tag for tag in found if not tag.startswith("tribo:")} - set(MECHANIC_DESCRIPTIONS), set())

    def test_enabler_and_payoff_pairs_use_known_tags(self):
        paired_tags = {tag for pair in ENABLER_AND_PAYOFF_PAIRS for tag in pair}
        self.assertEqual(paired_tags - set(MECHANIC_DESCRIPTIONS), set())


class ImpulseDrawTests(unittest.TestCase):
    def tags_of_text(self, rules_text):
        return TAGGER.tags_for(make_card("Test Card", "Instant", rules_text))

    def test_playing_the_exiled_top_card_counts_as_card_draw(self):
        self.assertIn("compra", self.tags_of_text(
            "Exile the top card of your library. You may cast that card. If you don't, this deals 2 "
            "damage to each opponent."))

    def test_playing_it_until_end_of_turn_counts_too(self):
        self.assertIn("compra", self.tags_of_text(
            "Exile the top two cards of your library. Until end of turn, you may play those cards."))

    def test_exiling_the_top_card_without_playing_it_is_not_card_draw(self):
        self.assertNotIn("compra", self.tags_of_text("Exile the top card of your library face down."))

    def test_an_opponent_drawing_is_not_card_draw(self):
        self.assertNotIn("compra", self.tags_of_text(
            "Whenever an opponent draws a card, this creature deals 1 damage to them."))

    def test_each_player_drawing_still_counts(self):
        self.assertIn("compra", self.tags_of_text("Each player draws a card."))


class PartnerMechanicsTests(unittest.TestCase):
    def test_payoffs_partner_their_enablers_and_the_reverse(self):
        self.assertEqual(
            (partner_mechanics_of("sacrificio"), partner_mechanics_of("morte-recompensa")),
            ({"morte-recompensa"}, {"sacrificio"}),
        )

    def test_roles_have_no_partner(self):
        self.assertEqual(partner_mechanics_of("remocao"), set())


if __name__ == "__main__":
    unittest.main()
