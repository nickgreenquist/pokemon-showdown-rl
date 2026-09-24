#!/usr/bin/env python
"""R7 FLEET CONFIG DERIVATION -- the lane configs of the ruled design, derived, never hand-edited.

The rulings (plan AMENDMENT BOX 6; maintainer, 2026-09-24 00:20Z): the fleet starts WARM from the base
trio's three R6 finals, PAIRED BY FINAL (final f seeds searched lane f and control lane f), +100M on a
re-armed anneal from a reduced starting LR; 3 + 3 lanes if the B0 bench passes six-wide, else 3 + 2. Each
lane warm-starts from a DIFFERENT checkpoint and `rl.train` takes one `init_from` per config, so every lane
gets its own config, all carrying the SAME pre-registration header (CLAUDE.md: the pre-reg lives in the
config header). Nothing is added to `rl.train` or `Config` (a new field would make every existing run dir
un-resumable), and a watchdog resume uses the lane's own config as for any lane.

THE BASE is R6's trios by THEIR OWN pre-stated branches on the 09-25 read (trio A's header, ACTION ON EACH
BRANCH), one of four:
  a    trio A's body (the W recipe + C6 + the outcome heads)        -> donors: trio A's finals
  b    trio B's FALLBACK body (the W recipe + C6 + the x4 batch)    -> donors: trio B's finals
  ab   trio A's body + trio B's three batch keys                     -> donors: trio A's finals
  w    trio B's body with the W recipe's batch keys (neither lever) -> donors: trio B's finals
An outcome head cannot be added to a head-off checkpoint (refused at load), so any base that keeps the
heads warm-starts from trio A's finals.

TWO STAGES (Friday, the idle box):
  --stage lr-smokes   three 2M warm-start smokes of the SEARCHED arm from lane 1's donor at the candidate
                      LRs {2.5e-4, 1.0e-4, 5.0e-5}; `--read-lr` then applies the pre-stated rule: the
                      LARGEST LR whose smoke keeps every per-update approx_kl <= 0.06 and its last-bin mean
                      entropy within +-20% of the donor's last-bin mean entropy.
  --stage fleet       the six lane configs (five under --b0 FAIL) and the two 400k warm-start shakedown
                      smokes (searched + control, lane 1's donor), at the chosen --lr.
Writes into --out (default configs/); prints the launch lines.
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import glob
import hashlib
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIO_A = "configs/showdown_r6_trio_a.yaml"
TRIO_B = "configs/showdown_r6_trio_b_fallback.yaml"
DONOR_SEEDS = {"a": (304, 312, 320), "b": (328, 336, 344)}
DONOR_DIR = {"a": "showdown_r6_trio_a_s{}", "b": "showdown_r6_trio_b_s{}"}
SEEDS = {"searched": (376, 384, 392), "control": (400, 408, 416)}
SMOKE_SEEDS = {"searched": 424, "control": 432}
LR_SMOKE = {2.5e-4: 440, 1.0e-4: 444, 5.0e-5: 448}
TAGS = {"searched": "r7fs", "control": "r7fc", "smoke_searched": "r7ws", "smoke_control": "r7wc", "lr": "r7lr"}
HORIZON = 100_000_000
B_BATCH = {"agent.rollout_steps": 15360, "agent.minibatches": 480, "selfplay.push_every_updates": 1}
W_BATCH = {"agent.rollout_steps": 3840, "agent.minibatches": 120, "selfplay.push_every_updates": 5}
HEAD_KEYS = ("collector.outcome_targets", "agent.aux_outcome_coef", "agent.trunk_kwargs.value_aux_out")
SEARCH = {"frac": 0.75, "top1_skip": 0.97, "cols_k": 4, "chance_s": 2, "tau": 0.05}
LEVER = {"searched": {"play": True, "search_policy_coef": 0.1, "search_value_coef": 0.1},
         "control": {"play": False, "search_policy_coef": 0.0, "search_value_coef": 0.0}}
BASE_LINE = {
    "a": "trio A's outcome heads (collector.outcome_targets / aux_outcome_coef 0.1 / value_aux_out 3) -- X-POS or X-FLAT-with-its-mechanism-moved on 09-25",
    "b": "trio B's x4 batch in its FALLBACK form (rollout 15360, minibatches 480, push every update) -- X-POS or X-FLAT-with-a-faster-update on 09-25",
    "ab": "BOTH R6 levers: trio A's outcome heads + trio B's fallback batch keys (warm from trio A's finals, which carry the heads)",
    "w": "NEITHER R6 lever (both read against keeping them on 09-25): the W recipe's batch keys, no heads (warm from trio B's finals, which carry no heads)",
}


def _set(d: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _del(d: dict, dotted: str) -> None:
    keys = dotted.split(".")
    for k in keys[:-1]:
        d = d.get(k, {})
    d.pop(keys[-1], None)


def base_body(base: str) -> dict:
    """The base's config body: the trio file whose levers it keeps, adjusted."""
    body = yaml.safe_load((ROOT / (TRIO_A if base in ("a", "ab") else TRIO_B)).read_text())
    if base == "ab":
        for k, v in B_BATCH.items():
            _set(body, k, v)
    if base == "w":
        for k, v in W_BATCH.items():
            _set(body, k, v)
    return body


def donor_trio(base: str) -> str:
    return "a" if base in ("a", "ab") else "b"


def donors(base: str, runs: pathlib.Path) -> list[dict]:
    """Each donor lane's FINAL checkpoint (the highest ckpt at or past 200M), its sha256, and its theta0."""
    out = []
    for s in DONOR_SEEDS[donor_trio(base)]:
        d = runs / DONOR_DIR[donor_trio(base)].format(s)
        finals = sorted(p for p in d.glob("ckpt_2000000*.pt"))
        if not finals:
            raise SystemExit(f"REFUSED: no final (ckpt_2000000*.pt) under {d} -- the donor lane has not finished")
        final = finals[-1]
        if not (d / "theta0.pt").exists():
            raise SystemExit(f"REFUSED: {d}/theta0.pt missing -- the warm start's L2 anchors are the donor's")
        out.append({"seed": s, "path": str(final.relative_to(runs.parent)) if final.is_relative_to(runs.parent) else str(final),
                    "sha256": hashlib.sha256(final.read_bytes()).hexdigest()})
    return out


def header(*, arm: str, lane: int | None, donor: dict, all_donors: list[dict], base: str, lr: float, lr_evidence: str,
           b0: str, kind: str) -> list[str]:
    today = dt.date.today().isoformat()
    donors_txt = "; ".join(f"f{i + 1} {d['path']} (sha {d['sha256'][:12]})" for i, d in enumerate(all_donors))
    lane_txt = f"LANE f{lane} of 3" if lane else kind
    return [
        f"# R7 FLEET -- EXPERT ITERATION ON THE STACKED BASE, WARM FROM R6, PAIRED BY FINAL. ARM: {arm.upper()}; {lane_txt}.",
        "# ENCODER_C6: on",
        f"# GENERATED by scripts/derive_r7_fleet.py on {today} (base {base}); never hand-edit -- re-derive. This lane warm-starts",
        f"#   from {donor['path']} (sha {donor['sha256'][:12]}).",
        "#",
        "# journey_step: \"14\" (R7; steps 8 and 10 folded in by the kitchen-sink ruling, 2026-09-23). Exit condition, verbatim:",
        "#   \"one comparison at a REAL budget, on the strongest gen-1 object we have. Search-with-our-evaluator vs the same",
        "#   checkpoint greedy, pooled under the standing credit line, with decisions/sec reported for both arms and the",
        "#   per-turn budget named in every quote.\" THIS FLEET IS NOT THAT COMPARISON (that is G2, ratified, run AFTER this",
        "#   fleet): it trains the objects G2 and the ladder will use, and credits ONE lever, expert iteration.",
        "#",
        "# THE LEVER (the searched arm; the plan's T-op, AMENDMENT BOXES 4-6): on ~40% of the learner's decisions (frac 0.75",
        "#   of eligible rows: > 1 legal action and pi_theta top-1 < 0.97) the collector runs native.solve on the TRUE world",
        "#   (B = 1; box 5 item 2's re-read licence) at k 4 / S 2 / tau 0.05 with the learner's OWN observation critic at the",
        "#   leaves (one view, box 5 item 5), PLAYS a' ~ pi' and records log pi'(a) (PPO's ratio carries the correction); the",
        "#   learner adds beta * KL(pi' || pi_theta) on searched rows (beta 0.1) and trains the v' aux head on the critic's",
        "#   context (coef 0.1; the GAE blend stays 0). THE CONTROL (box 5 item 6): the same two-core lane with the T-op at the",
        "#   same dose and cost, play false and both coefficients 0 -- the arms differ by the WHOLE lever at matched cost, lag",
        "#   and counters. beta 0.1 / coef 0.1 are the plan's defaults, UNMEASURED in magnitude (the smokes check they are not",
        "#   inert; G3 whether the student absorbs).",
        "#",
        "# THE BASE (every lane, UNCREDITED BY DESIGN): the W recipe + C6 + E2 (the scorer factorization, common-mode, 38f7736)",
        "#   + the mmap'd team bank + R6's trio lever(s) by THEIR OWN pre-stated branches on the 09-25 read:",
        f"#   {BASE_LINE[base]}.",
        "#   B2 (the antisymmetric privileged critic) is OUT (box 5 item 5): the T-op scores its leaves with the learner's critic.",
        "#",
        "# START (R-F1, ruled 2026-09-24): WARM + PAIRED BY FINAL -- lane f of each arm from the base trio's f-th final:",
        f"#   {donors_txt}.",
        f"#   +100M env steps on a RE-ARMED anneal (begin_warm_start) from lr {lr:g} ({lr_evidence}); the L2-toward-init",
        "#   anchors are the DONOR's theta0 (7014f11). DISCLOSED ON EVERY NUMBER: JOURNEY 10's convention (\"never a warm start",
        "#   off a finished checkpoint\") is SUSPENDED for this fleet -- its finals are 300M-trained objects on two anneals",
        "#   (N-ANNEAL); a comparison with R6's finals is confounded, the within-fleet comparison is not.",
        f"# WIDTH (R-F2, ruled): 3 searched + 3 control if the B0 bench passed six-wide, else 3 + 2 (lane f3's control dropped). B0: {b0}.",
        "#",
        "# R0 SANITY GATES (before launch, and per lane before it counts):",
        "#   (1) the 400k warm-start shakedown smokes (searched + control, lane f1's donor) PASS: every stacked lever's counter",
        "#       present and moving in history.csv (search/*, loss/search_policy, loss/search_value, search/kl_update,",
        "#       value/bias_mirror, collect/weights_lag_updates <= 1, collect/child_idle_frac, l2init/*, and the base's own",
        "#       aux_outcome/* when it keeps the heads); the log carries the THETA0 donor line; the control's search/override",
        "#       counters present with its behaviour unchanged (play false).",
        "#   (2) the 2M LR smokes set the starting LR by the rule in scripts/derive_r7_fleet.py (--read-lr): the LARGEST of",
        "#       {2.5e-4, 1.0e-4, 5.0e-5} whose smoke keeps every per-update approx_kl <= 0.06 and its last-bin mean entropy",
        "#       within +-20% of the donor's last-bin mean entropy.",
        "#   (3) the suite at the launch commit: tests/test_engine_bank_mmap.py PASSES (not skipped), tests/test_lop.py and",
        "#       tests/test_derive_r7_fleet.py pass; meta.yaml stamps engine.bank_zero_copy true, encoder.c6 true, a clean sha.",
        "#   (4) throughput inside the B0 bench's band at this width; a window that straddles startup is not a record.",
        "#   (5) every resume's from_step read from meta.yaml; RESUMES= / NODE_RESTARTS= disclosed; the /timer line travels.",
        "#",
        "# PRIMARY READ -- off FP@20 (search_time_ms 20 per arm), GREEDY, n = 3000 per lane, ONE session, SEQUENTIAL arms, fresh",
        "#   prefix-free usernames -- the configs/eval/r6_reads_offfp.yaml protocol. delta = the equal-weight mean of the three",
        "#   SEARCHED finals minus the equal-weight mean of the CONTROL finals (the across-lane aggregator), both read in the same",
        "#   session. se_diff is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff (k 3 vs 3; k 3 vs 2",
        "#   under the five-wide fallback), the latter from the per-lane finals at read time. CREDIT LINE, verbatim (CLAUDE.md):",
        "#   \"a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the pooled-binomial",
        "#   se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals at read time.\" Boundary: a",
        "#   delta EXACTLY +0.025 or EXACTLY 2*se_diff reads as NOT met. Both FP@20 disclosures travel with every number,",
        "#   forever: the equivalence test is weakly powered, and the point estimate flatters us; FP@20 is an instrument, not a",
        "#   rung. DOSE IS MATCHED BY CONSTRUCTION and CHECKED: the same donors, 100M env steps, horizon, anneal, starting LR, k,",
        "#   two-core lane and T-op dose; a searched/control pair's configs differ EXACTLY in {seed, run_name, seat_tag,",
        "#   collector.search.play, agent.search_policy_coef, agent.search_value_coef} (tests/test_derive_r7_fleet.py).",
        "#   THE PAIRED READ (secondary): the mean over finals f of (searched_f - control_f), each pair sharing its donor --",
        "#   reported beside the primary, never replacing it. POLICY FORM: greedy, loop breaker OFF on both arms (matched).",
        "# MECHANISM CO-PRIMARIES (G3's six conditions, amendment 3 item 3 / box 4 item 6), on the fleet's own checkpoints at",
        "#   12M and at the end, SEARCHED RELATIVE TO CONTROL, never a win rate: (i) search/kl_prior falling; (ii) search/override",
        "#   at the fixed gate falling; (iii) the leaf critic's per-position cell Spearman on HELD-OUT G0 positions rising",
        "#   (scripts/rollout_q_evaluator.py's statistic); (iv) search/value_gap falling; (v) value/bias_mirror ~ 0; (vi) THE",
        "#   COMPOUNDING READ: regret_depth1_ceiling(student greedy) on held-out positions falls faster on the searched arm.",
        "#   Rule 6: a 12M null on any of these is not a kill; the fleet runs.",
        "# SECONDARY: vs SH under the LOCKED protocol (final, 3000 battles/lane, lanes pooled per arm, ties non-wins,",
        "#   deterministic; saturated -- reported, never the verdict); FP@500 on the arms' committees; the committees ENS3-S and",
        "#   ENS3-C off FP@20 in the same session -- DESCRIPTIVE, they pick the G2/ladder object and credit nothing; G2 (ratified)",
        "#   on the strongest object after this readout.",
        "# ACTION ON EACH BRANCH -- exhaustive, strict boundaries, no unnamed cells, the word \"kill\" absent (rule 6):",
        "#   X-POS (delta >= +0.025 AND >= 2*se_diff, the boundary above): EXPERT ITERATION IS CREDITED on this base; the",
        "#     searched finals are the next objects (G2, the ladder pre-reg); the next fleet keeps the lever.",
        "#   X-NEG (delta < -0.025 AND |delta| > 2*se_diff): credited NEGATIVE; the next fleet drops the lever; the mechanism",
        "#     reads decide whether the target form or the evaluator failed.",
        "#   X-FLAT (everything else): a NULL at this dose that closes nothing; the mechanism co-primaries decide the next",
        "#     fleet (kl_prior and the compounding read MOVED -> repeat at a longer horizon or a stronger evaluator; NOT MOVED ->",
        "#     the target form or the evaluator is the next lap -- never \"search does not work\").",
        "#   The mechanism axis (MOVED / NOT-MOVED / PARTIAL) is reported beside every cell and changes no action.",
        "# ANCHOR BATTERY before any README row: vs SH locked, the BC-clone h2h (500), FP@20 h2h; a missing leg reads PENDING.",
        "# LAUNCH (over 5 h -> the maintainer launches, CLAUDE.md rule 4): from a CLEAN tree at the merge commit, normal QoS,",
        "#   one launcher invocation per lane config (each lane has its own donor), the lines scripts/derive_r7_fleet.py prints.",
        "# OWED AT READOUT: RESUMES= / NODE_RESTARTS=, every from_step, the /timer line, the donors' sha256, the chosen LR and",
        "#   its smoke, the B0 verdict, meta stamps (c6, bank_zero_copy, param counts), the anchor battery, RESULTS, README.",
    ]


def lane_config(base: str, arm: str, *, seed: int, donor: dict, lr: float, total: int, tag: str,
                search_on: bool = True) -> dict:
    body = copy.deepcopy(base_body(base))
    body["seed"] = seed
    body["total_steps"] = total
    body["run_name"] = f"r7_{tag}_s{seed}"
    body["init_from"] = donor["path"]
    body.setdefault("env_kwargs", {})["seat_tag"] = tag
    col = body.setdefault("collector", {})
    col["process"] = True
    col["search"] = {**SEARCH, "play": LEVER[arm]["play"]}
    ag = body.setdefault("agent", {})
    ag["lr"] = lr
    ag["lr_anneal_steps"] = total
    ag["search_targets"] = True
    ag["search_policy_coef"] = LEVER[arm]["search_policy_coef"]
    ag["search_value_head"] = True
    ag["search_value_coef"] = LEVER[arm]["search_value_coef"]
    ag["search_value_blend"] = 0.0
    return body


def write(path: pathlib.Path, head: list[str], body: dict) -> None:
    path.write_text("\n".join(head) + "\n" + yaml.safe_dump(body, sort_keys=False))


def _entropy_last_bin(history: pathlib.Path, frac: float = 0.25) -> float:
    rows = list(csv.DictReader(history.open()))
    vals = [float(r["loss/entropy"]) for r in rows if r.get("loss/entropy") not in (None, "")]
    if not vals:
        raise SystemExit(f"{history}: no loss/entropy rows")
    tail = vals[-max(1, int(len(vals) * frac)):]
    return sum(tail) / len(tail)


def read_lr(runs: pathlib.Path, base: str) -> float:
    """The pre-stated LR rule over the three 2M smokes' history.csv files."""
    donor_dir = runs / DONOR_DIR[donor_trio(base)].format(DONOR_SEEDS[donor_trio(base)][0])
    ref = _entropy_last_bin(donor_dir / "history.csv", frac=0.01)
    chosen = None
    for lr in sorted(LR_SMOKE, reverse=True):
        h = runs / f"r7_lr_smoke_{lr:g}_s{LR_SMOKE[lr]}" / "history.csv"
        rows = list(csv.DictReader(h.open()))
        kls = [float(r["loss/approx_kl"]) for r in rows if r.get("loss/approx_kl") not in (None, "")]
        ent = _entropy_last_bin(h)
        ok = kls and max(kls) <= 0.06 and abs(ent - ref) <= 0.2 * abs(ref)
        print(f"lr {lr:g}: max approx_kl {max(kls) if kls else float('nan'):.4f}, last-bin entropy {ent:.4f} vs donor {ref:.4f} -> {'OK' if ok else 'FAILS'}")
        if ok and chosen is None:
            chosen = lr
    if chosen is None:
        raise SystemExit("no candidate LR passed the rule -- a maintainer ruling, not a default")
    print(f"CHOSEN LR {chosen:g}")
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", choices=("a", "b", "ab", "w"), required=True)
    ap.add_argument("--stage", choices=("lr-smokes", "fleet"), default=None)
    ap.add_argument("--read-lr", action="store_true", help="apply the LR rule to the three smokes' history.csv")
    ap.add_argument("--lr", type=float, default=None, help="the starting LR (--stage fleet): the rule's choice")
    ap.add_argument("--lr-evidence", default="chosen by the 2M LR smokes' rule", help="where the LR came from, for the header")
    ap.add_argument("--b0", choices=("PASS", "FAIL"), default=None, help="the B0 bench's six-wide verdict (--stage fleet)")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--out", default="configs")
    args = ap.parse_args()
    runs = pathlib.Path(args.runs) if pathlib.Path(args.runs).is_absolute() else ROOT / args.runs
    out = pathlib.Path(args.out) if pathlib.Path(args.out).is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    if args.read_lr:
        read_lr(runs, args.base)
        return
    ds = donors(args.base, runs)
    lines = []
    if args.stage == "lr-smokes":
        for lr, seed in LR_SMOKE.items():
            tag = f"lr_smoke_{lr:g}"
            body = lane_config(args.base, "searched", seed=seed, donor=ds[0], lr=lr, total=2_000_000, tag=TAGS["lr"])
            body["run_name"] = f"r7_{tag}_s{seed}"
            body["eval_every"] = 100_000_000
            head = header(arm="searched", lane=None, donor=ds[0], all_donors=ds, base=args.base, lr=lr,
                          lr_evidence="an LR SMOKE candidate", b0="n/a", kind=f"2M LR SMOKE, NOT A PRE-REG RUN (lr {lr:g})")
            name = f"r7_lr_smoke_{lr:g}.yaml"
            write(out / name, head, body)
            lines.append(f"bash scripts/monster_fleet.sh configs/{name} 2000000 {seed}")
    elif args.stage == "fleet":
        if args.lr is None or args.b0 is None:
            raise SystemExit("--stage fleet needs --lr (the rule's choice) and --b0 (the bench's verdict)")
        for arm in ("searched", "control"):
            for f, seed in enumerate(SEEDS[arm], start=1):
                if arm == "control" and f == 3 and args.b0 == "FAIL":
                    continue
                body = lane_config(args.base, arm, seed=seed, donor=ds[f - 1], lr=args.lr, total=HORIZON, tag=TAGS[arm])
                head = header(arm=arm, lane=f, donor=ds[f - 1], all_donors=ds, base=args.base, lr=args.lr,
                              lr_evidence=args.lr_evidence, b0=args.b0, kind="")
                name = f"r7_fleet_{arm}_f{f}.yaml"
                write(out / name, head, body)
                lines.append(f"bash scripts/monster_fleet.sh configs/{name} {HORIZON} {seed}")
            smoke = lane_config(args.base, arm, seed=SMOKE_SEEDS[arm], donor=ds[0], lr=args.lr, total=400_000,
                                tag=TAGS[f"smoke_{arm}"])
            smoke["eval_every"] = 100_000_000
            head = header(arm=arm, lane=None, donor=ds[0], all_donors=ds, base=args.base, lr=args.lr,
                          lr_evidence=args.lr_evidence, b0=args.b0, kind="400k WARM-START SHAKEDOWN SMOKE, NOT A PRE-REG RUN")
            write(out / f"r7_fleet_smoke400k_{arm}.yaml", head, smoke)
            lines.insert(0, f"bash scripts/monster_fleet.sh configs/r7_fleet_smoke400k_{arm}.yaml 400000 {SMOKE_SEEDS[arm]}")
    else:
        raise SystemExit("--stage lr-smokes | fleet, or --read-lr")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
