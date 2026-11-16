"""Reads card details from the game's local card database (Raw_CardDatabase_*.mtga).

Every card is keyed by its Arena id (the game's GrpId), the same id the collection uses.
"""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from mtg_arena_collection.mana_symbols import (
    calculate_mana_value,
    convert_arena_mana_text,
    convert_symbols_in_rules_text,
)

RARITY_NAMES = {0: "token", 1: "basic", 2: "common", 3: "uncommon", 4: "rare", 5: "mythic"}
COLOR_LETTERS = {"1": "W", "2": "U", "3": "B", "4": "R", "5": "G"}
FORMATTING_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
CARD_NAME_PLACEHOLDER = "CARDNAME"
ALCHEMY_PREFIX = "A-"
FORMATTED_TEXT_VARIANT = 1

CARDS_QUERY = """
SELECT GrpId, TitleId, TypeTextId, SubtypeTextId, Rarity, ExpansionCode, DigitalReleaseSet,
       CollectorNumber, OldSchoolManaText, Colors, ColorIdentity, Power, Toughness, AbilityIds,
       IsDigitalOnly, IsRebalanced
FROM Cards
"""


@dataclass(frozen=True)
class Card:
    arena_id: int
    name: str
    portuguese_name: str
    set_code: str
    digital_release_set: str
    collector_number: str
    rarity: str
    mana_cost: str
    mana_value: int
    colors: str
    color_identity: str
    type_line: str
    power: str
    toughness: str
    rules_text: str
    is_digital_only: bool
    is_rebalanced: bool


def load_card_catalog(database_path: Path) -> dict[int, Card]:
    connection = sqlite3.connect(f"{Path(database_path).as_uri()}?mode=ro", uri=True)
    try:
        english_texts = _load_texts(connection, "Localizations_enUS")
        portuguese_texts = _load_texts(connection, "Localizations_ptBR")
        card_rows = connection.execute(CARDS_QUERY).fetchall()
    finally:
        connection.close()

    catalog = {}
    for row in card_rows:
        card = _build_card(row, english_texts, portuguese_texts)
        catalog[card.arena_id] = card
    return catalog


def _load_texts(connection: sqlite3.Connection, table_name: str) -> dict[int, str]:
    rows = connection.execute(
        f"SELECT LocId, Loc FROM {table_name} WHERE Formatted = ?", (FORMATTED_TEXT_VARIANT,)
    )
    return {text_id: _remove_formatting(text or "") for text_id, text in rows}


def _remove_formatting(text: str) -> str:
    return FORMATTING_TAG.sub("", text)


def _build_card(row: tuple, english_texts: dict[int, str], portuguese_texts: dict[int, str]) -> Card:
    (
        arena_id,
        title_id,
        type_text_id,
        subtype_text_id,
        rarity_code,
        set_code,
        digital_release_set,
        collector_number,
        arena_mana_text,
        color_codes,
        color_identity_codes,
        power,
        toughness,
        ability_ids,
        is_digital_only,
        is_rebalanced,
    ) = row
    name = _with_alchemy_prefix(english_texts.get(title_id, ""), is_rebalanced)
    mana_cost = convert_arena_mana_text(arena_mana_text or "")
    return Card(
        arena_id=arena_id,
        name=name,
        portuguese_name=_with_alchemy_prefix(portuguese_texts.get(title_id, ""), is_rebalanced),
        set_code=set_code or "",
        digital_release_set=digital_release_set or "",
        collector_number=collector_number or "",
        rarity=RARITY_NAMES.get(rarity_code, f"unknown-{rarity_code}"),
        mana_cost=mana_cost,
        mana_value=calculate_mana_value(mana_cost),
        colors=_color_letters(color_codes),
        color_identity=_color_letters(color_identity_codes),
        type_line=_type_line(english_texts, type_text_id, subtype_text_id),
        power=power or "",
        toughness=toughness or "",
        rules_text=_rules_text(english_texts, ability_ids, name),
        is_digital_only=bool(is_digital_only),
        is_rebalanced=bool(is_rebalanced),
    )


def _with_alchemy_prefix(name: str, is_rebalanced: int) -> str:
    """The game shows rebalanced cards with an "A" icon; Scryfall and deck sites write "A-"."""
    return f"{ALCHEMY_PREFIX}{name}" if name and is_rebalanced else name


def _color_letters(color_codes: str) -> str:
    return "".join(COLOR_LETTERS[code] for code in (color_codes or "").split(",") if code)


def _type_line(english_texts: dict[int, str], type_text_id: int, subtype_text_id: int) -> str:
    types = english_texts.get(type_text_id, "")
    subtypes = english_texts.get(subtype_text_id, "")
    return f"{types} — {subtypes}" if subtypes else types


def _rules_text(english_texts: dict[int, str], ability_ids: str, card_name: str) -> str:
    ability_texts = []
    for ability_and_text_id in (ability_ids or "").split(","):
        if ":" not in ability_and_text_id:
            continue
        text_id = int(ability_and_text_id.split(":")[1])
        text = english_texts.get(text_id, "")
        if text:
            text = text.replace(CARD_NAME_PLACEHOLDER, card_name)
            ability_texts.append(convert_symbols_in_rules_text(text))
    return "\n".join(ability_texts)
