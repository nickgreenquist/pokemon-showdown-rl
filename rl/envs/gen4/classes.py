"""The ability / item class taxonomies (encoder_requirements.md §3, A3) and
the ability type-modifier table behind the ability-aware matchup scalars (A5).

DATA-AS-CODE, on purpose: open_questions.md Q21 asks whether the taxonomy is
pre-registered as data or left to the implementer. Until ruled, it lives here
where a reviewer can read every assignment, and the import-time checks below
make a typo or an unclassified ability a loud failure against the vocab
(rl/envs/gen4/data/gen4_vocab.json), not a silent zero row.

The class bits are COARSE PRIORS beside the embedding id — the id carries
identity, the bits carry what the ability/item does at the level a policy
needs before it has seen the ability enough times to learn it. An ability is
in exactly one class; the choice for the borderline ones is recorded inline.
"""

from __future__ import annotations

from poke_env.battle.pokemon_type import PokemonType

from rl.envs.gen4.vocab import VOCAB

# --- abilities: 12 classes ------------------------------------------------
ABILITY_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    # A1 immunity to a TYPE of attack (the matchup scalars fold these in)
    ("type_immunity", frozenset({
        "levitate", "waterabsorb", "voltabsorb", "flashfire", "dryskin", "motordrive", "wonderguard",
    })),
    # A2 sets permanent weather on switch-in (gen <= 5: duration 0)
    ("weather_setter", frozenset({"drizzle", "drought", "sandstream", "snowwarning"})),
    # A3 changes under / suppresses weather
    ("weather_interact", frozenset({
        "chlorophyll", "swiftswim", "sandveil", "snowcloak", "hydration", "leafguard",
        "forecast", "flowergift", "airlock", "cloudnine",
    })),
    # A4 raises the mon's own damage, accuracy or crit output
    ("offense_boost", frozenset({
        "adaptability", "blaze", "overgrow", "torrent", "swarm", "guts", "hugepower", "purepower",
        "ironfist", "technician", "tintedlens", "sniper", "superluck", "skilllink", "serenegrace",
        "noguard", "compoundeyes", "moldbreaker", "scrappy",
    })),
    # A5 reduces incoming damage / crits (Sturdy: OHKO-immunity only at gen 4;
    # Soundproof: immunity to sound moves — a move class, not a type)
    ("damage_reduction", frozenset({
        "thickfat", "filter", "solidrock", "marvelscale", "battlearmor", "shellarmor", "sturdy", "soundproof",
    })),
    # A6 immune to, cures, or profits from a status / indirect damage (Rock Head: recoil)
    ("status_immune_or_heal", frozenset({
        "immunity", "insomnia", "vitalspirit", "limber", "waterveil", "owntempo", "innerfocus",
        "naturalcure", "shedskin", "earlybird", "magicguard", "rockhead", "poisonheal", "tangledfeet", "shielddust",
    })),
    # A7 punishes contact / drain / the attacker (Bad Dreams: sleeping foes)
    ("contact_punish", frozenset({
        "static", "flamebody", "poisonpoint", "roughskin", "aftermath", "cutecharm", "liquidooze", "baddreams",
    })),
    # A8 immune to stat drops
    ("stat_drop_immunity", frozenset({"clearbody", "whitesmoke", "hypercutter", "keeneye"})),
    # A9 traps the foe (the maybe_trapped source; survey G1)
    ("trapping", frozenset({"arenatrap", "shadowtag", "magnetpull"})),
    # A10 speed / tempo
    ("speed_tempo", frozenset({"speedboost", "quickfeet", "unburden", "steadfast"})),
    # A11 switch-in / information / misc active effects (Intimidate is a
    # switch-in stat drop; Pressure doubles PP cost; Trace copies; Multitype
    # and Color Change change type; Simple doubles stages)
    ("switch_in_or_misc", frozenset({
        "pressure", "intimidate", "download", "trace", "anticipation", "forewarn", "synchronize",
        "stickyhold", "suctioncups", "colorchange", "multitype", "simple",
    })),
    # A12 handicaps and abilities inert in randbats singles
    ("handicap_or_inert", frozenset({"slowstart", "truant", "minus", "plus", "pickup", "runaway", "gluttony"})),
)

# --- items: 5 classes ------------------------------------------------------
_PLATES = frozenset({
    "dracoplate", "dreadplate", "earthplate", "fistplate", "flameplate", "icicleplate", "insectplate",
    "ironplate", "meadowplate", "mindplate", "skyplate", "splashplate", "spookyplate", "stoneplate",
    "toxicplate", "zapplate",
})
ITEM_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    # I1 locks the holder into its first move (the Choice-lock inference)
    ("choice", frozenset({"choiceband", "choicespecs", "choicescarf"})),
    # I2 passive end-of-turn healing (Black Sludge is Leftovers for Poison types)
    ("passive_heal", frozenset({"leftovers", "blacksludge"})),
    # I3 raises damage (species-locked boosters, plates, Life Orb, Expert Belt, type boosters)
    ("damage_boost", frozenset({
        "lifeorb", "expertbelt", "blackglasses", "silkscarf", "souldew", "thickclub", "lightball",
        "stick", "lustrousorb", "griseousorb",
    }) | _PLATES),
    # I4 one-shot consumables (self-reveal on use; `-enditem`)
    ("consumable", frozenset({"sitrusberry", "chestoberry", "lumberry", "custapberry", "focussash"})),
    # I5 other (Toxic Orb self-status; Damp Rock rain length; Light Clay screens; Quick Powder Ditto speed)
    ("other", frozenset({"toxicorb", "damprock", "lightclay", "quickpowder"})),
)

# --- ability type modifiers: what a KNOWN defender ability does to an
# incoming move type's chart multiplier (mechanics_delta.md §11; gen-4
# semantics: Lightning Rod / Storm Drain redirect only, no immunity).
ABILITY_TYPE_MODS: dict[str, dict[PokemonType, float]] = {
    "levitate": {PokemonType.GROUND: 0.0},
    "waterabsorb": {PokemonType.WATER: 0.0},
    "dryskin": {PokemonType.WATER: 0.0, PokemonType.FIRE: 1.25},
    "voltabsorb": {PokemonType.ELECTRIC: 0.0},
    "motordrive": {PokemonType.ELECTRIC: 0.0},
    "flashfire": {PokemonType.FIRE: 0.0},
    "thickfat": {PokemonType.FIRE: 0.5, PokemonType.ICE: 0.5},
}
# Multiplicative on super-effective hits only (Filter, Solid Rock: x0.75) and
# Wonder Guard (only super-effective hits land).
_SE_REDUCERS = {"filter": 0.75, "solidrock": 0.75}


def ability_type_multiplier(ability: str | None, move_type: PokemonType, base: float) -> float:
    """The chart multiplier `base` of `move_type` into a defender whose ability
    is `ability` (an id or None = unknown / no effect)."""
    if not ability:
        return base
    mods = ABILITY_TYPE_MODS.get(ability)
    if mods and move_type in mods:
        return base * mods[move_type]
    if ability == "wonderguard":
        return base if base > 1.0 else 0.0
    if base > 1.0 and ability in _SE_REDUCERS:
        return base * _SE_REDUCERS[ability]
    return base


# --- lookups ---------------------------------------------------------------
ABILITY_CLASS_NAMES = tuple(name for name, _ in ABILITY_CLASSES)
ITEM_CLASS_NAMES = tuple(name for name, _ in ITEM_CLASSES)
ABILITY_CLASS_INDEX: dict[str, int] = {
    a: i for i, (_, members) in enumerate(ABILITY_CLASSES) for a in members
}
ITEM_CLASS_INDEX: dict[str, int] = {
    it: i for i, (_, members) in enumerate(ITEM_CLASSES) for it in members
}


def _check(kind: str, index: dict[str, int], classes, vocab_ids: tuple[str, ...]) -> None:
    listed = [m for _, members in classes for m in members]
    dup = {m for m in listed if listed.count(m) > 1}
    assert not dup, f"{kind} in more than one class: {sorted(dup)}"
    unknown = sorted(set(listed) - set(vocab_ids))
    assert not unknown, f"{kind} class members absent from the vocab (typo?): {unknown}"
    missing = sorted(set(vocab_ids) - set(listed))
    assert not missing, f"vocab {kind} with no class: {missing}"


_check("ability", ABILITY_CLASS_INDEX, ABILITY_CLASSES, VOCAB.abilities)
_check("item", ITEM_CLASS_INDEX, ITEM_CLASSES, VOCAB.items)
