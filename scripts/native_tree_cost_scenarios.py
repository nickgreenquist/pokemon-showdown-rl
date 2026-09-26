"""Step C's search cost under its candidate designs, priced from WORK UNITS (rl/search/cost_model.py).

The units are deterministic, so they are generated UNTIMED under any load (the E-cores are fine) and priced by a
calibration file, which says under what load it ran. Each scenario runs Step C's lever form -- stepc_a's stamped tr_256
dials (sims 256, br_prior, root grid, depth cap 8, cols_k 4, chance_k 2, soft_br, tau 0.05, batch 8; pass_leaf
through) on the TRUE world with G0's foe prior -- over groups of K decisions in ONE search_many call. That is the TreeOp's
in-line form at K = a poll's searched decisions, and the deferred wide lockstep's at K ~ 16-64 (the research
catalogue's D1). Per decision = the group's predicted total / K.

  env -u POKEMON_RL_ENCODER_C6 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<worktree> taskpolicy -b <python> \\
      scripts/native_tree_cost_scenarios.py --net ckpt:<b328> --c6 --models <cal json> [<cal json> ...]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

TR_256 = dict(sims=256, mode="br_prior", root_grid=True, depth_cap=8, cols_k=4, chance_k=2, root_rule="soft_br",
              tau=0.05, batch=8)
SCENARIOS = {                                  # name -> (dials, decisions per search_many call)
    "inline_K1": (TR_256, 1),                 # Step C's floor: ~1 searched decision a poll
    "inline_K3": (TR_256, 3),                 # R7's frac: ~3 a poll
    "deferred_K16": (TR_256, 16),
    "deferred_K64": (TR_256, 64),
    "deferred_K64_lazy": (dict(TR_256, lazy_priors=True), 64),
    "inline_K1_batch1": (dict(TR_256, batch=1), 1),   # the TreeOp's default batch, for scale
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", required=True, help="ckpt:PATH (the TreeOp's callables)")
    ap.add_argument("--c6", action="store_true")
    ap.add_argument("--models", nargs="+", required=True, help="calibration JSONs to price the units with")
    ap.add_argument("--roots", type=int, default=64)
    ap.add_argument("--g0-dir", default="/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/results/r7_g0")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if os.environ.get("POKEMON_RL_ENCODER_C6"):
        sys.exit("REFUSED: set --c6, not the environment")
    if args.c6:
        os.environ["POKEMON_RL_ENCODER_C6"] = "1"
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    import pkmn_gen1
    import native_tree_gates as g
    import rollout_q as rq
    from rl.envs.engine_tables import build_tables
    from rl.search import cost_model as cm
    from rl.search import native_tree
    from rl.search.native import World
    from rl.search.tree_top import TreeOp

    torch.set_num_threads(1)
    rows_all, _g0s, _ = g.load_g0(pathlib.Path(args.g0_dir))
    tables, _fp = build_tables()
    one, prov = rq.load_committee([args.net.removeprefix("ckpt:")], None, np.random.default_rng(0))
    op = TreeOp(one.members[0], tables, seat="p1", seed=0, play=False, tree={"sims": 1})
    by_b: dict[int, list] = {}
    for r in sorted(rows_all, key=lambda r: int(r["pid"])):
        by_b.setdefault(int(r["bucket"]), []).append(r)
    per = -(-args.roots // len(by_b))
    roots = [r for b in sorted(by_b) for r in by_b[b][:per]][: args.roots]
    models = {pathlib.Path(m).stem: cm.CostModel.from_json(pathlib.Path(m).read_text()) for m in args.models}

    def spec(r):
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        m1 = np.asarray(node.mask(tables, "p1"), bool)
        prior1 = np.where(m1, np.asarray(r["pi1"], np.float64), 0.0)
        opp = np.where(np.asarray(node.mask(tables, "p2"), bool), np.asarray(r["pi2"]), 0.0)
        return ([World(node)], prior1, opp, int(r["pid"]) * 7919 + 1)

    out = {"net": prov[0]["sha256"][:12], "roots": len(roots), "scenarios": {}}
    for name, (dials, k) in SCENARIOS.items():
        per_dec = {m: [] for m in models}
        units_all = []
        for i in range(0, len(roots) - k + 1, k):
            res = native_tree.search_many([spec(r) for r in roots[i:i + k]], tables, "p1", op.value_fn, op._probs,
                                          **native_tree.dials_from(dials))
            us = [cm.units_of(x) for x in res]
            tot = {"share": {n: np.sum([u["share"][n] for u in us], axis=0).tolist() for n in cm.NETS},
                   "rows": {n: np.sum([u["rows"][n] for u in us], axis=0).tolist() for n in cm.NETS},
                   "count": {c: float(sum(u["count"][c] for u in us)) for c in us[0]["count"]}}
            units_all.append(tot)
            for m, model in models.items():
                p = model.predict(tot)
                per_dec[m].append({kk: v / k for kk, v in p.items()})
        c = lambda f: float(np.mean([f(u) for u in units_all]) / k)       # noqa: E731
        row = {"K": k, "groups": len(units_all),
               "per_decision_units": {"v_rows": c(lambda u: sum(u["rows"]["v"])), "p_rows": c(lambda u: sum(u["rows"]["p"])),
                                      "call_share": c(lambda u: u["count"]["call_share"]),
                                      "sims_tree": c(lambda u: u["count"]["sims_tree"])},
               "ms_per_decision": {m: {kk: float(np.median([x[kk] for x in xs])) for kk in xs[0]} for m, xs in per_dec.items()}}
        out["scenarios"][name] = row
        print(f"{name:20s} K {k:3d} | v rows {row['per_decision_units']['v_rows']:6.1f} p rows {row['per_decision_units']['p_rows']:6.1f} "
              f"call share {row['per_decision_units']['call_share']:6.1f} | ms/decision " +
              " ".join(f"{m.removeprefix('cost_model_')}: {x['total']:6.1f} (v {x['nn_v']:.1f} p {x['nn_p']:.1f} eng {x['engine']:.1f} py {x['python']:.1f})"
                       for m, x in row["ms_per_decision"].items()), flush=True)
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
