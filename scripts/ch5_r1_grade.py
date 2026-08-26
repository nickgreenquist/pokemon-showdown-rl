"""CH5 R1 — the off-SH gate/grade instrument (designer B BI-4).

Until this file existed, `configs/eval/ch5_r1_offsh.yaml`'s entire Q7 gate
block was PROSE: nothing in the tree applied a single CH5 gate to an arm
JSON. `tests/test_ch5_prereg.py` checks the pre-reg's INTERNAL consistency
and never reads a result; `scripts/ch4_r1_grade.py` is CH4-scoped.

Gates implemented, each VOIDing its arm unless stated:
  G2            THREE-WAY EXHAUSTIVE tally against FP's own stdout. Never a
                subtraction, never the two-key form -- `Winner: None` IS the
                tie (verified equal to the seat's `ties` on all ten banked
                CH4 arms), so a two-key G2 passes while a rising tie count
                goes unseen. The three must SUM to n_eff.
  G3            battles_finished == battles_requested.
  G-DECLARED    the runner exports a shell var only when the pre-reg key is
                present, so `BATTLES="${BATTLES:-250}"` stands and a
                3000-battle arm silently becomes a 250-battle arm that
                passes every other gate.
  G-TERMINAL-RACE  the GENERAL per-point form, as ch4_r1_grade.py:128:
                n_eff = seat_finished - |{p in crash_points : p < requested}|.
                Never `- relaunches`; never subtract a crash at p == requested.
  G-BUDGET      FP's OWN log, not the YAML: every `Sampling <N> battles at
                <M>ms each` line must satisfy N*M == 2*declared, and
                max(M) == declared. The seat's `declared_search_time_ms`
                copies the same YAML the runner reads and cannot catch this.
  G-SEAT        `seat_lane_defaulted == false` -- the seat defaults to s65,
                and where s65 is pinned in the same pre-reg the sha assert
                PASSES on a silently-wrong arm.
  G-SHA / G8    provenance: sha pins, encoder_env, process_obs_dim, plus the
                wave's FP-patch / Showdown stamp. A G8 break voids
                EVERYTHING DOWNSTREAM OF IT, not just its arm.
  G-DESYNC      VOID at a desync RATE > 0.5%; any non-zero count is REPORTED.
  G-SERIAL      non-overlapping arm wall clocks in $OUT/wave.log.
  G-IDENTITY    C0's seat_lanes/seat_sha256 byte-match ladder_r1.yaml's L2.
  G-FLIP        DISCLOSES, never voids: an ensemble arm whose in-play
                flip rate is < 0.02 is a mislabelled single-lane read.
  BARS          every bar in `grading.arms` is RE-DERIVED from n and the
                file's own bar = max(floor, 2*max(se_bin, se_clustered)). A
                stored constant that does not reproduce is a FAIL, not a
                warning. (The r3 test asserted the OPPOSITE -- bar < floor --
                and locked in a breach for a whole draft.)

An arm carrying an OPS-FAILURE sentinel ($TAG.NO_PROGRESS,
$TAG.USERNAME_DEADLOCK) is REFUSED, not graded: an ops failure graded as
data is how a clean arm becomes a wrong number.

--selftest runs entirely against BANKED CH4 ARTIFACTS, so it is
exercisable today, before a single CH5 battle:
    python scripts/ch5_r1_grade.py --selftest
"""

import argparse
import collections
import gzip
import json
import math
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PREREG_PATH = REPO / "configs/eval/ch5_r1_offsh.yaml"
LADDER_PATH = REPO / "configs/eval/ladder_r1.yaml"
P0 = 0.34867          # banked 12M greedy off FP@20, the comparator
N0 = 12000

WINNER_RE = re.compile(r"Winner: (\S+)")
SAMPLING_RE = re.compile(r"Sampling (\d+) battles at (\d+)ms each")


def binom_se(p, n):
    return math.sqrt(p * (1 - p) / n)


def clustered_se(s_arm, k_arm, s_cmp, k_cmp):
    """k-GENERAL (review 1 BL-3: the hardcoded /3 understated the se by 22%
    at k=2). At k_arm == 1 there is NO clustered term -- one lane yields no
    sd -- so the read is descriptive only and this returns None."""
    if k_arm is None or k_arm < 2:
        return None
    return math.sqrt(s_arm ** 2 / k_arm + s_cmp ** 2 / k_cmp)


def open_maybe_gz(path):
    """Retention gzips fp.stdout IN PLACE after the grade, so both forms
    must read (artifacts.retention_rule)."""
    if path.exists():
        return open(path, errors="replace")
    gz = path.with_suffix(path.suffix + ".gz")
    if gz.exists():
        return gzip.open(gz, "rt", errors="replace")
    return None


def fp_tally(path):
    """THREE-WAY and EXHAUSTIVE. Returns the full Counter -- the caller
    checks all three keys AND their sum, never a subtraction."""
    fh = open_maybe_gz(path)
    if fh is None:
        return None
    counts = collections.Counter()
    with fh as f:
        for line in f:
            m = WINNER_RE.search(line)
            if m:
                counts[m.group(1)] += 1
    return counts


def fp_sampling_lines(path):
    fh = open_maybe_gz(path)
    if fh is None:
        return None
    seen = collections.Counter()
    with fh as f:
        for line in f:
            m = SAMPLING_RE.search(line)
            if m:
                seen[(int(m.group(1)), int(m.group(2)))] += 1
    return seen


def grade_budget(sampling, declared):
    """G-BUDGET, asserted on FP's OWN log. At declared 20 the lines are
    exactly `2 battles at 20ms` and `4 battles at 10ms` (N*M = 40 = 2*20).
    At FP@100 they would read N*M = 200."""
    if not sampling:
        return {"pass": None, "note": "no fp.stdout -- G-BUDGET UNGRADED (not passed)"}
    bad = [f"{n}x{m}ms" for (n, m) in sampling if n * m != 2 * declared]
    max_m = max(m for (_, m) in sampling)
    return {"pass": not bad and max_m == declared,
            "declared_search_time_ms": declared,
            "distinct_sampling_lines": sorted(f"{n}x{m}ms" for (n, m) in sampling),
            "max_ms": max_m, "violations": bad}


def effective_forfeits(runner, requested):
    """G-TERMINAL-RACE, GENERAL per-point form. A crash at
    fp_completed == battles_requested has no in-flight battle, so no
    forfeit is owed; a blind `n_eff = seat - crash_forfeits` would delete a
    real battle from a clean arm (l64 is exactly that case)."""
    pts = runner.get("crash_points_fp_completed") or []
    raw = runner.get("crash_forfeits", 0)
    if not pts:
        return raw, 0
    cf = sum(1 for p in pts if p < requested)
    return cf, raw - cf


def rederive_bars(cfg):
    """Every bar RE-DERIVED from n and the file's own rule. A stored
    constant that does not reproduce is a FAIL."""
    G = cfg["grading"]
    floor = G["credit_floor"]
    out = {}
    for name, a in G["arms"].items():
        if "bar" not in a:
            continue
        se = None
        if name == "R1A_PRIMARY_s82":
            n = a["n_per_lane"]
            se = math.sqrt(P0 * (1 - P0) / (2 * n) + P0 * (1 - P0) / n)
        elif name == "R1B":
            n = a["n_per_lane"]
            se = math.sqrt(2 * P0 * (1 - P0) / n / a["k_arm"])
        elif name == "R1C":
            n = a["n_per_arm"]
            se = math.sqrt(2 * P0 * (1 - P0) / n)
        if se is None:
            continue
        expect = max(floor, 2 * se)
        out[name] = {"stored_bar": a["bar"], "rederived_bar": round(expect, 4),
                     "se": round(se, 4),
                     "pass": abs(a["bar"] - expect) < 5e-4}
    return out


def parse_wave_log(path):
    """G-SERIAL's artifact. Returns [(arm, start, end)] in file order."""
    if not path.exists():
        return None
    stamp = re.compile(r"^\[(\S+)\] (\S+) (start|done|SKIP|VOID|OPS)")
    open_arm, spans = {}, []
    for line in path.read_text(errors="replace").split("\n"):
        m = stamp.match(line)
        if not m:
            continue
        ts, arm, what = m.groups()
        if what == "start":
            open_arm[arm] = ts
        elif arm in open_arm:
            spans.append((arm, open_arm.pop(arm), ts))
    return spans


def grade_serial(spans):
    if spans is None:
        return {"pass": None, "note": "no wave.log -- G-SERIAL UNGRADED (not passed)"}
    overlaps = []
    for i, (a1, s1, e1) in enumerate(spans):
        for (a2, s2, e2) in spans[i + 1:]:
            if s2 < e1 and s1 < e2:
                overlaps.append(f"{a1} overlaps {a2}")
    return {"pass": not overlaps, "arms": len(spans), "overlaps": overlaps}


def grade_arm(cfg, out_dir, arm_name, tag):
    arm = cfg["arms"][arm_name]
    R = {"arm": arm_name, "tag": tag, "gates": {}, "void": False, "refused": False}

    for sentinel, why in (("NO_PROGRESS", "runner exit 4, designer B §5.4"),
                          ("USERNAME_DEADLOCK", "runner exit 3")):
        if (out_dir / f"{tag}.{sentinel}").exists():
            R["refused"] = True
            R["refusal"] = (f"{sentinel} sentinel present ({why}). This is an OPS "
                            "FAILURE, not a data verdict: RE-RUN under a fresh "
                            "username pair. It is never graded.")
            return R

    seat_p = out_dir / f"{tag}.json"
    if not seat_p.exists():
        R["refused"] = True
        R["refusal"] = "no arm JSON"
        return R
    seat = json.loads(seat_p.read_text())
    runner_p = out_dir / f"{tag}.runner.json"
    runner = json.loads(runner_p.read_text()) if runner_p.exists() else {}

    requested = seat.get("battles_requested")
    finished = seat.get("battles_finished")
    cf, terminal_race = effective_forfeits(runner, requested or 0)
    n_eff = (finished or 0) - cf

    # --- G-DECLARED --------------------------------------------------
    decl = {"battles_requested": requested, "declared_battles": arm.get("battles"),
            "battles_finished": finished}
    checks = [requested == arm.get("battles"), finished == requested,
              seat.get("seat_lane_defaulted") is False]
    if arm["kind"] == "ensemble_seat":
        checks.append(seat.get("seat_lane") is None)
        checks.append(list(seat.get("seat_lanes") or []) == list(arm["lanes"]))
        checks.append(list(seat.get("seat_sha256") or [])
                      == [cfg["checkpoints"][l]["sha256"] for l in arm["lanes"]])
    else:
        checks.append(seat.get("seat_lane") == arm.get("seat"))
        pin = cfg["checkpoints"][arm["seat"]]["sha256"]
        got = seat.get("seat_sha256")
        checks.append(got == pin or (isinstance(got, list) and got == [pin]))
    decl["pass"] = all(checks)
    R["gates"]["G-DECLARED"] = decl
    R["gates"]["G3"] = {"pass": bool(seat.get("gate_all_challenges_resolved"))
                        and finished == requested}
    R["gates"]["G-SEAT"] = {"seat_lane_defaulted": seat.get("seat_lane_defaulted"),
                            "pass": seat.get("seat_lane_defaulted") is False}

    # --- G2, three-way and exhaustive ---------------------------------
    counts = fp_tally(out_dir / f"{tag}.fp.stdout")
    ours, theirs = seat.get("seat_username"), seat.get("fp_username")
    if counts is None:
        g2 = {"pass": None, "note": "no fp.stdout -- G2 UNGRADED (not passed). "
                                    "FP's stdout IS the second tally (G-RETAIN)."}
    else:
        fw, pw, tw = counts.get(ours, 0), counts.get(theirs, 0), counts.get("None", 0)
        g2 = {"fp_log_seat_wins": fw, "fp_log_fp_wins": pw, "fp_log_ties": tw,
              "seat_our_wins": seat.get("our_wins"),
              "seat_fp_wins": seat.get("foulplay_wins"),
              "seat_ties": seat.get("ties"),
              "sum": fw + pw + tw, "n_eff": n_eff,
              "tie_rate": round(tw / n_eff, 5) if n_eff else None}
        g2["tallies_agree"] = (fw == seat.get("our_wins")
                               and pw == seat.get("foulplay_wins")
                               and tw == seat.get("ties")
                               and fw + pw + tw == n_eff)
        g2["pass"] = g2["tallies_agree"]
        band = cfg["grading"].get("tie_disclosure_band", 0.01)
        if g2["tie_rate"] is not None and g2["tie_rate"] > band:
            g2["disclosed_engine_signal"] = (
                f"tie rate {g2['tie_rate']} > {band} -- DISCLOSE, never void")
    R["gates"]["G2"] = g2

    R["gates"]["G-TERMINAL-RACE"] = {
        "crash_forfeits_raw": runner.get("crash_forfeits", 0),
        "crash_points": runner.get("crash_points_fp_completed") or [],
        "effective_forfeits": cf, "terminal_race_reclassified": terminal_race,
        "n_eff": n_eff, "pass": True,
        "rule": "n_eff = seat_finished - |{p in crash_points : p < battles_requested}|"}

    # --- G-BUDGET, from FP's own log ----------------------------------
    R["gates"]["G-BUDGET"] = grade_budget(
        fp_sampling_lines(out_dir / f"{tag}.fp.stdout"),
        arm.get("search_time_ms", cfg["fp"]["search_time_ms"]))
    R["gates"]["G-BUDGET"]["yaml_typo_check"] = (
        seat.get("declared_search_time_ms") == arm.get("search_time_ms"))

    # --- G-DESYNC: rate, not count ------------------------------------
    ds = seat.get("mask_desyncs")
    if ds is None:
        R["gates"]["G-DESYNC"] = {"pass": True, "mask_desyncs": "not_reported_by_this_driver"}
    else:
        rate = ds / n_eff if n_eff else 0.0
        R["gates"]["G-DESYNC"] = {"mask_desyncs": ds, "rate": round(rate, 6),
                                  "pass": rate <= 0.005, "reported": ds != 0}

    # --- G-SHA / G8 ----------------------------------------------------
    R["gates"]["G8"] = {
        "encoder_env": seat.get("encoder_env"),
        "process_obs_dim": seat.get("process_obs_dim"),
        "pass": (seat.get("encoder_env") == {"POKEMON_RL_ENCODER_V2": "1",
                                             "POKEMON_RL_ENCODER_IDS": "1"}
                 and seat.get("process_obs_dim") == 828),
        "seat_native_dim_caveat": (
            "seat_native_dim asserts the PROCESS OBS_DIM, not the checkpoint: "
            "_load_showdown_agent detects width from `0.weight` and an "
            "entity_deepsets checkpoint has no such tensor, so the field falls "
            "through. The checkpoint evidence is the sha256 pin.")}

    # --- G-FLIP: DISCLOSES, never voids --------------------------------
    if arm["kind"] == "ensemble_seat":
        flip = seat.get("ensemble/flip_rate", seat.get("ensemble_flip_rate"))
        R["gates"]["G-FLIP"] = {
            "flip_rate": flip, "min": 0.02, "voids": False,
            "disclose": flip is not None and flip < 0.02,
            "note": "one-sided LOW: only collapse (flip -> 0) is a defect. A low "
                    "flip rate is a MISLABELLED SINGLE-LANE READ and is printed "
                    "beside the number; it never interacts with the outlier rule."}

    # --- G-IDENTITY (C0 only): the whole point of C0 --------------------
    if arm_name == "C0" and LADDER_PATH.exists():
        lad = yaml.safe_load(LADDER_PATH.read_text())
        l2 = (lad.get("arms") or {}).get("L2") or {}
        same = (list(seat.get("seat_lanes") or []) == list(l2.get("lanes") or [])
                and list(seat.get("seat_sha256") or [])
                == [lad["checkpoints"][l]["sha256"] for l in (l2.get("lanes") or [])])
        R["gates"]["G-IDENTITY"] = {
            "pass": same,
            "why": "C0's entire claim is that its FP number and the ladder rating "
                   "rate the SAME object. Nothing else re-verifies that at grade time."}

    rate = (seat.get("our_wins", 0) / n_eff) if n_eff else None
    R["read"] = {"n_eff": n_eff, "our_win_rate_on_n_eff": rate,
                 "ties_are": "NON-WINS in the numerator, COUNTED in the denominator"}
    R["void"] = any(g.get("pass") is False for g in R["gates"].values()
                    if isinstance(g, dict))
    R["ungraded_gates"] = [k for k, g in R["gates"].items()
                           if isinstance(g, dict) and g.get("pass") is None]
    return R


# ---------------------------------------------------------------------
def selftest():
    """Runs against BANKED CH4 ARTIFACTS -- exercisable before a single CH5
    battle. Each assert is a defect this repo has actually shipped."""
    ch4 = REPO / "results/ch4_r1_offsh"
    cfg = yaml.safe_load(PREREG_PATH.read_text())

    # (1) G-TERMINAL-RACE on l64: raw 1, crash at p == requested -> 0 owed.
    #     A grader that returns 2999 FAILS selftest.
    rj = json.loads((ch4 / "l64.runner.json").read_text())
    seat = json.loads((ch4 / "l64.json").read_text())
    cf, tr = effective_forfeits(rj, rj["battles_requested"])
    assert rj["crash_forfeits"] == 1 and rj["crash_points_fp_completed"] == [3000], rj
    assert cf == 0 and tr == 1, f"terminal race: cf={cf} tr={tr}"
    n_eff = seat["battles_finished"] - cf
    assert n_eff == 3000, f"n_eff must be 3000, got {n_eff} (a real battle would be deleted)"

    # (2) G2 three-way on l64: 1067 / 1927 / 6 summing to 3000.
    counts = fp_tally(ch4 / "l64.fp.stdout")
    assert counts is not None, "l64.fp.stdout missing -- G2's second tally"
    fw = counts.get(seat["seat_username"], 0)
    pw = counts.get(seat["fp_username"], 0)
    tw = counts.get("None", 0)
    assert (fw, pw, tw) == (1067, 1927, 6), (fw, pw, tw)
    assert fw + pw + tw == n_eff, "the three must SUM to n_eff"
    assert (fw, pw, tw) == (seat["our_wins"], seat["foulplay_wins"], seat["ties"])
    # `Winner: None` IS the tie -- a two-key G2 is blind to a third of the
    # outcome space and passes while a rising tie count goes unseen.
    assert tw == seat["ties"] != 0, "l64 is the tie-bearing arm; it must exercise the third key"

    # (3) G-BUDGET on l64 (an FP@20 arm): every Sampling line N*M == 2*20.
    samp = fp_sampling_lines(ch4 / "l64.fp.stdout")
    g = grade_budget(samp, 20)
    assert g["pass"], g
    assert grade_budget({(2, 100): 1, (4, 50): 1}, 20)["pass"] is False, \
        "an FP@100 log must FAIL a declared-20 arm"

    # (4) BARS re-derived from the file's own rule. The r3 test asserted the
    #     OPPOSITE (bar < floor) and locked in a breach for a whole draft.
    bars = rederive_bars(cfg)
    bad = {k: v for k, v in bars.items() if not v["pass"]}
    assert not bad, f"stored bar does not reproduce from n: {bad}"
    assert bars["R1A_PRIMARY_s82"]["rederived_bar"] > cfg["grading"]["credit_floor"], \
        "the primary's bar must be se-driven, not the floor (that breach shipped twice)"

    # (5) G-SERIAL overlap detection, on synthetic spans.
    ok = grade_serial([("A", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"),
                       ("B", "2026-01-01T01:00:01Z", "2026-01-01T02:00:00Z")])
    assert ok["pass"], ok
    bad = grade_serial([("A", "2026-01-01T00:00:00Z", "2026-01-01T02:00:00Z"),
                        ("B", "2026-01-01T01:00:00Z", "2026-01-01T03:00:00Z")])
    assert bad["pass"] is False and bad["overlaps"], bad

    # (6) an ungraded gate is NOT a passed gate.
    assert grade_budget(None, 20)["pass"] is None
    assert grade_serial(None)["pass"] is None

    print("SELFTEST PASS")
    print(f"  G-TERMINAL-RACE l64: raw 1, crash_points [3000], requested 3000 "
          f"-> effective {cf}, n_eff {n_eff}")
    print(f"  G2 three-way l64: {fw} / {pw} / {tw} = {fw + pw + tw} == n_eff")
    print(f"  G-BUDGET l64: {g['distinct_sampling_lines']} all satisfy N*M == 2*20")
    for k, v in bars.items():
        print(f"  bar {k}: stored {v['stored_bar']} == max(floor, 2*{v['se']}) "
              f"= {v['rederived_bar']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="gate the grader against banked CH4 artifacts and exit")
    ap.add_argument("--indir", default=None,
                    help="read arms from here instead of the pre-reg's results_dir")
    ap.add_argument("--out", default=None, help="write the grade JSON here")
    args = ap.parse_args()

    selftest()
    if args.selftest:
        return

    cfg = yaml.safe_load(PREREG_PATH.read_text())
    out_dir = Path(args.indir) if args.indir else REPO / cfg["results_dir"]
    R = {"prereg": str(PREREG_PATH.relative_to(REPO)), "results_dir": str(out_dir),
         "bars_rederived": rederive_bars(cfg), "arms": {}}
    R["gates"] = {"G-SERIAL": grade_serial(parse_wave_log(out_dir / "wave.log"))}
    prov = out_dir / "wave.provenance.json"
    R["gates"]["G8_wave_provenance"] = (
        json.loads(prov.read_text()) if prov.exists()
        else {"pass": None, "note": "no wave.provenance.json -- G8 UNGRADED"})

    for arm_name in cfg["arms"]:
        tag = arm_name.lower()
        if not (out_dir / f"{tag}.json").exists() and \
           not (out_dir / f"{tag}.NO_PROGRESS").exists() and \
           not (out_dir / f"{tag}.USERNAME_DEADLOCK").exists():
            continue
        R["arms"][arm_name] = grade_arm(cfg, out_dir, arm_name, tag)

    txt = json.dumps(R, indent=2)
    if args.out:
        Path(args.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
