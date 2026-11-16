"""Designs a deck from the owned cards around an engine: a mechanic in some colors, or in Brawl a
commander, with the roles, curve and land count of the meta decks (meta_lessons.py).

The targets come from the meta decks built around the engine mechanic, or from all the format's
decks when the meta has no such group. Every nonland slot takes the copy with the best score:
- engine: +3 for the engine mechanic; +1.5 for its partner (gaining life and the payoffs for it)
  or for being part of it (a Goblin in a Goblin deck, an instant in a spells deck); +0.75 for a
  mechanic the meta plays together with it;
- meta: +3 × the share of the format's meta decks that play the card;
- synergy: +0.5 for each card already in that the meta plays together with this one (up to 4);
- needs: +1 when the deck still lacks creatures (or noncreature cards) or cards at that mana
  value, −1 when it has enough; +1 for each role (removal, card draw...) still below its target;
- consistency: +0.5 for another copy of a card already in.
Lands: lands making two or more of the deck's colors (or any color) first, up to half, and basic
lands split the rest by the colored mana symbols of the spells.
"""

import itertools
import re
from collections import Counter
from dataclasses import dataclass, replace

from mtg_arena_collection.arena_deck_files import (
    COLOR_ORDER,
    ArenaDecklist,
    DeckCard,
    DeckFolder,
    color_combination_name,
)
from mtg_arena_collection.card_catalog import Card
from mtg_arena_collection.card_mechanics import (
    MechanicTagger,
    creature_types_of,
    partner_mechanics_of,
    plural_of,
)
from mtg_arena_collection.card_pool import PoolCard, copy_limit, is_basic_land
from mtg_arena_collection.meta_decks import is_brawl_format
from mtg_arena_collection.meta_lessons import (
    FormatLessons,
    GroupSummary,
    PlayedTogether,
    curve_bucket_of,
    is_creature,
    is_land,
)

ENGINE_WEIGHT = 3.0
PARTNER_WEIGHT = 1.5
META_PARTNER_WEIGHT = 0.75
META_PRESENCE_WEIGHT = 3.0
SYNERGY_WEIGHT = 0.5
MAXIMUM_SYNERGY_PARTNERS = 4
NEED_WEIGHT = 1.0
CONSISTENCY_WEIGHT = 0.5
SHARE_OF_FIXING_LANDS = 0.5
ENGINE_SHARE_OF_NONLAND_SLOTS = 1 / 3
EXTRA_COLOR_FACTOR = 0.85
CORE_SHARE_OF_NONLAND_SLOTS = 1 / 6
MECHANICS_THAT_ARE_NOT_ENGINES = frozenset(
    {"entrada", "evasao", "protecao", "remocao", "limpa-mesa", "compra", "anula"}
)
MEMBER_CARD_TYPES = {
    "magicas": ("Instant", "Sorcery"),
    "artefatos-recompensa": ("Artifact",),
    "encantamentos-recompensa": ("Enchantment",),
}
TRIBE_PREFIX = "tribo:"
BASIC_LAND_NAMES = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
ANY_COLOR_TEXT = "mana of any color"
COLORED_MANA_SYMBOL = re.compile(r"[WUBRG]")
ONE_AND_TWO_COLOR_OPTIONS = tuple(frozenset(color) for color in COLOR_ORDER) + tuple(
    frozenset(pair) for pair in itertools.combinations(COLOR_ORDER, 2)
)
DESIGNER_SUFFIX = "(designer)"


class DeckNotDesigned(ValueError):
    pass


@dataclass(frozen=True)
class Engine:
    mechanic: str
    colors: frozenset[str]
    commander: str | None = None
    required_cards: tuple[str, ...] = ()


@dataclass(frozen=True)
class DesignedDeck:
    format_name: str
    engine: Engine
    reference: GroupSummary
    commander: PoolCard | None
    nonland_cards: tuple[tuple[PoolCard, int], ...]
    lands: tuple[tuple[PoolCard, int], ...]
    unfilled_slots: int


def design_deck(
    pool: dict[str, PoolCard], lessons: FormatLessons, engine: Engine, tagger: MechanicTagger
) -> DesignedDeck:
    commander = _find_commander(pool, engine.commander, lessons.format_name)
    if commander:
        engine = replace(engine, colors=frozenset(commander.card.color_identity))
    if not engine.colors:
        raise DeckNotDesigned("An engine needs at least one color.")
    reference = reference_group(lessons, engine.mechanic)
    land_count = round(reference.land_count)
    picker = _NonlandPicker(engine, reference, lessons, tagger, lessons.main_deck_size - land_count)
    for card_name in engine.required_cards:
        required = _find_in_pool(pool, card_name, lessons.format_name)
        if not set(required.card.color_identity) <= engine.colors:
            raise DeckNotDesigned(f"{card_name} is outside the deck colors.")
        picker.add(required, min(copy_limit(required, lessons.format_name), picker.free_slots()))
    picker.fill([
        pool_card for pool_card in pool.values()
        if _fits_the_deck(pool_card, engine.colors, engine.commander, lessons.format_name)
    ])
    nonland_cards = picker.chosen_cards()
    unfilled_slots = picker.free_slots()
    commander_cards = ((commander, 1),) if commander else ()
    return DesignedDeck(
        format_name=lessons.format_name,
        engine=engine,
        reference=reference,
        commander=commander,
        nonland_cards=nonland_cards,
        lands=build_mana_base(
            pool, engine.colors, land_count + unfilled_slots, nonland_cards + commander_cards,
            lessons.format_name,
        ),
        unfilled_slots=unfilled_slots,
    )


def reference_group(lessons: FormatLessons, mechanic: str) -> GroupSummary:
    return next((group for group in lessons.by_mechanic if group.label == mechanic), lessons.all_decks)


def build_mana_base(
    pool: dict[str, PoolCard],
    colors: frozenset[str],
    land_count: int,
    nonland_cards: tuple[tuple[PoolCard, int], ...],
    format_name: str,
) -> tuple[tuple[PoolCard, int], ...]:
    lands = []
    if len(colors) >= 2:
        fixing_budget = int(land_count * SHARE_OF_FIXING_LANDS)
        for pool_card in _fixing_lands(pool, colors):
            copies = min(copy_limit(pool_card, format_name), fixing_budget)
            if copies:
                lands.append((pool_card, copies))
                fixing_budget -= copies
    basic_land_count = land_count - sum(copies for _, copies in lands)
    lands.extend(_basic_lands(pool, colors, basic_land_count, nonland_cards))
    return tuple(lands)


def suggest_engines(
    pool: dict[str, PoolCard], lessons: FormatLessons, tagger: MechanicTagger, count: int
) -> list[Engine]:
    """Engines the collection can carry, best first (see _option_score), each with a different
    mechanic and, in Brawl, a different commander."""
    tags_by_name = {name: frozenset(tagger.tags_for(pool_card.card)) for name, pool_card in pool.items()}
    if is_brawl_format(lessons.format_name):
        options = _commander_options(pool, tags_by_name, lessons)
    else:
        options = _color_options(pool, tags_by_name, lessons)
    chosen, used_mechanics, used_commanders = [], set(), set()
    for engine in (option.engine for option in sorted(options, key=_option_order)):
        if engine.mechanic in used_mechanics or engine.commander in used_commanders:
            continue
        chosen.append(engine)
        used_mechanics |= {engine.mechanic} | partner_mechanics_of(engine.mechanic)
        if engine.commander:
            used_commanders.add(engine.commander)
        if len(chosen) == count:
            break
    return chosen


def best_engine_for_commander(
    pool: dict[str, PoolCard], lessons: FormatLessons, tagger: MechanicTagger, commander_name: str
) -> Engine:
    commander = _find_commander(pool, commander_name, lessons.format_name)
    tags_by_name = {name: frozenset(tagger.tags_for(pool_card.card)) for name, pool_card in pool.items()}
    options = _commander_options(pool, tags_by_name, lessons, only_commander=commander.name)
    if not options:
        raise DeckNotDesigned(f"{commander_name} has no mechanic with enough owned cards in its colors.")
    return min(options, key=_option_order).engine


def engine_card_copies(deck: DesignedDeck, tagger: MechanicTagger) -> int:
    """Nonland copies with the engine mechanic, its partner mechanic or a member type."""
    partner_mechanics = partner_mechanics_of(deck.engine.mechanic)
    copies = 0
    for pool_card, card_copies in deck.nonland_cards:
        tags = set(tagger.tags_for(pool_card.card))
        if (deck.engine.mechanic in tags or tags & partner_mechanics
                or is_engine_member(pool_card.card, deck.engine.mechanic)):
            copies += card_copies
    return copies


def is_engine_member(card: Card, mechanic: str) -> bool:
    """Part of the engine by type: a Goblin for tribo:goblin, an instant for magicas."""
    if mechanic.startswith(TRIBE_PREFIX):
        tribe = mechanic.removeprefix(TRIBE_PREFIX)
        return tribe in {creature_type.lower() for creature_type in creature_types_of(card.type_line)}
    front_face = card.type_line.split("//")[0]
    return any(card_type in front_face for card_type in MEMBER_CARD_TYPES.get(mechanic, ()))


def is_commander_candidate(card: Card) -> bool:
    front_face = card.type_line.split("//")[0]
    return "Legendary" in front_face and ("Creature" in front_face or "Planeswalker" in front_face)


def archetype_title(mechanic: str) -> str:
    if mechanic.startswith(TRIBE_PREFIX):
        return plural_of(mechanic.removeprefix(TRIBE_PREFIX).capitalize())
    words = mechanic.replace("-", " ")
    return words[:1].upper() + words[1:]


def designed_deck_name(deck: DesignedDeck) -> str:
    archetype = archetype_title(deck.engine.mechanic)
    if deck.commander:
        return f"{deck.commander.name.split(',')[0]} {archetype} {DESIGNER_SUFFIX}"
    colors = color_combination_name("".join(deck.engine.colors)).replace("-", " ").title()
    return f"{colors} {archetype} {DESIGNER_SUFFIX}"


def designed_deck_folder(deck: DesignedDeck) -> DeckFolder:
    return DeckFolder(deck.format_name, "".join(deck.engine.colors), archetype_title(deck.engine.mechanic))


def to_arena_decklist(deck: DesignedDeck) -> ArenaDecklist:
    nonland_cards = sorted(deck.nonland_cards, key=lambda item: (item[0].card.mana_value, item[0].name))
    return ArenaDecklist(
        name=designed_deck_name(deck),
        main=tuple(_deck_card(pool_card, copies) for pool_card, copies in [*nonland_cards, *deck.lands]),
        commander=_deck_card(deck.commander, 1) if deck.commander else None,
    )


class _NonlandPicker:
    """Adds nonland cards one copy at a time, always the best scoring one."""

    def __init__(self, engine: Engine, reference: GroupSummary, lessons: FormatLessons,
                 tagger: MechanicTagger, slot_count: int):
        self.engine = engine
        self.format_name = lessons.format_name
        self.tagger = tagger
        self.slot_count = slot_count
        self.card_presence = lessons.card_presence
        self.partner_mechanics = partner_mechanics_of(engine.mechanic)
        self.meta_partner_mechanics = (
            _partners_in(lessons.mechanics_played_together, engine.mechanic)
            - self.partner_mechanics - {engine.mechanic}
        )
        self.card_partners = _card_partners(lessons.cards_played_together)
        reference_nonland_count = sum(reference.curve)
        scale = slot_count / reference_nonland_count if reference_nonland_count else 0.0
        self.curve_targets = [copies * scale for copies in reference.curve]
        self.creature_target = reference.creature_count * scale
        self.role_targets = {tag: copies * scale for tag, copies in reference.role_counts.items()}
        self.copies = Counter()
        self.chosen = {}
        self.curve = [0] * len(reference.curve)
        self.creature_count = 0
        self.role_counts = Counter()
        self._tags = {}

    def free_slots(self) -> int:
        return self.slot_count - sum(self.copies.values())

    def add(self, pool_card: PoolCard, copies: int) -> None:
        card = pool_card.card
        self.chosen.setdefault(pool_card.name, pool_card)
        self.copies[pool_card.name] += copies
        self.curve[curve_bucket_of(card.mana_value)] += copies
        if is_creature(card):
            self.creature_count += copies
        for tag in self.tags_of(card):
            self.role_counts[tag] += copies

    def fill(self, candidates: list[PoolCard]) -> None:
        while self.free_slots() > 0:
            available = [
                pool_card for pool_card in candidates
                if self.copies[pool_card.name] < copy_limit(pool_card, self.format_name)
            ]
            if not available:
                return
            self.add(min(available, key=lambda pool_card: (-self.score(pool_card), pool_card.name)), 1)

    def chosen_cards(self) -> tuple[tuple[PoolCard, int], ...]:
        return tuple((pool_card, self.copies[name]) for name, pool_card in self.chosen.items())

    def score(self, pool_card: PoolCard) -> float:
        card = pool_card.card
        tags = self.tags_of(card)
        synergy_partners = len(self.card_partners.get(card.name, set()) & self.chosen.keys())
        score = (
            self._engine_score(card, tags)
            + META_PRESENCE_WEIGHT * self.card_presence.get(card.name, 0.0)
            + SYNERGY_WEIGHT * min(synergy_partners, MAXIMUM_SYNERGY_PARTNERS)
            + self._need_score(card, tags)
        )
        if self.copies[card.name]:
            score += CONSISTENCY_WEIGHT
        return score

    def tags_of(self, card: Card) -> frozenset[str]:
        if card.name not in self._tags:
            self._tags[card.name] = frozenset(self.tagger.tags_for(card))
        return self._tags[card.name]

    def _engine_score(self, card: Card, tags: frozenset[str]) -> float:
        if self.engine.mechanic in tags:
            return ENGINE_WEIGHT
        if tags & self.partner_mechanics or is_engine_member(card, self.engine.mechanic):
            return PARTNER_WEIGHT
        if tags & self.meta_partner_mechanics:
            return META_PARTNER_WEIGHT
        return 0.0

    def _need_score(self, card: Card, tags: frozenset[str]) -> float:
        if is_creature(card):
            lacks_this_kind = self.creature_count < self.creature_target
        else:
            noncreature_count = sum(self.copies.values()) - self.creature_count
            lacks_this_kind = noncreature_count < self.slot_count - self.creature_target
        bucket = curve_bucket_of(card.mana_value)
        lacks_this_mana_value = self.curve[bucket] < self.curve_targets[bucket]
        roles_lacking = sum(
            1 for tag in tags if tag in self.role_targets and self.role_counts[tag] < self.role_targets[tag]
        )
        return NEED_WEIGHT * (
            (1 if lacks_this_kind else -1) + (1 if lacks_this_mana_value else -1) + roles_lacking
        )


def _find_commander(pool: dict[str, PoolCard], commander_name: str | None, format_name: str) -> PoolCard | None:
    if commander_name is None:
        return None
    commander = _find_in_pool(pool, commander_name, format_name)
    if not is_commander_candidate(commander.card):
        raise DeckNotDesigned(f"{commander_name} is not a legendary creature or planeswalker.")
    return commander


def _find_in_pool(pool: dict[str, PoolCard], card_name: str, format_name: str) -> PoolCard:
    if card_name not in pool:
        raise DeckNotDesigned(f"{card_name} is not in the collection or not legal in {format_name}.")
    return pool[card_name]


def _fits_the_deck(pool_card: PoolCard, colors: frozenset[str], commander_name: str | None, format_name: str) -> bool:
    card = pool_card.card
    return (
        not is_land(card)
        and card.name != commander_name
        and set(card.color_identity) <= colors
        and copy_limit(pool_card, format_name) > 0
    )


def _partners_in(pairs: tuple[PlayedTogether, ...], item: str) -> set[str]:
    return {pair.second if pair.first == item else pair.first for pair in pairs if item in (pair.first, pair.second)}


def _card_partners(pairs: tuple[PlayedTogether, ...]) -> dict[str, set[str]]:
    partners = {}
    for pair in pairs:
        partners.setdefault(pair.first, set()).add(pair.second)
        partners.setdefault(pair.second, set()).add(pair.first)
    return partners


def _fixing_lands(pool: dict[str, PoolCard], colors: frozenset[str]) -> list[PoolCard]:
    fixing = []
    for pool_card in pool.values():
        card = pool_card.card
        if not is_land(card) or is_basic_land(card):
            continue
        identity = set(card.color_identity)
        if ANY_COLOR_TEXT in card.rules_text.lower() or (len(identity) >= 2 and identity <= colors):
            fixing.append(pool_card)
    return sorted(
        fixing,
        key=lambda pool_card: (
            -len(set(pool_card.card.color_identity) & colors), -pool_card.owned_copies, pool_card.name
        ),
    )


def _basic_lands(
    pool: dict[str, PoolCard], colors: frozenset[str], count: int, nonland_cards: tuple[tuple[PoolCard, int], ...]
) -> list[tuple[PoolCard, int]]:
    if count <= 0:
        return []
    deck_colors = [color for color in COLOR_ORDER if color in colors]
    symbols = Counter()
    for pool_card, copies in nonland_cards:
        for color in COLORED_MANA_SYMBOL.findall(pool_card.card.mana_cost):
            if color in colors:
                symbols[color] += copies
    weights = [symbols[color] for color in deck_colors] if symbols else [1] * len(deck_colors)
    split = _split_by_largest_remainder(count, weights)
    return [
        (pool[BASIC_LAND_NAMES[color]], copies) for color, copies in zip(deck_colors, split) if copies > 0
    ]


def _split_by_largest_remainder(total: int, weights: list[int]) -> list[int]:
    shares = [total * weight / sum(weights) for weight in weights]
    counts = [int(share) for share in shares]
    by_remainder = sorted(range(len(weights)), key=lambda index: (-(shares[index] - counts[index]), index))
    for index in by_remainder[: total - sum(counts)]:
        counts[index] += 1
    return counts


def _engine_card_copies(
    pool: dict[str, PoolCard], tags_by_name: dict[str, frozenset[str]], mechanic: str,
    colors: frozenset[str], format_name: str, commander_name: str | None = None,
) -> tuple[int, int]:
    """Copies of the cards with the mechanic itself (core) and of its partner or member cards."""
    partner_mechanics = partner_mechanics_of(mechanic)
    core_copies = partner_copies = 0
    for name, pool_card in pool.items():
        if not _fits_the_deck(pool_card, colors, commander_name, format_name):
            continue
        tags = tags_by_name[name]
        if mechanic in tags:
            core_copies += copy_limit(pool_card, format_name)
        elif tags & partner_mechanics or is_engine_member(pool_card.card, mechanic):
            partner_copies += copy_limit(pool_card, format_name)
    return core_copies, partner_copies


@dataclass(frozen=True)
class _EngineOption:
    score: float
    engine_cards: int
    engine: Engine


def _engine_option(
    pool, tags_by_name, lessons: FormatLessons, engine: Engine
) -> _EngineOption | None:
    """The engine when the collection carries it, with its score: engine cards up to the nonland
    slots, since more cards than slots add nothing, where partner cards count up to the core ones
    (a payoff needs enablers, and the reverse). Each color after the first costs a share, for the
    weaker mana; mechanics the meta builds around gain their share of the meta."""
    nonland_slots = lessons.main_deck_size - round(lessons.all_decks.land_count)
    core, partners = _engine_card_copies(
        pool, tags_by_name, engine.mechanic, engine.colors, lessons.format_name, engine.commander
    )
    if core < nonland_slots * CORE_SHARE_OF_NONLAND_SLOTS or core + partners < nonland_slots * ENGINE_SHARE_OF_NONLAND_SLOTS:
        return None
    engine_cards = core + min(partners, core)
    meta_share = next((group.weight_share for group in lessons.by_mechanic if group.label == engine.mechanic), 0.0)
    score = min(engine_cards, nonland_slots) * EXTRA_COLOR_FACTOR ** (len(engine.colors) - 1) * (1 + meta_share)
    return _EngineOption(score, engine_cards, engine)


def _color_options(pool, tags_by_name, lessons) -> list[_EngineOption]:
    mechanics = {
        tag for name, tags in tags_by_name.items() if not is_land(pool[name].card) for tag in tags
    } - MECHANICS_THAT_ARE_NOT_ENGINES
    options = (
        _engine_option(pool, tags_by_name, lessons, Engine(mechanic, colors))
        for mechanic in mechanics
        for colors in ONE_AND_TWO_COLOR_OPTIONS
    )
    return [option for option in options if option is not None]


def _commander_options(pool, tags_by_name, lessons, only_commander: str | None = None) -> list[_EngineOption]:
    options = []
    for name, pool_card in pool.items():
        colors = frozenset(pool_card.card.color_identity)
        if not is_commander_candidate(pool_card.card) or not colors:
            continue
        if only_commander is not None and name != only_commander:
            continue
        for mechanic in tags_by_name[name] - MECHANICS_THAT_ARE_NOT_ENGINES:
            option = _engine_option(pool, tags_by_name, lessons, Engine(mechanic, colors, commander=name))
            if option is not None:
                options.append(option)
    return options


def _option_order(option: _EngineOption) -> tuple:
    """Best score first; on a tie, more engine cards, then fewer colors."""
    engine = option.engine
    colors = "".join(color for color in COLOR_ORDER if color in engine.colors)
    return -option.score, -option.engine_cards, len(engine.colors), engine.mechanic, colors, engine.commander or ""


def _deck_card(pool_card: PoolCard, copies: int) -> DeckCard:
    card = pool_card.card
    return DeckCard(copies, card.name, card.set_code, card.collector_number)
