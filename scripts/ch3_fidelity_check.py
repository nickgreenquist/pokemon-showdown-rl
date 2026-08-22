"""CH3 R1 — the FG battery (ch3_search_design_r2.md §4 R1 table + §5).

    python scripts/ch3_fidelity_check.py --prereg configs/eval/ch3_rung0.yaml
    python scripts/ch3_fidelity_check.py --fg5          # attestation only

Runs FG-1..FG-7 (FG-8 is conditional on K0-1, which PASSED — not run) plus
the zero-battle-cost R1 reads (oppact/sh_accuracy + sh_nll, Z2' truncation
probe, the successor-ranking read, unmodellable frequencies) against the
harvest in results/ch3_r1/. Writes results/ch3_r1/fg_battery.json.

SEAT-2 DATA (harvest_priv_*.pkl) is consumed HERE and only here — offline
diagnostics measuring against SH are allowed (design §8.4); the agent and
everything under rl/search/ never read it (FG-4's static gate greps).

Interpretation notes baked into the outputs (adjudication-relevant):
- FG-2's engine can only simulate opponent actions present in the
  determinization (measured: 'Invalid move' otherwise), so transitions
  whose TRUE opponent action no determinization contains are the
  `action_unsimulable` stratum — determinization support, not forward-model
  error; FG-2 coverage is reported both conditional on simulability
  (primary) and unconditional. FG-7 is the support gate proper.
- Transitions with an intervening forced replacement (waits_after > 0)
  cannot be compared on the opponent's NEW active identity (a seat-2
  decision outside the joint action) — the branch must instead predict
  their faint; counted `replacement_relaxed`.
- FG-6 is measured on NON-ALIASED roots (the search never runs on aliased
  turns); det-visible dims (unrevealed bench the determinizer filled, slot
  known-probs at 1.0) are named exempt families per MF-8's process: the
  budget is FROZEN from this measured pass, before any verdict battle.
"""

import argparse
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

# ---------------------------------------------------------------------------
# FG-5 — engine attestation (no other imports needed)
# ---------------------------------------------------------------------------

def fg5_attestation() -> dict:
    import hashlib

    import poke_engine

    so = next(Path(poke_engine.__file__).parent.glob("*.so"))
    blob = so.read_bytes()
    counts = (
        blob.count(b"src/gen1/"),
        blob.count(b"src/genx/"),
        blob.count(b"used for spc"),
    )
    ok = counts[0] >= 1 and counts[1] == 0 and counts[2] >= 1
    return {
        "gate": "FG-5",
        "so": str(so),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "counts_gen1_genx_spc": list(counts),
        "expected_rows": {"gen1": "7/0/1", "gen4": "0/genx>0/0", "gen9": "0/20+/0"},
        "pass": bool(ok),
    }


# ---------------------------------------------------------------------------
# shared loading + mapping tables
# ---------------------------------------------------------------------------

NAMED_VOLATILES = frozenset({
    "reflect", "mist", "focusenergy", "leechseed", "confusion",
    "partiallytrapped", "bide", "mustrecharge", "flinch",
})

_STATUS_CANON = {"burn", "paralyze", "poison", "toxic", "sleep", "freeze"}


def _tables():
    from poke_env.data import GenData

    gen1 = GenData.from_gen(1)
    move_by_num = {}
    for mid, e in gen1.moves.items():
        num = e.get("num")
        if isinstance(num, int) and 1 <= num <= 165 and num not in move_by_num:
            move_by_num[num] = mid
    species_by_num = {}
    for sid, e in gen1.pokedex.items():
        num = e.get("num", 0)
        if 1 <= num <= 151 and num not in species_by_num:
            species_by_num[num] = sid
    return move_by_num, species_by_num


def load_lanes(prereg: dict, harvest_dir: Path):
    lanes = {}
    for lane in prereg["checkpoints"]:
        with open(harvest_dir / f"harvest_{lane}.pkl", "rb") as f:
            pub = pickle.load(f)
        with open(harvest_dir / f"harvest_priv_{lane}.pkl", "rb") as f:
            priv = pickle.load(f)
        lanes[lane] = (pub, priv)
    return lanes


def _snap_status_engine(m: dict) -> str:
    from rl.search.bridge import _STATUS_MAP

    return _STATUS_MAP.get(m["status"], "none") if m["status"] else "none"


def _snap_volatiles(m: dict) -> set:
    from rl.search.bridge import EFFECT_VOLATILE_MAP

    vols = {EFFECT_VOLATILE_MAP[e] for e in m["effects"] if e in EFFECT_VOLATILE_MAP}
    if m["must_recharge"]:
        vols.add("mustrecharge")
    return vols & NAMED_VOLATILES


def _leaf_mons(side) -> dict:
    return {m.id.lower(): m for m in side.pokemon if m.id.lower() != "none"}


def _active_of(side):
    ai = side.active_index
    ai = ai if isinstance(ai, int) else int(str(ai)[-1])
    return side.pokemon[ai]


# ---------------------------------------------------------------------------
# FG-1 — string stability
# ---------------------------------------------------------------------------

def fg1_string_stability(lanes, per_lane: int = 200) -> dict:
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import decision_rng
    from poke_engine import State

    n = stable = panics = 0
    vf_n = vf_stable = 0  # volatile-free stratum (the RULED scope)
    lane_seeds = {lane: i for i, lane in enumerate(lanes)}
    for lane, (pub, _) in lanes.items():
        rows = [(bi, si) for bi, b in enumerate(pub) for si in range(len(b["rows"]))]
        for k in np.linspace(0, len(rows) - 1, num=per_lane, dtype=int):
            bi, si = rows[k]
            row = pub[bi]["rows"][si]
            battle = rehydrate_battle(row["battle"])
            rng = decision_rng(1000 + lane_seeds[lane], bi, battle.turn, si)
            det = sample_determinization(battle, rng)
            state = battle_to_state(battle, det, BridgeCounters())
            volatile_free = not (
                state.side_one.volatile_statuses or state.side_two.volatile_statuses
            )
            n += 1
            vf_n += int(volatile_free)
            try:
                s1 = state.to_string()
                s2 = State.from_string(s1).to_string()
                ok = int(s1 == s2)
                stable += ok
                vf_stable += ok if volatile_free else 0
            except BaseException:
                panics += 1
    return {
        "gate": "FG-1",
        "bar": ("RULED SCOPE (maintainer, 2026-08-22): 100% byte-identical on "
                "VOLATILE-FREE states — the engine's own from_string drops "
                "volatile_statuses (known landmine), so byte-identity is "
                "structurally unreachable on volatile states; the "
                "object-construction invariant carries the load and strings "
                "are FG-1-only"),
        "blocking": True,
        "n": n, "stable": stable, "panics": panics,
        "volatile_free_n": vf_n, "volatile_free_stable": vf_stable,
        "volatile_stratum_recorded": {
            "n": n - vf_n, "stable": stable - vf_stable,
        },
        "pass": bool(vf_stable == vf_n and panics == 0),
    }


# ---------------------------------------------------------------------------
# FG-6 — encoder parity with named field families
# ---------------------------------------------------------------------------

def _fg6_classify(d: int, n_revealed: int) -> str:
    from rl.envs.showdown import (
        ACTIVE_DIM, GLOBAL_DIM, ID_DIM, MON_DIM, MOVE_DIM, OBS_DIM,
    )

    o_team = GLOBAL_DIM
    o_act = o_team + 6 * MON_DIM
    o_moves = o_act + ACTIVE_DIM
    p_team = o_moves + 4 * MOVE_DIM
    p_act = p_team + 6 * (MON_DIM + 1)
    p_moves = p_act + ACTIVE_DIM
    ids = OBS_DIM - ID_DIM
    if d < o_team:
        # dim 3 force_switch is synthesized by the shadow; dim 4 is gen1
        # partial-trap `trapped` (set on 3/13,396 roots — poke-env leaves it
        # False on nearly all partial-trap turns, encoder note)
        return "root_trapped" if d == 4 else "global"
    if d < o_act:
        return "our_team"
    if d < o_moves:
        rel = d - o_act
        return "sleep_rest_counter" if rel == 14 else (
            "preparing" if rel == 15 else
            "volatiles" if 7 <= rel <= 13 else "our_active"
        )
    if d < p_team:
        rel = (d - o_moves) % MOVE_DIM
        return "pp" if rel == 3 else "our_moves"
    if d < p_act:
        i, rel = divmod(d - p_team, MON_DIM + 1)
        if i >= n_revealed:
            return "det_unrevealed_bench"
        return "opp_hp_grain" if rel == 1 else "opp_revealed_block"
    if d < p_moves:
        rel = d - p_act
        return "sleep_rest_counter" if rel == 14 else (
            "preparing" if rel == 15 else
            "volatiles" if 7 <= rel <= 13 else "opp_active"
        )
    if d < ids:
        rel = (d - p_moves) % MOVE_DIM
        return "slot_known_prob" if rel == 0 else ("pp" if rel == 3 else "opp_move_block")
    rel = d - ids
    if 6 <= rel <= 11 and rel - 6 >= n_revealed:
        return "det_unrevealed_bench"
    return "id_suffix"


# The exempt families and their tolerances, MF-8: named here, FROZEN from
# this measured pass. Everything else must be exact to 1e-6.
FG6_EXEMPT = {
    "det_unrevealed_bench": np.inf,  # det-visible by design (leaf information)
    "transform_ditto": np.inf,       # copied stats unrepresentable from the dex
    "root_trapped": 1.0,             # gen1 partial-trap flag, 3/13,396 roots
    "slot_known_prob": 1.0,          # det shows p=1.0 where battle1 shows prior p
    "pp": 1.0,                       # poke-env never decrements; engine defaults
    "opp_hp_grain": 0.0105,          # /100 public grain + round-trip rounding
    "sleep_rest_counter": 1.0,       # engine splits sleep/Rest; toxic n unmapped
    "volatiles": 1.0,                # unmapped Effects counted, not carried
    "preparing": 1.0,                # FLY/DIG volatiles not mapped back
}


def fg6_encoder_parity(lanes, type_chart) -> dict:
    from rl.envs.showdown import embed_battle
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import decision_rng
    from rl.search.shadow_battle import shadow_battle

    fam_count: Counter = Counter()
    fam_max: dict[str, float] = defaultdict(float)
    violations = []
    n = skipped_aliased = 0
    lane_seeds = {lane: i for i, lane in enumerate(lanes)}
    for lane, (pub, _) in lanes.items():
        for bi, b in enumerate(pub):
            for si, row in enumerate(b["rows"]):
                if row["aliased"]:
                    skipped_aliased += 1
                    continue
                n += 1
                battle = rehydrate_battle(row["battle"])
                rng = decision_rng(2000 + lane_seeds[lane], bi, battle.turn, si)
                det = sample_determinization(battle, rng)
                state = battle_to_state(battle, det, BridgeCounters())
                sb = shadow_battle(state, turn=battle.turn)
                v_shadow = embed_battle(sb, type_chart)
                v_live = row["obs"]
                n_rev = len(row["battle"]["opponent_team"])
                # transform (ditto) roots: poke-env carries COPIED stats on
                # the live battle, the static dex cannot — every stat-derived
                # dim (speed edge, base stats) legitimately differs. Named,
                # counted, exempt; frequency travels with the budget.
                has_ditto = any(
                    m["species"] == "ditto"
                    for m in row["battle"]["team"] + row["battle"]["opponent_team"]
                )
                diff = np.abs(v_shadow - v_live)
                for d in np.flatnonzero(diff > 1e-6):
                    fam = _fg6_classify(int(d), n_rev)
                    if has_ditto and fam in (
                        "our_team", "opp_revealed_block", "our_moves",
                        "opp_move_block", "our_active", "opp_active",
                    ):
                        fam = "transform_ditto"
                    fam_count[fam] += 1
                    fam_max[fam] = max(fam_max[fam], float(diff[d]))
                    tol = FG6_EXEMPT.get(fam)
                    if tol is None or diff[d] > tol:
                        if len(violations) < 50:
                            violations.append({
                                "lane": lane, "episode": bi, "step": si,
                                "dim": int(d), "family": fam, "diff": float(diff[d]),
                            })
    return {
        "gate": "FG-6",
        "bar": "all non-exempt dims exact to 1e-6; exempt families named+frozen",
        "blocking": True,
        "n_roots": n, "skipped_aliased_roots": skipped_aliased,
        "family_diff_counts": dict(fam_count),
        "family_diff_max": {k: float(v) for k, v in fam_max.items()},
        "exempt_families": {k: (None if np.isinf(v) else v) for k, v in FG6_EXEMPT.items()},
        "violations_first50": violations,
        "pass": not violations,
    }


# ---------------------------------------------------------------------------
# FG-2 / FG-2p / FG-2k — one-step agreement vs the real server
# ---------------------------------------------------------------------------

def _hp_band_ok(dmg_obs: float, dmg_br: float, tol: float) -> bool:
    if dmg_br <= 0:  # heal / no damage: deterministic in gen1
        return abs(dmg_obs - dmg_br) <= tol
    lo = 0.85 * dmg_br / 0.925 - tol
    hi = dmg_br / 0.925 + tol
    return lo <= dmg_obs <= hi


_EVT_RE = __import__("re").compile(r"^Damage Side(One|Two): (-?\d+)$")


def _branch_move_damage(br) -> tuple[int, int]:
    """Largest single Damage event per side in this branch's instruction
    list — the move-damage component the roll band applies to (chips and
    heals are deterministic). Feeds the heal-aware SECONDARY band."""
    d = {"One": 0, "Two": 0}
    for ins in br.instruction_list:
        m = _EVT_RE.match(str(ins))
        if m:
            v = int(m.group(2))
            if v > d[m.group(1)]:
                d[m.group(1)] = v
    return d["One"], d["Two"]


def _hp_band_ok_ctx(dmg_obs: float, dmg_br: float, tol: float, d_move: float) -> bool:
    """Roll band applied to the MOVE component only: the branch's net hp
    delta dmg_br composes move damage d_move (average leaf ~0.925 x max,
    rolls 0.85..1.0 x max) with deterministic heals/chip. The strict
    checker gives net-heal turns a ZERO-variance band (measured: 161 of
    the 493 residual hp_band fails, 2026-08-22 turn-order diagnostic) —
    this band keeps their roll variance. Reduces exactly to the strict
    band when the branch is a single pure damage event."""
    if d_move <= 0:
        return abs(dmg_obs - dmg_br) <= tol
    lo = dmg_br - d_move + 0.85 * d_move / 0.925 - tol
    hi = dmg_br - d_move + d_move / 0.925 + tol
    return lo <= dmg_obs <= hi


def _match_branch(leaf, snap_next: dict, snap_now: dict, det: dict,
                  relaxed_opp_active: bool,
                  band_ctx: tuple[int, int] | None = None) -> tuple[bool, dict]:
    """Field-set comparison of one branch leaf vs the observed next state.
    `band_ctx` (heal-aware SECONDARY only): per-side move-damage components
    from _branch_move_damage; None keeps the strict pre-registered band."""
    fails = {}
    s1, s2 = leaf.side_one, leaf.side_two
    our_leaf, opp_leaf = _leaf_mons(s1), _leaf_mons(s2)
    team_next = {m["species"]: m for m in snap_next["team"]}
    team_now = {m["species"]: m for m in snap_now["team"]}
    opp_next = {m["species"]: m for m in snap_next["opponent_team"]}
    opp_now = {m["species"]: m for m in snap_now["opponent_team"]}

    # our active identity (unless the next state is our forced replacement)
    ai = snap_next["active_index"]
    if ai is not None and not snap_next["force_switch"]:
        if _active_of(s1).id.lower() != snap_next["team"][ai]["species"]:
            fails["our_active"] = True
    # their active identity
    oi = snap_next["opponent_active_index"]
    if oi is not None:
        obs_sp = snap_next["opponent_team"][oi]["species"]
        if relaxed_opp_active:
            # a forced replacement happened: the branch must have predicted
            # their previous active's faint instead
            prev_oi = snap_now["opponent_active_index"]
            prev_sp = snap_now["opponent_team"][prev_oi]["species"]
            m = opp_leaf.get(prev_sp)
            if m is None or m.hp > 0:
                fails["opp_faint_before_replacement"] = True
        elif _active_of(s2).id.lower() != obs_sp:
            fails["opp_active"] = True

    # per-mon: faints, status, HP band (ours exact ints, theirs fractions)
    for sp, m_next in team_next.items():
        lm = our_leaf.get(sp)
        m_now = team_now.get(sp)
        if lm is None or m_now is None:
            continue
        if (lm.hp <= 0) != m_next["fainted"]:
            fails.setdefault("faints", 0)
            fails["faints"] += 1
            continue
        if not m_next["fainted"]:
            st = str(lm.status).lower()
            st = st if st in _STATUS_CANON else "none"
            if st != _snap_status_engine(m_next):
                fails.setdefault("status", 0)
                fails["status"] += 1
            _obs = m_now["current_hp"] - m_next["current_hp"]
            _br = m_now["current_hp"] - lm.hp
            if not _hp_band_ok(_obs, _br, tol=1.5) and not (
                band_ctx is not None
                and _hp_band_ok_ctx(_obs, _br, 1.5, band_ctx[0])
            ):
                fails.setdefault("hp_band", 0)
                fails["hp_band"] += 1
    for sp, m_next in opp_next.items():
        lm = opp_leaf.get(sp)
        m_now = opp_now.get(sp)
        if lm is None:
            continue  # revealed after the step; det may not carry it
        if (lm.hp <= 0) != m_next["fainted"]:
            fails.setdefault("faints", 0)
            fails["faints"] += 1
            continue
        if not m_next["fainted"]:
            st = str(lm.status).lower()
            st = st if st in _STATUS_CANON else "none"
            if st != _snap_status_engine(m_next):
                fails.setdefault("status", 0)
                fails["status"] += 1
            f_now = m_now["current_hp_fraction"] if m_now else 1.0
            _obs = f_now - m_next["current_hp_fraction"]
            _br = f_now - (lm.hp / lm.maxhp if lm.maxhp else 0.0)
            if not _hp_band_ok(_obs, _br, tol=0.0155) and not (
                band_ctx is not None and lm.maxhp
                and _hp_band_ok_ctx(_obs, _br, 0.0155, band_ctx[1] / lm.maxhp)
            ):
                fails.setdefault("hp_band", 0)
                fails["hp_band"] += 1

    # boosts of the next actives (side-level in gen1)
    for side, snap_team, idx in ((s1, snap_next["team"], ai),
                                 (s2, snap_next["opponent_team"], oi)):
        if idx is None:
            continue
        b = snap_team[idx]["boosts"]
        got = (side.attack_boost, side.defense_boost, side.special_attack_boost,
               side.speed_boost, side.accuracy_boost, side.evasion_boost)
        want = (b["atk"], b["def"], b["spa"], b["spe"], b["accuracy"], b["evasion"])
        if got != want:
            fails["boosts"] = True

    # volatile sets of the next actives, named intersection (readback
    # UPPERCASES volatiles — normalized here). mustrecharge is compared as
    # its own field: the engine keeps MUSTRECHARGE after a KO where gen1's
    # server skips the recharge (measured — the KO-skip Hyper Beam rule),
    # so the caller can report coverage with and without it.
    if ai is not None and not snap_next["force_switch"]:
        want = _snap_volatiles(snap_next["team"][ai])
        got = {v.lower() for v in s1.volatile_statuses} & NAMED_VOLATILES
        if (got - {"mustrecharge"}) != (want - {"mustrecharge"}):
            fails["volatiles"] = True
        elif got != want:
            fails["recharge"] = True
    if oi is not None and not relaxed_opp_active:
        want = _snap_volatiles(snap_next["opponent_team"][oi])
        got = {v.lower() for v in s2.volatile_statuses} & NAMED_VOLATILES
        if (got - {"mustrecharge"}) != (want - {"mustrecharge"}):
            fails["volatiles_opp"] = True
        elif got != want:
            fails["recharge"] = True

    # sleep counters, +-1 (engine/poke-env conventions differ; exact rate
    # is recorded separately by the caller via this flag)
    if ai is not None:
        m_next = snap_next["team"][ai]
        lm = our_leaf.get(m_next["species"])
        if lm is not None and _snap_status_engine(m_next) == "sleep":
            if abs(int(lm.sleep_turns or 0) - m_next["status_counter"]) > 1:
                fails["sleep_counter"] = True
    return (not fails), fails


def fg2_battery(lanes, prereg: dict) -> dict:
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.expansion import expand_leaf
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import decision_rng, our_action_str
    from poke_engine import calculate_damage, generate_instructions

    move_by_num, species_by_num = _tables()
    n_det, top_b = 4, 6

    strata = Counter()
    fail_fields = Counter()
    results = {"normal": [0, 0], "placeholder": [0, 0]}  # [covered, total]
    ex_recharge = [0, 0]  # normal-stratum coverage excusing ONLY the KO-skip recharge flag
    healaware = [0, 0]    # normal-stratum coverage under the heal-aware band (SECONDARY)
    mass_on_observed = []
    ko_total = ko_disagree = ko_post_disagree = 0
    lane_seeds = {lane: int(lane[1:]) for lane in lanes}

    for lane, (pub, priv) in lanes.items():
        for bi, (b, p) in enumerate(zip(pub, priv)):
            snaps = [r["battle"] for r in b["rows"]] + [b["final_battle"]]
            for si, row in enumerate(b["rows"]):
                snap_now, snap_next = snaps[si], snaps[si + 1]
                choice = p["choices"][si]
                battle = rehydrate_battle(snap_now)
                rng = decision_rng(lane_seeds[lane], bi, battle.turn, si)
                dets = [sample_determinization(battle, rng) for _ in range(n_det)]

                a_str = "none" if row["aliased"] else our_action_str(battle, row["action"])
                placeholder = row["aliased"] or (
                    choice is not None and (choice["flags"] & 2)
                )
                # opponent's TRUE action, per det
                if choice is None:
                    b_strs = ["none"] * n_det
                elif choice["flags"] & 2:
                    b_strs = ["none"] * n_det
                elif choice["kind"] == 1:
                    mid = move_by_num.get(choice["id"])
                    if mid is None:  # fight/recharge placeholder or unknown
                        b_strs = ["none"] * n_det
                    else:
                        b_strs = [
                            mid if mid in det["opponents"].get(
                                battle.opponent_active_pokemon.species, {}
                            ).get("moves", []) else None
                            for det in dets
                        ]
                else:
                    sid = species_by_num.get(choice["id"])

                    def _switch_ok(det):
                        spec = det["opponents"].get(sid)
                        if spec is None or sid == battle.opponent_active_pokemon.species:
                            return False
                        live = spec.get("live")
                        return live is None or not live.fainted

                    b_strs = [sid if _switch_ok(det) else None for det in dets]
                if all(bs is None for bs in b_strs):
                    strata["action_unsimulable"] += 1
                    continue

                relaxed = row["waits_after"] > 0
                if relaxed:
                    strata["replacement_relaxed"] += 1
                covered = False
                covered_ex_recharge = False
                covered_healaware = False
                faint_covered = False  # FG-2k post-expansion: some variant
                best_mass = 0.0        # predicts the observed faint outcome
                branch_faint_pred = None
                obs_faints = (
                    {m["species"] for m in snap_next["team"] if m["fainted"]},
                    {m["species"] for m in snap_next["opponent_team"] if m["fainted"]},
                )
                comparable_opp = {m["species"] for m in snap_next["opponent_team"]}
                for det, bs in zip(dets, b_strs):
                    if bs is None:
                        continue
                    state = battle_to_state(battle, det, BridgeCounters())
                    try:
                        branches = generate_instructions(state, a_str, bs)
                    except BaseException:
                        strata["engine_reject"] += 1
                        continue
                    try:
                        dmg = calculate_damage(state, a_str, bs, True)
                    except BaseException:
                        dmg = None
                    branches = sorted(branches, key=lambda x: -x.percentage)[:top_b]
                    total = sum(x.percentage for x in branches) or 1.0
                    det_mass = 0.0
                    for br in branches:
                        dctx = _branch_move_damage(br)
                        raw_leaf = state.apply_instructions(br)
                        expanded = expand_leaf(state, raw_leaf, dmg)
                        if len(expanded) > 1 or expanded[0][0] is not raw_leaf:
                            # keep the average leaf matchable at ZERO mass: the
                            # 2-point split narrows the survivor band, but an
                            # observed near-average outcome is still model-covered
                            expanded = expanded + [(raw_leaf, 0.0)]
                        for leaf, w in expanded:
                            ok, fails = _match_branch(leaf, snap_next, snap_now, det, relaxed)
                            if ok:
                                covered = True
                                covered_ex_recharge = True
                                covered_healaware = True
                                det_mass += w * br.percentage / total
                            else:
                                if set(fails) == {"recharge"}:
                                    covered_ex_recharge = True
                                if not covered_healaware and _match_branch(
                                    leaf, snap_next, snap_now, det, relaxed,
                                    band_ctx=dctx,
                                )[0]:
                                    covered_healaware = True
                                for k in fails:
                                    fail_fields[k] += 1
                            our_leaf = _leaf_mons(leaf.side_one)
                            opp_leaf = _leaf_mons(leaf.side_two)
                            pred = (
                                {sp for sp, m in our_leaf.items() if m.hp <= 0},
                                {sp for sp, m in opp_leaf.items() if m.hp <= 0},
                            )
                            if (pred[0] == obs_faints[0]
                                    and (pred[1] & comparable_opp)
                                    == (obs_faints[1] & comparable_opp)):
                                faint_covered = True
                        if branch_faint_pred is None:  # max-mass RAW branch
                            our_leaf = _leaf_mons(raw_leaf.side_one)
                            opp_leaf = _leaf_mons(raw_leaf.side_two)
                            branch_faint_pred = (
                                {sp for sp, m in our_leaf.items() if m.hp <= 0},
                                {sp for sp, m in opp_leaf.items() if m.hp <= 0},
                            )
                    best_mass = max(best_mass, det_mass)
                key = "placeholder" if placeholder else "normal"
                results[key][1] += 1
                results[key][0] += int(covered)
                if not placeholder:
                    ex_recharge[0] += int(covered_ex_recharge)
                    ex_recharge[1] += 1
                    healaware[0] += int(covered_healaware)
                    healaware[1] += 1
                if "ditto" in (battle.opponent_active_pokemon.species,):
                    strata["opp_active_ditto"] += 1
                if covered:
                    mass_on_observed.append(best_mass)
                # FG-2k on the max-mass branch of the first simulable det:
                # average-roll faint/no-faint vs the server's, restricted to
                # mons both sides can name (ours all; theirs revealed-in-det)
                if branch_faint_pred is not None and not placeholder:
                    pred_our, pred_opp = branch_faint_pred
                    ko_total += 1
                    ko_disagree += int(
                        pred_our != obs_faints[0]
                        or (pred_opp & comparable_opp)
                        != (obs_faints[1] & comparable_opp)
                    )
                    ko_post_disagree += int(not faint_covered)

    cov_n, tot_n = results["normal"]
    cov_p, tot_p = results["placeholder"]
    unsim = strata["action_unsimulable"]
    mass = np.array(mass_on_observed) if mass_on_observed else np.array([0.0])
    return {
        "gate": "FG-2/FG-2p/FG-2k",
        "bars": {"FG-2": ">=0.98 covered", "FG-2p": ">=0.95", "FG-2k": "recorded; >0.05 -> 2-point roll expansion"},
        "blocking": True,
        "n_transitions": tot_n + tot_p + unsim,
        "fg2_covered_given_simulable": cov_n / max(tot_n, 1),
        "fg2_n": tot_n,
        "fg2_pass": bool(cov_n / max(tot_n, 1) >= 0.98),
        "fg2_covered_ex_recharge_SECONDARY": ex_recharge[0] / max(ex_recharge[1], 1),
        "fg2_ex_recharge_note": ("recharge excused = branch matched everything except "
                                 "the engine's MUSTRECHARGE after a KO, where gen1's "
                                 "server skips the recharge (KO-skip Hyper Beam rule); "
                                 "recorded, never governing — the primary keeps the "
                                 "pre-registered field set"),
        "fg2_ruling": ("RULED (b), maintainer 2026-08-22: ACCEPTED at the "
                       "measured primary with the residual map as NAMED "
                       "STRATA (fg2_pass keeps reporting vs the original "
                       "0.98 bar — the number is never rewritten); R2 "
                       "adjudicates whether flips WIN. Full map: the "
                       "2026-08-22 turn-order-diagnostic log entry."),
        "fg2_covered_healaware_SECONDARY": healaware[0] / max(healaware[1], 1),
        "fg2_healaware_note": ("heal-aware = the roll band applied to the branch's "
                               "move-damage component only (heals/chip deterministic); "
                               "the strict band gives net-heal turns zero variance — a "
                               "checker artifact, 161/493 residual hp_band fails in the "
                               "turn-order diagnostic. Recorded, never governing, until "
                               "the maintainer rules on promoting it"),
        "fg2p_covered": cov_p / max(tot_p, 1),
        "fg2p_n": tot_p,
        "fg2p_pass": bool(cov_p / max(tot_p, 1) >= 0.95),
        "fg2_covered_unconditional": (cov_n + cov_p) / max(tot_n + tot_p + unsim, 1),
        "action_unsimulable_frac": unsim / max(tot_n + tot_p + unsim, 1),
        "strata": dict(strata),
        "branch_fail_fields": dict(fail_fields),
        "mass_on_observed_mean": float(mass.mean()),
        "mass_on_observed_ge_0.05": float((mass >= 0.05).mean()),
        "fg2k_ko_disagreement": ko_disagree / max(ko_total, 1),
        "fg2k_n": ko_total,
        "fg2k_expansion_needed": bool(ko_disagree / max(ko_total, 1) > 0.05),
        "fg2k_post_expansion_residual": ko_post_disagree / max(ko_total, 1),
        "fg2k_post_expansion_note": ("fraction of transitions where NO expanded "
                                     "variant of any retained branch predicts the "
                                     "observed faint outcome — what the built "
                                     "2-point expansion does not recover"),
    }


# ---------------------------------------------------------------------------
# FG-3 — 5-step drift (recorded, non-blocking)
# ---------------------------------------------------------------------------

def fg3_drift(lanes, horizon: int = 5) -> dict:
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import decision_rng, our_action_str
    from poke_engine import generate_instructions

    move_by_num, species_by_num = _tables()
    hp_drifts, faint_drifts = [], []
    windows = skipped = 0
    for lane, (pub, priv) in lanes.items():
        for bi, (b, p) in enumerate(zip(pub, priv)):
            rows = b["rows"]
            if len(rows) < horizon + 1:
                continue
            start = 0
            battle0 = rehydrate_battle(rows[start]["battle"])
            rng = decision_rng(9000, bi, battle0.turn, start)
            det = sample_determinization(battle0, rng)
            state = battle_to_state(battle0, det, BridgeCounters())
            ok = True
            for si in range(start, start + horizon):
                row, choice = rows[si], p["choices"][si]
                battle = rehydrate_battle(row["battle"])
                a_str = "none" if row["aliased"] else our_action_str(battle, row["action"])
                if choice is None or (choice["flags"] & 2):
                    bs = "none"
                elif choice["kind"] == 1:
                    bs = move_by_num.get(choice["id"])
                else:
                    bs = species_by_num.get(choice["id"])
                if bs is None:
                    ok = False
                    break
                try:
                    branches = generate_instructions(state, a_str, bs)
                except BaseException:
                    ok = False
                    break
                if not branches:
                    ok = False
                    break
                br = max(branches, key=lambda x: x.percentage)
                state = state.apply_instructions(br)
            if not ok:
                skipped += 1
                continue
            windows += 1
            snap5 = rows[start + horizon]["battle"]
            our_leaf = _leaf_mons(state.side_one)
            diffs = []
            faint_pred = faint_obs = 0
            for m in snap5["team"]:
                lm = our_leaf.get(m["species"])
                if lm is None:
                    continue
                diffs.append(abs((lm.hp / lm.maxhp if lm.maxhp else 0) - m["current_hp_fraction"]))
                faint_pred += int(lm.hp <= 0)
                faint_obs += int(m["fainted"])
            opp_leaf = _leaf_mons(state.side_two)
            for m in snap5["opponent_team"]:
                lm = opp_leaf.get(m["species"])
                if lm is None:
                    continue
                diffs.append(abs((lm.hp / lm.maxhp if lm.maxhp else 0) - m["current_hp_fraction"]))
            if diffs:
                hp_drifts.append(float(np.mean(diffs)))
            faint_drifts.append(abs(faint_pred - faint_obs))
    hp = np.array(hp_drifts) if hp_drifts else np.array([0.0])
    return {
        "gate": "FG-3", "blocking": False, "flag_bar": 0.10,
        "windows": windows, "skipped_windows": skipped, "horizon": horizon,
        "hp_frac_drift_mean": float(hp.mean()), "hp_frac_drift_p90": float(np.percentile(hp, 90)),
        "faint_count_drift_mean": float(np.mean(faint_drifts)) if faint_drifts else 0.0,
        "flagged": bool(hp.mean() > 0.10),
    }


# ---------------------------------------------------------------------------
# FG-4 — leak gate (static half; the live sentinel runs at R2 chunk 0, SF-13)
# ---------------------------------------------------------------------------

def fg4_static() -> dict:
    search_dir = Path("rl/search")
    text = {p.name: p.read_text() for p in search_dir.glob("*.py")}
    # calculate_damage is design-ALLOWED (§2 "pure transition function" list);
    # the engine's SEARCH entry points are not.
    forbidden = {
        "fp_import": ["import fp", "from fp"],
        "engine_search_entry": ["mcts(", "monte_carlo", "iterative_deepening"],
        "privileged_reads": ["harvest_priv", "battle2", 'info["privileged"]'],
    }
    hits = defaultdict(list)
    for name, src in text.items():
        for cat, pats in forbidden.items():
            for pat in pats:
                if pat in src:
                    hits[cat].append(f"{name}: {pat}")
    provenance_asserted = "provenance" in text.get("bridge.py", "")
    return {
        "gate": "FG-4 (static half)",
        "blocking": True,
        "note": ("raise-on-access sentinel + poisoned-battle run at chunk 0 of "
                 "every verdict arm (SF-13, R2 driver); rl/search consumes only "
                 "battle1-derived snapshots by construction (freeze_battle)"),
        "forbidden_hits": dict(hits),
        "rsd_provenance_asserted": provenance_asserted,
        "pass": not hits and provenance_asserted,
    }


# ---------------------------------------------------------------------------
# FG-7 — RSD support (seat-2 truth, offline only)
# ---------------------------------------------------------------------------

def fg7_support(lanes) -> dict:
    from rl.envs import randbats_prior
    from rl.search.determinize import _TeamCaps, sample_determinization
    from rl.search.harvest import rehydrate_battle

    known = randbats_prior.known_species()
    n = in_support = 0
    fail_reasons = Counter()
    recalls = []
    for lane, (pub, priv) in lanes.items():
        for bi, (b, p) in enumerate(zip(pub, priv)):
            true_team = p["true_team"]
            n += 1
            ok = True
            missing = [sp for sp in true_team if sp not in known]
            if missing:
                fail_reasons["species_not_in_pool"] += 1
                ok = False
            caps = _TeamCaps()
            if ok:
                for sp in true_team:
                    caps.admit(sp)
                if (any(v > 2 for v in caps.type_count.values())
                        or any(v > 2 for v in caps.weak_count.values())
                        or caps.max_level > 1):
                    fail_reasons["true_team_violates_caps"] += 1
                    ok = False
            if ok:
                for sp, spec in true_team.items():
                    probs = dict(randbats_prior.conditional_move_probs(sp, frozenset()))
                    if any(m not in probs or probs[m] <= 0 for m in spec["moves"]):
                        fail_reasons["true_moves_outside_set_support"] += 1
                        ok = False
                        break
            in_support += int(ok)
            # top-1 species recall on unrevealed slots at the LAST decision
            last = b["rows"][-1]["battle"]
            revealed = {m["species"] for m in last["opponent_team"]}
            unrevealed = set(true_team) - revealed
            if unrevealed:
                battle = rehydrate_battle(last)
                det = sample_determinization(battle, np.random.default_rng(bi))
                sampled = set(det["opponents"]) - revealed
                recalls.append(len(sampled & unrevealed) / len(unrevealed))
    return {
        "gate": "FG-7", "bar": ">=0.99", "blocking": True,
        "n_battles": n, "true_team_in_support": in_support / max(n, 1),
        "fail_reasons": dict(fail_reasons),
        "top1_species_recall_unrevealed_recorded": float(np.mean(recalls)) if recalls else None,
        "note": "support != calibration (SF-3); recall is recorded, never governing",
        "pass": bool(in_support / max(n, 1) >= 0.99),
    }


# ---------------------------------------------------------------------------
# model-based reads: oppact sh_accuracy/sh_nll, successor ranking, Z2'
# ---------------------------------------------------------------------------

def _load_agent(spec: dict):
    import gymnasium as gym

    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.envs.showdown import OBS_DIM
    from rl.train import make_agent

    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    env = gym.Env()
    env.observation_space = gym.spaces.Box(-1.0, 4.0, shape=(OBS_DIM,), dtype=np.float32)
    env.action_space = gym.spaces.Discrete(10)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg


def oppact_reads(lanes, prereg: dict) -> dict:
    import torch

    from rl.common.masking import masked_logits
    from rl.networks.opp_action import canonicalise

    out = {}
    for lane, (pub, priv) in lanes.items():
        agent, _ = _load_agent(prereg["checkpoints"][lane])
        obs, choices = [], []
        for b, p in zip(pub, priv):
            for row, ch in zip(b["rows"], p["choices"]):
                obs.append(row["obs"])
                choices.append(
                    (ch["kind"], ch["id"], ch["flags"]) if ch else (-1, -1, 0)
                )
        obs_t = torch.as_tensor(np.stack(obs), dtype=torch.float32)
        ch_t = torch.as_tensor(np.array(choices, dtype=np.int64))
        with torch.no_grad():
            _, *feats = agent.actor(obs_t, return_features=True)
            logits = agent.aux_head(*feats)
        target, allow, valid, stats = canonicalise(obs_t, ch_t, agent.actor.tokenizer)
        ml = masked_logits(logits, allow.bool())
        logp = torch.log_softmax(ml, dim=-1)
        v = valid.bool()
        acc = float((ml[v].argmax(-1) == target[v]).float().mean())
        nll = float(-logp[v].gather(1, target[v].unsqueeze(1)).mean())
        q = torch.softmax(logits, dim=-1)
        ent = -(q * torch.log(q + 1e-12)).sum(-1)
        out[lane] = {
            "sh_accuracy": acc, "sh_nll": nll,
            "n_valid": int(v.sum()), "n": len(obs),
            "labelled_frac": stats["aux/labelled_frac"],
            "entropy_median": float(ent.median()),
            "entropy_frac_above_0.95ln6": float((ent > 0.95 * np.log(6)).float().mean()),
        }
    accs = [o["sh_accuracy"] for o in out.values()]
    return {
        "read": "oppact/sh_accuracy + sh_nll (R1, zero battles)",
        "per_lane": out,
        "pooled_accuracy_mean": float(np.mean(accs)),
        "marginal_baseline_note": "L6 argmax-marginal baseline ~= slot-0 frequency (R0 audit: 0.436)",
    }


def successor_ranking(lanes, prereg: dict) -> dict:
    import torch

    sys.path.insert(0, "scripts")
    from ch3_audit import _auc

    per_lane = {}
    pooled_v, pooled_y, pooled_rel = [], [], []
    for lane, (pub, _) in lanes.items():
        agent, _ = _load_agent(prereg["checkpoints"][lane])
        obs_next, labels, rels, pmax_obs, masks = [], [], [], [], []
        for b in pub:
            rows = b["rows"]
            fin = max(rows[-1]["turn"], 1)
            for si in range(len(rows) - 1):
                obs_next.append(rows[si + 1]["obs"])
                labels.append(1 if b["outcome"] > 0 else 0)
                rels.append(min(rows[si + 1]["turn"] / fin, 1.0))
                pmax_obs.append(rows[si]["obs"])
                masks.append(rows[si]["mask"])
        obs_t = torch.as_tensor(np.stack(pmax_obs), dtype=torch.float32)
        mask_t = torch.as_tensor(np.stack(masks))
        with torch.no_grad():
            from rl.common.masking import masked_logits as _ml
            logits, *_ = agent.actor(obs_t, return_features=True)
            probs = torch.softmax(_ml(logits, mask_t), dim=-1)  # masked, as R0.A
            pmax = probs.max(-1).values.numpy()
            v_next = agent.critic(
                torch.as_tensor(np.stack(obs_next), dtype=torch.float32)
            ).reshape(-1).numpy()
        contested = pmax < 0.90
        y = np.array(labels)[contested]
        v = v_next[contested]
        rel = np.array(rels)[contested]
        pooled_v.append(v); pooled_y.append(y); pooled_rel.append(rel)
        per_lane[lane] = {"n_contested": int(contested.sum()),
                          "contested_frac": float(contested.mean())}
    v = np.concatenate(pooled_v); y = np.concatenate(pooled_y)
    rel = np.concatenate(pooled_rel)
    decile = np.minimum((rel * 10).astype(int), 9)
    mid = (decile >= 1) & (decile <= 7)
    return {
        "read": "successor-ranking (V's ordering of TRUE next states at contested decisions)",
        "definition": "AUC of V(s_{t+1}) vs episode outcome, pooled turn deciles 2-8, p_max<0.90",
        "per_lane": per_lane,
        "auc_pooled_deciles_2_8": _auc(v[mid], y[mid]),
        "auc_all_contested": _auc(v, y),
        "k0_1_context": "K0-1 passed at 0.780 on root states; this is the matched revisit statistic",
    }


def z2_truncation(lanes, prereg: dict, n_states: int = 500) -> dict:
    import torch

    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import DOSES, Dose, decision_rng, solve_decision
    from rl.search.agent import SearchAgent

    full = Dose(n_det=4, top_branches=999, leaf_cap=10 ** 6, node_cap=None)
    deltas, retained = [], []
    per_lane_n = max(n_states // len(lanes), 1)
    for lane, (pub, _) in lanes.items():
        agent, cfg = _load_agent(prereg["checkpoints"][lane])
        sa = SearchAgent(agent, DOSES["M"], checkpoint_seed=cfg.seed)
        pool = [(bi, si) for bi, b in enumerate(pub)
                for si, row in enumerate(b["rows"]) if not row["aliased"]]
        for k in np.linspace(0, len(pool) - 1, num=per_lane_n, dtype=int):
            bi, si = pool[k]
            row = pub[bi]["rows"][si]
            battle = rehydrate_battle(row["battle"])
            prior, q = sa._forward(row["obs"], row["mask"])
            evs = []
            for dose in (DOSES["M"], full):
                rng = decision_rng(cfg.seed, bi, battle.turn, si)
                _, stats = solve_decision(
                    battle, np.asarray(row["mask"]), q, prior, dose, rng,
                    sa._critic_fn, sa._type_chart,
                )
                evs.append(np.array(stats["search/ev_matrix"]))
                if dose is DOSES["M"]:
                    retained.append(stats["search/retained_mass_mean"])
            a, b_ = evs
            if a.shape == b_.shape:
                deltas.append(float(np.max(np.abs(a - b_))))
    d = np.array(deltas) if deltas else np.array([0.0])
    r = np.array(retained) if retained else np.array([1.0])
    return {
        "read": "Z2' truncation probe (|top-6 - all-branch| cell delta) + retained_mass",
        "n_states": len(deltas),
        "cell_delta_max_mean": float(d.mean()),
        "cell_delta_max_p95": float(np.percentile(d, 95)),
        "cell_delta_max_max": float(d.max()),
        "retained_mass_mean": float(r.mean()),
        "retained_mass_flag_lt_0.95": bool(r.mean() < 0.95),
    }


def unmodellable_freqs(lanes) -> dict:
    n = opp_recharge = opp_trapped = 0
    ls_moves = choice_moves = 0
    for lane, (pub, priv) in lanes.items():
        for b, p in zip(pub, priv):
            for row in b["rows"]:
                n += 1
                oi = row["battle"]["opponent_active_index"]
                if oi is not None:
                    m = row["battle"]["opponent_team"][oi]
                    opp_recharge += int(m["must_recharge"])
                    opp_trapped += int(any(
                        e in ("TRAPPED", "PARTIALLY_TRAPPED", "BINDING")
                        for e in m["effects"]
                    ))
            for ch in p["choices"]:
                if ch and ch["kind"] == 1:
                    choice_moves += 1
                    if "lightscreen" in ch["order"].replace(" ", "").lower():
                        ls_moves += 1
    return {
        "read": "unmodellable frequencies (honesty notes)",
        "n_decisions": n,
        "opp_mustrecharge_frac": opp_recharge / max(n, 1),
        "opp_partialtrap_frac": opp_trapped / max(n, 1),
        "sh_lightscreen_use_per_move_choice": ls_moves / max(choice_moves, 1),
    }


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", default="configs/eval/ch3_rung0.yaml")
    ap.add_argument("--harvest", default="results/ch3_r1")
    ap.add_argument("--fg5", action="store_true", help="attestation only")
    ap.add_argument("--skip-model", action="store_true",
                    help="skip checkpoint-based reads (oppact/successor/Z2')")
    args = ap.parse_args()

    report = {"fg5": fg5_attestation()}
    if args.fg5:
        print(json.dumps(report["fg5"], indent=2))
        return

    import os

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required"
    from poke_env.data import GenData

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    harvest_dir = Path(args.harvest)
    lanes = load_lanes(prereg, harvest_dir)
    type_chart = GenData.from_format("gen1randombattle").type_chart

    for name, fn in [
        ("fg4", lambda: fg4_static()),
        ("fg1", lambda: fg1_string_stability(lanes)),
        ("fg7", lambda: fg7_support(lanes)),
        ("fg6", lambda: fg6_encoder_parity(lanes, type_chart)),
        ("fg2", lambda: fg2_battery(lanes, prereg)),
        ("fg3", lambda: fg3_drift(lanes)),
        ("unmodellable", lambda: unmodellable_freqs(lanes)),
    ]:
        t0 = time.time()
        report[name] = fn()
        print(f"{name}: done in {time.time() - t0:.1f}s")
    if not args.skip_model:
        for name, fn in [
            ("oppact", lambda: oppact_reads(lanes, prereg)),
            ("successor_ranking", lambda: successor_ranking(lanes, prereg)),
            ("z2_truncation", lambda: z2_truncation(lanes, prereg)),
        ]:
            t0 = time.time()
            report[name] = fn()
            print(f"{name}: done in {time.time() - t0:.1f}s")

    out = harvest_dir / "fg_battery.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {out}\n")
    for k in ("fg1", "fg2", "fg4", "fg5", "fg6", "fg7"):
        r = report.get(k, {})
        verdict = r.get("pass")
        if k == "fg2":
            print(f"FG-2  covered|simulable {r['fg2_covered_given_simulable']:.4f} "
                  f"(n={r['fg2_n']}, pass={r['fg2_pass']}) | FG-2p {r['fg2p_covered']:.4f} "
                  f"(pass={r['fg2p_pass']}) | FG-2k ko {r['fg2k_ko_disagreement']:.4f} "
                  f"(expansion={r['fg2k_expansion_needed']}) | unsimulable "
                  f"{r['action_unsimulable_frac']:.4f}")
        else:
            print(f"{r.get('gate', k)}: pass={verdict}")


if __name__ == "__main__":
    main()
