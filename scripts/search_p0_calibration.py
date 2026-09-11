"""PHASE 0 of `docs/search_relook/ENGINE_SEARCH_DESIGN.md` §7 — calibration.

Four offline measurements, no server, no new production code. Nothing here
credits anything; this is a GATE on whether Form B (depth-2 with sampled
chance) gets built at all.

    (1) sigma-margin calibration (design §1.2)   -- stages a + b + combine
    (2) top-k retained mass      (design §5.3)   -- stage a
    (3) W-ACTIVESTATS incidence  (design §2.5)   -- already measured, quoted
    (4) last_selected_move in poke-env 0.15      -- source read, quoted

TWO STAGES, TWO ENVIRONMENTS, because no single env has both simulators
(CLAUDE.md watch items, CLEANUP E1):

    stage a   conda env `pokemon-showdown-rl`   (poke_engine + rl + torch)
              runs the EXISTING depth-1 solve (`rl.search.matrix.solve_decision`)
              on the selected harvest roots, and writes everything stage b
              needs: the root observable-state dict, the determinizations, the
              column law's realised classes/actions/weights, row_ev, margins.

    stage b   conda env `pkmn-engine-port`      (pkmn_gen1 + rl + torch)
              rebuilds each root as 384 engine bytes through the Phase-0 write
              spike, samples chance S times per (row, col, det) over R
              independent seed families, and reports sd(margin).

    detblind-ref
              conda env `pokemon-showdown-rl`
              re-solves the restricted roots with `leaf_encoding=det_blind`, the
              encoding design §1.1 defines Form A against and the one the engine
              spike structurally uses, so the argmax-agreement leg is not
              confounded by the encoding swap (DET_BLIND.md measured that alone
              at an 11.4% flip rate). Optional; `combine` folds it in if present.

    combine   either env; merges into results/search_p0/p0.json.

Usage (each block is one command; torch threads are pinned, the box is shared):

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
      python scripts/search_p0_calibration.py stage-a --out results/search_p0

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
      python scripts/search_p0_calibration.py stage-b --out results/search_p0

    python scripts/search_p0_calibration.py combine --out results/search_p0

PURITY. Stage a reads `results/ch3_r1/harvest_s6*.pkl` only — never
`harvest_priv_*` (FG-4). Stage b reads stage a's dump and the same public
checkpoints. Neither stage touches a live battle.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import time
from pathlib import Path

import numpy as np

HARVEST_LANES = ("s62", "s63", "s64", "s65")
DOSE_NAME = "M"
TOPK_VALUES = (3, 4, 6)


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
def require_encoder_flags() -> None:
    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        if os.environ.get(var) != "1":
            raise SystemExit(f"{var}=1 required (828-d D26 objects)")


def load_agent(path: str):
    import gymnasium as gym
    import numpy as _np

    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.envs.showdown import OBS_DIM
    from rl.train import make_agent

    ckpt = load_checkpoint(path)
    cfg = Config(**ckpt["config"])
    assert not getattr(cfg, "normalize_obs", False)
    env = gym.Env()
    env.observation_space = gym.spaces.Box(-1.0, 4.0, shape=(OBS_DIM,), dtype=_np.float32)
    env.action_space = gym.spaces.Discrete(10)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg


def select_roots(harvest_dir: Path, n_per_lane: int, n_restricted_per_lane: int):
    """(selection, census). Two strided draws, reported separately:

    * `plain`  — n_per_lane evenly strided over the NON-ALIASED pool, exactly
      as `scripts/ch3_r1_spike.py` draws its 200. The design's "~200 harvest
      roots" read literally; how many survive the restriction is a headline.
    * `restricted` — n_restricted_per_lane strided over the RESTRICTED pool,
      so the sigma measurement has its full n instead of whatever survives.
    """
    import search_p0_write_spike as spike

    census = {"rows": 0, "non_aliased": 0, "restricted": 0, "reasons": {}}
    sel: dict[tuple, dict] = {}
    for lane in HARVEST_LANES:
        with open(harvest_dir / f"harvest_{lane}.pkl", "rb") as f:
            battles = pickle.load(f)
        pool, restricted = [], []
        for bi, b in enumerate(battles):
            for si, row in enumerate(b["rows"]):
                census["rows"] += 1
                if row["aliased"]:
                    continue
                census["non_aliased"] += 1
                pool.append((bi, si))
                bad = spike.restricted_ok(row["battle"])
                for r in bad:
                    census["reasons"][r] = census["reasons"].get(r, 0) + 1
                if not bad:
                    census["restricted"] += 1
                    restricted.append((bi, si))
        for name, cand, n in (("plain", pool, n_per_lane),
                              ("restricted", restricted, n_restricted_per_lane)):
            if not cand:
                continue
            idx = np.linspace(0, len(cand) - 1, num=min(n, len(cand)), dtype=int)
            for k in sorted(set(int(i) for i in idx)):
                bi, si = cand[k]
                key = (lane, bi, si)
                ent = sel.setdefault(key, {"lane": lane, "episode": bi, "step": si,
                                           "draws": []})
                if name not in ent["draws"]:
                    ent["draws"].append(name)
    return sel, census


# --------------------------------------------------------------------------
# STAGE A — the poke_engine depth-1 solve, and everything stage b needs
# --------------------------------------------------------------------------
def stage_a(args) -> None:
    require_encoder_flags()
    import torch
    import yaml

    torch.set_num_threads(args.torch_threads)

    from poke_env.data import GenData

    from rl.common.masking import masked_logits
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import (
        DOSES, N_L6, OTHER_MOVE, SWITCH, Dose, decision_rng, solve_decision,
        _OPP_LOCK_VOLATILES, _opp_bench_target,
    )
    import engine_p1
    import search_p0_write_spike as spike

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    harvest_dir = Path(args.harvest)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sel, census = select_roots(harvest_dir, args.n_per_lane, args.n_restricted_per_lane)
    print(f"census: {census['rows']} rows, {census['non_aliased']} non-aliased, "
          f"{census['restricted']} restricted "
          f"({census['restricted'] / max(census['non_aliased'], 1):.1%})")
    plain = [k for k, v in sel.items() if "plain" in v["draws"]]
    restr = [k for k, v in sel.items() if "restricted" in v["draws"]]
    print(f"selected {len(sel)} roots ({len(plain)} plain draw, {len(restr)} restricted draw)")

    type_chart = GenData.from_format("gen1randombattle").type_chart
    dose = DOSES[DOSE_NAME]
    extra_doses = {}
    for tb in args.top_branches_extra:
        extra_doses[tb] = Dose(n_det=dose.n_det, top_branches=int(tb),
                               leaf_cap=dose.leaf_cap * 4, node_cap=None)

    records: list[dict] = []
    by_lane: dict[str, list[tuple]] = {}
    for key in sel:
        by_lane.setdefault(key[0], []).append(key)

    for lane, keys in by_lane.items():
        agent, cfg = load_agent(prereg["checkpoints"][lane]["path"])
        assert agent.aux_head is not None, "the oppact head is required"
        with open(harvest_dir / f"harvest_{lane}.pkl", "rb") as f:
            battles = pickle.load(f)
        seed = int(cfg.seed)

        def critic_fn(batch: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                v = agent.critic(torch.as_tensor(batch, dtype=torch.float32))
            return v.reshape(-1).numpy()

        t_lane = time.perf_counter()
        for n_done, key in enumerate(sorted(keys)):
            _, bi, si = key
            row = battles[bi]["rows"][si]
            root = row["battle"]
            battle = rehydrate_battle(root)
            obs = np.asarray(row["obs"], dtype=np.float32)
            mask = np.asarray(row["mask"], dtype=bool)
            turn = int(battle.turn)

            with torch.no_grad():
                logits, *feats = agent.actor(
                    torch.as_tensor(obs).unsqueeze(0), return_features=True)
                prior = torch.softmax(
                    masked_logits(logits, torch.as_tensor(mask)), dim=-1)[0].numpy()
                q = torch.softmax(agent.aux_head(*feats), dim=-1)[0].numpy()

            t0 = time.perf_counter()
            rng = decision_rng(seed, bi, turn, si)
            chosen, stats = solve_decision(battle, mask, q, prior, dose, rng,
                                           critic_fn, type_chart)
            ms = (time.perf_counter() - t0) * 1e3

            # Replay the determinization + column draws with an IDENTICAL rng so
            # stage b can rebuild the same matrix. Same functions, same order,
            # so the values are the same draws; asserted against the solve's own
            # recorded col_classes.
            rng2 = decision_rng(seed, bi, turn, si)
            dets = [sample_determinization(battle, rng2) for _ in range(dose.n_det)]
            states = [battle_to_state(battle, d, BridgeCounters()) for d in dets]
            col_classes, col_actions, col_w, other_mass = _columns(
                battle, dets, states, q, dose, rng2, SWITCH, OTHER_MOVE,
                _OPP_LOCK_VOLATILES, _opp_bench_target)
            assert col_classes == list(stats["search/col_classes"]), (
                col_classes, stats["search/col_classes"])

            rows = [i for i in range(len(mask)) if mask[i]]
            row_ev = np.array([stats["search/row_ev"][i] for i in rows])
            srt = np.sort(row_ev)[::-1]
            margin = float(srt[0] - srt[1]) if len(srt) > 1 else float("nan")

            rec = {
                "lane": lane, "episode": bi, "step": si, "turn": turn,
                "draws": sel[key]["draws"],
                "restricted": not spike.restricted_ok(root),
                "restriction_reasons": spike.restricted_ok(root),
                "mask": [bool(x) for x in mask],
                "rows": rows,
                "prior": [float(x) for x in prior],
                "q": [float(x) for x in q],
                "row_ev": [float(x) for x in row_ev],
                "ev_matrix": stats["search/ev_matrix"],
                "col_classes": col_classes,
                "col_actions": col_actions,
                "col_w": [float(x) for x in col_w],
                "other_move_mass": float(other_mass),
                "margin": margin,
                "chosen": int(chosen),
                "policy_argmax": int(stats["search/policy_argmax"]),
                "retained_mass_mean": float(stats["search/retained_mass_mean"]),
                "leaves": int(stats["search/leaves"]),
                "opp_locked": int(stats["search/opp_locked"]),
                "force_switch": int(stats["search/force_switch"]),
                "ms": ms,
                "dets": [_slim_det(d) for d in dets],
            }
            if rec["restricted"]:
                st = engine_p1.state_from_battle(battle, {})
                rec["obs_state"] = spike.augment_root_state(root, st)
                rec["root"] = root
                rec["obs"] = obs.tolist()
            # the top_branches sensitivity legs (a DIAGNOSTIC dose, never a
            # credited one: node_cap is off and leaf_cap is widened)
            for tb, d2 in extra_doses.items():
                rng3 = decision_rng(seed, bi, turn, si)
                _c2, s2 = solve_decision(battle, mask, q, prior, d2, rng3,
                                         critic_fn, type_chart)
                ev2 = np.array([s2["search/row_ev"][i] for i in rows])
                o2 = np.sort(ev2)[::-1]
                rec[f"tb{tb}"] = {
                    "argmax": int(rows[int(np.argmax(ev2))]),
                    "margin": float(o2[0] - o2[1]) if len(o2) > 1 else float("nan"),
                    "retained_mass_mean": float(s2["search/retained_mass_mean"]),
                }
            records.append(rec)
            if (n_done + 1) % 25 == 0:
                el = time.perf_counter() - t_lane
                print(f"  {lane} {n_done + 1}/{len(keys)}  {el:.0f}s "
                      f"({el / (n_done + 1) * 1e3:.0f} ms/root)", flush=True)

    dump = {
        "census": census,
        "n_plain": len(plain),
        "n_plain_surviving": sum(1 for r in records
                                 if "plain" in r["draws"] and r["restricted"]),
        "n_restricted_draw": len(restr),
        "dose": DOSE_NAME,
        "dose_fields": dose.__dict__ if hasattr(dose, "__dict__") else {
            "n_det": dose.n_det, "top_branches": dose.top_branches,
            "leaf_cap": dose.leaf_cap, "node_cap": dose.node_cap},
        "top_branches_extra": list(args.top_branches_extra),
        "records": records,
    }
    with open(out / "stage_a.pkl", "wb") as f:
        pickle.dump(dump, f, protocol=4)
    (out / "stage_a_summary.json").write_text(json.dumps(
        {k: v for k, v in dump.items() if k != "records"}, indent=2) + "\n")
    print(f"wrote {out / 'stage_a.pkl'} ({len(records)} roots)")


def _slim_det(det: dict) -> dict:
    """The determinization as plain data — `live` is a poke-env object and the
    engine side needs only species / moves / level."""
    return {sp: {"moves": list(v["moves"]), "level": int(v["level"])}
            for sp, v in det["opponents"].items()}


def _columns(battle, dets, states, q, dose, rng, SWITCH, OTHER_MOVE,
             lock_vols, bench_fn):
    """`matrix.py:181-196`'s column block, replayed. Same functions, same rng
    order, so the draws are identical; the caller asserts that."""
    opp_active_species = battle.opponent_active_pokemon.species
    slot_moves = dets[0]["opponents"][opp_active_species]["moves"]
    opp_locked = any(v in states[0].side_two.volatile_statuses for v in lock_vols)
    force_switch = bool(battle.force_switch)
    if force_switch or opp_locked:
        return [-1], [["none"] * dose.n_det], np.array([1.0]), 0.0
    col_classes = list(range(len(slot_moves[:4])))
    col_actions = [[mid] * dose.n_det for mid in slot_moves[:4]]
    switch_targets = [bench_fn(s, rng) for s in states]
    if any(t is not None for t in switch_targets):
        col_classes.append(SWITCH)
        col_actions.append([t if t is not None else "none" for t in switch_targets])
    other = float(q[OTHER_MOVE])
    w = np.array([float(q[c]) for c in col_classes], dtype=np.float64)
    col_w = (w / w.sum()) if w.sum() > 0 else np.full(len(w), 1.0 / len(w))
    return col_classes, col_actions, col_w, other


# --------------------------------------------------------------------------
# measurement (2): top-k retained mass  (design §5.3)
# --------------------------------------------------------------------------
def topk_report(records: list[dict]) -> dict:
    """Three prunings, priced separately, because §5.3 conflates two axes.

    ROW pruning by the POLICY PRIOR is the cut a depth-2 root would have to
    make WITHOUT §5.3's depth-1 pre-pass; its argmax-change rate is the cost
    of not paying for the pre-pass. ROW pruning by the DEPTH-1 pre-pass itself
    cannot change the depth-1 argmax (it is rank 1 by construction), so what is
    reported there is the row_ev GAP a depth-2 correction would have to clear
    to make the cut wrong. COLUMN pruning by q-tilde is the opponent-action
    mass question.
    """
    out: dict = {"n": len(records)}
    rows_n = [len(r["rows"]) for r in records]
    out["legal_rows"] = _dist(rows_n)
    out["cols_n"] = _dist([len(r["col_classes"]) for r in records])
    out["retained_branch_mass_at_top6"] = _dist(
        [r["retained_mass_mean"] for r in records])

    prior_cut, prepass_cut, col_cut = {}, {}, {}
    for k in TOPK_VALUES + ("all",):
        chg_p, mass_p, loss_p = [], [], []
        gap, free = [], []
        chg_c, mass_c = [], []
        for r in records:
            rows = r["rows"]
            ev = np.asarray(r["row_ev"], dtype=np.float64)
            prior = np.asarray(r["prior"], dtype=np.float64)[rows]
            kk = len(rows) if k == "all" else min(int(k), len(rows))
            full_arg = int(np.argmax(ev))

            # --- (a) rows kept by policy prior -------------------------------
            keep = np.argsort(-prior, kind="stable")[:kk]
            mass_p.append(float(prior[keep].sum() / max(prior.sum(), 1e-12)))
            sub = keep[int(np.argmax(ev[keep]))]
            chg_p.append(int(sub != full_arg))
            loss_p.append(float(ev[full_arg] - ev[sub]))

            # --- (b) rows kept by the depth-1 pre-pass ----------------------
            order = np.argsort(-ev, kind="stable")
            free.append(int(kk >= len(rows)))
            gap.append(0.0 if kk >= len(rows)
                       else float(ev[order[kk - 1]] - ev[order[kk]]))

            # --- (c) columns kept by q-tilde --------------------------------
            evm = np.asarray(r["ev_matrix"], dtype=np.float64)
            w = np.asarray(r["col_w"], dtype=np.float64)
            ck = len(w) if k == "all" else min(int(k), len(w))
            ckeep = np.argsort(-w, kind="stable")[:ck]
            mass_c.append(float(w[ckeep].sum() / max(w.sum(), 1e-12)))
            w2 = w[ckeep] / max(w[ckeep].sum(), 1e-12)
            ev2 = evm[:, ckeep] @ w2
            chg_c.append(int(int(np.argmax(ev2)) != full_arg))

        key = str(k)
        prior_cut[key] = {"argmax_change_rate": float(np.mean(chg_p)),
                          "retained_prior_mass": _dist(mass_p),
                          "row_ev_loss_mean": float(np.mean(loss_p)),
                          "row_ev_loss_when_changed": float(
                              np.mean([l for l, c in zip(loss_p, chg_p) if c])
                              if any(chg_p) else 0.0)}
        prepass_cut[key] = {"argmax_change_rate": 0.0,
                            "frac_decisions_no_cut": float(np.mean(free)),
                            "gap_to_best_excluded": _dist(gap)}
        col_cut[key] = {"argmax_change_rate": float(np.mean(chg_c)),
                        "retained_opp_mass": _dist(mass_c)}
    out["rows_by_policy_prior"] = prior_cut
    out["rows_by_depth1_prepass"] = prepass_cut
    out["cols_by_q_tilde"] = col_cut

    tbs = sorted({int(k[2:]) for r in records for k in r if k.startswith("tb")})
    if tbs:
        base_arg = [int(r["rows"][int(np.argmax(r["row_ev"]))]) for r in records]
        out["top_branches_sensitivity"] = {
            str(tb): {
                "argmax_change_rate_vs_6": float(np.mean(
                    [int(r[f"tb{tb}"]["argmax"] != a)
                     for r, a in zip(records, base_arg) if f"tb{tb}" in r])),
                "retained_branch_mass": _dist(
                    [r[f"tb{tb}"]["retained_mass_mean"] for r in records
                     if f"tb{tb}" in r]),
                "median_margin": float(np.median(
                    [r[f"tb{tb}"]["margin"] for r in records if f"tb{tb}" in r])),
            } for tb in tbs}
    return out


def _dist(xs) -> dict:
    a = np.asarray(list(xs), dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size), "mean": float(a.mean()), "p10": float(np.percentile(a, 10)),
            "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90)),
            "min": float(a.min()), "max": float(a.max())}


# --------------------------------------------------------------------------
# STAGE B — the engine spike and the sigma-margin calibration
# --------------------------------------------------------------------------
def stage_b(args) -> None:
    require_encoder_flags()
    import torch
    import yaml

    torch.set_num_threads(args.torch_threads)

    import pkmn_gen1

    from rl.envs.engine_tables import build_tables
    import search_p0_write_spike as spike

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    out = Path(args.out)
    with open(out / "stage_a.pkl", "rb") as f:
        dump = pickle.load(f)
    records = [r for r in dump["records"] if r["restricted"]]
    if args.limit:
        records = records[: args.limit]
    print(f"stage b: {len(records)} restricted roots, "
          f"S={args.s_max}, R={args.families}")

    tables, fp = build_tables()
    s_grid = [s for s in (1, 2, 4, 8, 16, 32) if s <= args.s_max]

    by_lane: dict[str, list[dict]] = {}
    for r in records:
        by_lane.setdefault(r["lane"], []).append(r)

    results, gates = [], {"s0_obs_exact": 0, "s0_obs_n": 0, "s0_maxabs": [],
                          "s1_roundtrip_n": 0, "s1_exact": 0, "s1_maxabs": [],
                          "s1_dims_diff": [], "s1_own_exact": 0,
                          "mask_parity_n": 0, "mask_parity_exact": 0,
                          "counters": {}}
    t_all = time.perf_counter()
    n_updates = 0
    for lane, recs in by_lane.items():
        agent, cfg = load_agent(prereg["checkpoints"][lane]["path"])

        def critic_fn(batch: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                v = agent.critic(torch.as_tensor(batch, dtype=torch.float32))
            return v.reshape(-1).numpy()

        for n_done, r in enumerate(recs):
            try:
                res, nu = _sigma_one_root(r, tables, critic_fn, spike, pkmn_gen1,
                                          s_grid, args, gates)
            except spike.SpikeError as exc:
                gates["counters"][f"refused:{exc}"] = \
                    gates["counters"].get(f"refused:{exc}", 0) + 1
                continue
            n_updates += nu
            results.append(res)
            if (n_done + 1) % 5 == 0:
                el = time.perf_counter() - t_all
                print(f"  {lane} {n_done + 1}/{len(recs)}  {el:.0f}s  "
                      f"{n_updates:,} updates ({n_updates / max(el, 1e-9):,.0f}/s)",
                      flush=True)

    payload = {"n_roots": len(results), "s_grid": s_grid,
               "families": args.families, "n_det": dump["dose_fields"]["n_det"],
               "tables_fingerprint": fp, "engine_sha": pkmn_gen1.__engine_sha__,
               "n_updates": n_updates,
               "wall_sec": time.perf_counter() - t_all,
               "gates": _finish_gates(gates), "roots": results}
    with open(out / "stage_b.pkl", "wb") as f:
        pickle.dump(payload, f, protocol=4)
    (out / "stage_b_summary.json").write_text(json.dumps(
        {k: v for k, v in payload.items() if k != "roots"}, indent=2) + "\n")
    print(json.dumps(payload["gates"], indent=2))
    print(f"wrote {out / 'stage_b.pkl'}")


def _finish_gates(g: dict) -> dict:
    o = dict(g)
    for k in ("s0_maxabs", "s1_maxabs", "s1_dims_diff"):
        o[k] = _dist(g[k])
    return o


def _sigma_one_root(r, tables, critic_fn, spike, pkmn_gen1, s_grid, args, gates):
    """One root: R independent chance-seed families x S samples per cell,
    with and without CRN-1. Returns (record, engine updates performed)."""
    root, obs_state = r["root"], r["obs_state"]
    rows, col_classes = r["rows"], r["col_classes"]
    n_det = len(r["dets"])
    col_w = np.asarray(r["col_w"], dtype=np.float64)

    # --- S-0: the Rust encoder on the ROOT state vs the harvest's own obs ---
    if gates["s0_obs_n"] < args.gate_n:
        v = np.asarray(tables.encode(obs_state), dtype=np.float32)
        ref = np.asarray(r["obs"], dtype=np.float32)
        gates["s0_obs_n"] += 1
        gates["s0_obs_exact"] += int(np.array_equal(v, ref))
        gates["s0_maxabs"].append(float(np.abs(v - ref).max()))

    states = [spike.build_root(root, {"opponents": _fat_det(d)}, obs_state)
              for d in r["dets"]]
    st0 = states[0]

    # --- S-1: the write side round-tripped through the engine's own bytes ---
    if gates["s1_roundtrip_n"] < args.gate_n:
        b0 = st0.battle(0)
        counters: dict = {}
        cs = spike.child_state(st0, b0, "move", counters)
        cs["turn"] = obs_state["turn"]          # the root, not root+1
        cs["_opp_revealed_moves"] = obs_state["_opp_revealed_moves"]
        v = np.asarray(tables.encode(cs), dtype=np.float32)
        ref = np.asarray(r["obs"], dtype=np.float32)
        d = np.abs(v - ref)
        gates["s1_roundtrip_n"] += 1
        gates["s1_exact"] += int(np.array_equal(v, ref))
        gates["s1_maxabs"].append(float(d.max()))
        gates["s1_dims_diff"].append(int((d > 0).sum()))
        own = slice(0, _own_block_end())
        gates["s1_own_exact"] += int(np.array_equal(v[own], ref[own]))
        # mask parity: the engine's own choices vs the harvest mask
        gates["mask_parity_n"] += 1
        gates["mask_parity_exact"] += int(
            _engine_mask(b0, st0) == set(r["rows"]))

    # --- the cell fill ------------------------------------------------------
    n_rows, n_cols = len(rows), len(col_classes)
    R, S = args.families, max(s_grid)
    # values[crn][f, s, ri, ci, di]
    values = {crn: np.zeros((R, S, n_rows, n_cols, n_det), dtype=np.float64)
              for crn in (True, False)}
    key = abs(hash((r["lane"], r["episode"], r["step"]))) & 0xFFFFFFFFFFFFFFFF
    obs_buf: list = []
    slots: list = []
    n_updates = 0
    counters = gates["counters"]
    rev_moves = obs_state["_opp_revealed_moves"]
    from_bytes = pkmn_gen1.Battle.from_bytes
    encode = tables.encode
    child_state = spike.child_state

    # A child's VALUE is a function of its OBSERVATION alone, and the
    # observation reads only the party records, the active blocks, the order
    # and the turn — bytes 0..370. B_LAST_DAMAGE (370), B_LAST_MOVES (372) and
    # the advanced PSRNG seed (376) are hidden and never encoded, so two chance
    # samples that landed on the same public state share a value exactly. Gen 1
    # has 39 damage rolls, so a cell's S=32x20 draws collapse hard. This is a
    # memo, not an approximation: same key, same 828 floats, same critic.
    vcache: dict = {}
    pending: dict = {}

    def flush() -> None:
        if not obs_buf:
            return
        batch = np.stack(obs_buf).astype(np.float32)
        vals = critic_fn(batch)
        for k, v in zip(slots, vals):
            vcache[k] = float(v)
            for crn, f, s, ri, ci, di in pending.pop(k):
                values[crn][f, s, ri, ci, di] = v
        obs_buf.clear()
        slots.clear()

    for di in range(n_det):
        st = states[di]
        raw = bytearray(st.bytes)
        for ci in range(n_cols):
            b_choice = _opp_choice(st, r["col_actions"][ci][di], col_classes[ci])
            for ri, a in enumerate(rows):
                a_choice = _our_choice(st, a)
                for crn in (True, False):
                    for f in range(R):
                        for s in range(S):
                            seed = _chance_seed(key, ci, di, s, f, crn,
                                                ri if not crn else -1)
                            raw[B_RNG_OFF:B_RNG_OFF + 8] = seed.to_bytes(8, "little")
                            bt = from_bytes(bytes(raw))
                            try:
                                outcome, p1r, _p2r = bt.update(
                                    "move", a_choice, "move", b_choice)
                            except Exception as exc:      # engine refused
                                k = f"update_error:{type(exc).__name__}"
                                counters[k] = counters.get(k, 0) + 1
                                values[crn][f, s, ri, ci, di] = np.nan
                                continue
                            n_updates += 1
                            tv = _terminal(outcome)
                            if tv is not None:
                                values[crn][f, s, ri, ci, di] = tv
                                continue
                            cb = bt.bytes()
                            if not isinstance(cb, (bytes, bytearray)):
                                cb = bytes(cb)
                            ck = (cb[:370], p1r)
                            hit = vcache.get(ck)
                            if hit is not None:
                                values[crn][f, s, ri, ci, di] = hit
                                continue
                            here = (crn, f, s, ri, ci, di)
                            if ck in pending:
                                pending[ck].append(here)
                                continue
                            cs = child_state(st, bt, p1r, counters, raw=cb)
                            cs["_opp_revealed_moves"] = rev_moves
                            obs_buf.append(encode(cs))
                            slots.append(ck)
                            pending[ck] = [here]
                            if len(obs_buf) >= args.critic_batch:
                                flush()
    flush()
    n_distinct = len(vcache)

    # --- margins per (crn, S, family) --------------------------------------
    out = {"lane": r["lane"], "episode": r["episode"], "step": r["step"],
           "turn": r["turn"], "n_rows": n_rows, "n_cols": n_cols,
           "n_det": n_det, "pe_margin": r["margin"],
           "n_distinct_children": n_distinct,
           "pe_argmax": int(r["rows"][int(np.argmax(r["row_ev"]))]),
           "margins": {}, "argmax": {}}
    for crn in (True, False):
        V = values[crn]
        for S_ in s_grid:
            cell = np.nanmean(V[:, :S_], axis=1)          # (R, rows, cols, det)
            cell = np.nanmean(cell, axis=3)               # average over dets
            rev = cell @ col_w                            # (R, rows)
            srt = np.sort(rev, axis=1)[:, ::-1]
            marg = srt[:, 0] - srt[:, 1] if n_rows > 1 else np.zeros(len(srt))
            tag = f"{'crn' if crn else 'nocrn'}_S{S_}"
            out["margins"][tag] = [float(x) for x in marg]
            out["argmax"][tag] = [int(rows[i]) for i in np.argmax(rev, axis=1)]
    return out, n_updates


def _fat_det(slim: dict) -> dict:
    return {sp: {"moves": v["moves"], "level": v["level"]} for sp, v in slim.items()}


def _chance_seed(key: int, ci: int, di: int, s: int, f: int, crn: bool, ri: int) -> int:
    """CRN-1 (design §1.2): the chance seed is a pure function of
    `(decision key, col, det, sample index)` and NEVER of the row. The
    `nocrn` arm deliberately breaks that by mixing the row in, so the two
    are a matched pair differing in exactly one term."""
    x = (key * 0x9E3779B97F4A7C15) ^ (ci * 0xBF58476D1CE4E5B9) \
        ^ (di * 0x94D049BB133111EB) ^ (s * 0xD6E8FEB86659FD93) \
        ^ (f * 0xA24BAED4963EE407)
    if not crn:
        x ^= (ri + 1) * 0x9FB21C651E98DF25
    return _splitmix64(x & 0xFFFFFFFFFFFFFFFF)


def _splitmix64(x: int) -> int:
    M = 0xFFFFFFFFFFFFFFFF
    x = (x + 0x9E3779B97F4A7C15) & M
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M
    return (z ^ (z >> 31)) & M


B_RNG_OFF = 376  # layout.rs B_RNG (showdown override; see search_p0_write_spike)


def _terminal(outcome: str):
    return {"none": None, "win": 1.0, "lose": -1.0, "tie": 0.0}[outcome]


def _our_choice(st, action: int):
    """Mask index -> engine choice. 0..5 = team slot switch (through the
    order permutation, `layout.rs:377-383`), 6..9 = the active's move slot."""
    if action < 6:
        slot = st.own_slot_of_party(action)
        return ("switch", slot)
    return ("move", action - 6 + 1)


def _opp_choice(st, action_str: str, cls: int):
    if cls == -1 or action_str == "none":
        return ("pass", 0)
    if cls == 5:                      # SWITCH: the string names a species
        return ("switch", st.opp_slot_of_species(action_str))
    return ("move", st.opp_move_slot(action_str))


def _engine_mask(battle, st) -> set:
    got = set()
    for kind, data in battle.choices("p1", "move"):
        if kind == "move":
            got.add(6 + data - 1)
        elif kind == "switch":
            got.add(st.own_party_of_slot(data))
    return got


def _own_block_end() -> int:
    from rl.envs.showdown import ACTIVE_DIM, GLOBAL_DIM, MON_DIM, MOVE_DIM
    return GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM + 4 * MOVE_DIM


# --------------------------------------------------------------------------
# DET_BLIND REFERENCE — closes the leaf-encoding confound in the agreement read
# --------------------------------------------------------------------------
def detblind_ref(args) -> None:
    """Re-solve the restricted roots on poke_engine with `leaf_encoding=det_blind`.

    WHY THIS EXISTS. Design §1.1 defines Form A as like-for-like against
    `det_blind` on poke_engine, and the engine spike's child projection IS
    det_blind by construction (§1.3's L-BOUNDARY falls out of the tracker).
    Stage a ran the DEFAULT (as-is) encoding, which is the R2-credited object
    and the right baseline for the MARGIN scale; but comparing argmaxes against
    it mixes the simulator difference with the encoding difference, and
    `DET_BLIND.md:234-255` measured the latter alone at an 11.4% flip rate.
    So the agreement leg gets its own, correctly-matched reference.

    Only argmax and margin are kept; nothing else changes.
    """
    require_encoder_flags()
    import torch
    import yaml

    torch.set_num_threads(args.torch_threads)
    from poke_env.data import GenData

    from rl.common.masking import masked_logits
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import DOSES, decision_rng, solve_decision
    from rl.search.shadow_battle import public_view

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    out = Path(args.out)
    with open(out / "stage_a.pkl", "rb") as f:
        dump = pickle.load(f)
    recs = [r for r in dump["records"] if r["restricted"]]
    dose = DOSES[DOSE_NAME]
    type_chart = GenData.from_format("gen1randombattle").type_chart
    by_lane: dict[str, list] = {}
    for r in recs:
        by_lane.setdefault(r["lane"], []).append(r)

    ref = {}
    t0 = time.perf_counter()
    for lane, rs in by_lane.items():
        agent, cfg = load_agent(prereg["checkpoints"][lane]["path"])
        with open(Path(args.harvest) / f"harvest_{lane}.pkl", "rb") as f:
            battles = pickle.load(f)

        def critic_fn(batch: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                return agent.critic(
                    torch.as_tensor(batch, dtype=torch.float32)).reshape(-1).numpy()

        for r in rs:
            row = battles[r["episode"]]["rows"][r["step"]]
            battle = rehydrate_battle(row["battle"])
            obs = np.asarray(row["obs"], dtype=np.float32)
            mask = np.asarray(row["mask"], dtype=bool)
            with torch.no_grad():
                logits, *feats = agent.actor(
                    torch.as_tensor(obs).unsqueeze(0), return_features=True)
                prior = torch.softmax(
                    masked_logits(logits, torch.as_tensor(mask)), dim=-1)[0].numpy()
                q = torch.softmax(agent.aux_head(*feats), dim=-1)[0].numpy()
            rng = decision_rng(int(cfg.seed), r["episode"], r["turn"], r["step"])
            _a, st = solve_decision(battle, mask, q, prior, dose, rng, critic_fn,
                                    type_chart, leaf_view=public_view(battle))
            rows = [i for i in range(len(mask)) if mask[i]]
            ev = np.array([st["search/row_ev"][i] for i in rows])
            srt = np.sort(ev)[::-1]
            ref[f"{lane}:{r['episode']}:{r['step']}"] = {
                "argmax": int(rows[int(np.argmax(ev))]),
                "margin": float(srt[0] - srt[1]) if len(srt) > 1 else float("nan"),
            }
    (out / "detblind_ref.json").write_text(json.dumps(ref, indent=2) + "\n")
    print(f"wrote {out / 'detblind_ref.json'} ({len(ref)} roots, "
          f"{time.perf_counter() - t0:.0f}s)")


# --------------------------------------------------------------------------
# combine
# --------------------------------------------------------------------------
def combine(args) -> None:
    out = Path(args.out)
    with open(out / "stage_a.pkl", "rb") as f:
        a = pickle.load(f)
    with open(out / "stage_b.pkl", "rb") as f:
        b = pickle.load(f)

    recs = a["records"]
    plain = [r for r in recs if "plain" in r["draws"]]
    restr = [r for r in recs if r["restricted"]]
    done = {(r["lane"], r["episode"], r["step"]) for r in b["roots"]}
    measured = [r for r in restr if (r["lane"], r["episode"], r["step"]) in done]

    # A root with exactly ONE legal action has no margin; S1 drops those too
    # (`S1_S2_SCREENS.md:146-149`, 19 of its 800). Dropped here, counted.
    def _margins(rs):
        return np.asarray([r["margin"] for r in rs
                           if np.isfinite(r["margin"])], dtype=np.float64)

    m_all, m_restr = _margins(plain), _margins(measured)
    med_all = float(np.median(m_all)) if m_all.size else float("nan")
    med_restr = float(np.median(m_restr)) if m_restr.size else float("nan")

    ref_path = out / "detblind_ref.json"
    ref = json.loads(ref_path.read_text()) if ref_path.exists() else {}

    def _ref(r):
        return ref.get(f"{r['lane']}:{r['episode']}:{r['step']}")

    sigma = {}
    for tag in sorted(b["roots"][0]["margins"]):
        per_root = []
        for r in b["roots"]:
            m = np.asarray(r["margins"][tag], dtype=np.float64)
            per_root.append(float(np.std(m, ddof=1)) if m.size > 1 else np.nan)
        per_root = np.asarray(per_root)
        sigma[tag] = {
            "sd_margin_mean": float(np.nanmean(per_root)),
            "sd_margin_median": float(np.nanmedian(per_root)),
            "sd_margin_p90": float(np.nanpercentile(per_root, 90)),
            "median_sampled_margin": float(np.nanmedian(
                [np.median(r["margins"][tag]) for r in b["roots"]])),
            "argmax_agreement_with_poke_engine_ASIS": float(np.mean(
                [np.mean([int(x == r["pe_argmax"]) for x in r["argmax"][tag]])
                 for r in b["roots"]])),
        }
        if ref:
            have = [r for r in b["roots"] if _ref(r)]
            sigma[tag]["argmax_agreement_with_poke_engine_DETBLIND"] = float(np.mean(
                [np.mean([int(x == _ref(r)["argmax"]) for x in r["argmax"][tag]])
                 for r in have]))
            sigma[tag]["n_agreement_roots"] = len(have)

    target = 0.5 * med_restr
    s_max = max(b["s_grid"])

    def _first(stat: str, mult: float):
        return next((s for s in b["s_grid"]
                     if sigma[f"crn_S{s}"][stat] <= mult * med_restr), None)

    # The gate statistic is the MEAN over roots of each root's sd across
    # chance-seed families; the MEDIAN-over-roots variant is reported beside it
    # so it is visible whether the branch depends on that choice.
    verdict = {
        "median_margin_restricted_subset": med_restr,
        "median_margin_plain_draw": med_all,
        "stop_rule_threshold_0p5x_median_margin": target,
        f"sd_margin_at_S{s_max}_crn_MEAN": sigma[f"crn_S{s_max}"]["sd_margin_mean"],
        f"sd_margin_at_S{s_max}_crn_MEDIAN": sigma[f"crn_S{s_max}"]["sd_margin_median"],
        f"ratio_at_S{s_max}_mean_over_threshold":
            sigma[f"crn_S{s_max}"]["sd_margin_mean"] / target if target else float("nan"),
        f"ratio_at_S{s_max}_median_over_threshold":
            sigma[f"crn_S{s_max}"]["sd_margin_median"] / target if target else float("nan"),
        "PASSES_STOP_RULE_on_mean": bool(
            sigma[f"crn_S{s_max}"]["sd_margin_mean"] <= target),
        "PASSES_STOP_RULE_on_median": bool(
            sigma[f"crn_S{s_max}"]["sd_margin_median"] <= target),
        "first_S_below_0p5x_median_on_mean": _first("sd_margin_mean", 0.5),
        "first_S_below_0p5x_median_on_median": _first("sd_margin_median", 0.5),
        "design_target_0p2x": 0.2 * med_restr,
        "first_S_below_0p2x_median_on_mean": _first("sd_margin_mean", 0.2),
        "first_S_below_0p2x_median_on_median": _first("sd_margin_median", 0.2),
    }
    crn_gain = {f"S{s}": sigma[f"nocrn_S{s}"]["sd_margin_mean"] /
                max(sigma[f"crn_S{s}"]["sd_margin_mean"], 1e-12)
                for s in b["s_grid"]}

    payload = {
        "written": time.strftime("%Y-%m-%d %H:%M:%S"),
        "census": a["census"],
        "n_plain_draw": a["n_plain"],
        "n_plain_surviving_restriction": a["n_plain_surviving"],
        "n_restricted_draw": a["n_restricted_draw"],
        "n_sigma_roots_measured": len(b["roots"]),
        "n_single_action_roots_dropped": {
            "plain": len(plain) - int(m_all.size),
            "sigma": len(measured) - int(m_restr.size)},
        "margin_percentiles_restricted": _dist(m_restr),
        "margin_percentiles_restricted_DETBLIND": _dist(
            [v["margin"] for v in ref.values()]) if ref else {"n": 0},
        "detblind_vs_asis_argmax_flip_rate": (
            float(np.mean([int(_ref(r)["argmax"] != r["pe_argmax"])
                           for r in b["roots"] if _ref(r)])) if ref else None),
        "margin_percentiles_plain": _dist(m_all),
        "dose": a["dose"], "dose_fields": a["dose_fields"],
        "engine": {"sha": b["engine_sha"], "tables": b["tables_fingerprint"],
                   "updates": b["n_updates"], "wall_sec": b["wall_sec"]},
        "write_side_gates": b["gates"],
        "sigma_margin": sigma,
        "crn_variance_ratio_nocrn_over_crn": crn_gain,
        "STOP_RULE": verdict,
        "topk_plain_draw": topk_report(plain),
        "topk_restricted_subset": topk_report(measured or restr),
        "w_activestats_incidence": {
            "source": "ENGINE_SEARCH_DESIGN.md §2.5 (measured, not re-measured "
                      "here per the Phase-0 brief)",
            "opponent_frac": 0.0226, "own_frac": 0.0108,
            "opponent_count": 310, "own_count": 148, "of_rows": 13702},
        "timing_note": "CONTENDED box; descriptive only, never a budget number "
                       "(S1_S2_SCREENS.md:152-159). Both sides of the ratio "
                       "below were measured on the SAME loaded box within the "
                       "same hour, which is the only reason the ratio is worth "
                       "quoting at all.",
        "ms_per_decision_poke_engine_dose_M": _dist([r["ms"] for r in recs]),
        "leaves_per_decision_poke_engine_dose_M": _dist([r["leaves"] for r in recs]),
        "us_per_leaf_poke_engine": float(
            np.sum([r["ms"] for r in recs]) * 1e3 / max(np.sum([r["leaves"] for r in recs]), 1)),
        "us_per_child_engine_spike": float(
            b["wall_sec"] * 1e6 / max(b["n_updates"], 1)),
        "distinct_children_per_root": _dist(
            [r.get("n_distinct_children", np.nan) for r in b["roots"]]),
    }
    (Path(args.out) / "p0.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(verdict, indent=2))
    print(f"wrote {Path(args.out) / 'p0.json'}")


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = dict(prereg="configs/eval/ch3_rung0.yaml", harvest="results/ch3_r1",
                  out="results/search_p0")
    a = sub.add_parser("stage-a")
    a.add_argument("--prereg", default=common["prereg"])
    a.add_argument("--harvest", default=common["harvest"])
    a.add_argument("--out", default=common["out"])
    a.add_argument("--n-per-lane", type=int, default=50)
    a.add_argument("--n-restricted-per-lane", type=int, default=50)
    a.add_argument("--top-branches-extra", type=int, nargs="*", default=[])
    a.add_argument("--torch-threads", type=int, default=1)
    a.set_defaults(fn=stage_a)

    b = sub.add_parser("stage-b")
    b.add_argument("--prereg", default=common["prereg"])
    b.add_argument("--out", default=common["out"])
    b.add_argument("--families", type=int, default=20,
                   help="R, independent chance-seed families (design asks R >= 20)")
    b.add_argument("--s-max", type=int, default=32)
    b.add_argument("--limit", type=int, default=0)
    b.add_argument("--gate-n", type=int, default=10**9)
    b.add_argument("--critic-batch", type=int, default=8192)
    b.add_argument("--torch-threads", type=int, default=2)
    b.set_defaults(fn=stage_b)

    d = sub.add_parser("detblind-ref")
    d.add_argument("--prereg", default=common["prereg"])
    d.add_argument("--harvest", default=common["harvest"])
    d.add_argument("--out", default=common["out"])
    d.add_argument("--torch-threads", type=int, default=1)
    d.set_defaults(fn=detblind_ref)

    c = sub.add_parser("combine")
    c.add_argument("--out", default=common["out"])
    c.set_defaults(fn=combine)

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
