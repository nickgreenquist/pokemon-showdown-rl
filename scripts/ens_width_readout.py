"""ens_width readout -- the reads PRE-STATED in configs/eval/ens_width.yaml (W1,
W2) and configs/eval/ens_width_offfp.yaml (R1, R2, R3), computed from disk.

    python scripts/ens_width_readout.py

Unpaired two-proportion binomial se everywhere: seeds do NOT pair battles
(docs/landmines.md, 2026-09-11), so there is no paired estimator to reach for.
Anything not on disk prints PENDING rather than a number. DESCRIPTIVE -- this
screen credits nothing; it informs the WIDTH of the 2026-09-12 fleet.

Every rate is wins / battles with ties as non-wins, which is what both the
chunk JSONs (`returns` > 0) and the FP h2h JSONs (`our_win_rate`) already
encode -- no key is read that the file does not carry (the 2026-09-11 lesson:
a diagnostic that read `override_rate` from a chunk that only the merged final
carries printed 0.000 and nearly voided a live arm).
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path

S3 = Path("results/search_s3_100m")
EW = Path("results/ens_width")
EWF = Path("results/ens_width_offfp")

BANKED_G100F_MEAN = 0.49844   # results/ch5_100m/t1{04,12,20}.json, 2026-09-03, n=3000 each
BANKED_G50F_MEAN = 0.47456    # RESULTS.md s18 control row (R2 50M finals off FP@20)
BANKED_ENS3F = (0.557, 1000)  # results/ens_offfp/ens3f.json, 2026-09-11


def chunks(d: Path, job: str):
    files = sorted(glob.glob(str(d / f"{job}.chunk*.json")))
    wins = n = 0
    for f in files:
        r = json.load(open(f))["returns"]
        wins += sum(1 for x in r if x > 0)
        n += len(r)
    return (wins / n, n) if n else None


def pooled(d: Path, jobs: list[str]):
    parts = [chunks(d, j) for j in jobs]
    if any(p is None for p in parts):
        return None
    w = sum(p[0] * p[1] for p in parts)
    n = sum(p[1] for p in parts)
    return w / n, n


def mean_of(d: Path, jobs: list[str]):
    parts = [chunks(d, j) for j in jobs]
    if any(p is None for p in parts):
        return None
    return sum(p[0] for p in parts) / len(parts), sum(p[1] for p in parts)


def fp(tag: str):
    f = EWF / f"{tag}.json"
    if not f.exists():
        return None
    d = json.load(open(f))
    if d.get("battles_finished", 0) < d.get("battles_requested", 1):
        return None
    return d["our_win_rate"], d["battles_finished"]


def se_diff(a, b):
    (pa, na), (pb, nb) = a, b
    return math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)


def fmt(x):
    return "PENDING" if x is None else f"{x[0]:.5f} (n={x[1]})"


def delta_line(name, a, b, floor=0.025):
    if a is None or b is None:
        print(f"  {name}: PENDING")
        return
    d = a[0] - b[0]
    se = se_diff(a, b)
    z = d / se if se else float("nan")
    tag = "clears +0.025 AND 2se" if (d >= floor and d >= 2 * se) else (
        "|d| < 2se: unresolved at this n" if abs(d) < 2 * se else "separates, below the floor" if d > 0 else "NEGATIVE at >= 2se")
    print(f"  {name}: {d:+.5f}  se_diff {se:.5f}  z {z:+.2f}  -> {tag}")


def main() -> None:
    print("== vs SH (locked protocol; block b0 = seeds 100-3099 unless pooled) ==")
    a0 = mean_of(S3, ["a0_s104", "a0_s112", "a0_s120"])
    ens2 = mean_of(S3, ["ens2a_b0", "ens2b_b0", "ens2c_b0"])
    ens3_b0 = chunks(S3, "ens3_b0")
    ens3 = pooled(S3, ["ens3_b0", "ens3_b1", "ens3_b2"])
    a50 = mean_of(EW, ["a50_s66", "a50_s75", "a50_s83"])
    e350_b0 = chunks(EW, "e350_b0")
    e350 = pooled(EW, ["e350_b0", "e350_b1", "e350_b2"])
    e4 = chunks(EW, "e4_b0")
    e5 = chunks(EW, "e5_b0")
    e6_b0 = chunks(EW, "e6mix_b0")
    e6 = pooled(EW, ["e6mix_b0", "e6mix_b1", "e6mix_b2"])
    print("W1 members-at-100M curve on b0 (members 4-6 are the 50M finals: a LOWER bound):")
    for k, v in [("1 (A0 singles mean)", a0), ("2 (ENS2 pairs mean)", ens2), ("3 (ENS3 b0)", ens3_b0),
                 ("4 (E4 b0: trio + s75)", e4), ("5 (E5 b0: + s66)", e5), ("6 (E6MIX b0)", e6_b0)]:
        print(f"  {k:28s} {fmt(v)}")
    print("  pooled n=9000:")
    print(f"    ENS3  {fmt(ens3)}")
    print(f"    E6MIX {fmt(e6)}")
    delta_line("E6MIX - ENS3 (pooled)", e6, ens3)
    print("W2 ensemble gain at 50M vs at 100M (3 members minus singles mean):")
    print(f"  A50 singles mean {fmt(a50)}   E350 pooled {fmt(e350)}")
    if a50 and e350:
        print(f"  gain@50M  {e350[0] - a50[0]:+.5f}   gain@100M {ens3[0] - a0[0]:+.5f}  (ENS3 pooled - A0 mean)")
    else:
        print("  gain@50M PENDING; gain@100M " + (f"{ens3[0] - a0[0]:+.5f}" if ens3 and a0 else "PENDING"))

    print("\n== off FP@20 (search_time_ms 20 per arm; both FP disclosures travel; n=1000 each) ==")
    g100 = [fp(t) for t in ("g104f", "g112f", "g120f")]
    g50 = [fp(t) for t in ("g66f", "g75f", "g83f")]
    ens3fr, e6f, e350f = fp("ens3fr"), fp("e6mixf"), fp("e350f")
    for name, v in [("G104F", g100[0]), ("G112F", g100[1]), ("G120F", g100[2]),
                    ("G66F", g50[0]), ("G75F", g50[1]), ("G83F", g50[2]),
                    ("E350F", e350f), ("E6MIXF", e6f), ("ENS3FR", ens3fr)]:
        print(f"  {name:7s} {fmt(v)}")
    g100m = (sum(x[0] for x in g100) / 3, 3000) if all(g100) else None
    g50m = (sum(x[0] for x in g50) / 3, 3000) if all(g50) else None
    print("R1 same-session greedy comparator, and the ensemble against it:")
    if g100m:
        print(f"  G100F mean {g100m[0]:.5f} vs banked 2026-09-03 mean {BANKED_G100F_MEAN:.5f}: era term {g100m[0] - BANKED_G100F_MEAN:+.5f}")
    else:
        print("  G100F mean PENDING")
    delta_line("ENS3F (banked 0.557) - G100F", BANKED_ENS3F, g100m)
    delta_line("ENS3FR - G100F", ens3fr, g100m)
    if ens3fr:
        print(f"  replicate spread |ENS3FR - ENS3F| = {abs(ens3fr[0] - BANKED_ENS3F[0]):.5f} (se of a 1000-vs-1000 difference ~0.022)")
    print("R2 six members vs three, off-FP (pooled ENS3F + ENS3FR as the 3-member point):")
    ens3_pool = ((BANKED_ENS3F[0] * 1000 + ens3fr[0] * ens3fr[1]) / (1000 + ens3fr[1]), 1000 + ens3fr[1]) if ens3fr else None
    delta_line("E6MIXF - pooled ENS3F/ENS3FR", e6f, ens3_pool, floor=0.039)
    print("R3 ensemble gain at 50M vs at 100M, off-FP:")
    if e350f and g50m:
        print(f"  gain@50M  {e350f[0] - g50m[0]:+.5f}  (G50F mean {g50m[0]:.5f}; banked 2026-09-03 {BANKED_G50F_MEAN:.5f})")
    else:
        print("  gain@50M PENDING")
    if ens3_pool and g100m:
        print(f"  gain@100M {ens3_pool[0] - g100m[0]:+.5f}  (pooled ENS3F/ENS3FR - G100F mean)")
    else:
        print("  gain@100M PENDING")


if __name__ == "__main__":
    main()
