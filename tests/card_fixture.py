from mtg_arena_collection.card_catalog import Card


def make_card(
    name, type_line, rules_text="", mana_cost="", arena_id=1, mana_value=0, colors="",
    color_identity=None, rarity="common",
):
    return Card(
        arena_id=arena_id, name=name, portuguese_name="", set_code="TST", digital_release_set="",
        collector_number="1", rarity=rarity, mana_cost=mana_cost, mana_value=mana_value,
        colors=colors, color_identity=colors if color_identity is None else color_identity,
        type_line=type_line, power="", toughness="", rules_text=rules_text,
        is_digital_only=False, is_rebalanced=False,
    )
