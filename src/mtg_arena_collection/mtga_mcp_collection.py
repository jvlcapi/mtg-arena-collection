"""Reads the collection that mtga-mcp (github.com/fkadriver/mtga-mcp) saved in its database.

mtga-mcp stores one row per printing in `collection (grp_id, count)`, with the same Arena ids
the card catalog uses. `mtga-mcp capture` adds the cards granted in the game logs.
"""

import sqlite3
from pathlib import Path

DEFAULT_MTGA_MCP_DATABASE = Path.home() / ".local/share/mtga-mcp/mtga.db"
COLLECTION_INSTRUCTIONS = (
    "Fill it with mtga-mcp first: with Detailed Logs on in MTG Arena, `mtga-mcp capture` adds the "
    "cards the game logs show. See the README."
)


class MtgaMcpCollectionUnavailable(RuntimeError):
    pass


def read_mtga_mcp_collection(database_path: Path = DEFAULT_MTGA_MCP_DATABASE) -> dict[int, int]:
    database_path = Path(database_path)
    if not database_path.exists():
        raise MtgaMcpCollectionUnavailable(
            f"No mtga-mcp database at {database_path}. {COLLECTION_INSTRUCTIONS}"
        )
    connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT grp_id, count FROM collection").fetchall()
    except sqlite3.OperationalError as error:
        raise MtgaMcpCollectionUnavailable(
            f"The mtga-mcp database has no collection yet ({error}). {COLLECTION_INSTRUCTIONS}"
        ) from error
    finally:
        connection.close()
    if not rows:
        raise MtgaMcpCollectionUnavailable(f"The mtga-mcp collection is empty. {COLLECTION_INSTRUCTIONS}")
    return {arena_id: count for arena_id, count in rows}
