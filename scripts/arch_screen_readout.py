"""Read out the R7 architecture screen by the rule configs/bc_arch_screen.yaml
pre-registered, from the files under results/arch_screen/.

    python scripts/arch_screen_readout.py --results results/arch_screen

It reads NOTHING from the pre-reg config. The rule is restated here as
constants and printed verbatim beside the verdict, so the two artefacts cannot
drift into agreement after the fact — the config is the record of what was
promised, this file is an independent implementation of it, and a disagreement
between them is visible rather than absorbed.

EVERY NUMBER IT PRINTS IS RE-DERIVED FROM DISK. The per-seed agreements are
recomputed from each fit's `*_val_rows.npz` (the saved per-row predictions at
that fit's best epoch) and CROSS-CHECKED against the `best_agreement_free`
the fit itself wrote into `*.json`; a mismatch is a hard failure, not a
warning. That check is the whole reason the rows are saved: a mean is not
auditable, and a correction typed from a remembered mean is the landmine this
repo has paid for more than once.

THE INTERVAL IS A CLUSTER BOOTSTRAP BY BATTLE. Consecutive decisions inside
one battle share a team, an opponent and a turn context, so resampling ROWS
would understate the interval by roughly sqrt(decisions per battle). One
replicate resamples each seed's held-out BATTLES with replacement — the SAME
battles for both arms, because the pairing is the point — recomputes both
arms' statistics over the resampled rows, differences them, and averages the
three seeds.

PAIRING IS VERIFIED, NOT ASSUMED. `battle_split` is seeded by the FIT SEED,
so at a given seed the two arms must hold out the same battles in the same row
order. The script asserts that element-wise and REFUSES to print a delta if it
fails — an unmatched comparison is exactly how a -0.0007 null became a -0.053
"result" here on 2026-09-17.
"""

import argparse
import json
from pathlib import Path

import numpy as np

# ---- the pre-registered rule, restated (configs/bc_arch_screen.yaml) -------
ARMS = {"A": ("entity_deepsets", "arch_screen_entity_s{seed}"),
        "B": ("attention", "arch_screen_attn_s{seed}")}
SEEDS = (0, 1, 2)
N_BOOT = 1000
BOOT_SEED = 20260920
CI = (2.5, 97.5)
GATE_DELTA = 0.02
GATE_THROUGHPUT = 3.0
RULE = (
    "CLEARS iff (i) delta agreement_free >= +0.02, (ii) its 95% cluster-"
    "bootstrap-by-battle CI excludes 0, and (iii) median train-step "
    "attention / entity_deepsets <= 3.0x."
)
SPEC_EXTRA_KL = -0.02  # ARCH_SCREEN_SPEC's stricter both-metrics variant.
REVEAL_BUCKETS = ((0, 1), (2, 3), (4, 6))


def _load(results: Path, seed: int, run_tpl: str):
    name = run_tpl.format(seed=seed)
    rep = json.loads((results / f"{name}.json").read_text())
    rows = dict(np.load(results / f"{name}_val_rows.npz"))
    # The fit's own selection, re-derived rather than trusted: best epoch is
    # the FIRST epoch attaining the max agreement_free, which is exactly the
    # strict `>` train_bc compares with.
    hist = rep["history"]
    best = max(h["agreement_free"] for h in hist)
    epoch = next(h["epoch"] for h in hist if h["agreement_free"] == best)
    assert int(rows["epoch"]) == epoch, (name, int(rows["epoch"]), epoch)
    assert rep.get("best_epoch", epoch) == epoch, (name, rep.get("best_epoch"), epoch)
    row = next(h for h in hist if h["epoch"] == epoch)
    # THE CROSS-CHECK: the saved rows must reproduce the fit's own three
    # reported means. All three, not just the one the gate reads — a row file
    # that agrees on agreement and disagrees on KL is a row file written from
    # a different forward pass, and the readout would not otherwise notice.
    free = rows["free"].astype(bool)
    for label, got, want, tol in (
        ("agreement_free", float(rows["agree"][free].mean()), best, 1e-6),
        ("val_kl", float(rows["kl"].mean()), row["val_kl"], 1e-5),
        ("fitted_entropy", float(rows["entropy"].mean()), row["fitted_entropy"], 1e-5),
    ):
        assert abs(got - want) < tol, (name, label, got, want)
    return name, rep, rows, epoch, row


def _stats(rows: dict, sel: np.ndarray) -> dict:
    """agreement_free and val_kl over a row selection. `free` gates agreement
    (single-legal-action rows are free for any policy); val_kl is over ALL
    held-out rows, which is how train_bc reports it."""
    free = rows["free"].astype(bool) & sel
    return {"agreement_free": float(rows["agree"][free].mean()),
            "val_kl": float(rows["kl"][sel].mean())}


def _bootstrap(per_seed: list[tuple[dict, dict]], n_boot: int, seed: int) -> dict:
    """per_seed[i] = (A_rows, B_rows) for seed i, already pair-verified.

    One replicate: for each seed resample its held-out BATTLES with
    replacement to the same battle count, recompute both arms over exactly
    those rows, difference, then average over seeds.
    """
    rng = np.random.default_rng(seed)
    # Row indices grouped by battle, computed once — the resample is an index
    # gather, not a mask rebuild, or 1,000 replicates over 3 seeds is slow
    # enough that someone will cut the replicate count.
    groups = []
    for a_rows, _ in per_seed:
        bids = a_rows["battle_ids"]
        order = np.argsort(bids, kind="stable")
        sorted_ids = bids[order]
        bounds = np.flatnonzero(np.r_[True, sorted_ids[1:] != sorted_ids[:-1]])
        groups.append([order[s:e] for s, e in
                       zip(bounds, np.r_[bounds[1:], len(order)])])
    out = {"agreement_free": [], "val_kl": []}
    for _ in range(n_boot):
        deltas = {"agreement_free": [], "val_kl": []}
        for (a_rows, b_rows), gs in zip(per_seed, groups):
            pick = rng.integers(0, len(gs), size=len(gs))
            # A battle drawn twice must count twice, so the resample is an
            # INDEX GATHER; a boolean mask would silently deduplicate it.
            idx = np.concatenate([gs[p] for p in pick])
            a_free = a_rows["free"][idx].astype(bool)
            for key, arr_a, arr_b, gate in (
                ("agreement_free", a_rows["agree"], b_rows["agree"], a_free),
                ("val_kl", a_rows["kl"], b_rows["kl"], None),
            ):
                take = idx[gate] if gate is not None else idx
                deltas[key].append(float(arr_b[take].mean() - arr_a[take].mean()))
        for key in out:
            out[key].append(float(np.mean(deltas[key])))
    return {k: np.asarray(v) for k, v in out.items()}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--boot", type=int, default=N_BOOT)
    p.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS),
                   help="the pre-registered seeds are 0 1 2; a subset is a SMOKE "
                        "of this script, never a readout")
    p.add_argument("--json-out", type=Path, default=None,
                   help="also write every printed quantity as JSON, so the "
                        "committed readout can CITE A FILE for each number "
                        "instead of having it transcribed from a terminal")
    args = p.parse_args()
    res = args.results
    seeds = tuple(args.seeds)
    if seeds != SEEDS:
        print(f"*** SMOKE ONLY: seeds {seeds} != the pre-registered {SEEDS}. "
              "This is not the screen's readout. ***\n")

    loaded, per_seed = {}, []
    out: dict = {"rule": RULE, "seeds": list(seeds), "n_boot": args.boot,
                 "boot_seed": BOOT_SEED, "ci_percentiles": list(CI), "fits": []}
    print(f"RULE (pre-registered, configs/bc_arch_screen.yaml):\n  {RULE}\n")
    print("PER-SEED, PER-ARM (each arm at its OWN best epoch; n = held-out rows)")
    header = (f"{'arm':16s} {'seed':>4s} {'ep':>3s} {'agree_free':>11s} {'val_kl':>8s} "
              f"{'fit_ent':>8s} {'tch_ent':>8s} {'r0-1':>7s} {'r2-3':>7s} {'r4-6':>7s} "
              f"{'n_free':>7s} {'n':>7s} {'params':>8s}")
    print(header)
    for seed in seeds:
        for arm, (trunk, tpl) in ARMS.items():
            name, rep, rows, epoch, row = _load(res, seed, tpl)
            loaded[(arm, seed)] = (name, rep, rows, epoch, row)
            free = rows["free"].astype(bool)
            buckets = []
            for lo, hi in REVEAL_BUCKETS:
                sel = free & (rows["reveal"] >= lo) & (rows["reveal"] <= hi)
                buckets.append(float(rows["agree"][sel].mean()) if sel.sum() else float("nan"))
            print(f"{trunk:16s} {seed:>4d} {epoch:>3d} "
                  f"{row['agreement_free']:>11.4f} {row['val_kl']:>8.4f} "
                  f"{row['fitted_entropy']:>8.4f} {row['teacher_entropy']:>8.4f} "
                  f"{buckets[0]:>7.4f} {buckets[1]:>7.4f} {buckets[2]:>7.4f} "
                  f"{int(free.sum()):>7d} {len(free):>7d} {rep['actor_params']:>8,d}")
            curve = [h["agreement_free"] for h in rep["history"]]
            out["fits"].append({
                "run_name": name, "arm": arm, "trunk": trunk, "seed": seed,
                "best_epoch": epoch, "epochs": rep["epochs"],
                "agreement_free": row["agreement_free"], "val_kl": row["val_kl"],
                "fitted_entropy": row["fitted_entropy"],
                "teacher_entropy": row["teacher_entropy"],
                "agree_reveal": {f"{lo}_{hi}": b
                                 for (lo, hi), b in zip(REVEAL_BUCKETS, buckets)},
                "n_free": int(free.sum()), "n": int(len(free)),
                "val_battles": int(len(np.unique(rows["battle_ids"]))),
                "actor_params": rep["actor_params"],
                # The plateau read: best-epoch selection over a flat tail is
                # picking noise, not a stopping point. Both arms get the same
                # treatment, so the bias largely cancels in the paired delta —
                # but the number has to be on the page to say that.
                "last5_spread": float(max(curve[-5:]) - min(curve[-5:])),
                "curve": [round(c, 4) for c in curve],
            })

    # ---- pairing, asserted before any delta is printed --------------------
    for seed in seeds:
        a = loaded[("A", seed)][2]
        b = loaded[("B", seed)][2]
        assert np.array_equal(a["battle_ids"], b["battle_ids"]), f"seed {seed}: split differs"
        assert np.array_equal(a["free"], b["free"]), f"seed {seed}: free mask differs"
        assert np.array_equal(a["action"], b["action"]), f"seed {seed}: labels differ"
        per_seed.append((a, b))
    n_battles = [len(np.unique(a["battle_ids"])) for a, _ in per_seed]
    print(f"\npairing verified: identical held-out rows per seed "
          f"(battles {n_battles}, rows {[len(a['agree']) for a, _ in per_seed]})")

    # ---- the paired deltas ------------------------------------------------
    point = {}
    for key in ("agreement_free", "val_kl"):
        ds = []
        for seed, (a, b) in zip(seeds, per_seed):
            sel = np.ones(len(a["agree"]), dtype=bool)
            ds.append(_stats(b, sel)[key] - _stats(a, sel)[key])
        point[key] = (float(np.mean(ds)), ds)

    boot = _bootstrap(per_seed, args.boot, BOOT_SEED)
    print(f"\nPAIRED DELTA (B attention - A entity_deepsets), mean over seeds "
          f"{list(seeds)}; CI = cluster bootstrap by battle, {args.boot} resamples")
    ci = {}
    for key in ("agreement_free", "val_kl"):
        mean, ds = point[key]
        lo, hi = np.percentile(boot[key], CI)
        ci[key] = (float(lo), float(hi))
        side = "positive favours attention" if key == "agreement_free" \
            else "negative favours attention"
        print(f"  d{key:15s} {mean:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]   "
              f"per-seed {[round(d, 4) for d in ds]}   ({side})")
        out.setdefault("paired", {})[key] = {
            "mean": mean, "ci95": [float(lo), float(hi)],
            "per_seed": [float(d) for d in ds], "direction": side,
        }

    # ---- reveal buckets, mechanism only -----------------------------------
    print("\nSECONDARY (MECHANISM, NEVER A VERDICT INPUT) — delta by how many "
          "opponent mons are revealed")
    for lo, hi in REVEAL_BUCKETS:
        ds, ns = [], []
        for a, b in per_seed:
            sel = a["free"].astype(bool) & (a["reveal"] >= lo) & (a["reveal"] <= hi)
            ds.append(float(b["agree"][sel].mean() - a["agree"][sel].mean()))
            ns.append(int(sel.sum()))
        print(f"  reveal {lo}-{hi}: d {np.mean(ds):+.4f}   per-seed "
              f"{[round(d, 4) for d in ds]}   n {ns}")
        out.setdefault("reveal_delta", {})[f"{lo}_{hi}"] = {
            "mean": float(np.mean(ds)), "per_seed": [float(d) for d in ds],
            "n_per_seed": ns,
        }
    for arm, (trunk, _) in ARMS.items():
        fe = [loaded[(arm, s)][4]["fitted_entropy"] for s in seeds]
        te = [loaded[(arm, s)][4]["teacher_entropy"] for s in seeds]
        print(f"  {trunk:16s} fitted_entropy {np.mean(fe):.4f} vs teacher "
              f"{np.mean(te):.4f} ({'ABOVE' if np.mean(fe) >= np.mean(te) else 'BELOW'} "
              "the teacher's)")
    eps = [loaded[(arm, s)][3] for arm in ARMS for s in seeds]
    if 20 in eps:
        print("  NOTE: at least one arm's best epoch is the LAST (20) — that arm was "
              "still improving and is UNDER-TRAINED at this budget. A caveat on the "
              "null, not on the arm.")

    # ---- throughput -------------------------------------------------------
    tp = json.loads((res / "throughput.json").read_text())
    print("\nTHROUGHPUT (one actor train step, batch "
          f"{tp['batch']}, threads {tp['env']['torch_threads']}, median of "
          f"{tp['steps']} after {tp['warmup']} warmup)")
    for name, row in tp["rows"].items():
        print(f"  {name:16s} policy {1e3 * row['policy']['median_s']:8.2f} ms   "
              f"value {1e3 * row['value']['median_s']:8.2f} ms   "
              f"params {row['policy']['params']:>9,d}")
    ratio = tp["ratios"]["GATE_attention_over_entity_deepsets_policy"]
    print(f"  GATE ratio attention / entity_deepsets = {ratio:.2f}x "
          f"(pre-registered ceiling {GATE_THROUGHPUT}x)")
    print(f"  historical comparator attention / mlp_512x512 = "
          f"{tp['ratios']['attention_over_mlp_policy_HISTORICAL_COMPARATOR']:.2f}x "
          "(the 2026-08-07 kill quoted 34.6x on this pairing)")
    # NOT the gate. An RL update trains BOTH heads, so this is the number a
    # future fleet-arm pre-reg would start its arithmetic from — printed here
    # so nobody has to recompute it by hand from the JSON.
    both = ((tp["rows"]["attention"]["policy"]["median_s"]
             + tp["rows"]["attention"]["value"]["median_s"])
            / (tp["rows"]["entity_deepsets"]["policy"]["median_s"]
               + tp["rows"]["entity_deepsets"]["value"]["median_s"]))
    print(f"  both-heads (actor + critic) attention / entity_deepsets = {both:.2f}x "
          "— NOT the gate; the input an RL projection would use")

    # ---- the verdict, by the rule ----------------------------------------
    d_agree = point["agreement_free"][0]
    lo, hi = ci["agreement_free"]
    c1 = d_agree >= GATE_DELTA
    c2 = (lo > 0) or (hi < 0)
    c3 = ratio <= GATE_THROUGHPUT
    print("\nVERDICT")
    print(f"  (i)   delta agreement_free {d_agree:+.4f} >= +{GATE_DELTA}      : "
          f"{'PASS' if c1 else 'FAIL'}")
    print(f"  (ii)  95% CI [{lo:+.4f}, {hi:+.4f}] excludes 0        : "
          f"{'PASS' if c2 else 'FAIL'}")
    print(f"  (iii) throughput ratio {ratio:.2f}x <= {GATE_THROUGHPUT}x          : "
          f"{'PASS' if c3 else 'FAIL'}")
    print(f"  => THE SCREEN {'CLEARS' if (c1 and c2 and c3) else 'DOES NOT CLEAR'}")
    d_kl, (klo, khi) = point["val_kl"][0], ci["val_kl"]
    spec = c1 and c2 and (d_kl <= SPEC_EXTRA_KL) and (khi < 0)
    print(f"  (ARCH_SCREEN_SPEC's stricter both-metrics variant, which also "
          f"required d val_kl <= {SPEC_EXTRA_KL}: d {d_kl:+.4f} "
          f"CI [{klo:+.4f}, {khi:+.4f}] -> would {'ALSO clear' if spec else 'NOT clear'})")
    if not c3:
        print("  (iii) is a MEASURED MECHANISM CEILING and is the one result here "
              "that may be cited against adoption. A failure of (i)/(ii) is NOT a "
              "kill and may not appear in a ranking or an opinion (CLAUDE.md rule 6).")

    if args.json_out:
        out["throughput"] = {
            "source": str((res / "throughput.json").resolve()),
            "batch": tp["batch"], "steps": tp["steps"], "warmup": tp["warmup"],
            "median_ms": {k: {h: 1e3 * v["median_s"] for h, v in r.items()}
                          for k, r in tp["rows"].items()},
            "params": {k: {h: v["params"] for h, v in r.items()}
                       for k, r in tp["rows"].items()},
            "gate_ratio_attention_over_entity_deepsets": ratio,
            "both_heads_ratio": both,
            "attention_over_mlp": tp["ratios"][
                "attention_over_mlp_policy_HISTORICAL_COMPARATOR"],
            "entity_deepsets_over_mlp": tp["ratios"]["entity_deepsets_over_mlp_policy"],
            "utc": tp["env"]["utc"], "git_sha": tp["env"].get("git_sha"),
            "note": tp.get("note", ""),
        }
        out["verdict"] = {
            "gate_i_delta_ge_0.02": bool(c1),
            "gate_ii_ci_excludes_zero": bool(c2),
            "gate_iii_throughput_le_3x": bool(c3),
            "clears": bool(c1 and c2 and c3),
            "spec_both_metrics_variant_would_clear": bool(spec),
        }
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(out, indent=2) + "\n")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
