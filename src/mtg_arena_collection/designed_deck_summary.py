"""Describes a designed deck next to the meta decks it was compared with, in Portuguese."""

from mtg_arena_collection.card_catalog import Card
from mtg_arena_collection.card_mechanics import MechanicTagger
from mtg_arena_collection.deck_designer import DesignedDeck, designed_deck_name, engine_card_copies
from mtg_arena_collection.meta_decks import MetaDeck, MetaDeckCard
from mtg_arena_collection.meta_lessons import ALL_DECKS_LABEL, CardLookup, profile_deck
from mtg_arena_collection.meta_lessons_report import REPORTED_ROLES, decimal_text

DESIGNER_SOURCE = "designer"


def describe_designed_deck(
    deck: DesignedDeck, deck_path: str, catalog: dict[int, Card], tagger: MechanicTagger
) -> str:
    profile = profile_deck(_as_meta_deck(deck), 1.0, CardLookup(catalog), tagger)
    reference = deck.reference
    if reference.label == ALL_DECKS_LABEL:
        compared_with = f"todos os {reference.deck_count} decks do formato"
    else:
        compared_with = f"os {reference.deck_count} decks do meta construídos em volta de {reference.label}"
    lines = [f"{designed_deck_name(deck)}: {deck_path}"]
    if deck.commander:
        lines.append(f"  Comandante: {deck.commander.name}.")
    lines += [
        f"  Motor: {deck.engine.mechanic}, com {engine_card_copies(deck, tagger)} cópias de cartas do motor. "
        f"Comparado com {compared_with}.",
        f"  Terrenos {profile.land_count} (meta {decimal_text(reference.land_count)}) · "
        f"Criaturas {profile.creature_count} (meta {decimal_text(reference.creature_count)}) · "
        f"Custo médio {decimal_text(profile.average_mana_value, 2)} "
        f"(meta {decimal_text(reference.average_mana_value, 2)})",
        f"  Curva 1/2/3/4/5/6+: {'/'.join(str(copies) for copies in profile.curve)} "
        f"(meta {'/'.join(str(round(copies)) for copies in reference.curve)})",
        "  " + " · ".join(
            f"{title} {profile.tag_counts.get(tag, 0)} (meta {decimal_text(reference.role_counts[tag])})"
            for tag, title in REPORTED_ROLES
        ),
    ]
    if deck.unfilled_slots:
        lines.append(f"  Faltaram cartas: {deck.unfilled_slots} vagas sem carta viraram terrenos básicos.")
    return "\n".join(lines)


def _as_meta_deck(deck: DesignedDeck) -> MetaDeck:
    return MetaDeck(
        deck_id=0,
        name=designed_deck_name(deck),
        format_name=deck.format_name,
        source=DESIGNER_SOURCE,
        meta_share=None,
        win_rate=None,
        main=tuple(
            MetaDeckCard(pool_card.name, copies, pool_card.card.arena_id)
            for pool_card, copies in (*deck.nonland_cards, *deck.lands)
        ),
        commander=(
            MetaDeckCard(deck.commander.name, 1, deck.commander.card.arena_id) if deck.commander else None
        ),
    )
