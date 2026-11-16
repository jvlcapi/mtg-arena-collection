"""Converts the game's mana notation into the usual brace notation.

The game writes a cost like {2}{W} as "o2oW" and hybrid symbols as "o(U/R)".
Rules text wraps the same notation in braces, sometimes several symbols at once: "{o1oB}".
"""

import re

SYMBOL_IN_BRACES = re.compile(r"\{([^{}]+)\}")
ARENA_SYMBOLS_IN_BRACES = re.compile(r"\{(o[^{}]*)\}")
VARIABLE_SYMBOLS = {"X", "Y", "Z"}


def convert_arena_mana_text(arena_mana_text: str) -> str:
    symbols = [symbol.strip("()") for symbol in arena_mana_text.split("o") if symbol]
    return "".join(f"{{{symbol}}}" for symbol in symbols)


def calculate_mana_value(mana_cost: str) -> int:
    total = 0
    for symbol in SYMBOL_IN_BRACES.findall(mana_cost):
        if symbol.isdigit():
            total += int(symbol)
        elif symbol in VARIABLE_SYMBOLS:
            continue
        else:
            first_half = symbol.split("/")[0]
            total += int(first_half) if first_half.isdigit() else 1
    return total


def convert_symbols_in_rules_text(rules_text: str) -> str:
    return ARENA_SYMBOLS_IN_BRACES.sub(
        lambda match: convert_arena_mana_text(match.group(1)), rules_text
    )
