"""What the meta decks teach about building a deck: land count, curve, roles, and the mechanics
and cards that show up together.

Every number comes from the meta decks mtga-mcp imported (meta_decks.py). Each deck weighs how
much it stands out in its own list: in a meta list, its meta share over the list's average; in a
list of top results, its win rate over the list's average. Counts are scaled to the format's main
deck size (60 cards, 99 in Historic Brawl), so lists of 61 or 64 cards compare with the others.

A deck is built around a mechanic (card_mechanics.py) when at least a quarter of its nonland
cards carry it; in Brawl the commander's own mechanics count too.

Two mechanics or two cards go together when they share decks more often than chance would put
them together: if one is in half the decks and the other in a third, chance puts them together
in a sixth. For cards, chance only counts the decks whose colors could play both cards, so two
red cards are not "together" just because both are red. Every lesson needs at least three decks.
"""

import functools
import itertools
import math
from collections import defaultdict
from dataclasses import dataclass

from mtg_arena_collection.card_catalog import Card
from mtg_arena_collection.card_mechanics import MechanicTagger
from mtg_arena_collection.meta_decks import MetaDeck, MetaDeckCard

MAIN_DECK_SIZES = {"HistoricBrawl": 99, "Brawl": 59}
DEFAULT_MAIN_DECK_SIZE = 60
CURVE_LABELS = ("1", "2", "3", "4", "5", "6+")
ROLE_TAGS = ("remocao", "limpa-mesa", "compra", "anula", "rampa", "descarte", "protecao")
THEME_SHARE_OF_NONLAND_CARDS = 0.25
SPEED_BANDS = (("rapido", 2.0), ("medio", 3.0), ("lento", math.inf))
MOST_PLAYED_CARDS_SHOWN = 8
MINIMUM_DECKS = 3
MINIMUM_TIMES_MORE_THAN_CHANCE_FOR_MECHANICS = 1.5
MINIMUM_TIMES_MORE_THAN_CHANCE_FOR_CARDS = 2.0
FORMAT_ORDER = ("Standard", "Historic", "HistoricBrawl")
ALL_DECKS_LABEL = "todos"
TOKEN_RARITY = "token"
FACE_SEPARATOR = " // "


class CardLookup:
    """Finds the catalog card of a decklist line: by Arena id, then by name or first face."""

    def __init__(self, catalog: dict[int, Card]):
        self.catalog = catalog
        playable_cards = [card for card in catalog.values() if card.rarity != TOKEN_RARITY]
        self.cards_by_name = {card.name: card for card in playable_cards}
        for card in playable_cards:
            for face_name in card.name.split(FACE_SEPARATOR):
                self.cards_by_name.setdefault(face_name, card)

    def find(self, deck_card: MetaDeckCard) -> Card | None:
        if deck_card.arena_id in self.catalog:
            return self.catalog[deck_card.arena_id]
        return self.cards_by_name.get(deck_card.name)


@dataclass(frozen=True)
class DeckProfile:
    deck: MetaDeck
    weight: float
    colors: frozenset[str]
    main_deck_size: int
    card_count: int
    land_count: int
    creature_count: int
    nonland_count: int
    average_mana_value: float
    curve: tuple[int, ...]
    tag_counts: dict[str, int]
    commander_tags: frozenset[str]
    nonland_card_colors: dict[str, frozenset[str]]
    unknown_card_names: tuple[str, ...]

    def scaled(self, count: float) -> float:
        """The count in a list of exactly the format's main deck size."""
        return count * self.main_deck_size / self.card_count if self.card_count else 0.0

    def themes(self) -> frozenset[str]:
        minimum_copies = THEME_SHARE_OF_NONLAND_CARDS * self.nonland_count
        built_around = {tag for tag, copies in self.tag_counts.items() if copies >= minimum_copies}
        return frozenset(built_around) | self.commander_tags


@dataclass(frozen=True)
class LandCountFit:
    """Lands in a main deck of the format's size, as a line over the average mana value."""

    intercept: float
    slope: float

    def land_count_for(self, average_mana_value: float) -> float:
        return self.intercept + self.slope * average_mana_value


@dataclass(frozen=True)
class GroupSummary:
    label: str
    deck_count: int
    weight_share: float
    land_count: float
    creature_count: float
    average_mana_value: float
    curve: tuple[float, ...]
    role_counts: dict[str, float]
    most_played_cards: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class PlayedTogether:
    first: str
    second: str
    deck_count: int
    times_more_than_chance: float


@dataclass(frozen=True)
class FormatLessons:
    format_name: str
    main_deck_size: int
    land_count_fit: LandCountFit
    all_decks: GroupSummary
    by_speed: tuple[GroupSummary, ...]
    by_mechanic: tuple[GroupSummary, ...]
    mechanics_played_together: tuple[PlayedTogether, ...]
    cards_played_together: tuple[PlayedTogether, ...]
    card_presence: dict[str, float]
    unknown_card_names: tuple[str, ...]


def learn_from_meta(
    decks: list[MetaDeck], catalog: dict[int, Card], tagger: MechanicTagger | None = None
) -> list[FormatLessons]:
    tagger = tagger or MechanicTagger.from_catalog(catalog)
    cards = CardLookup(catalog)
    weights = deck_weights(decks)
    profiles_by_format = defaultdict(list)
    for deck in decks:
        profiles_by_format[deck.format_name].append(profile_deck(deck, weights[deck.deck_id], cards, tagger))
    format_names = sorted(profiles_by_format, key=_format_position)
    return [learn_from_format(name, profiles_by_format[name]) for name in format_names]


def learn_from_format(format_name: str, profiles: list[DeckProfile]) -> FormatLessons:
    format_weight = sum(profile.weight for profile in profiles)
    profiles_by_speed = defaultdict(list)
    profiles_by_theme = defaultdict(list)
    for profile in profiles:
        profiles_by_speed[speed_band_of(profile.average_mana_value)].append(profile)
        for theme in profile.themes():
            profiles_by_theme[theme].append(profile)
    by_mechanic = [
        summarize_group(theme, members, format_weight)
        for theme, members in profiles_by_theme.items()
        if len(members) >= MINIMUM_DECKS
    ]
    return FormatLessons(
        format_name=format_name,
        main_deck_size=main_deck_size_of(format_name),
        land_count_fit=fit_land_count(profiles),
        all_decks=summarize_group(ALL_DECKS_LABEL, profiles, format_weight),
        by_speed=tuple(
            summarize_group(label, profiles_by_speed[label], format_weight)
            for label, _ in SPEED_BANDS
            if profiles_by_speed[label]
        ),
        by_mechanic=tuple(sorted(by_mechanic, key=lambda summary: (-summary.weight_share, summary.label))),
        mechanics_played_together=tuple(mechanics_played_together(profiles)),
        cards_played_together=tuple(cards_played_together(profiles)),
        card_presence=card_presence(profiles),
        unknown_card_names=tuple(sorted({name for profile in profiles for name in profile.unknown_card_names})),
    )


def mechanics_played_together(
    profiles: list[DeckProfile],
    minimum_times_more_than_chance: float = MINIMUM_TIMES_MORE_THAN_CHANCE_FOR_MECHANICS,
) -> list[PlayedTogether]:
    decks = [(profile.weight, profile.colors, profile.themes()) for profile in profiles]
    return _played_together(decks, {}, minimum_times_more_than_chance)


def cards_played_together(
    profiles: list[DeckProfile],
    minimum_times_more_than_chance: float = MINIMUM_TIMES_MORE_THAN_CHANCE_FOR_CARDS,
) -> list[PlayedTogether]:
    card_colors = {}
    for profile in profiles:
        card_colors.update(profile.nonland_card_colors)
    decks = [(profile.weight, profile.colors, frozenset(profile.nonland_card_colors)) for profile in profiles]
    return _played_together(decks, card_colors, minimum_times_more_than_chance)


def deck_weights(decks: list[MetaDeck]) -> dict[int, float]:
    """Each deck's meta share (or win rate) over the average of its list; 1 without either."""
    standings_by_list = defaultdict(list)
    weights = {}
    for deck in decks:
        standing = deck.meta_share if deck.meta_share is not None else deck.win_rate
        if standing is None:
            weights[deck.deck_id] = 1.0
        else:
            standings_by_list[(deck.format_name, deck.source)].append((deck.deck_id, standing))
    for standings in standings_by_list.values():
        average = sum(standing for _, standing in standings) / len(standings)
        for deck_id, standing in standings:
            weights[deck_id] = standing / average if average > 0 else 1.0
    return weights


def profile_deck(deck: MetaDeck, weight: float, cards: CardLookup, tagger: MechanicTagger) -> DeckProfile:
    found_cards, unknown_card_names = _find_cards(deck.main, cards)
    nonland_cards = [(card, quantity) for card, quantity in found_cards if not is_land(card)]
    nonland_count = sum(quantity for _, quantity in nonland_cards)
    nonland_card_colors = {card.name: frozenset(card.color_identity) for card, _ in nonland_cards}
    commander = cards.find(deck.commander) if deck.commander else None
    if commander:
        colors = frozenset(commander.color_identity)
    else:
        colors = frozenset().union(*nonland_card_colors.values())
    total_mana_value = sum(card.mana_value * quantity for card, quantity in nonland_cards)
    return DeckProfile(
        deck=deck,
        weight=weight,
        colors=colors,
        main_deck_size=main_deck_size_of(deck.format_name),
        card_count=sum(quantity for _, quantity in found_cards),
        land_count=sum(quantity for card, quantity in found_cards if is_land(card)),
        creature_count=sum(quantity for card, quantity in nonland_cards if is_creature(card)),
        nonland_count=nonland_count,
        average_mana_value=total_mana_value / nonland_count if nonland_count else 0.0,
        curve=_curve(nonland_cards),
        tag_counts=_tag_counts(nonland_cards, tagger),
        commander_tags=frozenset(tagger.tags_for(commander)) if commander else frozenset(),
        nonland_card_colors=nonland_card_colors,
        unknown_card_names=tuple(unknown_card_names),
    )


def fit_land_count(profiles: list[DeckProfile]) -> LandCountFit:
    """Weighted least squares of the scaled land count over the average mana value."""
    total_weight = sum(profile.weight for profile in profiles)
    average_cost = sum(profile.weight * profile.average_mana_value for profile in profiles) / total_weight
    average_lands = sum(profile.weight * _scaled_lands(profile) for profile in profiles) / total_weight
    covariance = sum(
        profile.weight * (profile.average_mana_value - average_cost) * (_scaled_lands(profile) - average_lands)
        for profile in profiles
    )
    variance = sum(profile.weight * (profile.average_mana_value - average_cost) ** 2 for profile in profiles)
    slope = covariance / variance if variance > 0 else 0.0
    return LandCountFit(intercept=average_lands - slope * average_cost, slope=slope)


def summarize_group(label: str, profiles: list[DeckProfile], format_weight: float) -> GroupSummary:
    def weighted_average(value_of) -> float:
        return sum(profile.weight * value_of(profile) for profile in profiles) / group_weight

    group_weight = sum(profile.weight for profile in profiles)
    return GroupSummary(
        label=label,
        deck_count=len(profiles),
        weight_share=group_weight / format_weight,
        land_count=weighted_average(_scaled_lands),
        creature_count=weighted_average(lambda profile: profile.scaled(profile.creature_count)),
        average_mana_value=weighted_average(lambda profile: profile.average_mana_value),
        curve=tuple(
            weighted_average(lambda profile, index=index: profile.scaled(profile.curve[index]))
            for index in range(len(CURVE_LABELS))
        ),
        role_counts={
            tag: weighted_average(lambda profile, tag=tag: profile.scaled(profile.tag_counts.get(tag, 0)))
            for tag in ROLE_TAGS
        },
        most_played_cards=tuple(itertools.islice(card_presence(profiles).items(), MOST_PLAYED_CARDS_SHOWN)),
    )


def speed_band_of(average_mana_value: float) -> str:
    return next(label for label, upper_bound in SPEED_BANDS if average_mana_value < upper_bound)


def main_deck_size_of(format_name: str) -> int:
    return MAIN_DECK_SIZES.get(format_name, DEFAULT_MAIN_DECK_SIZE)


def is_land(card: Card) -> bool:
    return "Land" in card.type_line.split("//")[0]


def is_creature(card: Card) -> bool:
    return "Creature" in card.type_line.split("//")[0]


def _find_cards(lines: tuple[MetaDeckCard, ...], cards: CardLookup) -> tuple[list, list[str]]:
    found_cards, unknown_card_names = [], []
    for line in lines:
        card = cards.find(line)
        if card is None:
            unknown_card_names.append(line.name)
        else:
            found_cards.append((card, line.quantity))
    return found_cards, unknown_card_names


def curve_bucket_of(mana_value: int) -> int:
    """Index in CURVE_LABELS: mana value 0 goes with 1, and 6 or more share the last step."""
    return min(max(mana_value, 1), len(CURVE_LABELS)) - 1


def _curve(nonland_cards: list[tuple[Card, int]]) -> tuple[int, ...]:
    copies_by_bucket = [0] * len(CURVE_LABELS)
    for card, quantity in nonland_cards:
        copies_by_bucket[curve_bucket_of(card.mana_value)] += quantity
    return tuple(copies_by_bucket)


def _tag_counts(nonland_cards: list[tuple[Card, int]], tagger: MechanicTagger) -> dict[str, int]:
    copies_by_tag = defaultdict(int)
    for card, quantity in nonland_cards:
        for tag in tagger.tags_for(card):
            copies_by_tag[tag] += quantity
    return dict(copies_by_tag)


def _scaled_lands(profile: DeckProfile) -> float:
    return profile.scaled(profile.land_count)


def _format_position(format_name: str) -> tuple[int, str]:
    position = FORMAT_ORDER.index(format_name) if format_name in FORMAT_ORDER else len(FORMAT_ORDER)
    return position, format_name


def _played_together(
    decks: list[tuple[float, frozenset[str], frozenset[str]]],
    item_colors: dict[str, frozenset[str]],
    minimum_times_more_than_chance: float,
) -> list[PlayedTogether]:
    """Pairs of items (mechanics or cards) in at least MINIMUM_DECKS decks, sharing decks more
    often than chance among the decks whose colors could play both. Each deck is
    (weight, colors, items); items without colors can go in any deck."""
    weight_together = defaultdict(float)
    decks_together = defaultdict(int)
    for weight, _, items in decks:
        for pair in itertools.combinations(sorted(items), 2):
            weight_together[pair] += weight
            decks_together[pair] += 1

    @functools.cache
    def weight_of_decks_with(colors: frozenset[str], item: str | None = None) -> float:
        return sum(
            weight
            for weight, deck_colors, items in decks
            if colors <= deck_colors and (item is None or item in items)
        )

    pairs = []
    for (first, second), deck_count in decks_together.items():
        if deck_count < MINIMUM_DECKS:
            continue
        colors = item_colors.get(first, frozenset()) | item_colors.get(second, frozenset())
        weight_by_chance = (
            weight_of_decks_with(colors, first) * weight_of_decks_with(colors, second)
            / weight_of_decks_with(colors)
        )
        times_more_than_chance = weight_together[(first, second)] / weight_by_chance
        if times_more_than_chance >= minimum_times_more_than_chance:
            pairs.append(PlayedTogether(first, second, deck_count, times_more_than_chance))
    return sorted(
        pairs, key=lambda pair: (-pair.times_more_than_chance, -pair.deck_count, pair.first, pair.second)
    )


def card_presence(profiles: list[DeckProfile]) -> dict[str, float]:
    """Each nonland card's weighted share of the decks that play it, most played first."""
    total_weight = sum(profile.weight for profile in profiles)
    weight_by_card = defaultdict(float)
    for profile in profiles:
        for card_name in profile.nonland_card_colors:
            weight_by_card[card_name] += profile.weight
    ranking = sorted(weight_by_card.items(), key=lambda item: (-item[1], item[0]))
    return {card_name: weight / total_weight for card_name, weight in ranking}
