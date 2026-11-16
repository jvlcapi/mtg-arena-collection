"""Where MTG Arena keeps its files on macOS."""

from pathlib import Path

GAME_SUPPORT_DIRECTORY = Path.home() / "Library/Application Support/com.wizards.mtga"
RAW_DOWNLOADS_DIRECTORY = GAME_SUPPORT_DIRECTORY / "Downloads/Raw"
CARD_DATABASE_PATTERN = "Raw_CardDatabase_*.mtga"


class CardDatabaseNotFound(FileNotFoundError):
    pass


def find_card_database(raw_downloads_directory: Path = RAW_DOWNLOADS_DIRECTORY) -> Path:
    databases = sorted(
        Path(raw_downloads_directory).glob(CARD_DATABASE_PATTERN),
        key=lambda path: path.stat().st_mtime,
    )
    if not databases:
        raise CardDatabaseNotFound(
            f"No card database ({CARD_DATABASE_PATTERN}) in {raw_downloads_directory}. "
            "Open MTG Arena once so it downloads the card data."
        )
    return databases[-1]
