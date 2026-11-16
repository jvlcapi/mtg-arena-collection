"""Deck files that MTG Arena imports from the clipboard (Decks → Import).

Arena has no official spec; community references agree on optional sections in this order,
each title on its own line and a blank line after it: About (with `Name <deck name>`),
Commander (one card), Companion (one card, also listed in the sideboard), Deck (required) and
Sideboard. Cards are `4 Card Name (SET) 123`: the set code and collector number pick the
printing, and Arena rejects collector numbers with leading zeros. Importing does not set the
deck's format; Arena asks for it afterwards.

Decks live at `decks/<format>/<colors>/<archetype>/<deck name>.txt`, for example
`decks/historic-brawl/mono-red/goblins/krenko-goblins.txt`.
"""

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

SECTION_TITLES = ("About", "Commander", "Companion", "Deck", "Sideboard")
COLOR_ORDER = "WUBRG"
COLOR_COMBINATION_NAMES = {
    "": "colorless",
    "W": "mono-white", "U": "mono-blue", "B": "mono-black", "R": "mono-red", "G": "mono-green",
    "WU": "azorius", "UB": "dimir", "BR": "rakdos", "RG": "gruul", "WG": "selesnya",
    "WB": "orzhov", "UR": "izzet", "BG": "golgari", "WR": "boros", "UG": "simic",
    "WUB": "esper", "UBR": "grixis", "BRG": "jund", "WRG": "naya", "WUG": "bant",
    "WBG": "abzan", "WUR": "jeskai", "UBG": "sultai", "WBR": "mardu", "URG": "temur",
    "WUBRG": "five-color",
}
COLOR_NAMES = {"W": "white", "U": "blue", "B": "black", "R": "red", "G": "green"}
CARD_LINE = re.compile(r"^(?P<quantity>\d+)\s+(?P<rest>.+)$")
PRINTING_AT_THE_END = re.compile(r"^(?P<name>.+) \((?P<set_code>[0-9A-Za-z]+)\) (?P<number>\d+)$")


class DecklistNotSaved(ValueError):
    pass


@dataclass(frozen=True)
class DeckCard:
    quantity: int
    name: str
    set_code: str = ""
    collector_number: str = ""


@dataclass(frozen=True)
class ArenaDecklist:
    name: str
    main: tuple[DeckCard, ...]
    sideboard: tuple[DeckCard, ...] = ()
    commander: DeckCard | None = None
    companion: DeckCard | None = None


@dataclass(frozen=True)
class DeckFolder:
    format_name: str
    colors: str
    archetype: str


def format_arena_decklist(decklist: ArenaDecklist) -> str:
    sections = []
    if decklist.name:
        sections.append(["About", f"Name {decklist.name}"])
    if decklist.commander:
        sections.append(["Commander", format_card_line(decklist.commander)])
    if decklist.companion:
        sections.append(["Companion", format_card_line(decklist.companion)])
    sections.append(["Deck", *(format_card_line(card) for card in decklist.main)])
    sideboard = list(decklist.sideboard)
    if decklist.companion and decklist.companion.name not in {card.name for card in sideboard}:
        sideboard.append(decklist.companion)
    if sideboard:
        sections.append(["Sideboard", *(format_card_line(card) for card in sideboard)])
    return "\n\n".join("\n".join(section) for section in sections) + "\n"


def format_card_line(card: DeckCard) -> str:
    collector_number = card.collector_number.lstrip("0")
    if card.set_code and collector_number.isdigit():
        return f"{card.quantity} {card.name} ({card.set_code}) {collector_number}"
    return f"{card.quantity} {card.name}"


def parse_arena_decklist(text: str) -> ArenaDecklist:
    name = ""
    cards_by_section = {title: [] for title in SECTION_TITLES}
    section = "Deck"
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if line in SECTION_TITLES:
            section = line
        elif section == "About" and line.startswith("Name "):
            name = line.removeprefix("Name ").strip()
        elif match := CARD_LINE.match(line):
            cards_by_section[section].append(parse_card(int(match["quantity"]), match["rest"]))
    return ArenaDecklist(
        name=name,
        main=tuple(cards_by_section["Deck"]),
        sideboard=tuple(cards_by_section["Sideboard"]),
        commander=next(iter(cards_by_section["Commander"]), None),
        companion=next(iter(cards_by_section["Companion"]), None),
    )


def parse_card(quantity: int, name_and_printing: str) -> DeckCard:
    printing = PRINTING_AT_THE_END.match(name_and_printing)
    if printing is None:
        return DeckCard(quantity, name_and_printing)
    return DeckCard(quantity, printing["name"], printing["set_code"], printing["number"])


def color_combination_name(colors: str) -> str:
    letters = "".join(color for color in COLOR_ORDER if color in colors.upper())
    if letters in COLOR_COMBINATION_NAMES:
        return COLOR_COMBINATION_NAMES[letters]
    missing_color = next(color for color in COLOR_ORDER if color not in letters)
    return f"four-color-no-{COLOR_NAMES[missing_color]}"


def index_cards_by_name(catalog: dict) -> dict:
    """Card details by name, for decklists that only carry names and printings."""
    return {card.name: card for card in catalog.values()}


def decklist_colors(decklist: ArenaDecklist, cards_by_name: dict) -> str:
    """The commander's color identity in Brawl, otherwise the colors of the non-land cards."""
    if decklist.commander:
        commander = cards_by_name.get(decklist.commander.name)
        letters = set(commander.color_identity) if commander else set()
    else:
        letters = set()
        for deck_card in decklist.main:
            card = cards_by_name.get(deck_card.name)
            if card is not None and "Land" not in card.type_line.split("//")[0]:
                letters |= set(card.colors)
    return "".join(color for color in COLOR_ORDER if color in letters)


def deck_file_path(decks_directory: Path, deck_name: str, folder: DeckFolder) -> Path:
    file_name = slugify(deck_name)
    if not file_name:
        raise DecklistNotSaved(
            f"A deck needs a name with letters or digits to be saved, got {deck_name!r}."
        )
    return (
        Path(decks_directory)
        / slugify(split_joined_words(folder.format_name))
        / color_combination_name(folder.colors)
        / slugify(folder.archetype)
        / f"{file_name}.txt"
    )


def save_arena_deck(decks_directory: Path, decklist: ArenaDecklist, folder: DeckFolder) -> Path:
    """Writes the decklist to its folder, replacing an older version of the same deck."""
    path = deck_file_path(decks_directory, decklist.name, folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.partial")
    temporary_path.write_text(format_arena_decklist(decklist), encoding="utf-8")
    os.replace(temporary_path, path)
    return path


def slugify(text: str) -> str:
    without_accents = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", without_accents.lower()).strip("-")


def split_joined_words(text: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
