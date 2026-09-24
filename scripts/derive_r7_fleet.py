#!/usr/bin/env python
"""R7 FLEET CONFIG DERIVATION -- the lane configs of the ruled design, derived, never hand-edited.

The rulings (plan AMENDMENT BOX 6; maintainer, 2026-09-24 00:20Z): the fleet starts WARM from the base
trio's three R6 finals, PAIRED BY FINAL (final f seeds searched lane f and control lane f), +100M on a
re-armed anneal from a REDUCED starting LR; 3 + 3 lanes if the B0 bench passes six-wide, else 3 + 2. Each
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

STAGES (Friday, the idle box; header r3 folds in both Opus reviews of 2026-09-24 and their verification passes):
  --stage lr-smokes   2M warm-start smokes from lane f1's donor at every candidate LR (each one BELOW the donors'
                      own starting LR -- checked), THREE per LR: the searched arm, the control, and a BETA-0
                      comparator (the searched arm with beta 0), on the lane's own schedule (anneal over the 100M
                      horizon). Run by `scripts/r7_smokes.sh lr <base>`.
  --stage lr-evals    prints the vs-SH commands (scripts/eval_checkpoint.py, n 3000) for the donor's final and
                      each finished searched/control smoke's final, into results/r7_lr/.
  --read-lr           applies the pre-stated rule and writes results/r7_lr/read_lr.json (the fleet stage's only
                      accepted source for --lr, unless --lr-ruled carries a maintainer ruling in its place).
  --stage fleet       the lane configs (3 + 3, or 3 + 2 under --b0 FAIL), the lane manifest for
                      scripts/r7_fleet_launch.sh, and the two warm-start shakedown smokes (eval + checkpoint every
                      100k; long enough that the async loop's checkpoint.pt exists before the searched one is killed
                      and resumed -- `scripts/r7_smokes.sh shakedown`).
The header's power statement is read from results/r7_fleet/power.json (scripts/r7_fleet_power.py) and its
counter gate from GATE_COUNTERS below (the checker, scripts/r7_smoke_check.py, imports the same table).
Writes into --out (default configs/); prints the next commands.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
TRIO_A = "configs/showdown_r6_trio_a.yaml"
TRIO_B = "configs/showdown_r6_trio_b_fallback.yaml"
DONOR_SEEDS = {"a": (304, 312, 320), "b": (328, 336, 344)}
DONOR_DIR = {"a": "showdown_r6_trio_a_s{}", "b": "showdown_r6_trio_b_s{}"}
DONOR_MIN_STEP = 200_000_000
SEEDS = {"searched": (376, 384, 392), "control": (400, 408, 416)}
SMOKE_SEEDS = {"searched": 424, "control": 432}
LR_CANDIDATES = (1.0e-4, 5.0e-5, 2.5e-5)
LR_ARMS = ("searched", "control", "beta0")
LR_SMOKE_SEEDS = {"searched": (440, 444, 448), "control": (452, 456, 460), "beta0": (464, 468, 472)}
TAGS = {"searched": "r7fs", "control": "r7fc", "smoke_searched": "r7ws", "smoke_control": "r7wc",
        "lr_searched": "r7ls", "lr_control": "r7lc", "lr_beta0": "r7lb"}
HORIZON = 100_000_000
LR_SMOKE_STEPS = 2_000_000
SMOKE_MIN_STEPS = 400_000          # the shakedown's floor (R6's smokes); longer when an update is large (below)
SMOKE_CADENCE = 100_000            # the shakedown's eval_every AND checkpoint_every (l2init/* is written at eval rows)
KL_MAX = 0.06                      # per-update approx_kl bar (the control's whole batch; the searched arm's unsearched rows)
ENT_TOL, ENT_TAIL, ENT_REF_TAIL = 0.20, 0.25, 0.01
SH_N = 3000                        # vs SH per checkpoint, the locked protocol's per-seed n
SH_SHOCK = 0.03                    # CLAUDE.md: one vs-SH rung at n 3000 is worth +-0.02
MECH_WINDOW = 5_000_000            # the in-loop mechanism counters are read as means over the last 5M steps
OBJECT_TOL = 0.013                 # trio A's object-rule tolerance (~1 se_diff at 3000 vs 3000)
B_BATCH = {"agent.rollout_steps": 15360, "agent.minibatches": 480, "selfplay.push_every_updates": 1}
W_BATCH = {"agent.rollout_steps": 3840, "agent.minibatches": 120, "selfplay.push_every_updates": 5}
HEAD_KEYS = ("collector.outcome_targets", "agent.aux_outcome_coef", "agent.trunk_kwargs.value_aux_out")
SEARCH = {"frac": 0.75, "top1_skip": 0.97, "cols_k": 4, "chance_s": 2, "tau": 0.05}
LEVER = {"searched": {"play": True, "search_policy_coef": 0.1, "search_value_coef": 0.1},
         "control": {"play": False, "search_policy_coef": 0.0, "search_value_coef": 0.0},
         # the LR smokes' comparator: the searched arm with beta 0 -- it plays pi' and trains the v' head, so the
         # searched arm differs from it by the policy target alone (the not-inert check's contrast)
         "beta0": {"play": True, "search_policy_coef": 0.0, "search_value_coef": 0.1}}
BASE_LINE = {
    "a": "trio A's outcome heads (collector.outcome_targets / aux_outcome_coef 0.1 / value_aux_out 3) -- X-POS or X-FLAT-with-its-mechanism-moved on 09-25",
    "b": "trio B's x4 batch in its FALLBACK form (rollout 15360, minibatches 480, push every update) -- X-POS or X-FLAT-with-a-faster-update on 09-25",
    "ab": "BOTH R6 levers: trio A's outcome heads + trio B's fallback batch keys (warm from trio A's finals, which carry the heads)",
    "w": "NEITHER R6 lever (both read against keeping them on 09-25): the W recipe's batch keys, no heads (warm from trio B's finals, which carry no heads)",
}
# R0 gate (1)'s counters -- ONE table: the header prints it and scripts/r7_smoke_check.py imports it. A name ending
# in "/" is a prefix. tests/test_derive_r7_fleet.py greps rl/ for every name, so a gate cannot name a counter that
# nothing writes (the typed-list landmine's other face).
GATE_COUNTERS = {
    "both": ("search/decisions", "search/searched_frac", "search/eligible_frac", "search/played_frac",
             "search/kl_prior", "search/override", "search/ms", "search/leaves", "search/rows_frac",
             "search/rows_update", "search/kl_update", "search/override_update", "search/value_gap",
             "loss/search_value", "loss/approx_kl_searched", "loss/approx_kl_unsearched",
             "loss/clip_frac_searched", "loss/clip_frac_unsearched", "loss/grad_norm", "loss/grad_clip_frac",
             "value/bias_mirror", "collect/weights_lag_updates", "collect/child_idle_frac"),
    "searched_only": ("loss/search_policy", "search_value/grad_norm", "search_value/clip_scale"),
    "eval_rows": ("l2init/",),
    "heads": ("aux_outcome/",),
}


def _set(d: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


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


def donor_lr(base: str) -> float:
    """The donors' own starting LR: the trio config they trained under (the batch adjustments never touch it)."""
    return float(yaml.safe_load((ROOT / (TRIO_A if donor_trio(base) == "a" else TRIO_B)).read_text())["agent"]["lr"])


def save_latest_every() -> int:
    """rl/train.py's SAVE_LATEST_EVERY_UPDATES, read from the source (never typed): how often the async loop writes the
    checkpoint.pt a resume loads."""
    m = re.search(r"^SAVE_LATEST_EVERY_UPDATES\s*=\s*(\d+)", (ROOT / "rl/train.py").read_text(), re.M)
    if not m:
        raise SystemExit("rl/train.py: SAVE_LATEST_EVERY_UPDATES not found -- the shakedown's length is derived from it")
    return int(m.group(1))


def steps_per_update(base: str) -> int:
    b = base_body(base)
    return int(b["agent"]["rollout_steps"]) * int(b["num_envs"])


def smoke_steps(base: str) -> int:
    """The shakedown's horizon: at least SMOKE_MIN_STEPS and at least (SAVE_LATEST_EVERY_UPDATES + 2) updates, rounded up
    to the cadence -- so the first checkpoint.pt exists with two updates left for the resumed lane (the wiring review's
    second pass: at base b's 122,880-step update the first checkpoint.pt is at ~491k, past a 400k horizon)."""
    need = (save_latest_every() + 2) * steps_per_update(base)
    return max(SMOKE_MIN_STEPS, SMOKE_CADENCE * math.ceil(need / SMOKE_CADENCE))


def _step(p: pathlib.Path) -> int | None:
    m = re.fullmatch(r"ckpt_(\d+)\.pt", p.name)
    return int(m.group(1)) if m else None


def final_ckpt(d: pathlib.Path, min_step: int = 0) -> pathlib.Path | None:
    """The highest-step ckpt_<step>.pt at or past `min_step` (parsed, never globbed on a digit prefix: a final
    can overshoot 200M by any amount)."""
    steps = [(s, p) for p in d.glob("ckpt_*.pt") if (s := _step(p)) is not None and s >= min_step]
    return max(steps)[1] if steps else None


def donors(base: str, runs: pathlib.Path) -> list[dict]:
    """Each donor lane's FINAL checkpoint (the highest ckpt at or past 200M), its sha256, and its theta0."""
    out = []
    for s in DONOR_SEEDS[donor_trio(base)]:
        d = runs / DONOR_DIR[donor_trio(base)].format(s)
        final = final_ckpt(d, DONOR_MIN_STEP)
        if final is None:
            raise SystemExit(f"REFUSED: no final (a ckpt at step >= {DONOR_MIN_STEP:,}) under {d} -- the donor lane has not finished")
        if not (d / "theta0.pt").exists():
            raise SystemExit(f"REFUSED: {d}/theta0.pt missing -- the warm start's L2 anchors are the donor's")
        out.append({"seed": s, "dir": d, "final": final,
                    "path": str(final.relative_to(runs.parent)) if final.is_relative_to(runs.parent) else str(final),
                    "sha256": hashlib.sha256(final.read_bytes()).hexdigest()})
    return out


def load_power(path: pathlib.Path) -> dict:
    if not path.exists():
        raise SystemExit(f"REFUSED: {path} missing -- run scripts/r7_fleet_power.py --out {path} (the header's power "
                         "statement is read from it, never typed)")
    raw = path.read_bytes()
    return {**json.loads(raw), "_sha": hashlib.sha256(raw).hexdigest()}


def _power_rows(power: dict, width: str) -> dict:
    return {(r["n"], r["delta"]): r for r in power["table"] if r["width"] == width and r["donor_share"] == 0.0}


def power_lines(power: dict, width: str) -> list[str]:
    rows = _power_rows(power, width)
    ds = (0.025, 0.030, 0.035, 0.040)
    p3 = " / ".join(f"{rows[(3000, d)]['X-POS']:.2f}" for d in ds)
    p6 = " / ".join(f"{rows[(6000, d)]['X-POS']:.2f}" for d in ds)
    at20 = rows[(3000, 0.020)]
    return [
        f"#   POWER ({power['version']}, results/r7_fleet/power.json sha {power['_sha'][:12]}, scripts/r7_fleet_power.py): five",
        "#   banked trio READS of per-lane FP@20 finals at n 3000 (four distinct trios; the 100M finals were read in two",
        f"#   sessions, so the {power['df']} df double-count their lane term): per-lane sd {power['pooled_sd']:.4f}, "
        f"{power['binomial_sd']:.4f} of it binomial;",
        f"#   median se_diff {rows[(3000, 0.030)]['se_diff_median']:.4f} at {width}, so the +0.025 FLOOR is the operative bar. "
        f"P(X-POS) at a true",
        f"#   +0.025 / +0.030 / +0.035 / +0.040: {p3}; at a true 0: {rows[(3000, 0.0)]['X-POS']:.3f}; at a true +0.020: X-POS "
        f"{at20['X-POS']:.2f}, X-GAIN {at20.get('X-GAIN', float('nan')):.2f}",
        f"#   ({width}, n 3000, the unpaired end of the donor split). AN X-FLAT OR X-GAIN IS LIKELY EVEN IF THE LEVER WORKS at the",
        "#   size the plan's own bounds suggest (G1's +0.050 in the mirror is the operator's inference-side UPPER bound, box 5;",
        f"#   the fleet's bet is compounding). n 6000 per lane would buy {p6} at the same deltas (~+8 h of quiet-box FP): a",
        "#   maintainer option, not taken here.",
    ]


def _fmt(names) -> str:
    return ", ".join(n + ("*" if n.endswith("/") else "") for n in names)


def header(*, arm: str, lane: int | None, donor: dict, all_donors: list[dict], base: str, lr: float, lr_evidence: str,
           b0: str, kind: str, power: dict) -> list[str]:
    today = dt.date.today().isoformat()
    donors_txt = "; ".join(f"f{i + 1} {d['path']} (sha {d['sha256'][:12]})" for i, d in enumerate(all_donors))
    lane_txt = f"LANE f{lane} of 3" if lane else kind
    width = "3+2" if b0 == "FAIL" else "3+3"
    n_lanes = 5 if b0 == "FAIL" else 6
    order = "C1, S1, C2, S2, S3" if b0 == "FAIL" else "C1, S1, C2, S2, C3, S3"
    body = base_body(base)
    push, pool_size = body["selfplay"]["push_every_updates"], body["selfplay"]["pool_size"]
    heads = base in ("a", "ab")
    s, lv = SEARCH, LEVER["searched"]
    h = HORIZON // 1_000_000
    spu, save_every, sm = steps_per_update(base), save_latest_every(), smoke_steps(base)
    at20 = _power_rows(power, width)[(3000, 0.020)]
    from r7_mechanism_reads import PER_BUCKET
    lane_loss = ("under 3+2, losing a lane of pair f1 or f2 leaves ONE full pair -> PRIMARY VOID, while losing searched f3"
                 " leaves 2 vs 2" if b0 == "FAIL" else "k 2 vs 2, disclosed")
    return [
        f"# R7 FLEET -- EXPERT ITERATION ON THE STACKED BASE, WARM FROM R6, PAIRED BY FINAL. ARM: {arm.upper()}; {lane_txt}.",
        "# ENCODER_C6: on",
        f"# GENERATED by scripts/derive_r7_fleet.py on {today} (base {base}; header r3: both Opus reviews of 2026-09-24 and their",
        f"#   verification passes folded in); never hand-edit -- re-derive. This lane warm-starts from {donor['path']} (sha {donor['sha256'][:12]}).",
        "#",
        "# journey_step: \"14\" (R7; steps 8 and 10 folded in by the kitchen-sink ruling, 2026-09-23). Exit condition, verbatim:",
        "#   \"one comparison at a REAL budget, on the strongest gen-1 object we have. Search-with-our-evaluator vs the same",
        "#   checkpoint greedy, pooled under the standing credit line, with decisions/sec reported for both arms and the",
        "#   per-turn budget named in every quote.\" THIS FLEET IS NOT THAT COMPARISON: G2 (ratified, run AFTER this fleet) reads",
        "#   the L-op on the R5 W committee it pins by sha; this fleet trains the objects a SECOND G2-protocol read and the next",
        "#   ladder may use (OBJECT RULE below) and credits ONE lever, expert iteration. Step 10's text carries no \"Exit",
        "#   condition:\" line (trio A's header quoted its lead sentence, \"The big one, with a recipe validated somewhere the",
        "#   instrument works\"); its one convention is suspended under START below.",
        "#",
        "# THE LEVER (the searched arm; the plan's T-op, AMENDMENT BOXES 4-6), ONE UNIT OF THREE CHANNELS (box 5 item 6). On the",
        f"#   eligible rows (> 1 legal action and pi_theta top-1 < {s['top1_skip']}) a coin at frac {s['frac']} (~40% of "
        "decisions) runs native.solve on the",
        f"#   TRUE world (B = 1; box 5 item 2's re-read licence) at k {s['cols_k']} / S {s['chance_s']} / tau {s['tau']} "
        "with the learner's OWN observation critic at the",
        "#   leaves (one view, box 5 item 5). (1) BEHAVIOUR: the lane PLAYS a' ~ pi' and records log pi'(a), so its data are",
        "#   off-policy from a true-world search and PPO's clipped ratio pi_theta/pi' is the only correction, exact only inside",
        "#   the clip (loss/clip_frac_searched vs _unsearched reads how much is clipped). (2) THE POLICY TARGET: beta *",
        f"#   KL(pi' || pi_theta) on searched rows (beta {lv['search_policy_coef']}); the term sits INSIDE the shared gradient "
        "clip (B5, the bc_kl",
        "#   precedent), which binds on ~99.9% of minibatches in this stack (rl/agents/ppo.py's own comment), so it also shrinks",
        "#   the searched arm's PPO actor AND critic steps by the ratio of the arms' pre-clip norms -- loss/grad_norm per arm",
        "#   reads that ratio, reported beside the primary (the critic sets the advantages: D18's falsifier). (3) THE VALUE",
        f"#   TARGET: the v' aux head on the critic's context (coef {lv['search_value_coef']}; applied after the clip read, "
        "critic only; the GAE blend",
        "#   stays 0). beta and the value coefficient are the plan's defaults, UNMEASURED in magnitude: R0 gate (2)'s not-inert",
        "#   check reads that beta moves the student at all; G3's reads whether it absorbs.",
        "# THE CONTROL (box 5 item 6): the same two-core lane with the T-op at the same rule and cost, play false and both",
        "#   coefficients 0 -- it searches and records, never plays, never trains on the targets; the arms differ by the WHOLE",
        "#   lever. DOSE IS MATCHED BY RULE, NOT BY COUNT: eligibility reads each arm's own pi_theta, so search/eligible_frac,",
        "#   search/searched_frac and search/played_frac are reported per arm at 12M and at the end, and a divergence is",
        "#   disclosed beside the primary.",
        "#",
        "# THE BASE (every lane, UNCREDITED BY DESIGN): the W recipe + C6 + E2 (the scorer factorization, common-mode, 38f7736)",
        "#   + the mmap'd team bank + R6's trio lever(s) by THEIR OWN pre-stated branches on the 09-25 read:",
        f"#   {BASE_LINE[base]}.",
        "#   B2 (the antisymmetric privileged critic) is OUT (box 5 item 5): the T-op scores its leaves with the learner's critic.",
        "#   The league pool restarts at [donor] (a warm start seeds it with the loaded policy alone); it refills one push every "
        f"{push} update(s) up",
        f"#   to pool_size {pool_size}.",
        "#",
        "# START (R-F1, ruled 2026-09-24): WARM + PAIRED BY FINAL -- lane f of each arm from the base trio's f-th final:",
        f"#   {donors_txt}.",
        f"#   +{h}M env steps on a RE-ARMED anneal (begin_warm_start) from lr {lr:g} ({lr_evidence}), below the donors' own",
        f"#   starting lr {donor_lr(base):g}; the L2-toward-init anchors are the DONOR's theta0 (7014f11). DISCLOSED ON EVERY "
        "NUMBER: JOURNEY 10's",
        "#   convention (\"never a warm start off a finished checkpoint\") is SUSPENDED for this fleet -- its finals are",
        "#   300M-trained objects on two anneals (N-ANNEAL); a comparison with R6's finals is confounded, the within-fleet",
        "#   comparison is not.",
        f"# WIDTH (R-F2, ruled): 3 searched + 3 control if the B0 bench passed six-wide, else 3 + 2 (control f3 dropped). B0: {b0}.",
        "#   SIX-WIDE DISCLOSURE (ruling 7): six two-core lanes put twelve cores' worth of work on ten performance cores, so some",
        "#   of it runs on the efficiency cores; B0's six-wide pass line (3.6 ms p99 per searched decision) is what licenses the",
        "#   width, and gate (4) reports every lane's rate beside its pair's. Both arms share the box, so the contention is",
        "#   common-mode; it is disclosed on every number, never repaired by a correction.",
        "#",
        "# R0 SANITY GATES (before launch; each with its action on a FAIL):",
        f"#   (1) THE WARM-START SHAKEDOWN SMOKES (searched + control from lane f1's donor, {sm // 1000}k steps = "
        f"{sm / spu:.1f} updates at this base; eval",
        f"#       and checkpoint every {SMOKE_CADENCE // 1000}k, since l2init/* is written at eval rows only; the lane's own "
        "anneal) PASS scripts/r7_smoke_check.py:",
        f"#       the SEARCHED smoke is killed once its first checkpoint.pt exists (the async loop writes it every {save_every} "
        f"updates, {save_every * spu:,}",
        "#       steps at this base) and resumed by the watchdog, and finishes; the first launch's log carries the THETA0 donor line",
        "#       and the resume's log its own THETA0 re-install line; meta.yaml stamps engine.bank_zero_copy true, encoder.c6 true",
        "#       and a clean sha; collect/weights_lag_updates <= 1 on every update row; and every counter below is in history.csv",
        "#       (GATE_COUNTERS in scripts/derive_r7_fleet.py -- one table, the header's and the checker's; a test greps rl/ for",
        "#       every name, so a gate cannot name a counter nothing writes):",
        f"#         BOTH ARMS: {_fmt(GATE_COUNTERS['both'])};",
        f"#         {_fmt(GATE_COUNTERS['eval_rows'])} at the eval rows" + (f"; {_fmt(GATE_COUNTERS['heads'])} (this base keeps the heads)." if heads else "."),
        f"#         SEARCHED ONLY: {_fmt(GATE_COUNTERS['searched_only'])} (they sit behind a coefficient > 0), and",
        "#         search/played_frac == search/searched_frac > 0 on every update row.",
        "#         CONTROL: the searched-only counters ABSENT, and search/played_frac == 0 on every update row.",
        "#       FAIL -> no fleet: diagnose, fix, re-smoke.",
        "#   (2) THE LR RULE (R-F1: \"a REDUCED starting LR that a 2M smoke sets by reading the policy for a shock (vs-SH",
        "#       before/after, approx_kl, entropy)\"). 2M warm-start smokes from lane f1's donor at each candidate lr in",
        f"#       {{{', '.join(f'{c:g}' for c in LR_CANDIDATES)}}}, every one below the donors' own starting lr {donor_lr(base):g} "
        "(checked), on the lane's own schedule (anneal",
        f"#       over {h}M: ALLOW_ANNEAL_OVER_HORIZON=1), THREE per lr under the same contention: the SEARCHED arm, the CONTROL, and",
        "#       a BETA-0 COMPARATOR (the searched arm with beta 0: it plays pi' and trains the v' head, so the searched arm differs",
        f"#       from it by the policy target alone). An lr PASSES iff: the CONTROL's every per-update loss/approx_kl <= {KL_MAX}",
        "#       (the whole batch: its behaviour is pi_theta everywhere, the bar's own calibration) and the SEARCHED arm's every",
        f"#       per-update loss/approx_kl_unsearched <= {KL_MAX} (under play the only uncontaminated rows -- a searched row's",
        "#       behaviour log-prob is log pi'(a), carrying KL(pi' || pi_theta) at ANY lr -- and ~80% confident or forced ones, so",
        f"#       the bar reads looser there: disclosed); the CONTROL's mean loss/entropy over its last {ENT_TAIL:.0%} of updates "
        f"is within +-{ENT_TOL:.0%}",
        f"#       of the donor's mean over its last {ENT_REF_TAIL:.0%}; and the CONTROL's final vs SH (scripts/eval_checkpoint.py, "
        f"n {SH_N}) is not below the",
        f"#       donor final's, read the same day at the same n, by more than {SH_SHOCK} (CLAUDE.md: one vs-SH rung at n 3000 is "
        "worth +-0.02).",
        "#       The SEARCHED arm's entropy and vs SH carry the lever's own 2M effect, so they are READ; a searched-only vs-SH drop",
        f"#       past {SH_SHOCK} at the chosen lr goes to a ruling. NOT-INERT, at the chosen lr: the SEARCHED arm's mean "
        "search/kl_update over",
        "#       its last half of updates is below the BETA-0 comparator's by more than 2 * sqrt(se_S^2 + se_0^2) (update-level se",
        "#       over those rows; ~8 autocorrelated updates, so the se understates the noise: disclosed) -- beta moves the student",
        "#       toward pi' beyond what playing pi' and the v' head do. The LARGEST",
        "#       passing lr is chosen (--read-lr writes results/r7_lr/read_lr.json; --stage fleet refuses any other lr). None",
        "#       passes, the not-inert check fails, or a searched-only vs-SH drop -> a maintainer ruling before launch, never a",
        "#       default.",
        "#   (3) THE SUITE at the launch commit, in pkmn-engine-port after the reinstall (the launcher's interpreter):",
        "#       tests/test_engine_bank_mmap.py and tests/test_r7_mechanism_reads.py (the mechanism instrument reproduces G0 and",
        "#       the evaluator) PASS, NOT SKIPPED; tests/test_lop.py (none skipped) and tests/test_derive_r7_fleet.py pass; every",
        "#       lane's meta.yaml stamps the SAME git sha, clean. FAIL -> no launch.",
        "#   (4) THROUGHPUT, read after each lane's first hour (a window that straddles startup is not a record): each lane's",
        "#       steps/s is reported beside its pair's (the arms run the same T-op at the same rule, so cost is matched by",
        "#       construction and this reads it); a lane below 0.6x the fleet's median (the R6 monitor's alert line) gets the",
        "#       CPU-delta check, then the maintainer -- a lane is never killed for speed alone.",
        "#   (5) every resume's from_step read from meta.yaml; RESUMES= / NODE_RESTARTS= from the ONE watchdog; the /timer line",
        "#       travels.",
        f"#   LANE LOSS (a named cell): a lane that fails a gate or cannot be resumed to {h}M is dropped WITH ITS PAIR; the primary",
        f"#       becomes the surviving pairs ({lane_loss}); fewer than two pairs -> PRIMARY VOID (the finals are",
        "#       recorded individually and never pooled).",
        "#",
        "# PRIMARY READ -- off FP@20 (search_time_ms 20 per arm), GREEDY, n = 3000 per lane, ONE session on a QUIET box (the FP",
        f"#   gate: nothing else at >= 50% of a core; G2 never beside it), SEQUENTIAL arms in the PINNED order {order}",
        "#   (control first in each pair, the G2 convention), then the OBJECT RULE's reads, then FP@500, then the anchors; a",
        "#   killed arm re-runs LAST on its rerun username pair; fresh prefix-free usernames -- the configs/eval/r6_reads_offfp.yaml",
        "#   protocol; the whole session is ~20 h. FP@20 is the primary as in [RWL-3] (configs/showdown_monster200m_l2lam.yaml;",
        "#   vs SH is saturated). delta = the equal-weight mean of the SEARCHED finals minus the equal-weight mean of the CONTROL",
        "#   finals (the across-lane aggregator). se_diff is the LARGER of the pooled-binomial se_diff and the seed-clustered",
        "#   se_diff (k 3 vs 3; k 3 vs 2 under the five-wide fallback), the latter from the per-lane finals at read time.",
        "#   CREDIT LINE, verbatim (CLAUDE.md): \"a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff",
        "#   is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed",
        "#   finals at read time.\" The operative test is STRICT: a delta EXACTLY +0.025 or EXACTLY 2*se_diff reads as NOT met",
        "#   (the house boundary, R6's and G2's). Both FP@20 disclosures travel with every number, forever: the equivalence test",
        "#   is weakly powered, and the point estimate flatters us; FP@20 is an instrument, not a rung.",
        *power_lines(power, width),
        f"#   DOSE IS MATCHED BY CONSTRUCTION and CHECKED: the same donors, {h}M env steps, horizon, anneal, starting lr, k,",
        "#   two-core lane and T-op rule; a searched/control pair's configs differ EXACTLY in {seed, run_name, seat_tag,",
        "#   collector.search.play, agent.search_policy_coef, agent.search_value_coef} (tests/test_derive_r7_fleet.py).",
        "#   THE PAIRED READ (secondary): lanes are paired by DONOR, not by battle (seeds do not pair battles). Under 3+3 each",
        "#   donor appears once per arm, so the equal-weight delta IS the mean of the pair differences; the paired se,",
        "#   sd(S_f - C_f)/sqrt(3), is PRINTED and NEVER governs (the credit line's clustered term is per arm; swapping it in",
        "#   after the data would be a forking path). Under 3+2 the primary is donor-unbalanced (f3 in the searched mean only);",
        "#   the balanced two-pair delta is printed beside it. POLICY FORM: greedy, loop breaker OFF on both arms (matched).",
        "#",
        "# MECHANISM READS (G3's six, amendment 3 item 3 / box 4 item 6), each SEARCHED MINUS CONTROL at the END checkpoint,",
        "#   paired by donor, both arms in one instrument session; se = the LARGER of the lane-clustered se (sd of the per-pair",
        "#   differences / sqrt(pairs)) and, for (iii) and (vi), the position-level se (paired by position); MOVED = the named",
        "#   sign AND |d| > 2 se AND every pair carries the named sign. (i) is the MANIPULATION CHECK (it moves whenever beta is",
        "#   not inert); the axis's decision rests on (vi), whose position-level floor holds the false-MOVED rate near nominal",
        "#   (on the lane-clustered se alone a 2-se bar is ~9% one-sided at 2 df, ~15% at 1 df). The 12M read is DESCRIPTIVE and",
        "#   changes no dial (plan section 6's G3 split branch and section 10's actor kill do not apply mid-fleet); rule 6: a 12M",
        "#   null is not a finding about the lever.",
        f"#   (i)   search/kl_prior (act-time KL(pi' || pi_theta) on searched decisions), mean over the last {MECH_WINDOW // 1_000_000}M steps: LOWER.",
        "#   (ii)  search/override (argmax pi' != argmax prior, UNGATED -- the T-op has no margin gate), same window: LOWER.",
        f"#   (iii) the leaf critic's per-position cell Spearman (the evaluator's spearman_base statistic) on G0's first {PER_BUCKET} "
        "positions of",
        "#         each turn bucket in row order, the same for every lane (held out: no lane trains on them): HIGHER.",
        "#   (iv)  search/value_gap (|v' - GAE target| on searched rows), same window: LOWER.",
        "#   (v)   value/bias_mirror per arm: REPORTED, a guard (section 31's +0.059 train/eval shift is the scale it watches);",
        "#         no action.",
        "#   (vi)  THE COMPOUNDING READ: the student greedy's split-sample regret on G0's banked halves at the same positions:",
        "#         LOWER. (iii) and (vi) are scripts/r7_mechanism_reads.py (tests/test_r7_mechanism_reads.py pins it to G0's banked",
        "#         greedy and ceiling and the evaluator's spearman_base); nodes re-encoded with c6 on. A FIXED YARDSTICK, disclosed:",
        "#         G0's Q-values are rollouts under the R5 committee, not either arm's own continuation.",
        "#   THE MECHANISM ROUTE (X-FLAT's action below): (i) NOT MOVED; (i) MOVED with (vi) NOT; or (i) and (vi) BOTH MOVED.",
        "#",
        "# SECONDARY (descriptive, credit nothing): vs SH under the LOCKED protocol (final, 3000 battles/lane, lanes pooled per",
        "#   arm, ties non-wins, deterministic; saturated; under 3+2 the control pools two lanes, a disclosed deviation from",
        "#   \"3 seeds pooled\"); FP@500 on ENS3-S and ENS3-C (the plan's G4) in the primary's policy form (greedy, loop breaker",
        "#   off), n 250 each (the FP budget ladder's precedent n;",
        "#   ~2.7 h each at the 38.8 s/battle of readouts/FP500_R5_READOUT.md; se_diff ~0.045, DESCRIPTIVE only); per-arm",
        "#   loss/grad_norm, the clip_frac split and the realized dose (above).",
        "# OBJECT RULE (in EVERY cell below: which object a second G2-protocol read and the next ladder pre-reg use): the same",
        "#   session re-draws the R6",
        "#   ladder object as R6's readout names it (trio A's OBJECT RULE) and ENS3 of the three donors (skipped when it IS the R6",
        "#   object), then reads ENS3-S and ENS3-C, n 3000 each -- ALL FOUR IN THE R6 OBJECT'S POLICY FORM (its loop breaker",
        "#   included; the primary above reads greedy with the breaker off). The fleet committee with the higher point estimate",
        f"#   becomes the object iff it reaches the re-drawn R6 object minus {OBJECT_TOL} (~1 se_diff at 3000 vs 3000; trio A's own",
        "#   tolerance); otherwise the R6 object stays. Disclosed: the higher of two committee reads carries a winner's curse of",
        "#   ~+0.005, so a replacement may sit ~0.018 below the incumbent in truth. Each arm's committee minus the donors' ENS3 is",
        "#   reported (DESCRIPTIVE, N-ANNEAL). The ratified G2 stays on the R5 W committee; a LADDER run needs its own earning",
        "#   read (the 09-22 principle, a ladder run is EARNED offline; R6's bar, ratified 09-24: >= +0.05 off FP@20 over the",
        "#   re-drawn previous object).",
        "#",
        "# ACTION ON EACH BRANCH -- exhaustive, strict boundaries, no unnamed cells, the word \"kill\" absent (rule 6):",
        "#   X-POS  (delta > +0.025 AND delta > 2*se_diff): EXPERT ITERATION IS CREDITED -- in the WARM-START regime (R6 finals +",
        f"#          {h}M at lr {lr:g}, a second anneal) with a TRUE-world T-op at these dials; nothing about fresh-start ExIt,",
        "#          nothing against R6's objects. The lever stays in the next fleet's base; the object follows the OBJECT RULE.",
        "#   X-GAIN (0 < delta <= +0.025 AND delta > 2*se_diff): a RESOLVED gain below the floor, NOT credited; the lever STAYS",
        "#          in the next fleet's base (the mirror of X-COST).",
        "#   Under X-POS or X-GAIN with (i) NOT MOVED (the manipulation check failed), the gain is DISCLOSED as the lever's",
        "#          behaviour and value channels, not the policy target -- the credit line's words stay, the attribution moves.",
        "#   X-COST (-0.025 <= delta < 0 AND |delta| > 2*se_diff): a RESOLVED cost below the floor, not a null; the lever leaves",
        "#          the base and gets its own lap on the channel the mechanism route names (below).",
        "#   X-NEG  (delta < -0.025 AND |delta| > 2*se_diff): credited NEGATIVE; the lever leaves the base; its own lap on the",
        "#          channel the mechanism route names.",
        "#   X-FLAT (everything else): a NULL at this dose that closes nothing (rule 6), routed on the mechanism reads:",
        "#          (i) NOT MOVED -> the lever leaves the base; the next lap is the TARGET FORM (beta, the value coefficient, tau:",
        "#            the cheaper of section 10's two readings; the student's capacity stays an own-lap item, JOURNEY 14).",
        "#          (i) MOVED, (vi) NOT -> the lever leaves the base; the next lap is the STRONGER EVALUATOR (the student absorbed",
        "#            targets that carry what the critic already knows -- the root-rule read's binding constraint, box 4).",
        "#          (i) and (vi) BOTH MOVED AND delta > 0 -> the lever STAYS in the base; the next lap is the STRONGER",
        f"#            EVALUATOR (the mechanism works below this fleet's power: P(X-POS) is {at20['X-POS']:.2f} at a true +0.020).",
        "#          (i) and (vi) BOTH MOVED AND delta <= 0 -> the lever leaves the base; the next lap is the BEHAVIOUR channel",
        "#            (X-COST's reading: the targets are absorbed and compound, yet the arm does not gain).",
        "#          Never \"search does not work\".",
        "#   THE CHANNEL a lap targets after X-COST or X-NEG, on the same route: (i) not moved -> the policy target; (i) moved,",
        "#   (vi) not -> the evaluator; both moved -> the behaviour channel (the targets are absorbed and compound, yet the arm",
        "#   loses: the off-policy data from a true-world search, or the clip's side channel -- the clip_frac split and",
        "#   loss/grad_norm per arm say which). The mechanism reads are reported beside every cell; outside X-FLAT, X-COST and",
        "#   X-NEG they change no action. LANE LOSS is the named cell under the R0 gates.",
        "# ANCHOR BATTERY before any README row (CLAUDE.md): vs SH locked, the BC-clone h2h (500), FP@20 h2h; a missing leg reads",
        "#   PENDING and the README row WAITS.",
        "# LAUNCH (over 5 h -> the maintainer launches, CLAUDE.md rule 4): from a CLEAN tree at the merge commit, normal QoS,",
        "#   `bash scripts/r7_fleet_launch.sh configs/r7_fleet_lanes.txt`: one launcher call per lane (each lane has its own",
        "#   donor) with the watchdog deferred, then ONE watchdog over every lane (one ensure_node, one RESUMES= line) and one",
        f"#   caffeinate; the width guard counts the FLEET ({n_lanes} two-core lanes"
        + ("; six need ALLOW_SIX_WIDE_DISCLOSED=1, the disclosure above)." if n_lanes == 6 else ")."),
        "# OWED AT READOUT: RESUMES= / NODE_RESTARTS=, every from_step, the /timer line, the donors' sha256, the chosen lr and its",
        "#   smokes, the B0 verdict, meta stamps (c6, bank_zero_copy, param counts), the per-arm reads above, the power inputs,",
        "#   the anchor battery, RESULTS, README.",
    ]


def lane_config(base: str, arm: str, *, seed: int, donor: dict, lr: float, total: int, tag: str,
                anneal: int = HORIZON, cadence: int | None = None) -> dict:
    """A lane (or smoke) body. `anneal` is the LANE's schedule for every stage (a smoke runs the first `total` steps
    of it); `cadence` sets eval_every AND checkpoint_every for a smoke (None keeps the base's)."""
    body = copy.deepcopy(base_body(base))
    body["seed"] = seed
    body["total_steps"] = total
    body["run_name"] = f"r7_{tag}_s{seed}"
    body["init_from"] = donor["path"]
    if cadence is not None:
        body["eval_every"] = cadence
        body["checkpoint_every"] = cadence
    body.setdefault("env_kwargs", {})["seat_tag"] = tag
    col = body.setdefault("collector", {})
    col["process"] = True
    col["search"] = {**SEARCH, "play": LEVER[arm]["play"]}
    ag = body.setdefault("agent", {})
    ag["lr"] = lr
    ag["lr_anneal_steps"] = anneal
    ag["search_targets"] = True
    ag["search_policy_coef"] = LEVER[arm]["search_policy_coef"]
    ag["search_value_head"] = True
    ag["search_value_coef"] = LEVER[arm]["search_value_coef"]
    ag["search_value_blend"] = 0.0
    return body


def write(path: pathlib.Path, head: list[str], body: dict) -> None:
    path.write_text("\n".join(head) + "\n" + yaml.safe_dump(body, sort_keys=False))


# ---- the LR rule ------------------------------------------------------------------------------------------------

def lr_smoke_name(arm: str, lr: float) -> str:
    return f"r7_lr_smoke_{arm}_{lr:g}"


def lr_smoke_dir(runs: pathlib.Path, arm: str, lr: float) -> pathlib.Path:
    """The launcher names a run dir <config basename>_s<seed> (scripts/monster_fleet.sh's TAG)."""
    return runs / f"{lr_smoke_name(arm, lr)}_s{LR_SMOKE_SEEDS[arm][LR_CANDIDATES.index(lr)]}"


def _history(run_dir: pathlib.Path) -> list[dict]:
    """The run's metric rows through merge_history.history_path: history_merged.csv for a RESUMED run (several offline
    wandb runs), else history.csv -- extracted when missing."""
    import csv
    from merge_history import history_path
    if not run_dir.exists():
        raise SystemExit(f"REFUSED: {run_dir} missing -- the smoke has not run")
    return list(csv.DictReader(history_path(run_dir).open()))


def _col(rows: list[dict], key: str) -> list[float]:
    return [float(r[key]) for r in rows if r.get(key) not in (None, "")]


def _tail_mean(vals: list[float], frac: float) -> float:
    tail = vals[-max(1, int(len(vals) * frac)):]
    return sum(tail) / len(tail)


def _tail_ms(vals: list[float], frac: float) -> tuple[float, float, int]:
    tail = vals[-max(2, int(len(vals) * frac)):]
    n = len(tail)
    m = sum(tail) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in tail) / (n - 1)) if n > 1 else float("nan")
    return m, sd / math.sqrt(n), n


def _sh(path: pathlib.Path) -> float:
    if not path.exists():
        raise SystemExit(f"REFUSED: {path} missing -- run the vs-SH evals first (--stage lr-evals prints them)")
    return float(json.loads(path.read_text())["eval/win_rate"])


def read_lr(runs: pathlib.Path, base: str, sh_dir: pathlib.Path, out: pathlib.Path | None = None) -> float | None:
    """The pre-stated LR rule over the nine 2M smokes (three arms at every candidate) and the vs-SH evals. Writes the
    verdict JSON (the fleet stage's only accepted --lr source) and returns the chosen lr, or None."""
    donor_dir = runs / DONOR_DIR[donor_trio(base)].format(DONOR_SEEDS[donor_trio(base)][0])
    ent_ref = _tail_mean(_col(_history(donor_dir), "loss/entropy"), ENT_REF_TAIL)
    sh_donor = _sh(sh_dir / "donor_f1.json")
    per_lr, largest = {}, None
    for lr in sorted(LR_CANDIDATES, reverse=True):
        rows = {arm: _history(lr_smoke_dir(runs, arm, lr)) for arm in LR_ARMS}
        c_kl = _col(rows["control"], "loss/approx_kl")
        s_kl = _col(rows["searched"], "loss/approx_kl_unsearched")
        if not c_kl or not s_kl:
            raise SystemExit(f"REFUSED: lr {lr:g} logged no loss/approx_kl (control) or loss/approx_kl_unsearched (searched) "
                             "-- a missing counter, not a pass")
        c_ent, s_ent = _tail_mean(_col(rows["control"], "loss/entropy"), ENT_TAIL), _tail_mean(_col(rows["searched"], "loss/entropy"), ENT_TAIL)
        c_sh = _sh(sh_dir / f"{lr_smoke_dir(runs, 'control', lr).name}.json")
        s_sh = _sh(sh_dir / f"{lr_smoke_dir(runs, 'searched', lr).name}.json")
        gates = {"control_kl_ok": max(c_kl) <= KL_MAX, "searched_kl_unsearched_ok": max(s_kl) <= KL_MAX,
                 "control_entropy_ok": abs(c_ent - ent_ref) <= ENT_TOL * abs(ent_ref),
                 "control_sh_ok": c_sh >= sh_donor - SH_SHOCK}
        s_klu = _tail_ms(_col(rows["searched"], "search/kl_update"), 0.5)
        b_klu = _tail_ms(_col(rows["beta0"], "search/kl_update"), 0.5)
        margin = 2.0 * math.sqrt(s_klu[1] ** 2 + b_klu[1] ** 2)
        rec = {"passes": all(gates.values()), "gates": gates, "control_max_approx_kl": max(c_kl),
               "searched_max_approx_kl_unsearched": max(s_kl), "control_entropy_tail": c_ent,
               "searched_entropy_tail_read": s_ent, "control_vs_sh": c_sh, "searched_vs_sh_read": s_sh,
               "searched_sh_drop": s_sh < sh_donor - SH_SHOCK,
               "kl_update_last_half": {"searched": s_klu[:2], "beta0": b_klu[:2], "rows": [s_klu[2], b_klu[2]]},
               "not_inert": (b_klu[0] - s_klu[0]) > margin, "not_inert_margin": margin}
        per_lr[f"{lr:g}"] = rec
        print(f"lr {lr:g}: control kl max {max(c_kl):.4f}, searched unsearched-kl max {max(s_kl):.4f}, control entropy "
              f"{c_ent:.4f} (donor {ent_ref:.4f}; searched {s_ent:.4f} read), vs SH control {c_sh:.4f} / searched {s_sh:.4f} "
              f"(donor {sh_donor:.4f}) -> {'PASS' if rec['passes'] else 'FAILS ' + str([k for k, v in gates.items() if not v])}; "
              f"kl_update searched {s_klu[0]:.4f} vs beta-0 {b_klu[0]:.4f} (margin {margin:.4f}) -> not-inert {rec['not_inert']}")
        if rec["passes"] and largest is None:
            largest = lr
    chosen, why = None, None
    if largest is None:
        why = "no candidate lr passed the shock rule"
    elif not per_lr[f"{largest:g}"]["not_inert"]:
        why = f"lr {largest:g} passed the shock rule but the NOT-INERT check failed"
    elif per_lr[f"{largest:g}"]["searched_sh_drop"]:
        why = f"lr {largest:g} passed, but the SEARCHED arm dropped vs SH past {SH_SHOCK}"
    else:
        chosen = largest
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "version": "r7_read_lr/2", "base": base, "chosen": chosen, "largest_passing": largest, "ruling_needed": why,
            "rule": {"candidates": list(LR_CANDIDATES), "kl_max": KL_MAX, "ent_tol": ENT_TOL, "ent_tail": ENT_TAIL,
                     "ent_ref_tail": ENT_REF_TAIL, "sh_n": SH_N, "sh_shock": SH_SHOCK},
            "donor_entropy_ref": ent_ref, "donor_vs_sh": sh_donor, "per_lr": per_lr}, indent=1) + "\n")
    if chosen is None:
        print(f"{why} -- a maintainer ruling before launch, never a default")
        return None
    print(f"CHOSEN LR {chosen:g}")
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", choices=("a", "b", "ab", "w"), required=True)
    ap.add_argument("--stage", choices=("lr-smokes", "lr-evals", "fleet"), default=None)
    ap.add_argument("--read-lr", action="store_true", help="apply the LR rule; writes --lr-verdict")
    ap.add_argument("--lr", type=float, default=None, help="the starting LR (--stage fleet): read_lr.json's choice")
    ap.add_argument("--lr-ruled", default=None,
                    help="a maintainer ruling that sets --lr in place of the rule (quoted into the header)")
    ap.add_argument("--b0", choices=("PASS", "FAIL"), default=None, help="the B0 bench's six-wide verdict (--stage fleet)")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--out", default="configs")
    ap.add_argument("--power", default="results/r7_fleet/power.json")
    ap.add_argument("--sh-dir", default="results/r7_lr", help="the vs-SH eval JSONs of the LR rule")
    ap.add_argument("--lr-verdict", default="results/r7_lr/read_lr.json")
    args = ap.parse_args()

    def path(p: str) -> pathlib.Path:
        q = pathlib.Path(p)
        return q if q.is_absolute() else ROOT / q

    runs, out, sh_dir, verdict = path(args.runs), path(args.out), path(args.sh_dir), path(args.lr_verdict)
    if args.read_lr:
        read_lr(runs, args.base, sh_dir, verdict)
        return
    ds = donors(args.base, runs)
    lines: list[str] = []
    if args.stage == "lr-evals":
        env = "POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 POKEMON_RL_ENCODER_C6=1"
        py = "/opt/anaconda3/envs/pkmn-engine-port/bin/python"
        lines.append(f"{env} {py} scripts/eval_checkpoint.py {ds[0]['path']} --episodes {SH_N} --out {sh_dir / 'donor_f1.json'}")
        for lr in LR_CANDIDATES:
            for arm in ("searched", "control"):
                d = lr_smoke_dir(runs, arm, lr)
                final = final_ckpt(d)
                if final is None:
                    raise SystemExit(f"REFUSED: {d} has no checkpoint -- the smoke has not run")
                lines.append(f"{env} {py} scripts/eval_checkpoint.py {final} --episodes {SH_N} --out {sh_dir / (d.name + '.json')}")
        print("# sequential, one at a time (usernames derive from each checkpoint's seed; never two beside each other)")
        print("\n".join(lines))
        return
    out.mkdir(parents=True, exist_ok=True)
    dlr = donor_lr(args.base)
    if any(c >= dlr for c in LR_CANDIDATES):
        raise SystemExit(f"REFUSED: a candidate lr is not below the donors' own starting lr {dlr:g} (R-F1: a REDUCED lr)")
    power = load_power(path(args.power))
    if args.stage == "lr-smokes":
        for lr in LR_CANDIDATES:
            for arm in LR_ARMS:
                seed = LR_SMOKE_SEEDS[arm][LR_CANDIDATES.index(lr)]
                body = lane_config(args.base, arm, seed=seed, donor=ds[0], lr=lr, total=LR_SMOKE_STEPS,
                                   tag=TAGS[f"lr_{arm}"], cadence=None)
                body["run_name"] = f"{lr_smoke_name(arm, lr)}_s{seed}"
                body["eval_every"] = 100_000_000
                head = header(arm=arm, lane=None, donor=ds[0], all_donors=ds, base=args.base, lr=lr,
                              lr_evidence="an LR SMOKE candidate", b0="n/a", power=power,
                              kind=f"2M LR SMOKE, NOT A PRE-REG RUN (lr {lr:g}, arm {arm})")
                write(out / f"{lr_smoke_name(arm, lr)}.yaml", head, body)
        lines += [f"# the nine LR smokes ({len(LR_CANDIDATES)} lr x {', '.join(LR_ARMS)}), their evals and the rule, orchestrated:",
                  f"bash scripts/r7_smokes.sh lr {args.base}"]
    elif args.stage == "fleet":
        if args.lr is None or args.b0 is None:
            raise SystemExit("--stage fleet needs --lr (the rule's choice) and --b0 (the bench's verdict)")
        if args.lr_ruled:
            lr_evidence = f"set by a maintainer ruling in place of the rule: {args.lr_ruled}"
        else:
            if not verdict.exists():
                raise SystemExit(f"REFUSED: {verdict} missing -- run --read-lr (or pass --lr-ruled with the ruling)")
            chosen = json.loads(verdict.read_text()).get("chosen")
            if chosen is None or abs(float(chosen) - args.lr) > 1e-12:
                raise SystemExit(f"REFUSED: --lr {args.lr:g} is not the rule's choice ({chosen}) in {verdict}")
            lr_evidence = f"the LR rule's choice, {verdict.relative_to(ROOT) if verdict.is_relative_to(ROOT) else verdict}"
        manifest = []
        sm = smoke_steps(args.base)
        for arm in ("searched", "control"):
            for f, seed in enumerate(SEEDS[arm], start=1):
                if arm == "control" and f == 3 and args.b0 == "FAIL":
                    continue
                body = lane_config(args.base, arm, seed=seed, donor=ds[f - 1], lr=args.lr, total=HORIZON, tag=TAGS[arm])
                head = header(arm=arm, lane=f, donor=ds[f - 1], all_donors=ds, base=args.base, lr=args.lr,
                              lr_evidence=lr_evidence, b0=args.b0, kind="", power=power)
                name = f"r7_fleet_{arm}_f{f}.yaml"
                body["run_name"] = f"{name[:-5]}_s{seed}"  # the launcher's run dir: <config basename>_s<seed>
                write(out / name, head, body)
                manifest.append(f"configs/{name} {seed}")
            smoke = lane_config(args.base, arm, seed=SMOKE_SEEDS[arm], donor=ds[0], lr=args.lr, total=sm,
                                tag=TAGS[f"smoke_{arm}"], cadence=SMOKE_CADENCE)
            smoke["run_name"] = f"r7_fleet_smoke_{arm}_s{SMOKE_SEEDS[arm]}"
            head = header(arm=arm, lane=None, donor=ds[0], all_donors=ds, base=args.base, lr=args.lr,
                          lr_evidence=lr_evidence, b0=args.b0, power=power,
                          kind=f"{sm // 1000}k WARM-START SHAKEDOWN SMOKE, NOT A PRE-REG RUN")
            write(out / f"r7_fleet_smoke_{arm}.yaml", head, smoke)
        (out / "r7_fleet_lanes.txt").write_text(
            "# R7 fleet lane manifest (scripts/derive_r7_fleet.py): <config> <seed>, one lane per line, launch order.\n"
            + "\n".join(manifest) + "\n")
        lines += ["# THE SHAKEDOWN SMOKES (R0 gate 1; the agent runs them -- the searched one is killed and resumed):",
                  "bash scripts/r7_smokes.sh shakedown",
                  "# ---- STOP: the fleet launches only after BOTH smokes PASS scripts/r7_smoke_check.py ----",
                  "# THE FLEET (the maintainer launches; over 5 h):",
                  ("ALLOW_SIX_WIDE_DISCLOSED=1 " if len(manifest) == 6 else "") + "bash scripts/r7_fleet_launch.sh configs/r7_fleet_lanes.txt"]
    else:
        raise SystemExit("--stage lr-smokes | lr-evals | fleet, or --read-lr")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
