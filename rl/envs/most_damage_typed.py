"""most-damage-typed — the fixed cross-generation anchor (JOURNEY's pre-step-3 add).

BORROWED DEFINITION (named per the standing obligation): Huang & Lee's
`MostDamageMovePlayer(type_aware=True)` in metagrok,
`pkmn/engine/baselines.py:48-152` (docs/prior_work/README.md). Score every
legal move as `base_power × type effectiveness against the defender's types`;
OHKO moves score 120; NOTHING ELSE — no STAB, accuracy, category, stats,
boosts, items, abilities, multi-hit, priority, status value or KO reasoning.
Pick the max, ties uniform at random. Never switch voluntarily. On a forced
switch pick the bench mon minimising the sum, over the opponent's types, of
that type's effectiveness against the candidate. H&L report 829-171 of 1000
gen7RB games against their trained agent, ties as non-wins.

WHY IT EXISTS (JOURNEY.md:15-19, docs/design_gen4/anchors_and_eval.md §2):
it is the only anchor whose own strength does not drift across generations —
SimpleHeuristicsPlayer has hazard branches that are inert in gen 1 and live
from gen 4 on, so an SH-denominated number partly measures SH. The RULE here
is the same product in every generation; the code still reads a
per-generation type chart. It is descriptive only, never a verdict input, and
"far weaker than SH" by the index's own caveat.

DEVIATIONS from H&L, disclosed wherever a number is quoted:
  (1) Return is scored at base power 102 — poke-env reports 0 for the
      friendship-dependent move (39 gen4 species carry it); gen 4+ only.
  (2) The type chart is poke-env's per-generation chart through
      `Pokemon.damage_multiplier` (H&L's dex is gen 7: Fairy present, Steel
      without its Ghost/Dark resistances — a silent error at gen 1/4).
  (3) Tie-breaks come from a per-instance seeded RNG, for reproducible evals.
Explosion / Self-Destruct score at raw base power like every move (gen 1:
170 / 130; gen 4: 250 / 200) — H&L's definition, and this bot's largest
weakness, disclosed rather than patched.
"""
from __future__ import annotations

import random

from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon
from poke_env.player import Player

OHKO_SCORE = 120.0   # H&L's constant for Fissure / Horn Drill / Guillotine / Sheer Cold
RETURN_BP = 102.0    # deviation (1): max-friendship Return


def move_score(move: Move, defender: Pokemon | None) -> float:
    """H&L's score: base power × effectiveness against the defender; OHKO = 120."""
    if move.entry.get("ohko"):
        return OHKO_SCORE
    bp = float(move.base_power)
    if bp == 0 and move.id == "return":
        bp = RETURN_BP
    if bp <= 0:
        return 0.0
    if defender is None:
        return bp
    return bp * float(defender.damage_multiplier(move))


def switch_weakness(candidate: Pokemon, opponent: Pokemon) -> float:
    """Sum over the opponent's types of that type's effectiveness against
    the candidate — H&L's forced-switch criterion (lower is better)."""
    return sum(float(candidate.damage_multiplier(t))
               for t in opponent.types if t is not None)


class MostDamageTypedPlayer(Player):
    """Registry key `most_damage_typed` (rl/envs/showdown.py OPPONENT_PLAYERS)."""

    def __init__(self, *args, seed: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(seed)

    def seed_rng(self, seed: int) -> None:
        """Reseed the private tie-break stream (ShowdownEnv.reset's per-sub-env
        hook, the same shape as PoolPlayer.seed_rng). Never touches the global
        `random` stream poke-env derives usernames from."""
        self._rng.seed(seed)

    def choose_move(self, battle):
        if self.format_is_doubles:
            return self.choose_random_move(battle)
        opponent = battle.opponent_active_pokemon
        moves = battle.available_moves
        if moves:
            # Never switch voluntarily: a move is chosen whenever one is legal,
            # even when every legal move scores 0 (ties -> uniform random).
            scored = [(move_score(m, opponent), m) for m in moves]
            best = max(s for s, _ in scored)
            return self.create_order(self._rng.choice([m for s, m in scored if s == best]))
        switches = battle.available_switches
        if switches:
            if opponent is not None:
                scored = [(switch_weakness(c, opponent), c) for c in switches]
                low = min(s for s, _ in scored)
                pool = [c for s, c in scored if s == low]
            else:
                pool = list(switches)
            return self.create_order(self._rng.choice(pool))
        return self.choose_random_move(battle)
