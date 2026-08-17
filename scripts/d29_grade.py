"""D29r readout grader — the credited stack at 50M (configs/showdown_sp_stack50m.yaml).

Committed BEFORE launch per R0-e (the R0-I lesson). Two reads under the credit
line with the larger-of clause:
  R-A PRIMARY   vs the frozen struct50m comparator (aux-off, anneal-off).
  R-B SECONDARY vs the frozen D26 12M stack (the scale read; may retire §13's
                250M line on futility, may NOT be promoted to satisfy §13(1)).
Frozen comparator values are ATTESTED from disk at every run (the d25_grade
R0-15 pattern) — a moved or corrupted comparator hard-stops the grade.
Lane-failure rule (D25's, verbatim): a dead lane is reported as-is, NEVER
replaced; both se terms recompute at the surviving count; fewer than 3
surviving treatment lanes VOIDS the primary.

    python scripts/d29_grade.py                # after results/d29/final_s9*.json
    python scripts/d29_grade.py --selftest     # known-answer checks, no run files
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from d25_grade import exact_perm_p, se_terms  # noqa: E402  (unchanged, per R0-e)

# 7-decimal frozen values; attest() re-derives both sets from disk and hard-stops
# on any mismatch > 5e-7 (the JSONs carry win rates at full precision).
R_A = {35: 0.6593333, 36: 0.5726667, 37: 0.5086667}   # struct50m, 3000 eps each
R_B = {62: 0.7296667, 63: 0.7186667, 64: 0.7216667, 65: 0.7030000}  # D26
SEEDS = (90, 91, 92)
BASE_LR, ANNEAL, STEPS_PER_UPDATE = 2.5e-4, 50_000_000, 1024
FLOOR = 0.025
TRACE_STEPS = (2_000_000, 10_000_000, 26_000_000, 50_000_000)
D25_POOLED = 0.6185  # the falsifier-class threshold (12M aux-only, anneal-off)


def attest() -> None:
    for frozen, tmpl in ((R_A, "results/struct50m_finals/final_s{}.json"),
                         (R_B, "results/d26/final_s{}.json")):
        for s, want in frozen.items():
            r = json.loads(Path(tmpl.format(s)).read_text())
            got = r["eval/win_rate"]
            if abs(got - want) > 5e-7:
                raise SystemExit(
                    f"ATTESTATION FAILED: {tmpl.format(s)} win_rate {got!r} != "
                    f"frozen {want} — comparator moved/corrupted; grade refused."
                )
            if r.get("episodes") != 3000:
                raise SystemExit(f"ATTESTATION FAILED: {tmpl.format(s)} episodes "
                                 f"{r.get('episodes')} != 3000")


def d_a_lr_trace(seeds) -> bool:
    from rl.common.checkpoint import load_checkpoint

    print("D-A  LR TRACE (hard; realised lr off checkpoints, pre-increment counter)")
    ok = True
    for s in seeds:
        run = Path(f"runs/showdown_sp_stack50m_s{s}")
        for step in TRACE_STEPS:
            path = run / f"ckpt_{step:09d}.pt"
            if not path.exists():
                print(f"  s{s} @{step}: MISSING — FAIL")
                ok = False
                continue
            ck = load_checkpoint(str(path))
            agent = ck["agent"] if "agent" in ck else ck
            groups = agent["optimizer"]["param_groups"]
            updates = agent["updates"]
            want = BASE_LR * max(0.0, 1.0 - (updates - 1) * STEPS_PER_UPDATE / ANNEAL)
            bad = [i for i, g in enumerate(groups)
                   if abs(g["lr"] - want) > 1e-12 * max(want, 1e-12)]
            good = len(groups) == 3 and not bad
            ok &= good
            print(f"  s{s} {path.name}: updates={updates} lr={groups[0]['lr']:.6e} "
                  f"want={want:.6e} {'OK' if good else f'FAIL {bad}'}")
    return ok


def grade_read(name, t_rates, t_n, c_rates, c_n, comp_label, quiet=False):
    pooled_t = sum(t_rates) / len(t_rates)
    pooled_c = sum(c_rates) / len(c_rates)
    delta = pooled_t - pooled_c
    se_b, se_c, s_t, s_c = se_terms(t_rates, t_n, c_rates, c_n)
    se_gov, gov = max((se_b, "binomial"), (se_c, "seed-clustered"))
    hi = max(FLOOR, 2 * se_gov)
    if delta >= hi:
        cell = "CREDIT"
    elif delta >= FLOOR:
        cell = "letter-met, seed-fragile, NOT credited"
    elif delta > -FLOOR:
        cell = "FLAT"
    elif delta > -hi:
        cell = "letter-met NEGATIVE, not credited"
    else:
        cell = "NEGATIVE, credited in reverse"
    k, total, p = exact_perm_p(t_rates, c_rates, +1)
    separated = min(t_rates) > max(c_rates)  # tie rule: strict, ties=non-separation
    if not quiet:
        print(f"\n{name}  vs {comp_label} (frozen {pooled_c:.5f})")
        print(f"  treatment pooled {pooled_t:.5f}  delta {delta:+.5f}  (n_T={len(t_rates)})")
        print(f"  se: binomial {se_b:.5f} | clustered {se_c:.5f} "
              f"(s_T {s_t:.4f}, s_C {s_c:.4f}) -> GOVERNING: {gov}")
        print(f"  operative bar delta >= {hi:.5f} (pooled >= {pooled_c + hi:.5f})")
        print(f"  exact perm ({len(t_rates)}v{len(c_rates)}): {k}/{total} = {p:.5f}"
              f"  | strict separation: {'YES' if separated else 'NO'}")
        if cell == "CREDIT" and not separated:
            print("  NAMED CELL — pre-written sentence: \"the read credits under "
                  "the governing credit line; the lanes do not fully separate, "
                  "and the non-separation is stated wherever the permutation "
                  "would be quoted.\"")
        print(f"  cell: {cell}")
    return cell, delta, pooled_t


def selftest() -> None:
    ra, rb = list(R_A.values()), list(R_B.values())
    k, total, p = exact_perm_p([0.70, 0.71, 0.72], ra, +1)
    assert total == 20 and k == 1 and abs(p - 0.05) < 1e-12, (k, total, p)
    k, total, p = exact_perm_p([0.74, 0.75, 0.76], rb, +1)
    assert total == 35 and k == 1, (k, total)
    assert not (min([0.6593333, 0.70, 0.71]) > max(ra))  # tie -> non-separation
    # The comparator floor term itself, no vacuous disjunct: at zero treatment
    # spread 2*se_clus must reproduce the header's 0.08732 row.
    _, se_c, s_t, _ = se_terms([0.718, 0.718, 0.718], 9000, ra, 9000)
    assert s_t == 0.0 and abs(2 * se_c - 0.08732) < 5e-5, (s_t, 2 * se_c)
    # Branch cuts through grade_read itself, in win-rate units (R0-e's promise).
    # R-A bar at these synthetic spreads: hi = max(0.025, 2*se_clus).
    cases = [  # (treatment triple, expected cell)
        ([0.72, 0.71, 0.70], "CREDIT"),                       # delta +0.130 >> hi
        ([0.668, 0.669, 0.670], "CREDIT"),                    # just over the 0.0885 hi
        ([0.640, 0.641, 0.642], "letter-met, seed-fragile, NOT credited"),
        ([0.580, 0.581, 0.582], "FLAT"),
        ([0.530, 0.531, 0.532], "letter-met NEGATIVE, not credited"),
        ([0.470, 0.471, 0.472], "NEGATIVE, credited in reverse"),
    ]
    for t, want in cases:
        cell, delta, _ = grade_read("t", t, 9000, ra, 9000, "c", quiet=True)
        assert cell == want, (t, delta, cell, want)
    print("SELFTEST OK: perm totals 20/35, tie rule, floor term 0.08732, and all "
          "five branch cells hit at known win-rate cuts.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    attest()
    rates, live, r04 = [], [], []
    for s in SEEDS:
        path = Path(f"results/d29/final_s{s}.json")
        if not path.exists():
            print(f"LANE s{s}: final MISSING — reported as-is, never replaced.")
            continue
        r = json.loads(path.read_text())
        if r.get("episodes") != 3000:
            raise SystemExit(f"final_s{s}.json episodes {r.get('episodes')} != 3000")
        if abs(r["eval/win_rate"] - r["wins_from_returns"]) > 1e-9:
            r04.append(s)
        rates.append(r["eval/win_rate"])
        live.append(s)
    if len(rates) < 3:
        print(f"\nONLY {len(rates)} SURVIVING LANE(S) — PRIMARY VOID (the D25 "
              "lane-failure rule). Surviving finals recorded individually, "
              "never pooled into a headline.")
        raise SystemExit(1)

    gate_ok = d_a_lr_trace(live)
    print("\nFinals: " + "  ".join(f"s{s} {r:.4f}" for s, r in zip(live, rates)))
    print(f"(median {sorted(rates)[len(rates) // 2]:.4f}, worst {min(rates):.4f} — "
          "recorded, never govern)")

    cell_a, _, pooled = grade_read(
        "R-A PRIMARY", rates, len(rates) * 3000, list(R_A.values()), 9000,
        "struct50m aux-off/anneal-off")
    cell_b, _, _ = grade_read(
        "R-B SCALE (may not satisfy §13(1); may retire the 250M line on futility)",
        rates, len(rates) * 3000, list(R_B.values()), 12000, "D26 12M stack")
    if pooled < D25_POOLED:
        print(f"\nFALSIFIER-CLASS: pooled {pooled:.5f} < {D25_POOLED} (the 12M "
              "aux-only number) — the annealed stack regresses vs its own 12M "
              "lineage (C-1 the named suspect). Composes with the R-A cell per "
              "the header's branch preamble; it does not replace it.")
    print(f"\nR0-4: {'PASS all' if not r04 else f'FAIL {r04}'}")
    print(f"D-A: {'PASS' if gate_ok else 'FAIL — READ VOID'}")
    print(f"\nR-A VERDICT CELL: {cell_a}")
    print(f"R-B VERDICT CELL: {cell_b}")
    if not gate_ok or r04:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
