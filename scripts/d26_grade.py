"""D26 readout grader — Q6 (primary, credit line) + D-A (LR trace, hard gate).

R0-I owed this script before readout ("one script implementing Q6 and Q10,
reusing d25_grade.py::se_terms and ::exact_perm_p unchanged"); it was found
missing at readout time (2026-08-17) and written then, before any final was
read. Q10's mechanism secondaries are recorded reads on history.csv and are
printed as raw numbers only — nothing here adjudicates them.

    python scripts/d26_grade.py            # after the 4 finals exist

Comparator (Q6, FROZEN, never re-scored): D25's five banked finals.
Treatment: results/d26/final_s{62..65}.json at 3000 battles each.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from d25_grade import exact_perm_p, se_terms  # noqa: E402  (R0-I: unchanged)

COMPARATOR = {52: 0.6233, 53: 0.6573, 54: 0.6063, 55: 0.6073, 56: 0.5980}
C_N_TOTAL = 5 * 3000
SEEDS = (62, 63, 64, 65)
BASE_LR, ANNEAL, STEPS_PER_UPDATE = 2.5e-4, 12_000_000, 1024
FLOOR = 0.025


def d_a_lr_trace() -> bool:
    """D-A (HARD): realised lr off the 2M/6M/12M checkpoints, every lane,
    conjunctive; Q3's PRE-increment convention, all three param groups."""
    from rl.common.checkpoint import load_checkpoint

    print("D-A  LR TRACE (hard; read off checkpoints, not the YAML)")
    ok = True
    for s in SEEDS:
        run = Path(f"runs/showdown_sp_recipe12m_s{s}")
        for step in (2_000_000, 6_000_000, 12_000_000):
            cks = sorted(run.glob("ckpt_*.pt"))
            ck_path = next((c for c in cks if int(c.stem.split("_")[1]) == step), None)
            if ck_path is None:  # the final threshold write is checkpoint.pt
                ck_path = run / "checkpoint.pt" if step == 12_000_000 else None
            if ck_path is None or not ck_path.exists():
                print(f"  s{s} @{step}: MISSING checkpoint — FAIL")
                ok = False
                continue
            ck = load_checkpoint(str(ck_path))
            agent = ck["agent"] if "agent" in ck else ck
            groups = agent["optimizer"]["param_groups"]
            updates = agent["updates"]
            want = BASE_LR * max(0.0, 1.0 - (updates - 1) * STEPS_PER_UPDATE / ANNEAL)
            bad = [i for i, g in enumerate(groups)
                   if abs(g["lr"] - want) > 1e-12 * max(want, 1e-12)]
            n_g = len(groups)
            good = n_g == 3 and not bad
            ok &= good
            print(f"  s{s} {ck_path.name}: updates={updates} groups={n_g} "
                  f"lr={groups[0]['lr']:.6e} want={want:.6e} "
                  f"{'OK' if good else f'FAIL {bad}'}")
    return ok


def main() -> None:
    gate_ok = d_a_lr_trace()

    rates, r04_fail = [], []
    for s in SEEDS:
        r = json.loads(Path(f"results/d26/final_s{s}.json").read_text())
        if abs(r["eval/win_rate"] - r["wins_from_returns"]) > 1e-9:
            r04_fail.append(s)
        rates.append(r["eval/win_rate"])

    c_rates = [COMPARATOR[s] for s in sorted(COMPARATOR)]
    pooled_t = sum(rates) / len(rates)          # Q6: EQUAL-WEIGHT MEAN governs
    pooled_c = sum(c_rates) / len(c_rates)
    delta = pooled_t - pooled_c
    se_b, se_c, s_t, s_c = se_terms(rates, len(SEEDS) * 3000, c_rates, C_N_TOTAL)
    se_gov, gov_name = max((se_b, "binomial"), (se_c, "seed-clustered"))
    hi = max(FLOOR, 2 * se_gov)

    if delta >= hi:
        branch = "B1 CREDIT"
    elif delta >= FLOOR:
        branch = "B2 letter-met, seed-fragile, NOT credited"
    elif delta > -FLOOR:
        branch = "B3 FLAT — licenses nothing (Q6: 'flat excludes nothing')"
    elif delta > -hi:
        branch = "B4 letter-met NEGATIVE, not credited"
    else:
        branch = "B5 NEGATIVE, credited in reverse"

    k, total, p = exact_perm_p(rates, c_rates, +1)
    print("\nQ6  PRIMARY — D26 vs frozen D25 comparator")
    for s, r in zip(SEEDS, rates):
        print(f"  s{s}: {r:.4f}")
    print(f"  pooled {pooled_t:.5f}  (median {sorted(rates)[1]:.4f}/"
          f"{sorted(rates)[2]:.4f}, worst {min(rates):.4f} — recorded, never govern)")
    print(f"  comparator {pooled_c:.5f} (frozen)   delta {delta:+.5f}")
    print(f"  se: binomial {se_b:.5f} | seed-clustered {se_c:.5f} "
          f"(s_T {s_t:.4f}, s_C {s_c:.4f}) -> GOVERNING: {gov_name}")
    print(f"  operative bar: delta >= {hi:.5f}  (pooled >= {pooled_c + hi:.5f})")
    print(f"  branch cuts (win-rate units): B1 >= {pooled_c + hi:.5f} | "
          f"B2 >= {pooled_c + FLOOR:.5f} | B3 > {pooled_c - FLOOR:.5f} | "
          f"B4 > {pooled_c - hi:.5f} | B5 <= {pooled_c - hi:.5f}")
    print(f"  exact 4v5 permutation (dir +1): {k}/{total} = {p:.5f}")
    print(f"  R0-4 win_rate==wins_from_returns: "
          f"{'PASS all' if not r04_fail else f'FAIL {r04_fail}'}")
    print(f"  D-A LR trace: {'PASS' if gate_ok else 'FAIL — READ IS VOID'}")
    print(f"\nVERDICT: {branch}")
    if not gate_ok or r04_fail:
        print("GATE FAILURE ABOVE — the verdict line is VOID until resolved.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
