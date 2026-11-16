import unittest

from mtg_arena_collection.mana_symbols import (
    calculate_mana_value,
    convert_arena_mana_text,
    convert_symbols_in_rules_text,
)


class ConvertArenaManaTextTests(unittest.TestCase):
    def test_generic_and_colored_symbols(self):
        self.assertEqual(convert_arena_mana_text("o2oW"), "{2}{W}")

    def test_hybrid_symbols_lose_parentheses(self):
        self.assertEqual(convert_arena_mana_text("o1o(U/R)o(U/R)"), "{1}{U/R}{U/R}")

    def test_variable_cost(self):
        self.assertEqual(convert_arena_mana_text("oXoGoG"), "{X}{G}{G}")

    def test_two_digit_generic_cost(self):
        self.assertEqual(convert_arena_mana_text("o10oG"), "{10}{G}")

    def test_lands_have_no_cost(self):
        self.assertEqual(convert_arena_mana_text(""), "")


class CalculateManaValueTests(unittest.TestCase):
    def test_generic_plus_colored(self):
        self.assertEqual(calculate_mana_value("{2}{W}"), 3)

    def test_variable_counts_as_zero(self):
        self.assertEqual(calculate_mana_value("{X}{G}{G}"), 2)

    def test_two_color_hybrid_counts_as_one(self):
        self.assertEqual(calculate_mana_value("{1}{U/R}{U/R}"), 3)

    def test_generic_hybrid_counts_its_number(self):
        self.assertEqual(calculate_mana_value("{2/W}{2/W}"), 4)

    def test_phyrexian_counts_as_one(self):
        self.assertEqual(calculate_mana_value("{1}{W/P}"), 2)

    def test_no_cost_is_zero(self):
        self.assertEqual(calculate_mana_value(""), 0)


class ConvertSymbolsInRulesTextTests(unittest.TestCase):
    def test_tap_and_generic_symbols(self):
        self.assertEqual(
            convert_symbols_in_rules_text("{o1}, {oT}: Draw a card."),
            "{1}, {T}: Draw a card.",
        )

    def test_several_symbols_inside_one_brace(self):
        self.assertEqual(
            convert_symbols_in_rules_text("{o1oB}: Regenerate it."),
            "{1}{B}: Regenerate it.",
        )

    def test_text_without_symbols_is_unchanged(self):
        self.assertEqual(convert_symbols_in_rules_text("Flying"), "Flying")


if __name__ == "__main__":
    unittest.main()
