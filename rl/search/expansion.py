"""Leaf corrections: the 2-point roll expansion + the gen1 KO-skip recharge
rule (ch3_search_design_r2.md §2.1; built because FG-2k read 0.0928 > 0.05).

The engine emits ONE average-damage leaf per branch (mean-of-39-rolls ~
0.925 x max), so faint/no-faint at the roll boundary is deterministic where
gen1 flips a coin. The pre-registered repair: where a branch's damage
straddles a KO threshold, replace its leaf with TWO leaves — a low-roll
survivor (0.85 x max) and a KO — weighted by the TRUE roll mass either
side of the threshold (uniform over the 39 discrete rolls 217..255,
damage_r = floor(max_dmg * r / 255)).

Also applied here: gen1's KO-SKIP RECHARGE rule — Hyper Beam does NOT
require a recharge turn when it KOs. The engine implements this on its OWN
branches (measured: KO branches carry no MUSTRECHARGE), so the strip below
matters for EXPANSION-CREATED KO variants, whose base (survived-at-average)
leaf legitimately carries the volatile.

Engine State/Side/Pokemon are IMMUTABLE from Python (measured), and
depth-1 leaves are never re-simulated — corrections are therefore
lightweight duck-typed VIEWS (hp/volatile overrides with full attribute
delegation), consumed by ShadowBattle and the FG battery exactly like raw
engine objects.

max-damage attribution per branch: `calculate_damage(state, a, b, True)`
returns ([normal_max, crit_max], ...) per side (verified: branch damage ~
0.925 x candidate); the branch's candidate is whichever is closest to its
realized average damage. A fainted-at-average defender whose damage was
truncated by hp uses the smallest candidate that can kill at average
(chip-damage conflations -> no split, documented approximation). Weights
compose multiplicatively if both sides straddle (rare).
"""

from __future__ import annotations

from typing import Any

_ROLLS = range(217, 256)  # gen1 damage roll numerators, uniform


class _MonView:
    """Engine Pokemon with an hp override; everything else delegates."""

    __slots__ = ("_base", "hp")

    def __init__(self, base: Any, hp: int):
        self._base = base
        self.hp = hp

    def __getattr__(self, name):
        return getattr(self._base, name)


class _SideView:
    """Engine Side with per-mon hp overrides and an optional mustrecharge
    strip; everything else delegates."""

    __slots__ = ("_base", "_hp_over", "_strip_recharge")

    def __init__(self, base: Any, hp_over: dict[int, int], strip_recharge: bool):
        self._base = base
        self._hp_over = hp_over
        self._strip_recharge = strip_recharge

    @property
    def pokemon(self):
        return [
            _MonView(m, self._hp_over[i]) if i in self._hp_over else m
            for i, m in enumerate(self._base.pokemon)
        ]

    @property
    def volatile_statuses(self):
        vols = set(self._base.volatile_statuses)
        if self._strip_recharge:
            vols = {v for v in vols if v.lower() != "mustrecharge"}
        return vols

    def __getattr__(self, name):
        return getattr(self._base, name)


class LeafView:
    __slots__ = ("side_one", "side_two")

    def __init__(self, side_one: Any, side_two: Any):
        self.side_one = side_one
        self.side_two = side_two


def _active(side):
    ai = side.active_index
    ai = ai if isinstance(ai, int) else int(str(ai)[-1])
    return ai, side.pokemon[ai]


def _has_recharge(side) -> bool:
    return any(v.lower() == "mustrecharge" for v in side.volatile_statuses)


def _ko_mass(max_dmg: int, hp_before: int) -> float:
    """True roll mass with floor(max_dmg * r/255) >= hp_before."""
    return sum(1 for r in _ROLLS if (max_dmg * r) // 255 >= hp_before) / len(_ROLLS)


def _branch_candidate(dmg_avg: int, candidates: list[int]) -> int | None:
    """Which max-damage candidate (normal/crit) this branch realized."""
    best, err = None, 0.2
    for c in candidates:
        if c <= 0:
            continue
        e = abs(dmg_avg - 0.925 * c) / (0.925 * c)
        if e < err:
            best, err = c, e
    return best


def _kill_candidate(hp_before: int, candidates: list[int]) -> int | None:
    """Smallest candidate whose AVERAGE kills — for truncated faint leaves."""
    for c in sorted(c for c in candidates if c > 0):
        if 0.925 * c >= hp_before:
            return c
    return None


def _side_split(root_side, leaf_side, dmg_candidates: list[int]):
    """(no_ko_hp, p_ko) for this side's ACTIVE as the damage TARGET, or None
    when its faint/no-faint is roll-certain."""
    li, leaf_mon = _active(leaf_side)
    root_mon = next(
        (m for m in root_side.pokemon if m.id.lower() == leaf_mon.id.lower()), None
    )
    if root_mon is None or root_mon.hp <= 0:
        return None
    hp_before, hp_after = root_mon.hp, leaf_mon.hp
    dmg = hp_before - hp_after
    if dmg <= 0:
        return None
    if hp_after > 0:
        cand = _branch_candidate(dmg, dmg_candidates)
        if cand is None or cand < hp_before:  # even max roll cannot KO
            return None
        p_ko = _ko_mass(cand, hp_before)
        if p_ko <= 0.0:
            return None
        return li, hp_after, p_ko
    cand = _kill_candidate(hp_before, dmg_candidates)
    if cand is None:  # chip-conflated faint: no roll read, keep as-is
        return None
    low = (cand * 217) // 255
    if low >= hp_before:  # even the lowest roll kills: certain KO
        return None
    p_ko = _ko_mass(cand, hp_before)
    return li, max(hp_before - low, 1), p_ko


def expand_leaf(
    root_state: Any, leaf: Any, dmg: tuple[list[int], list[int]] | None
) -> list[tuple[Any, float]]:
    """One engine leaf -> [(leaf_like, weight)] with sum(weight) == 1.

    Applies the 2-point roll expansion on each side's active (independent
    splits, weights multiply) and the KO-skip recharge strip on every
    resulting variant. With no straddle and no recharge to strip, returns
    the raw leaf untouched (zero overhead)."""
    splits = []  # per side: (side_idx, mon_idx, no_ko_hp, p_ko) or None
    for si, (root_side, leaf_side, cands) in enumerate((
        (root_state.side_one, leaf.side_one, (dmg[1] if dmg else [])),  # s1 active is hit by s2's move
        (root_state.side_two, leaf.side_two, (dmg[0] if dmg else [])),
    )):
        s = _side_split(root_side, leaf_side, list(cands)) if cands else None
        splits.append((si, *s) if s else None)

    variants: list[tuple[dict, dict, float]] = [({}, {}, 1.0)]  # (hp_over_s1, hp_over_s2, w)
    for sp in splits:
        if sp is None:
            continue
        si, mi, no_ko_hp, p_ko = sp
        new = []
        for o1, o2, w in variants:
            over = (o1, o2)[si]
            ko = dict(over)
            no_ko = dict(over) | {mi: no_ko_hp}
            ko[mi] = 0
            pair = [(no_ko, w * (1 - p_ko)), (ko, w * p_ko)]
            for ov, wv in pair:
                if wv <= 0:
                    continue
                n1, n2 = (ov, o2) if si == 0 else (o1, ov)
                new.append((n1, n2, wv))
        variants = new

    out = []
    for o1, o2, w in variants:
        s1_active_hp = _view_active_hp(leaf.side_one, o1)
        s2_active_hp = _view_active_hp(leaf.side_two, o2)
        strip1 = _has_recharge(leaf.side_one) and s2_active_hp <= 0
        strip2 = _has_recharge(leaf.side_two) and s1_active_hp <= 0
        if not o1 and not o2 and not strip1 and not strip2:
            out.append((leaf, w))
            continue
        out.append((LeafView(
            _SideView(leaf.side_one, o1, strip1),
            _SideView(leaf.side_two, o2, strip2),
        ), w))
    return out


def _view_active_hp(side, hp_over: dict[int, int]) -> int:
    ai, mon = _active(side)
    return hp_over.get(ai, mon.hp)
