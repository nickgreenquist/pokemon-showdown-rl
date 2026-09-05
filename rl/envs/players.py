"""Scripted opponents beyond poke-env's three — generation-agnostic by rule.

`MostDamageTypedPlayer`: JOURNEY.md's pre-step-3 anchor ("highest-damage move
with type awareness, nothing else"), the H&L 2019 / metagrok
`MostDamageMovePlayer(type_aware=True)` definition at the precision their code
gives it (docs/design_gen4/anchors_and_eval.md §2, [src]
metagrok/pkmn/engine/baselines.py:48-152):

  - score every legal move as base_power x type effectiveness against the
    defender's types; OHKO moves as 120; NOTHING else — no STAB, accuracy,
    category, stats, boosts, items, abilities, multi-hit, priority, status
    value, KO reasoning; status moves score 0;
  - pick the max, ties broken uniformly at random (seeded);
  - never switch voluntarily; on a forced switch pick the bench mon that
    minimises the sum of the opponent's TYPES' effectiveness against it.

Why it exists: the only anchor whose own strength does not drift across
generations (SimpleHeuristicsPlayer's hazard branches are inert in gen 1 and
live from gen 4), so it is the one denominator that means the same thing in
gen 1, gen 4 and gen 9. H&L's agent scored 829-171 of 1000 gen7RB games
against it, ties as non-wins (a cross-format placement, confounded, as
JOURNEY says). DESCRIPTIVE ONLY: it joins the anchor battery only by
maintainer ruling (open_questions.md Q36); building it is not admitting it.

Two disclosed deviations from H&L: the Return base-power override (102 —
happiness is always 255 in randbats and poke-env reports 0; without it the
bot cannot see a 102-BP move on 39 gen-4 species), and Hidden Power read
through its typed id (poke-env keeps `hiddenpowerfire`). "No
generation-dependent code" is true of the RULE, not of the code: the type
chart is per format, and that is the only per-generation input.
"""

from __future__ import annotations

import random

from poke_env.battle.move_category import MoveCategory
from poke_env.data import GenData
from poke_env.player import Player

# gen-agnostic per-move overrides of poke-env's data (randbats happiness is 255)
_BASE_POWER_OVERRIDE = {"return": 102.0}
_OHKO_SCORE = 120.0


class MostDamageTypedPlayer(Player):
    def __init__(self, *args, battle_format: str, seed: int = 0, **kwargs):
        super().__init__(*args, battle_format=battle_format, **kwargs)
        self._type_chart = GenData.from_format(battle_format).type_chart
        # A private stream: never the global `random` (rule 2 — usernames are
        # derived from it) and never poke-env's.
        self._tie_rng = random.Random(seed)

    def seed_rng(self, seed: int) -> None:
        self._tie_rng = random.Random(seed)

    def _score(self, move, foe) -> float:
        if move.category == MoveCategory.STATUS:
            return 0.0
        entry = move.entry
        if entry.get("ohko"):
            return _OHKO_SCORE
        bp = _BASE_POWER_OVERRIDE.get(move.id, float(move.base_power))
        if foe is None:
            return bp
        return bp * move.type.damage_multiplier(foe.type_1, foe.type_2, type_chart=self._type_chart)

    def _weakness(self, mon, foe) -> float:
        """Sum of the foe's TYPES' effectiveness against `mon` (H&L's forced-
        switch rule: types, not moves)."""
        if foe is None:
            return 0.0
        return sum(
            t.damage_multiplier(mon.type_1, mon.type_2, type_chart=self._type_chart)
            for t in foe.types if t is not None
        )

    def choose_move(self, battle):
        foe = battle.opponent_active_pokemon
        if battle.available_moves:
            scored = [(self._score(m, foe), m) for m in battle.available_moves]
            best = max(s for s, _ in scored)
            choices = [m for s, m in scored if s == best]
            return self.create_order(self._tie_rng.choice(choices))
        if battle.available_switches:
            scored = [(self._weakness(m, foe), m) for m in battle.available_switches]
            best = min(s for s, _ in scored)
            choices = [m for s, m in scored if s == best]
            return self.create_order(self._tie_rng.choice(choices))
        return self.choose_default_move()
