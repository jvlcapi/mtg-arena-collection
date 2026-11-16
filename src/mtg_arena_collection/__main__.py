"""Command line for the MTG Arena collection exporter.

    python3 -m mtg_arena_collection import-from-mtga-mcp [--database PATH] [--output PATH] [--change-log PATH]
    python3 -m mtg_arena_collection refresh-collection [--mtga-mcp PATH] [--database PATH] [--output PATH] [--change-log PATH]
    python3 -m mtg_arena_collection install-automatic-refresh [--python PATH]
    python3 -m mtg_arena_collection uninstall-automatic-refresh
    python3 -m mtg_arena_collection save-deck --format NAME --archetype NAME [--name NAME] [--colors WUBRG] [--input PATH]
    python3 -m mtg_arena_collection learn-from-meta [--database PATH] [--output-directory PATH]
    python3 -m mtg_arena_collection design-decks --format NAME [--count N] [--mechanic TAG --colors WUBRG | --commander NAME [--mechanic TAG]] [--include NAME ...] [--database PATH]

import-from-mtga-mcp turns the collection saved by mtga-mcp into the CSV and logs what changed.
refresh-collection first adds the cards granted in the game logs (`mtga-mcp capture`). The
scheduled refresh runs it, so it prints nothing when nothing changed.
install-automatic-refresh schedules refresh-collection with launchd; uninstall removes it.
save-deck stores a decklist in MTG Arena's import format under decks/<format>/<colors>/<archetype>/,
reading it from standard input (for example `pbpaste` after Export in Arena) or --input.
learn-from-meta reads the meta decks mtga-mcp imported and writes what they teach (land count,
curve, roles, mechanics and cards played together) as a report and as JSON.
design-decks designs decks from the owned cards around an engine (a mechanic in some colors,
or a commander in Brawl), suggested from the collection or given, and saves them in decks/.
"""

import argparse
import functools
import shutil
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mtg_arena_collection.arena_deck_files import (
    DeckFolder,
    DecklistNotSaved,
    decklist_colors,
    index_cards_by_name,
    parse_arena_decklist,
    save_arena_deck,
)
from mtg_arena_collection.card_catalog import load_card_catalog
from mtg_arena_collection.card_mechanics import MechanicTagger
from mtg_arena_collection.card_pool import CardLegalityUnavailable, build_card_pool, read_legal_arena_ids
from mtg_arena_collection.collection_changes import (
    ChangeLogEntry,
    CollectionUpdate,
    PreviousCsvUnreadable,
    update_collection_csv,
)
from mtg_arena_collection.collection_csv import find_unknown_arena_ids
from mtg_arena_collection.collection_refresh import refresh_collection
from mtg_arena_collection.deck_designer import (
    DeckNotDesigned,
    Engine,
    best_engine_for_commander,
    design_deck,
    designed_deck_folder,
    suggest_engines,
    to_arena_decklist,
)
from mtg_arena_collection.designed_deck_summary import describe_designed_deck
from mtg_arena_collection.game_files import CardDatabaseNotFound, find_card_database
from mtg_arena_collection.launch_agent import (
    DEFAULT_LAUNCH_AGENT_PATH,
    DEFAULT_REFRESH_LOG_PATH,
    REFRESH_INTERVAL_SECONDS,
    LaunchAgentCommandFailed,
    build_launch_agent,
    install_launch_agent,
    uninstall_launch_agent,
)
from mtg_arena_collection.meta_decks import MetaDecksUnavailable, is_brawl_format, read_meta_decks
from mtg_arena_collection.meta_lessons import learn_from_meta
from mtg_arena_collection.meta_lessons_report import write_meta_lessons
from mtg_arena_collection.mtga_mcp_collection import (
    DEFAULT_MTGA_MCP_DATABASE,
    MtgaMcpCollectionUnavailable,
    read_mtga_mcp_collection,
)
from mtg_arena_collection.mtga_mcp_commands import (
    DEFAULT_MTGA_MCP_EXECUTABLE,
    MtgaMcpCommandFailed,
    run_capture,
)

PROJECT_DIRECTORY = Path(__file__).resolve().parents[2]
EXPORTS_DIRECTORY = PROJECT_DIRECTORY / "exports"
DEFAULT_CSV_PATH = EXPORTS_DIRECTORY / "collection.csv"
DEFAULT_CHANGE_LOG_PATH = EXPORTS_DIRECTORY / "collection-changes.csv"
DECKS_DIRECTORY = PROJECT_DIRECTORY / "decks"
DEFAULT_META_LESSONS_DIRECTORY = EXPORTS_DIRECTORY / "meta-lessons"
CHANGES_SHOWN_AT_MOST = 20
REFRESH_COMMAND = "refresh-collection"
EXPECTED_FAILURES = (
    CardDatabaseNotFound,
    CardLegalityUnavailable,
    DeckNotDesigned,
    DecklistNotSaved,
    LaunchAgentCommandFailed,
    MetaDecksUnavailable,
    MtgaMcpCollectionUnavailable,
    MtgaMcpCommandFailed,
    PreviousCsvUnreadable,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mtg_arena_collection")
    commands = parser.add_subparsers(dest="command", required=True)
    mtga_mcp_command = commands.add_parser(
        "import-from-mtga-mcp", help="Gera o CSV a partir da coleção salva pelo mtga-mcp."
    )
    add_csv_options(mtga_mcp_command)
    refresh_command = commands.add_parser(
        REFRESH_COMMAND,
        help="Soma as cartas novas dos logs do jogo (mtga-mcp capture) e atualiza o CSV.",
    )
    add_mtga_mcp_executable_option(refresh_command)
    add_csv_options(refresh_command)
    install_command = commands.add_parser(
        "install-automatic-refresh",
        help=f"Agenda o {REFRESH_COMMAND} a cada {REFRESH_INTERVAL_SECONDS // 60} minutos (launchd).",
    )
    install_command.add_argument(
        "--python", type=Path, default=None, help="Python 3.10+ que o agendamento usa."
    )
    commands.add_parser("uninstall-automatic-refresh", help="Remove o agendamento.")
    save_command = commands.add_parser(
        "save-deck",
        help="Salva uma lista no formato do Arena em decks/<formato>/<cores>/<tipo>/.",
    )
    save_command.add_argument(
        "--format", dest="format_name", required=True,
        help="Formato do deck: Standard, Historic, Historic Brawl...",
    )
    save_command.add_argument(
        "--archetype", required=True, help="Tipo do deck, como Goblins ou Ganho de vida."
    )
    save_command.add_argument(
        "--name", default=None, help="Nome do deck; obrigatório se a lista não tiver About/Name."
    )
    save_command.add_argument(
        "--colors", default=None, help="Cores em letras WUBRG; sem isso, saem das cartas."
    )
    save_command.add_argument(
        "--input", type=Path, default=None, help="Arquivo com a lista; sem isso, lê da entrada."
    )
    meta_command = commands.add_parser(
        "learn-from-meta",
        help="Aprende com os decks do meta: terrenos, curva, papéis e o que anda junto.",
    )
    meta_command.add_argument(
        "--database", type=Path, default=DEFAULT_MTGA_MCP_DATABASE, help="Banco do mtga-mcp."
    )
    meta_command.add_argument(
        "--output-directory", type=Path, default=DEFAULT_META_LESSONS_DIRECTORY,
        help="Pasta do relatório e do JSON.",
    )
    design_command = commands.add_parser(
        "design-decks",
        help="Desenha decks com as suas cartas em volta de uma mecânica ou comandante e salva em decks/.",
    )
    design_command.add_argument(
        "--format", dest="format_name", required=True, help="Standard, Historic ou HistoricBrawl."
    )
    design_command.add_argument(
        "--count", type=int, default=3, help="Quantos decks sugerir, sem --mechanic e sem --commander."
    )
    design_command.add_argument(
        "--mechanic", default=None, help="Mecânica do motor, como ganho-de-vida ou tribo:goblin."
    )
    design_command.add_argument(
        "--colors", default=None, help="Cores do deck em letras WUBRG, junto com --mechanic."
    )
    design_command.add_argument("--commander", default=None, help="Comandante, no Brawl.")
    design_command.add_argument(
        "--include", action="append", default=[],
        help="Carta que tem de entrar; repita para várias, como as peças de um combo.",
    )
    design_command.add_argument(
        "--database", type=Path, default=DEFAULT_MTGA_MCP_DATABASE, help="Banco do mtga-mcp."
    )
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "import-from-mtga-mcp":
            import_from_mtga_mcp(arguments.database, arguments.output, arguments.change_log)
            return 0
        if arguments.command == REFRESH_COMMAND:
            return refresh_from_game_logs(
                arguments.mtga_mcp, arguments.database, arguments.output, arguments.change_log
            )
        if arguments.command == "install-automatic-refresh":
            return install_automatic_refresh(arguments.python)
        if arguments.command == "uninstall-automatic-refresh":
            return uninstall_automatic_refresh()
        if arguments.command == "save-deck":
            return save_deck(
                arguments.input, arguments.name, arguments.format_name, arguments.archetype,
                arguments.colors,
            )
        if arguments.command == "learn-from-meta":
            return learn_from_meta_decks(arguments.database, arguments.output_directory)
        return design_decks(
            arguments.format_name, arguments.count, arguments.mechanic, arguments.colors,
            arguments.commander, tuple(arguments.include), arguments.database,
        )
    except EXPECTED_FAILURES as failure:
        report_failure(arguments.command, failure)
        return 1


def add_csv_options(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument(
        "--database", type=Path, default=DEFAULT_MTGA_MCP_DATABASE, help="Banco do mtga-mcp."
    )
    command_parser.add_argument(
        "--output", type=Path, default=DEFAULT_CSV_PATH, help="Onde salvar o CSV."
    )
    command_parser.add_argument(
        "--change-log",
        type=Path,
        default=DEFAULT_CHANGE_LOG_PATH,
        help="Onde registrar o que mudou na coleção.",
    )


def add_mtga_mcp_executable_option(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument(
        "--mtga-mcp",
        type=Path,
        default=DEFAULT_MTGA_MCP_EXECUTABLE,
        help="Executável do mtga-mcp (o da pasta .venv dele).",
    )


def import_from_mtga_mcp(
    database_path: Path, output_path: Path, change_log_path: Path
) -> CollectionUpdate:
    load_catalog = create_catalog_loader()
    collection = read_mtga_mcp_collection(database_path)
    update = update_collection_csv(
        collection,
        load_catalog,
        output_path,
        change_log_path,
        current_time(),
        rewrite_when_unchanged=True,
    )
    print(
        f"Coleção do mtga-mcp: {len(collection)} impressões, "
        f"{sum(collection.values())} cópias."
    )
    print(f"CSV: {output_path}")
    print_changes(update, change_log_path)
    warn_about_unknown_cards(collection, load_catalog())
    return update


def refresh_from_game_logs(
    mtga_mcp_executable: Path, database_path: Path, output_path: Path, change_log_path: Path
) -> int:
    load_catalog = create_catalog_loader()
    update = refresh_collection(
        run_capture=lambda: run_capture(mtga_mcp_executable),
        update_csv=lambda: update_collection_csv(
            read_mtga_mcp_collection(database_path),
            load_catalog,
            output_path,
            change_log_path,
            current_time(),
        ),
    )
    if update.csv_written:
        print(f"{current_time()} CSV atualizado pelos logs do jogo: {output_path}")
        print_changes(update, change_log_path)
    return 0


def install_automatic_refresh(python_executable: Path | None) -> int:
    launch_agent = build_launch_agent(
        PROJECT_DIRECTORY, python_executable or find_python_executable(), DEFAULT_REFRESH_LOG_PATH
    )
    install_launch_agent(launch_agent, DEFAULT_LAUNCH_AGENT_PATH)
    print(
        f"Atualização automática instalada: roda a cada {REFRESH_INTERVAL_SECONDS // 60} "
        "minutos e uma vez agora."
    )
    print(f"Agendamento: {DEFAULT_LAUNCH_AGENT_PATH}")
    print(f"Registro das execuções: {DEFAULT_REFRESH_LOG_PATH}")
    return 0


def find_python_executable() -> Path:
    python_path = shutil.which("python3")
    if python_path is None:
        raise LaunchAgentCommandFailed(
            "python3 is not on PATH; pass --python with the Python 3.10+ the schedule should use."
        )
    return Path(python_path)


def uninstall_automatic_refresh() -> int:
    uninstall_launch_agent(DEFAULT_LAUNCH_AGENT_PATH)
    print("Atualização automática removida.")
    return 0


def save_deck(
    input_path: Path | None, deck_name: str | None, format_name: str, archetype: str,
    colors: str | None,
) -> int:
    text = input_path.read_text(encoding="utf-8") if input_path else sys.stdin.read()
    decklist = parse_arena_decklist(text)
    if deck_name:
        decklist = replace(decklist, name=deck_name)
    if not decklist.main:
        raise DecklistNotSaved("The list has no cards. Copy it with Export in MTG Arena and try again.")
    if not decklist.name:
        raise DecklistNotSaved("The list has no About/Name section; give the deck a name with --name.")
    if colors is None:
        colors = decklist_colors(
            decklist, index_cards_by_name(load_card_catalog(find_card_database()))
        )
    path = save_arena_deck(DECKS_DIRECTORY, decklist, DeckFolder(format_name, colors, archetype))
    print(f"Deck salvo: {path}")
    return 0


def learn_from_meta_decks(database_path: Path, output_directory: Path) -> int:
    decks = read_meta_decks(database_path)
    lessons = learn_from_meta(decks, load_card_catalog(find_card_database()))
    report_path, json_path = write_meta_lessons(lessons, output_directory, current_time())
    deck_counts = ", ".join(f"{lesson.format_name} {lesson.all_decks.deck_count}" for lesson in lessons)
    print(f"Decks do meta lidos: {len(decks)} ({deck_counts}).")
    print(f"Relatório: {report_path}")
    print(f"Dados para o designer de decks: {json_path}")
    return 0


def design_decks(
    format_name: str, count: int, mechanic: str | None, colors: str | None, commander: str | None,
    included_cards: tuple[str, ...], database_path: Path,
) -> int:
    format_name = format_name.replace(" ", "")
    catalog = load_card_catalog(find_card_database())
    tagger = MechanicTagger.from_catalog(catalog)
    [lessons] = learn_from_meta(read_meta_decks(database_path, formats={format_name}), catalog, tagger)
    pool = build_card_pool(
        read_mtga_mcp_collection(database_path), catalog, read_legal_arena_ids(database_path, format_name)
    )
    engines = choose_engines(pool, lessons, tagger, count, mechanic, colors, commander, included_cards)
    if not engines:
        print("Nenhuma mecânica tem cartas suficientes na coleção para este formato.")
        return 0
    for engine in engines:
        deck = design_deck(pool, lessons, engine, tagger)
        path = save_arena_deck(DECKS_DIRECTORY, to_arena_decklist(deck), designed_deck_folder(deck))
        print(describe_designed_deck(deck, str(path.relative_to(PROJECT_DIRECTORY)), catalog, tagger))
        print()
    return 0


def choose_engines(
    pool, lessons, tagger, count: int, mechanic: str | None, colors: str | None, commander: str | None,
    included_cards: tuple[str, ...],
) -> list[Engine]:
    if included_cards and not (mechanic or commander):
        raise DeckNotDesigned("Use --include together with --mechanic or --commander.")
    if commander:
        if mechanic:
            engine = Engine(mechanic, frozenset(), commander=commander)
        else:
            engine = best_engine_for_commander(pool, lessons, tagger, commander)
    elif mechanic:
        if is_brawl_format(lessons.format_name):
            raise DeckNotDesigned("Brawl decks need a commander: add --commander.")
        if not colors or not set(colors.upper()) <= set("WUBRG"):
            raise DeckNotDesigned("Give the deck colors with --colors, in WUBRG letters.")
        engine = Engine(mechanic, frozenset(colors.upper()))
    else:
        return suggest_engines(pool, lessons, tagger, count)
    return [replace(engine, required_cards=included_cards)]


def create_catalog_loader():
    """Loads the card catalog on the first call only (it takes about half a second)."""
    return functools.cache(lambda: load_card_catalog(find_card_database()))


def current_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def print_changes(update: CollectionUpdate, change_log_path: Path) -> None:
    if update.is_first_csv:
        return
    if not update.changes:
        print("Nenhuma quantidade mudou desde o último CSV.")
        return
    change_count = len(update.changes)
    change_word = "mudança" if change_count == 1 else "mudanças"
    print(f"{change_count} {change_word} desde o último CSV (registro em {change_log_path}):")
    for entry in update.changes[:CHANGES_SHOWN_AT_MOST]:
        print(f"  {describe_change_log_entry(entry)}")
    if change_count > CHANGES_SHOWN_AT_MOST:
        print(f"  … e mais {change_count - CHANGES_SHOWN_AT_MOST}")


def describe_change_log_entry(entry: ChangeLogEntry) -> str:
    name = entry.name or f"carta {entry.arena_id} (fora do catálogo)"
    set_code = f" ({entry.set_code})" if entry.set_code else ""
    return f"{name}{set_code}: {entry.previous_quantity} → {entry.new_quantity}"


def warn_about_unknown_cards(collection: dict[int, int], catalog: dict) -> None:
    unknown_arena_ids = find_unknown_arena_ids(collection, catalog)
    if unknown_arena_ids:
        print(
            f"Atenção: {len(unknown_arena_ids)} cartas não estão no catálogo do jogo "
            f"(primeiras: {unknown_arena_ids[:10]}). O jogo pode ter atualizado depois da exportação."
        )


def report_failure(command: str, failure: Exception) -> None:
    time_prefix = f"{current_time()} " if command == REFRESH_COMMAND else ""
    print(f"{time_prefix}Erro: {failure}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
