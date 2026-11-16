"""Builds a tiny copy of the game's card database for tests.

Only the columns the catalog reads are created, with the same names the game uses.
"""

import sqlite3
from pathlib import Path

CARD_COLUMN_DEFAULTS = {
    "GrpId": 0,
    "TitleId": 0,
    "TypeTextId": 0,
    "SubtypeTextId": 0,
    "Rarity": 0,
    "ExpansionCode": "",
    "DigitalReleaseSet": "",
    "CollectorNumber": "",
    "OldSchoolManaText": "",
    "Colors": "",
    "ColorIdentity": "",
    "Power": "",
    "Toughness": "",
    "AbilityIds": "",
    "IsToken": 0,
    "IsPrimaryCard": 1,
    "IsDigitalOnly": 0,
    "IsRebalanced": 0,
}

PICARD_ARENA_ID = 106584
RELEASE_TO_THE_WIND_ARENA_ID = 66709
SIMIC_GOLD_CARD_ARENA_ID = 70001
ISLAND_ARENA_ID = 75557

SAMPLE_CARDS = [
    {
        "GrpId": PICARD_ARENA_ID,
        "TitleId": 100,
        "TypeTextId": 200,
        "SubtypeTextId": 201,
        "Rarity": 5,
        "ExpansionCode": "TRK",
        "CollectorNumber": "7",
        "OldSchoolManaText": "o2oW",
        "Colors": "1",
        "ColorIdentity": "1",
        "Power": "2",
        "Toughness": "3",
        "AbilityIds": "2433:300,208450:301",
    },
    {
        "GrpId": RELEASE_TO_THE_WIND_ARENA_ID,
        "TitleId": 101,
        "TypeTextId": 202,
        "Rarity": 4,
        "ExpansionCode": "RIX",
        "CollectorNumber": "46",
        "OldSchoolManaText": "o2oU",
        "Colors": "2",
        "ColorIdentity": "2",
        "AbilityIds": "9001:302",
    },
    {
        "GrpId": SIMIC_GOLD_CARD_ARENA_ID,
        "TitleId": 102,
        "TypeTextId": 203,
        "Rarity": 3,
        "ExpansionCode": "Y24",
        "DigitalReleaseSet": "Y24-OTJ",
        "CollectorNumber": "12",
        "OldSchoolManaText": "o1o(U/G)o(U/G)",
        "Colors": "2,5",
        "ColorIdentity": "2,5",
        "IsDigitalOnly": 1,
        "IsRebalanced": 1,
    },
    {
        "GrpId": ISLAND_ARENA_ID,
        "TitleId": 103,
        "TypeTextId": 204,
        "SubtypeTextId": 205,
        "Rarity": 1,
        "ExpansionCode": "FDN",
        "CollectorNumber": "273",
    },
]

SAMPLE_ENGLISH_TEXTS = {
    100: "Captain <nobr>Jean-Luc</nobr> Picard",
    101: "Release to the Wind",
    102: "Simic Test Card",
    103: "Island",
    200: "Legendary Creature",
    201: "Human Officer",
    202: "Instant",
    203: "Sorcery",
    204: "Basic Land",
    205: "Island",
    300: "Other creatures you control get <nobr>+1/+1</nobr>.",
    301: "{o1}, {oT}: CARDNAME deals 1 damage to any target.",
    302: "Exile target nonland permanent. <i>(You may cast it this turn.)</i>",
}

SAMPLE_PORTUGUESE_TEXTS = {
    100: "Capitão <nobr>Jean-Luc</nobr> Picard",
    101: "Soltar ao Vento",
    103: "Ilha",
}


def create_card_database(
    database_path: Path,
    cards: list[dict] = SAMPLE_CARDS,
    english_texts: dict[int, str] = SAMPLE_ENGLISH_TEXTS,
    portuguese_texts: dict[int, str] = SAMPLE_PORTUGUESE_TEXTS,
) -> Path:
    connection = sqlite3.connect(database_path)
    try:
        column_names = list(CARD_COLUMN_DEFAULTS)
        connection.execute(f"CREATE TABLE Cards({', '.join(column_names)})")
        for card in cards:
            values = [card.get(name, default) for name, default in CARD_COLUMN_DEFAULTS.items()]
            placeholders = ", ".join("?" for _ in column_names)
            connection.execute(f"INSERT INTO Cards VALUES ({placeholders})", values)

        for table_name, texts in (
            ("Localizations_enUS", english_texts),
            ("Localizations_ptBR", portuguese_texts),
        ):
            connection.execute(f"CREATE TABLE {table_name}(LocId, Formatted, Loc)")
            connection.executemany(
                f"INSERT INTO {table_name} VALUES (?, 1, ?)",
                list(texts.items()),
            )
        connection.commit()
    finally:
        connection.close()
    return database_path
