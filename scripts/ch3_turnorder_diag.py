"""CH3 R1 — the FG-2 turn-order diagnostic (STATUS next-action, 2026-08-22).

    python scripts/ch3_turnorder_diag.py --prereg configs/eval/ch3_rung0.yaml

FG-2 sits at 0.9074 vs the 0.98 bar after the roll expansion + Ditto
bridge. This script re-runs the FG-2 coverage loop (same dets — identical
decision_rng stream — same top-6 truncation, same expansion) and, for every
NORMAL-stratum transition the branch set fails to cover, runs counterfactual
probes that attribute the failure to a named family:

  P1  truncation   — coverage with the top-6 branch cap LIFTED (all engine
                     branches kept). Covers => the observed outcome was in a
                     branch we threw away; the covering branch's mass RANK is
                     recorded, which prices a "raise top_b" repair directly.
  P2  we-first     — cap lifted AND the opponent active's speed forced to 1
  P3  opp-first    — cap lifted AND forced to 9999 (bridge's
                     opp_active_speed_override; gen1 damage never reads
                     speed, so this flips action order and nothing else —
                     crit RATE shifts branch weights, never membership).
                     Either covers when P1 didn't => turn_order: the
                     determinized relative speed put the actions in the
                     wrong order (wrong-DV tail, engine/server order edge).
  pattern reads    — newly-slept / newly-frozen mons this turn (the engine
                     lets a freshly-slept mon still self-KO — measured,
                     engine-internal), recorded as flags on what remains.

Engine facts this diagnostic leans on (probed 2026-08-22, this session):
  - the engine DOES branch both orders on an exact effective-speed tie
    (8 branches, 50/50) — ties are a truncation/mass problem, not a
    missing-branch problem;
  - paralysis speed-quartering is applied by the engine;
  - the sleep-success branch of a faster sleeper still applies the slept
    mon's Explosion SELF-KO (no damage dealt) — engine-internal.

Residual (nothing recovers it) transitions get a minimal fail-field
signature histogram — the map for the status/band-tail pass.

Writes results/ch3_r1/turnorder_diag.json. Purely diagnostic: consumes the
harvest + privileged files exactly like the FG battery (offline seat-2 use
is design §8.4-allowed); nothing under rl/search/ changes behavior here.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch3_fidelity_check as fc  # noqa: E402  (helpers + load_lanes)

# gen1 stat-stage multipliers (x100), index = boost + 6
_STAGE = (25, 28, 33, 40, 50, 66, 100, 150, 200, 250, 300, 350, 400)


def _eff_speed(raw: int, boost: int, para: bool) -> int:
    s = raw * _STAGE[max(-6, min(6, boost)) + 6] // 100
    return s // 4 if para else s


def _newly_statused(snap_now: dict, snap_next: dict, which: str) -> list[tuple[str, str]]:
    """(side, species) for mons whose status became `which` this turn and
    who are alive in the observed next state."""
    out = []
    for side_key, side_name in (("team", "us"), ("opponent_team", "opp")):
        now = {m["species"]: m for m in snap_now[side_key]}
        for m in snap_next[side_key]:
            if m["fainted"]:
                continue
            if fc._snap_status_engine(m) != which:
                continue
            prev = now.get(m["species"])
            if prev is not None and fc._snap_status_engine(prev) != which:
                out.append((side_name, m["species"]))
    return out


def _coverage(battle, dets, b_strs, a_str, snap_now, snap_next, relaxed,
              top_b, speed_override, strata):
    """One FG-2 coverage pass. Returns (covered, cover_rank, best_fails,
    leaf_faint_sets) — cover_rank is the mass rank (0-based) of the branch
    the first covering leaf came from; best_fails the fewest-fail dict seen;
    leaf_faint_sets the union of {species: fainted-in-some-leaf} per side."""
    from poke_engine import calculate_damage, generate_instructions

    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.expansion import expand_leaf

    covered = False
    cover_rank = None
    best_fails = None
    best_leaf = None
    best_det_idx = None
    faint_union = (set(), set())
    for det_idx, (det, bs) in enumerate(zip(dets, b_strs)):
        if bs is None:
            continue
        state = battle_to_state(
            battle, det, BridgeCounters(),
            opp_active_speed_override=speed_override,
        )
        try:
            branches = generate_instructions(state, a_str, bs)
        except BaseException:
            strata["engine_reject"] += 1
            continue
        try:
            dmg = calculate_damage(state, a_str, bs, True)
        except BaseException:
            dmg = None
        branches = sorted(branches, key=lambda x: -x.percentage)
        if top_b is not None:
            branches = branches[:top_b]
        for rank, br in enumerate(branches):
            raw_leaf = state.apply_instructions(br)
            expanded = expand_leaf(state, raw_leaf, dmg)
            if len(expanded) > 1 or expanded[0][0] is not raw_leaf:
                expanded = expanded + [(raw_leaf, 0.0)]
            for leaf, _w in expanded:
                ok, fails = fc._match_branch(leaf, snap_next, snap_now, det, relaxed)
                if ok:
                    covered = True
                    if cover_rank is None:
                        cover_rank = rank
                elif best_fails is None or len(fails) < len(best_fails):
                    best_fails = fails
                    best_leaf = leaf
                    best_det_idx = det_idx
                our_leaf = fc._leaf_mons(leaf.side_one)
                opp_leaf = fc._leaf_mons(leaf.side_two)
                faint_union[0].update(sp for sp, m in our_leaf.items() if m.hp <= 0)
                faint_union[1].update(sp for sp, m in opp_leaf.items() if m.hp <= 0)
        if covered:
            break  # attribution needs existence, not mass
    return covered, cover_rank, best_fails, faint_union, best_leaf, best_det_idx


def _band_detail(leaf, snap_now, snap_next):
    """For a best-leaf that fails ONLY hp_band: which ACTIVE mon sits outside
    the roll band, and by how much. Returns [(side, species, signed_dist)]
    where dist>0 means observed damage ABOVE the band's high edge (more
    damage than any roll explains) and dist<0 below the low edge, in our
    case absolute HP, in theirs HP fraction."""
    out = []
    team_next = {m["species"]: m for m in snap_next["team"]}
    team_now = {m["species"]: m for m in snap_now["team"]}
    opp_next = {m["species"]: m for m in snap_next["opponent_team"]}
    opp_now = {m["species"]: m for m in snap_now["opponent_team"]}
    for side_name, leaf_side, nxt, now, tol, frac in (
        ("us", leaf.side_one, team_next, team_now, 1.5, False),
        ("opp", leaf.side_two, opp_next, opp_now, 0.0155, True),
    ):
        mons = fc._leaf_mons(leaf_side)
        for sp, m_next in nxt.items():
            lm, m_now = mons.get(sp), now.get(sp)
            if lm is None or m_now is None or m_next["fainted"] or lm.hp <= 0:
                continue
            if frac:
                dmg_obs = m_now["current_hp_fraction"] - m_next["current_hp_fraction"]
                dmg_br = dmg_obs if lm.maxhp == 0 else (
                    (m_now["current_hp_fraction"] * lm.maxhp - lm.hp) / lm.maxhp
                )
            else:
                dmg_obs = m_now["current_hp"] - m_next["current_hp"]
                dmg_br = m_now["current_hp"] - lm.hp
            if fc._hp_band_ok(dmg_obs, dmg_br, tol):
                continue
            if dmg_br <= 0:
                out.append((side_name, sp, dmg_obs - dmg_br, dmg_obs, dmg_br))
                continue
            lo = 0.85 * dmg_br / 0.925 - tol
            hi = dmg_br / 0.925 + tol
            out.append((side_name, sp,
                        (dmg_obs - hi) if dmg_obs > hi else (dmg_obs - lo),
                        dmg_obs, dmg_br))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prereg", default="configs/eval/ch3_rung0.yaml")
    ap.add_argument("--harvest", default="results/ch3_r1")
    ap.add_argument("--max-battles", type=int, default=None,
                    help="per lane, for smokes")
    args = ap.parse_args()

    from rl.search.determinize import sample_determinization
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import decision_rng, our_action_str

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    harvest_dir = Path(args.harvest)
    lanes = fc.load_lanes(prereg, harvest_dir)
    move_by_num, species_by_num = fc._tables()
    n_det, top_b = 4, 6

    strata = Counter()
    attribution = Counter()
    cover_rank_hist = Counter()   # truncation cases: rank of covering branch
    order_probe_detail = Counter()  # which override recovered
    residual_sigs = Counter()
    residual_fail_fields = Counter()
    hpband_mover = Counter()      # (damaging move, direction) for band fails
    hpband_side = Counter()
    hpband_dists = {"us": [], "opp": []}
    hpband_examples = []
    hpband_subfamily = Counter()
    plain_detail = []  # (side, dist) for every plain-subfamily band fail
    sleep_flags = Counter()
    tie_stats = Counter()         # effective-speed relation on uncovered turns
    n_normal = n_covered = 0

    t0 = time.time()
    for lane, (pub, priv) in lanes.items():
        lane_seed = int(lane[1:])
        for bi, (b, p) in enumerate(zip(pub, priv)):
            if args.max_battles is not None and bi >= args.max_battles:
                break
            snaps = [r["battle"] for r in b["rows"]] + [b["final_battle"]]
            for si, row in enumerate(b["rows"]):
                snap_now, snap_next = snaps[si], snaps[si + 1]
                choice = p["choices"][si]
                battle = rehydrate_battle(snap_now)
                rng = decision_rng(lane_seed, bi, battle.turn, si)
                dets = [sample_determinization(battle, rng) for _ in range(n_det)]

                a_str = "none" if row["aliased"] else our_action_str(battle, row["action"])
                placeholder = row["aliased"] or (
                    choice is not None and (choice["flags"] & 2)
                )
                if placeholder:
                    continue  # FG-2p stratum: out of scope per ruling
                if choice is None:
                    b_strs = ["none"] * n_det
                elif choice["kind"] == 1:
                    mid = move_by_num.get(choice["id"])
                    if mid is None:
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
                n_normal += 1

                covered, _, _, _, _, _ = _coverage(
                    battle, dets, b_strs, a_str, snap_now, snap_next,
                    relaxed, top_b, None, strata,
                )
                if covered:
                    n_covered += 1
                    continue

                # ---- probes on the uncovered transition ----
                # descriptive: effective-speed relation in det 0 vs us
                our = battle.active_pokemon
                opp = battle.opponent_active_pokemon
                det0 = dets[0]
                spec = det0["opponents"].get(opp.species) or {}
                bs0 = spec.get("base_stats") or {}
                from rl.search.bridge import _status_str, gen1_stat
                opp_raw = gen1_stat(
                    bs0.get("spe", 100), spec.get("level") or 100,
                    dv=(spec.get("dvs") or {}).get("spe", 15),
                )
                eff_us = _eff_speed(
                    int((our.stats or {}).get("spe") or 0),
                    int((our.boosts or {}).get("spe", 0)),
                    _status_str(our) == "paralyze",
                )
                eff_opp = _eff_speed(
                    opp_raw,
                    int((opp.boosts or {}).get("spe", 0)),
                    _status_str(opp) == "paralyze",
                )
                d = eff_us - eff_opp
                tie_stats["exact_tie" if d == 0 else
                          ("near_tie_le2" if abs(d) <= 2 else
                           ("we_faster" if d > 0 else "opp_faster"))] += 1

                p1, p1_rank, p1_fails, p1_faints, p1_leaf, p1_det = _coverage(
                    battle, dets, b_strs, a_str, snap_now, snap_next,
                    relaxed, None, None, strata,
                )
                if p1:
                    attribution["truncation"] += 1
                    cover_rank_hist[p1_rank] += 1
                    continue
                p2, _, _, _, _, _ = _coverage(
                    battle, dets, b_strs, a_str, snap_now, snap_next,
                    relaxed, None, 1, strata,
                )
                p3 = False
                if not p2:
                    p3, _, _, _, _, _ = _coverage(
                        battle, dets, b_strs, a_str, snap_now, snap_next,
                        relaxed, None, 9999, strata,
                    )
                if p2 or p3:
                    attribution["turn_order"] += 1
                    order_probe_detail["we_first_covers" if p2 else "opp_first_covers"] += 1
                    continue

                # residual: pattern flags + minimal fail signature (from P1,
                # the untruncated same-speed pass)
                newly_slept = _newly_statused(snap_now, snap_next, "sleep")
                newly_frozen = _newly_statused(snap_now, snap_next, "freeze")
                selfko = any(
                    sp in p1_faints[0 if side == "us" else 1]
                    for side, sp in newly_slept + newly_frozen
                )
                if selfko:
                    attribution["sleep_interrupt_selfko"] += 1
                    continue
                attribution["residual"] += 1
                if newly_slept:
                    sleep_flags["residual_newly_slept"] += 1
                if newly_frozen:
                    sleep_flags["residual_newly_frozen"] += 1
                sig = tuple(sorted(p1_fails)) if p1_fails else ("<no simulable det>",)
                residual_sigs[sig] += 1
                for k in (p1_fails or {}):
                    residual_fail_fields[k] += 1
                if sig == ("hp_band",) and p1_leaf is not None:
                    details = _band_detail(p1_leaf, snap_now, snap_next)
                    # subfamily tags, one per CASE (priority order)
                    ditto_involved = (
                        battle.active_pokemon.species == "ditto"
                        or battle.opponent_active_pokemon.species == "ditto"
                        or any(sp == "ditto" for _, sp, *_ in details)
                    )
                    net_heal = any(d_br <= 0 for *_, d_br in details)
                    chip = any(
                        (nowm.get(sp, {}).get("status") in
                         ("BRN", "PSN", "TOX"))
                        or "LEECH_SEED" in nowm.get(sp, {}).get("effects", [])
                        for nowm in (
                            {m["species"]: m for m in snap_now["team"]},
                            {m["species"]: m for m in snap_now["opponent_team"]},
                        )
                        for _, sp, *_ in details
                    )
                    fam = ("ditto" if ditto_involved else
                           ("net_heal" if net_heal else
                            ("chip_status" if chip else "plain")))
                    hpband_subfamily[fam] += 1
                    if fam == "plain":
                        plain_detail.extend(
                            (sn, round(float(dd), 4)) for sn, _, dd, *_ in details
                        )
                    for side_name, sp, dist, dmg_obs, dmg_br in details:
                        # damage TO opp active came from OUR move; damage to
                        # our side from the opponent's true action
                        mover = a_str if side_name == "opp" else (
                            b_strs[p1_det] or "<switch/none>"
                        )
                        direction = "above_band" if dist > 0 else "below_band"
                        hpband_mover[f"{mover}|{direction}"] += 1
                        hpband_side[side_name] += 1
                        hpband_dists[side_name].append(round(float(dist), 4))
                        if len(hpband_examples) < 80:
                            att = (battle.opponent_active_pokemon.species
                                   if side_name == "us"
                                   else battle.active_pokemon.species)
                            hpband_examples.append({
                                "lane": lane, "battle": bi, "step": si,
                                "side_hit": side_name, "mon_hit": sp,
                                "attacker": att, "move": mover,
                                "dmg_obs": round(float(dmg_obs), 4),
                                "dmg_branch_avg": round(float(dmg_br), 4),
                                "dist": round(float(dist), 4),
                                "our_boosts": dict(battle.active_pokemon.boosts or {}),
                                "opp_boosts": dict(
                                    battle.opponent_active_pokemon.boosts or {}),
                                "opp_status": snap_now["opponent_team"][
                                    snap_now["opponent_active_index"]]["status"]
                                if snap_now["opponent_active_index"] is not None else None,
                                "our_status": snap_now["team"][
                                    snap_now["active_index"]]["status"]
                                if snap_now["active_index"] is not None else None,
                            })

    tot = max(n_normal, 1)
    n_unc = n_normal - n_covered
    out = {
        "gate": "FG-2 turn-order diagnostic (descriptive; no bar)",
        "n_normal": n_normal,
        "n_covered_baseline": n_covered,
        "fg2_baseline_check": n_covered / tot,
        "n_uncovered": n_unc,
        "attribution": dict(attribution),
        "attribution_frac_of_normal": {
            k: v / tot for k, v in attribution.items()
        },
        "fg2_if_family_recovered_cumulative": _cumulative(
            n_covered, tot,
            [("truncation", attribution["truncation"]),
             ("turn_order", attribution["turn_order"]),
             ("sleep_interrupt_selfko", attribution["sleep_interrupt_selfko"])],
        ),
        "truncation_cover_rank_hist": {
            str(k): v for k, v in sorted(cover_rank_hist.items())
        },
        "order_probe_detail": dict(order_probe_detail),
        "uncovered_speed_relation_det0": dict(tie_stats),
        "residual_signatures_top20": [
            {"fields": list(k), "n": v}
            for k, v in residual_sigs.most_common(20)
        ],
        "residual_fail_fields": dict(residual_fail_fields),
        "residual_hpband_only_by_move_direction_top30": [
            {"mover_move|direction": k, "n": v}
            for k, v in hpband_mover.most_common(30)
        ],
        "residual_hpband_only_by_side": dict(hpband_side),
        "residual_hpband_dist_quantiles": {
            k: ([round(float(q), 4) for q in
                 __import__("numpy").quantile(v, [0.05, 0.25, 0.5, 0.75, 0.95])]
                if v else None)
            for k, v in hpband_dists.items()
        },
        "residual_hpband_examples": hpband_examples,
        "residual_hpband_subfamily": dict(hpband_subfamily),
        "residual_hpband_plain_detail": plain_detail,
        "residual_pattern_flags": dict(sleep_flags),
        "strata": dict(strata),
        "elapsed_sec": round(time.time() - t0, 1),
        "note": ("attribution is hierarchical (first probe that recovers "
                 "claims the case): truncation -> turn_order -> "
                 "sleep_interrupt_selfko -> residual; probes share the "
                 "battery's exact determinization stream"),
    }
    dest = harvest_dir / "turnorder_diag.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    print(f"\nwrote {dest}")


def _cumulative(n_covered: int, tot: int, families: list[tuple[str, int]]) -> dict:
    out, run = {}, n_covered
    for name, n in families:
        run += n
        out[f"+{name}"] = run / tot
    return out


if __name__ == "__main__":
    main()
