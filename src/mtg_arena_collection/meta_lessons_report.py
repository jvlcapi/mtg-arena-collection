"""Writes what the meta teaches (meta_lessons.py) as a Markdown report in Portuguese, to read,
and as JSON, for the deck designer."""

import json
import os
from dataclasses import asdict
from pathlib import Path

from mtg_arena_collection.meta_lessons import (
    MINIMUM_DECKS,
    MINIMUM_TIMES_MORE_THAN_CHANCE_FOR_CARDS,
    FormatLessons,
    GroupSummary,
    PlayedTogether,
)

REPORT_FILE_NAME = "meta-lessons.md"
JSON_FILE_NAME = "meta-lessons.json"
FORMAT_DISPLAY_NAMES = {"HistoricBrawl": "Historic Brawl"}
GROUP_DISPLAY_NAMES = {
    "todos": "Todos",
    "rapido": "Rápido (custo médio abaixo de 2)",
    "medio": "Médio (de 2 a 3)",
    "lento": "Lento (3 ou mais)",
}
REPORTED_ROLES = (("remocao", "Remoção"), ("compra", "Compra"), ("rampa", "Rampa"), ("anula", "Anula"))
EXAMPLE_AVERAGE_COSTS = (1.5, 2.5, 3.5)
MOST_PLAYED_CARDS_IN_THE_REPORT = 5
CARD_PAIRS_IN_THE_REPORT = 20
JSON_DECIMALS = 3

INTRODUCTION = """# O que o meta ensina

Gerado em {generated_at} a partir de {deck_count} decks do meta (Bo1) que o mtga-mcp importou
do AetherHub: a lista dos mais jogados, com a fatia do meta de cada deck, e a lista dos melhores
resultados, com o win rate.

Como ler:

- **Peso**: cada deck pesa a fatia do meta (ou o win rate) dividida pela média da sua lista. A
  coluna Peso diz quanto do meta, somando esses pesos, cai em cada grupo.
- **Contagens**: por deck de 60 cartas (99 no Historic Brawl, fora o comandante).
- **Curva**: quantas mágicas (as cartas que não são terreno) custam 1 ou menos, 2, 3, 4, 5 e 6 ou
  mais.
- **Mecânica de um deck**: o deck é construído em volta dela quando pelo menos um quarto das
  mágicas a tem. No Brawl, as mecânicas do comandante também contam. A lista das mecânicas está
  em `src/mtg_arena_collection/card_mechanics.py`.
- **Vezes o acaso**: quantas vezes mais duas mecânicas ou cartas aparecem juntas do que
  apareceriam por sorte. Para cartas, a sorte só conta os decks cujas cores poderiam jogar as duas.
  Todo par aparece em pelo menos {minimum_decks} decks."""


def write_meta_lessons(
    lessons: list[FormatLessons], output_directory: Path, generated_at: str
) -> tuple[Path, Path]:
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / REPORT_FILE_NAME
    json_path = output_directory / JSON_FILE_NAME
    _write_atomically(report_path, format_meta_lessons_report(lessons, generated_at))
    _write_atomically(json_path, meta_lessons_as_json(lessons, generated_at))
    return report_path, json_path


def format_meta_lessons_report(lessons: list[FormatLessons], generated_at: str) -> str:
    introduction = INTRODUCTION.format(
        generated_at=generated_at,
        deck_count=sum(lesson.all_decks.deck_count for lesson in lessons),
        minimum_decks=MINIMUM_DECKS,
    )
    return "\n\n".join([introduction, *(_format_section(lesson) for lesson in lessons)]) + "\n"


def meta_lessons_as_json(lessons: list[FormatLessons], generated_at: str) -> str:
    data = {"generated_at": generated_at, "formats": [asdict(lesson) for lesson in lessons]}
    return json.dumps(_rounded(data), ensure_ascii=False, indent=1) + "\n"


def _format_section(lesson: FormatLessons) -> str:
    format_name = FORMAT_DISPLAY_NAMES.get(lesson.format_name, lesson.format_name)
    parts = [
        f"## {format_name} ({lesson.all_decks.deck_count} decks)",
        _land_count_paragraph(lesson),
        "### Por velocidade",
        _group_table("Velocidade", [lesson.all_decks, *lesson.by_speed]),
        "### Por mecânica",
        _group_table("Mecânica", list(lesson.by_mechanic)),
        "Cartas mais jogadas em cada mecânica (parte dos decks do grupo que jogam a carta):",
        _most_played_cards_list(lesson.by_mechanic),
        "### Mecânicas que andam juntas",
        _pairs_table("Mecânica", lesson.mechanics_played_together),
        "### Cartas que andam juntas",
        _card_pairs_introduction(lesson.cards_played_together),
        _pairs_table("Carta", _most_frequent_first(lesson.cards_played_together)[:CARD_PAIRS_IN_THE_REPORT]),
    ]
    if lesson.unknown_card_names:
        parts.append(
            "Cartas fora do catálogo do jogo, que ficaram de fora das contas: "
            + ", ".join(lesson.unknown_card_names) + "."
        )
    return "\n\n".join(parts)


def _land_count_paragraph(lesson: FormatLessons) -> str:
    fit = lesson.land_count_fit
    examples = "; ".join(
        f"custo médio {decimal_text(cost)} → {decimal_text(fit.land_count_for(cost))} terrenos"
        for cost in EXAMPLE_AVERAGE_COSTS
    )
    return (
        f"**Terrenos**: {decimal_text(lesson.all_decks.land_count)} em média. Pela curva, "
        f"terrenos ≈ {decimal_text(fit.intercept)} + {decimal_text(fit.slope, 2)} × custo médio das mágicas "
        f"({examples})."
    )


def _group_table(first_column_title: str, summaries: list[GroupSummary]) -> str:
    if not summaries:
        return f"Nenhum grupo com {MINIMUM_DECKS} decks ou mais."
    role_titles = " | ".join(title for _, title in REPORTED_ROLES)
    lines = [
        f"| {first_column_title} | Decks | Peso | Terrenos | Criaturas | Custo médio | "
        f"Curva 1/2/3/4/5/6+ | {role_titles} |",
        "|" + "---|" * (7 + len(REPORTED_ROLES)),
    ]
    for summary in summaries:
        roles = " | ".join(decimal_text(summary.role_counts[tag]) for tag, _ in REPORTED_ROLES)
        lines.append(
            f"| {GROUP_DISPLAY_NAMES.get(summary.label, summary.label)} | {summary.deck_count} | "
            f"{_percent(summary.weight_share)} | {decimal_text(summary.land_count)} | "
            f"{decimal_text(summary.creature_count)} | {decimal_text(summary.average_mana_value, 2)} | "
            f"{'/'.join(str(round(copies)) for copies in summary.curve)} | {roles} |"
        )
    return "\n".join(lines)


def _most_played_cards_list(summaries: tuple[GroupSummary, ...]) -> str:
    return "\n".join(
        f"- **{summary.label}**: "
        + ", ".join(
            f"{card_name} ({_percent(share)})"
            for card_name, share in summary.most_played_cards[:MOST_PLAYED_CARDS_IN_THE_REPORT]
        )
        for summary in summaries
    ) or "Nenhuma."


def _card_pairs_introduction(pairs: tuple[PlayedTogether, ...]) -> str:
    shown = min(len(pairs), CARD_PAIRS_IN_THE_REPORT)
    return (
        f"Os {shown} pares mais frequentes entre os {len(pairs)} que aparecem juntos pelo menos "
        f"{decimal_text(MINIMUM_TIMES_MORE_THAN_CHANCE_FOR_CARDS)} vezes mais do que o acaso "
        f"(todos estão no JSON):"
    )


def _pairs_table(item_title: str, pairs) -> str:
    if not pairs:
        return f"Nenhum par em {MINIMUM_DECKS} decks ou mais."
    lines = [f"| {item_title} | Com | Decks | Vezes o acaso |", "|---|---|---|---|"]
    lines += [
        f"| {pair.first} | {pair.second} | {pair.deck_count} | {decimal_text(pair.times_more_than_chance)} |"
        for pair in pairs
    ]
    return "\n".join(lines)


def _most_frequent_first(pairs: tuple[PlayedTogether, ...]) -> list[PlayedTogether]:
    return sorted(pairs, key=lambda pair: (-pair.deck_count, -pair.times_more_than_chance, pair.first))


def decimal_text(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def _percent(share: float) -> str:
    return f"{round(share * 100)}%"


def _rounded(value):
    if isinstance(value, float):
        return round(value, JSON_DECIMALS)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    return value


def _write_atomically(path: Path, text: str) -> None:
    temporary_path = path.with_name(f".{path.name}.partial")
    temporary_path.write_text(text, encoding="utf-8")
    os.replace(temporary_path, path)
