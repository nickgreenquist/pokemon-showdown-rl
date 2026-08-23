"""Chapter-3 RUNG-4 grader (BI-3): the ensemble-critic credit test.

    python scripts/ch3_r4_grade.py --prereg configs/eval/ch3_r4_ensemble_critic.yaml
    python scripts/ch3_r4_grade.py --selftest

R4 semantics (configs/eval/ch3_r4_ensemble_critic.yaml, REGISTERED
2026-08-23): d_i = p(A1E, lane) - p(A1S, lane), PAIRED on the four
checkpoint lanes, BOTH ARMS FRESH SAME-SESSION; delta = equal-weight mean.
land()/check_partition()/se_terms_r2/CREDIT_LINE are IMPORTED UNMODIFIED
from ch3_r2_grade (the pre-reg pins the boundary landings to that law —
notably delta = -0.025 -> B5 when hi = 0.025). A0 is recorded-only and
enters no delta. B1 splits: B1a iff credit AND A1E pooled > 0.79283 AND
the F10 offset <= 0.020; else B1b ("new best" not claimable). KILL closes
the evaluator line within the chapter and suppresses B3's "axis not dead"
clause. F-gates before any branch: F3 leaves band (both search arms), F5
evaluator provenance (membership evidence in every A1E chunk), F6 arm
contrast, F7 leaf match (non-voiding, strips the no-compute-confound
clause), F8 win_rate == wins_from_returns exact (every chunk, every arm),
F9 mask-desync disclosure, F4 era bands (disclosure/STOP, never VOID),
F10 A1S reproduction tripwire (disclose 0.020 / VOID 0.040), F11 pairing
window (>= 80% span overlap per lane, non-voiding disclosure). Refuses:
DRAFT status, any "[MAINTAINER RULING" bracket, non-byte-equal credit
line, dirty tree, uncommitted pre-reg.
"""

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from ch3_r2_grade import CREDIT_LINE, FLOOR, check_partition, land, se_terms_r2  # noqa: E402


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


def _span_overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Overlap of two wall-clock spans as a fraction of the shorter span."""
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    shorter = min(a[1] - a[0], b[1] - b[0])
    if shorter <= 0:
        return 0.0
    return max(0.0, hi - lo) / shorter


def grade(prereg_path: str) -> dict:
    raw = Path(prereg_path).read_text()
    prereg = yaml.safe_load(raw)
    assert "DRAFT" not in str(prereg.get("status", "")), (
        "pre-reg status is DRAFT — registration is the maintainer's, not the "
        "grader's"
    )
    assert "[MAINTAINER RULING" not in raw, (
        "an unruled maintainer bracket remains in the pre-reg (U4 pattern) — "
        "rule it before grading"
    )
    assert prereg["credit_line"] == CREDIT_LINE, (
        "pre-reg credit_line is not byte-equal to the module constant"
    )
    dirty = _git(["status", "--porcelain"])
    assert not dirty, f"tree is dirty; commit before grading:\n{dirty}"
    assert not _git(["status", "--porcelain", "--", prereg_path]), "pre-reg uncommitted"

    rdir = Path(prereg["results_dir"])
    arms = prereg["arms"]
    lanes = arms["A1S"]["lanes"]
    assert lanes == arms["A1E"]["lanes"] == arms["A0"]["lanes"]
    n = arms["A1S"]["battles"]
    assert n == arms["A1E"]["battles"]

    # ---- F6 ARM CONTRAST (VOID): identical dicts except `evaluator` ----
    f_gates: dict[str, str] = {}
    a1s_dict = {k: v for k, v in arms["A1S"].items() if k != "evaluator"}
    a1e_dict = {k: v for k, v in arms["A1E"].items() if k != "evaluator"}
    if a1s_dict != a1e_dict or "evaluator" in arms["A1S"] or "evaluator" not in arms["A1E"]:
        f_gates["F6"] = "A1S/A1E arm dicts differ beyond `evaluator`, or A1S has one"

    # ---- F8 (VOID) on every chunk file, every arm; collect timestamps ----
    spans: dict[str, dict[str, tuple[float, float]]] = {"a1s": {}, "a1e": {}}
    desyncs: dict[str, int] = {}
    pins = {k: v["sha256"] for k, v in prereg["checkpoints"].items()}
    for chunk in sorted(rdir.glob("*.chunk*.json")):
        rep = json.loads(chunk.read_text())
        if rep["eval/win_rate"] != rep["wins_from_returns"]:
            f_gates["F8"] = f"reward-sign guard: {chunk.name}"
        job = rep["job"]
        arm_l, lane = job.split("_", 1)
        if arm_l in spans and "started_at" in rep:
            s0, s1 = spans[arm_l].get(lane, (rep["started_at"], rep["finished_at"]))
            spans[arm_l][lane] = (min(s0, rep["started_at"]), max(s1, rep["finished_at"]))
        # ---- F5 (VOID): membership evidence in every A1E chunk ----
        if arm_l == "a1e":
            ev = rep.get("evaluator")
            if not ev:
                f_gates["F5"] = f"{chunk.name}: no evaluator provenance in chunk JSON"
            else:
                ok = (
                    ev.get("kind") == "loo"
                    and len(ev.get("members", [])) == 3
                    and lane not in ev.get("members", [])
                    and ev.get("member_sha256") == [pins[m] for m in ev.get("members", [])]
                )
                if not ok:
                    f_gates["F5"] = f"{chunk.name}: membership evidence bad: {ev}"

    def final(job: str) -> dict:
        p = rdir / f"{job}.final.json"
        assert p.exists(), f"missing {p} — job incomplete"
        return json.loads(p.read_text())

    a0 = {l: final(f"a0_{l}") for l in lanes}
    a1s = {l: final(f"a1s_{l}") for l in lanes}
    a1e = {l: final(f"a1e_{l}") for l in lanes}
    for arm_finals in (a0, a1s, a1e):
        for l in lanes:
            desyncs[arm_finals[l]["job"]] = arm_finals[l].get("mask_desyncs", 0)
    p0 = [a1s[l]["eval/win_rate"] for l in lanes]
    p1 = [a1e[l]["eval/win_rate"] for l in lanes]
    d = [x - y for x, y in zip(p1, p0)]
    delta = sum(d) / len(d)
    a0_pooled = sum(a0[l]["eval/win_rate"] for l in lanes) / len(lanes)
    a1s_pooled = sum(p0) / len(p0)
    a1e_pooled = sum(p1) / len(p1)

    # ---- F3 (VOID): search searched, BOTH search arms ----
    exp_leaves = float(prereg["f3_leaves_expected"])
    band = float(prereg["f3_band"])
    for tag, finals in (("a1s", a1s), ("a1e", a1e)):
        for l in lanes:
            lm = finals[l].get("search/leaves_mean")
            if lm is None or abs(lm - exp_leaves) / exp_leaves > band:
                f_gates["F3"] = f"{tag}_{l}: leaves_mean {lm} vs {exp_leaves}"

    # ---- F1/F2 transcripts recorded ----
    if "<filled" in str(prereg.get("r4_1_fg_transcript", "<filled")):
        f_gates.setdefault("F1", "r4_1_fg_transcript not recorded at launch sha")

    # ---- F4 ERA (disclosure / STOP-should-have-happened; never VOID) ----
    g_lo, g_hi = prereg["f4_era_green_band"]
    s_lo, s_hi = prereg["f4_era_stop_band"]
    if g_lo <= a0_pooled <= g_hi:
        f4 = "green"
    elif s_lo <= a0_pooled <= s_hi:
        f4 = f"DISCLOSED: A0 pooled {a0_pooled:.5f} outside green [{g_lo}, {g_hi}]"
    else:
        f4 = (
            f"STOP-SHOULD-HAVE-FIRED: A0 pooled {a0_pooled:.5f} outside "
            f"[{s_lo}, {s_hi}] — if any search battle ran, the readout is VOID"
        )
        f_gates["F4-STOP"] = f4

    # ---- F10 A1S tripwire (disclose 0.020 / VOID 0.040) ----
    t = prereg["f10_a1s_tripwire"]
    off = a1s_pooled - float(t["anchor"])
    if abs(off) > float(t["void"]):
        f_gates["F10"] = f"A1S offset {off:+.5f} > {t['void']} — VOID, diagnose"
        f10 = "VOID"
    elif abs(off) > float(t["disclose"]):
        f10 = f"DISCLOSED: A1S offset {off:+.5f} (B1a unclaimable)"
    else:
        f10 = "green"

    # ---- F7 leaf match (NON-VOIDING) ----
    f7_band = float(prereg["f7_leaf_match_band"])
    f7_fired_lanes = []
    f7_table = {}
    for l in lanes:
        ls, le = a1s[l].get("search/leaves_mean"), a1e[l].get("search/leaves_mean")
        rel = abs(le - ls) / ls if ls else None
        f7_table[l] = {"a1s": ls, "a1e": le, "rel_diff": rel}
        if rel is None or rel > f7_band:
            f7_fired_lanes.append(l)

    # ---- F11 pairing window (NON-VOIDING) ----
    f11 = {}
    min_ov = float(prereg["f11_pairing_window"]["min_overlap_frac"])
    for l in lanes:
        if l in spans["a1s"] and l in spans["a1e"]:
            ov = _span_overlap(spans["a1s"][l], spans["a1e"][l])
            f11[l] = {"overlap_frac": round(ov, 4), "paired": ov >= min_ov}
        else:
            f11[l] = {"overlap_frac": None, "paired": False}
    f11_unpaired = [l for l in lanes if not f11[l]["paired"]]

    terms = se_terms_r2(p1, p0, n)
    hi = max(FLOOR, 2 * terms["se_gov"])
    check_partition(hi)
    cell = land(delta, hi)
    kill = delta <= 0 and sum(1 for x in d if x <= 0) >= 3

    b1_sub = None
    if cell == "B1":
        b1a = a1e_pooled > float(t["anchor"]) and abs(off) <= float(t["disclose"])
        b1_sub = "B1a" if b1a else "B1b"

    voiding = {k: v for k, v in f_gates.items()}
    out = {
        "prereg": prereg_path,
        "prereg_sha256": hashlib.sha256(Path(prereg_path).read_bytes()).hexdigest(),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "lane_rates_A0": {l: a0[l]["eval/win_rate"] for l in lanes},
        "lane_rates_A1S": dict(zip(lanes, p0)),
        "lane_rates_A1E": dict(zip(lanes, p1)),
        "per_lane_deltas": dict(zip(lanes, d)),
        "delta_equal_weight_mean": delta,
        **terms,
        "operative_bar_hi": hi,
        "cell_IF_NO_F_GATE_FIRES": cell,
        "b1_sub_cell": b1_sub,
        "f_gates_fired": voiding,
        "VOID": bool(voiding),
        "kill_rule_fired": kill,
        "kill_note": (
            "closure sentence is the ONLY licensed narration (B3 'axis not "
            "dead' clause suppressed)" if kill else None
        ),
        "f4_era": f4,
        "a0_pooled": a0_pooled,
        "f10_tripwire": f10,
        "a1s_pooled_fresh": a1s_pooled,
        "a1e_pooled": a1e_pooled,
        "f7_leaf_match": {"fired_lanes": f7_fired_lanes, "table": f7_table},
        "f7_consequence_applies": bool(f7_fired_lanes),
        "f11_pairing": f11,
        "f11_unpaired_lanes": f11_unpaired,
        "f9_mask_desyncs": desyncs,
        "B2_B4_empty": hi <= FLOOR + 1e-12,
        "b2_b4_empty_expected": prereg["b2_b4_empty_expected"],
        "recorded_only": {
            "per_lane_median_delta": statistics.median(d),
            "worst_lane_delta": min(d),
            "composed_delta_a1e_minus_a0": a1e_pooled - a0_pooled,
            "search_flip_rate": {
                f"{tag}_{l}": f[l].get("search/flip_rate")
                for tag, f in (("a1s", a1s), ("a1e", a1e)) for l in lanes
            },
            "placeholder_skip_rate": {
                f"{tag}_{l}": f[l].get("search/placeholder_skip_rate")
                for tag, f in (("a1s", a1s), ("a1e", a1e)) for l in lanes
            },
            "ms_mean": {
                f"{tag}_{l}": f[l].get("search/ms_mean")
                for tag, f in (("a1s", a1s), ("a1e", a1e)) for l in lanes
            },
        },
        "anchors_run_iff": prereg["anchors_run_iff"],
    }
    print(json.dumps(out, indent=2))
    if voiding:
        print(f"\nVOID — F-gates fired: {voiding}; no band is adjudicated.")
    else:
        label = b1_sub or cell
        print(
            f"\nVERDICT CELL: {label} | delta {delta:+.5f} | bar {hi:.5f} | "
            f"governing se: {terms['governing']} ({terms['se_gov']:.5f})"
            + (" | KILL: evaluator line CLOSED within the chapter" if kill else "")
        )
        print(
            f"B2_B4_empty at read time: {out['B2_B4_empty']} (pre-reg stance: "
            f"the cells were NOT pre-named empty — b2_b4_empty_expected="
            f"{prereg['b2_b4_empty_expected']}; reported per review finding 24)"
        )
        if label in ("B1a", "B1b", "B2"):
            print("ANCHOR BATTERY OWED (anchors_run_iff satisfied): run "
                  "scripts/ch3_r4_anchors.py + the FP anchor, then "
                  "ch3_r4_anchor_grade.py --delta-sh " f"{delta:.5f}")
    (rdir / "r4_readout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def selftest() -> None:
    """Pins: the five boundary landings from the pre-reg header, the B1a/B1b
    split, F5 evidence checks, F11 overlap arithmetic, and the mu=0 size
    components P(B1) AND P(B2) by simulation (20k replicates)."""
    import numpy as np

    # boundary landings (pre-reg BAND BOUNDARIES; review 1 blocker 2)
    assert land(0.025, 0.025) == "B1"
    assert land(0.025, 0.030) == "B2"
    assert land(-0.025, 0.030) == "B4"
    assert land(-0.025, 0.025) == "B5"      # the expected-case landing
    assert land(-0.030, 0.030) == "B5"
    check_partition(0.025)
    check_partition(0.031)
    # B1a/B1b split logic
    anchor, disclose = 0.79283, 0.020
    for a1e_p, off, want in [(0.80, 0.005, "B1a"), (0.79, 0.005, "B1b"),
                             (0.82, 0.030, "B1b"), (0.80, -0.025, "B1b")]:
        b1a = a1e_p > anchor and abs(off) <= disclose
        assert ("B1a" if b1a else "B1b") == want, (a1e_p, off)
    # F11 overlap
    assert _span_overlap((0, 100), (0, 100)) == 1.0
    assert _span_overlap((0, 100), (90, 190)) == 0.1
    assert _span_overlap((0, 100), (200, 300)) == 0.0
    # F5 evidence shape
    pins = {"s62": "a", "s63": "b", "s64": "c", "s65": "d"}
    ev = {"kind": "loo", "members": ["s62", "s63", "s64"],
          "member_sha256": ["a", "b", "c"]}
    assert (ev["kind"] == "loo" and len(ev["members"]) == 3
            and "s65" not in ev["members"]
            and ev["member_sha256"] == [pins[m] for m in ev["members"]])
    bad = dict(ev, members=["s65", "s63", "s64"])
    assert "s65" in bad["members"]  # the self-inclusion case the gate kills
    # size components at mu=0 (20k replicates, tau=0.025 worst case)
    rng = np.random.default_rng(20260823)
    base = np.array([0.78200, 0.79300, 0.80400, 0.79233])
    n, reps, tau = 3000, 20000, 0.025
    b1 = b2 = 0
    for _ in range(reps):
        di = rng.normal(0.0, tau, 4)
        p0s = np.clip(base, 0.01, 0.99)
        p1s = np.clip(base + di, 0.01, 0.99)
        o0 = rng.binomial(n, p0s) / n
        o1 = rng.binomial(n, p1s) / n
        t = se_terms_r2(list(o1), list(o0), n)
        hi = max(FLOOR, 2 * t["se_gov"])
        cell = land(float(np.mean(o1 - o0)), hi)
        b1 += cell == "B1"
        b2 += cell == "B2"
    print(f"size components at mu=0, tau={tau}: P(B1)={b1/reps:.4f} "
          f"P(B2)={b2/reps:.4f} (pre-reg discloses P(B1) <= 0.016)")
    assert b1 / reps <= 0.02, "size regression vs the pre-registered bound"
    print("ch3_r4_grade selftest: ALL GREEN")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    assert args.prereg, "--prereg or --selftest"
    grade(args.prereg)


if __name__ == "__main__":
    main()
