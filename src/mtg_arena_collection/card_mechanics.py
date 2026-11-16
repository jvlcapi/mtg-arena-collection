"""Tags cards with the mechanics a deck can be built around, from their rules text.

Themes come in pairs where it matters for deck building: the cards that do something
(`ganho-de-vida`, gaining life) and the cards rewarded for it (`ganho-de-vida-recompensa`).
Roles such as removal, card draw or ramp are tags too. Tribes are `tribo:<type>` for cards
whose text names a creature type, like Krenko, Mob Boss counting Goblins.

The patterns read the English rules text from the game's card database, which follows the
current Oracle wording ("this creature" instead of the card's name, no reminder text).
"""

import re
from dataclasses import dataclass

from mtg_arena_collection.card_catalog import Card

NUMBER = r"(?:\d+|x|a|an|one|two|three|four|five|six|seven|that many|that much|twice that much)"


@dataclass(frozen=True)
class Mechanic:
    tag: str
    description: str
    pattern: re.Pattern
    nonland_cards_only: bool = False


def _pattern(text):
    return re.compile(text, re.MULTILINE)


MECHANICS = (
    Mechanic("ganho-de-vida", "Ganha vida, inclusive com vínculo com a vida.",
             _pattern(rf"\blifelink\b|\bgains? {NUMBER} life\b|\bgains? life equal to\b")),
    Mechanic("ganho-de-vida-recompensa", "Fica melhor quando você ganha vida.",
             _pattern(r"\bwhenever you gain life\b|\bwhenever you gain \d+ or more life\b"
                      r"|\bif you(?:'ve)? gained (?:\d+ or more )?life\b|\blife you(?:'ve)? gained\b")),
    Mechanic("marcadores", "Usa marcadores +1/+1.", _pattern(r"\+1/\+1 counters?\b|\bproliferate\b")),
    Mechanic("fichas", "Cria fichas de criatura.",
             _pattern(r"\bcreates? [^.]*?\bcreature tokens?\b")),
    Mechanic("fichas-de-artefato", "Cria Tesouros, Comidas, Pistas e outras fichas de artefato.",
             _pattern(r"\b(?:treasure|food|clue|map|blood|powerstone|junk|incubator|gold) tokens?\b")),
    Mechanic("bonus-para-o-time", "Fortalece todas as suas criaturas.",
             _pattern(r"\bcreatures you control get \+\d+/\+\d+"
                      r"|\bother [^.]{0,40}? you control get \+\d+/\+\d+"
                      r"|\bcreature tokens you control get \+")),
    Mechanic("sacrificio", "Sacrifica as próprias permanentes como custo ou efeito.",
             _pattern(r"\bsacrifice (?:a|an|another|two|three|x|one or more|any number of) "
                      r"(?:[\w-]+ )?(?:creatures?|artifacts?|permanents?|tokens?|lands?|enchantments?"
                      r"|foods?|treasures?|clues?)\b")),
    Mechanic("morte-recompensa", "Ganha algo quando criaturas morrem.",
             _pattern(r"\b(?:whenever|when) [^.]*?\bdies\b|\bwhenever [^.]*?\bdie\b"
                      r"|\bput into a graveyard from the battlefield\b")),
    Mechanic("reanimar", "Devolve permanentes ao campo de batalha.",
             _pattern(r"\breturns? [^.]*? to the battlefield\b")),
    Mechanic("cemiterio", "Usa ou enche o cemitério.",
             _pattern(r"\bfrom (?:your|a|their) graveyard\b|\bcards? in your graveyard\b"
                      r"|\binto your graveyard\b|\bmills?\b|\bsurveil\b|\bflashback\b|\bescapes?\b"
                      r"|\bunearth\b|\bdisturb\b|\bembalm\b|\beternalize\b|\bdelve\b")),
    Mechanic("magicas", "Fica melhor com mágicas instantâneas e feitiços.",
             _pattern(r"\bwhenever you cast (?:an? )?(?:instant|sorcery|noncreature)\b|\bmagecraft\b"
                      r"|\bprowess\b|\binstant (?:and|or) sorcery cards? in your graveyard\b"
                      r"|\bcopy target instant or sorcery\b")),
    Mechanic("anula", "Anula mágicas.", _pattern(r"\bcounter target\b")),
    Mechanic("compra", "Compra cartas, escolhe cartas do grimório para a mão ou joga as do topo (impulso).",
             _pattern(rf"(?<!opponent )(?<!opponents )\bdraws? {NUMBER} cards?\b|\bdraw cards\b"
                      r"|\bput (?:one|two|three|four|x|\w+ of them|that card|those cards) into your hand\b"
                      r"|\bexile the top (?:card|\w+ cards) of your library\b[^\n]{0,80}?\byou may (?:play|cast)\b")),
    Mechanic("remocao", "Remove uma ameaça do oponente.",
             _pattern(r"\b(?:destroy|exile) target (?:[\w-]+ ){0,3}?(?:creature|permanent|planeswalker"
                      r"|artifact|enchantment|nonland|battle)"
                      rf"|\bdeals? {NUMBER} damage to (?:any target|target creature|target (?:attacking"
                      r"|blocking|tapped)|each creature|target planeswalker|another target)"
                      r"|\btarget creature (?:an opponent controls )?gets -\d+/-\d+|\bfights?\b"
                      r"|\breturn target (?:[\w-]+ ){0,3}?(?:creature|permanent) to its owner's hand")),
    Mechanic("limpa-mesa", "Remove várias criaturas de uma vez.",
             _pattern(r"\b(?:destroy|exile) all (?:[\w-]+ ){0,2}?creatures\b"
                      r"|\bdeals? (?:\d+|x) damage to each creature\b"
                      r"|\b(?:all|each) creatures? gets? -\d+/-\d+")),
    Mechanic("dano-direto", "Causa dano ou perda de vida direto no oponente.",
             _pattern(rf"\bdeals? {NUMBER} damage to (?:any target|target player|target opponent"
                      r"|each opponent|each player)"
                      rf"|\b(?:target opponent|each opponent|that player|defending player) loses "
                      rf"(?:{NUMBER}|half)")),
    Mechanic("protecao", "Protege as próprias permanentes.",
             _pattern(r"\bhexproof\b|\bindestructible\b|\bward\b|\bprotection from\b|\bshroud\b")),
    Mechanic("evasao", "Difícil de bloquear: voar, ameaçar, atropelar.",
             _pattern(r"^(?:flying|menace|trample|skulk|intimidate|fear|shadow)\b"
                      r"|\bcan't be blocked\b|\b(?:gains?|has|have) (?:flying|menace|trample)\b")),
    Mechanic("impeto", "Ataca no turno em que entra (ímpeto).",
             _pattern(r"^haste\b|\b(?:gains?|has|have) haste\b")),
    Mechanic("entrada", "Faz algo quando entra no campo de batalha.",
             _pattern(r"\b(?:when|whenever) (?:this|[^.]{1,40}?) enters\b")),
    Mechanic("rampa", "Gera mana extra ou busca terrenos.",
             _pattern(r"\{t\}: add\b|\badd \{[wubrgc]\}|\badd (?:one|two|three|x) mana\b"
                      r"|\bsearch your library for (?:a|up to (?:one|two)) (?:basic )?lands? cards?\b"),
             nonland_cards_only=True),
    Mechanic("artefatos-recompensa", "Fica melhor com artefatos.",
             _pattern(r"\bartifacts? you control\b|\bwhenever (?:an|another|one or more) (?:[\w-]+ )?"
                      r"artifacts?\b|\bfor each artifact\b|\baffinity for artifacts\b|\bimprovise\b"
                      r"|\bmetalcraft\b")),
    Mechanic("encantamentos-recompensa", "Fica melhor com encantamentos.",
             _pattern(r"\benchantments? you control\b|\bwhenever (?:an|another) (?:[\w-]+ )?enchantment\b"
                      r"|\bconstellation\b|\bfor each enchantment\b")),
    Mechanic("terrenos", "Fica melhor quando terrenos entram (landfall).",
             _pattern(r"\blandfall\b|\bwhenever a land (?:you control )?enters\b")),
    Mechanic("descarte", "Faz o oponente descartar ou tira cartas da mão dele.",
             _pattern(r"\b(?:target|each) (?:player|opponent) discards\b|\bthat player discards\b"
                      r"|\btarget opponent reveals their hand\b")),
)
MECHANIC_DESCRIPTIONS = {mechanic.tag: mechanic.description for mechanic in MECHANICS}
ENABLER_AND_PAYOFF_PAIRS = (
    ("ganho-de-vida", "ganho-de-vida-recompensa"),
    ("sacrificio", "morte-recompensa"),
    ("fichas", "bonus-para-o-time"),
    ("cemiterio", "reanimar"),
    ("fichas-de-artefato", "artefatos-recompensa"),
)

IRREGULAR_PLURALS = {
    "Elf": "Elves", "Dwarf": "Dwarves", "Wolf": "Wolves", "Werewolf": "Werewolves",
    "Mouse": "Mice", "Fungus": "Fungi", "Octopus": "Octopi", "Ox": "Oxen",
}


def partner_mechanics_of(tag: str) -> set[str]:
    """The other half of an enabler and payoff pair: payoffs for an enabler and the reverse."""
    return {
        second if first == tag else first
        for first, second in ENABLER_AND_PAYOFF_PAIRS
        if tag in (first, second)
    }


def plural_of(creature_type: str) -> str:
    if creature_type in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[creature_type]
    if creature_type.endswith(("s", "x", "ch", "sh")):
        return f"{creature_type}es"
    if creature_type.endswith("y") and creature_type[-2:-1] not in ("a", "e", "i", "o", "u"):
        return f"{creature_type[:-1]}ies"
    return f"{creature_type}s"


def creature_types_of(type_line: str) -> set[str]:
    return _subtypes_of(type_line, on_creature_faces=True)


def noncreature_subtypes_of(type_line: str) -> set[str]:
    return _subtypes_of(type_line, on_creature_faces=False)


def _subtypes_of(type_line: str, on_creature_faces: bool) -> set[str]:
    subtypes = set()
    for face in type_line.split("//"):
        kinds, _, face_subtypes = face.partition("—")
        is_creature_face = "Creature" in kinds or "Kindred" in kinds or "Tribal" in kinds
        if is_creature_face == on_creature_faces:
            subtypes.update(face_subtypes.split())
    return subtypes


class MechanicTagger:
    def __init__(self, creature_types: set[str]):
        self.creature_types = set(creature_types)
        self._type_by_word = {}
        for creature_type in self.creature_types:
            self._type_by_word[creature_type] = creature_type
            self._type_by_word[plural_of(creature_type)] = creature_type
        words = sorted(self._type_by_word, key=len, reverse=True)
        self._tribe_pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b") if words else None

    @classmethod
    def from_catalog(cls, catalog: dict[int, Card]) -> "MechanicTagger":
        """Creature types, leaving out the subtypes that also name noncreature cards, such as
        Treasure (Goldhound is an "Artifact Creature — Treasure Dog") or Forest."""
        creature_types, noncreature_subtypes = set(), set()
        for card in catalog.values():
            creature_types |= creature_types_of(card.type_line)
            noncreature_subtypes |= noncreature_subtypes_of(card.type_line)
        return cls(creature_types - noncreature_subtypes)

    def tags_for(self, card: Card) -> tuple[str, ...]:
        text = card.rules_text.lower()
        is_land = "Land" in card.type_line.split("//")[0]
        tags = {
            mechanic.tag
            for mechanic in MECHANICS
            if not (mechanic.nonland_cards_only and is_land) and mechanic.pattern.search(text)
        }
        tags |= {f"tribo:{tribe.lower()}" for tribe in self._tribes_named_in(card)}
        return tuple(sorted(tags))

    def _tribes_named_in(self, card: Card) -> set[str]:
        if self._tribe_pattern is None:
            return set()
        text = card.rules_text
        for face_name in card.name.split(" // "):
            text = text.replace(face_name, "")
        return {self._type_by_word[word] for word in self._tribe_pattern.findall(text)}
