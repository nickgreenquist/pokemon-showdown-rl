# Handoff — written 2026-08-26, for a fresh-context session

**Nothing is in flight. Tree is clean. Suite is green (538 passed, 17 skipped).
LADDER R1 is COMPLETE at n=200.** Fold this into STATUS.md / SESSION_LOGS.md on
pickup and restore the empty stub.

## Read order

1. `STATUS.md` — authoritative, 60-line cap.
2. **`LADDER_R1_READOUT.md`** — generated, tracked, carries all three
   pre-registered readout obligations. This is the ladder result.
3. The newest SESSION_LOGS entries (2026-08-26). Index with
   `grep -n '^- 20' SESSION_LOGS.md`, read by offset.
4. **Do NOT read `DESIGN.md` for "what next"** — HISTORICAL/SPENT banner.
5. `REPLAY_AUDIT.md` is **n=39 and SUPERSEDED** by the ~175-battle sweep in
   SESSION_LOGS. Where they disagree, the sweep wins.

## WHERE THE LADDER DATA IS — the maintainer asked for this explicitly

`results/` is gitignored with zero tracked files, AND a rated ladder game is
**unrepeatable** — unlike a training run it cannot be regenerated at any price.
Three copies, verified in sync at **200 rows / 217 replays** by
`scripts/backup_ladder.sh` (it exits non-zero if the mirror drifts — run it
after any ladder session):

1. `results/ladder/` — live working copy
2. `../pokemon-showdown-rl-d25-backup-20260815/ladder/` — rsync mirror
3. `~/pokemon-showdown-rl-ladder-archive/ladder_r1_*.tar.gz` — dated tarballs

**The NUMBERS survive separately from the FILES.** `scripts/ladder_readout.py`
writes to a TRACKED path, so losing all three copies still leaves the readout
in git and the method in the script — `scripts/README.md`'s grader-script rule,
applied harder. Regenerate with:

    python scripts/ladder_readout.py
    python scripts/ladder_classify.py

## What the ladder produced

95–105 (0.475); played-only 91/196 (0.464); PS Elo 1000 → **1311** (peak 1348)
against a top-500 cutoff of 1357; 141 distinct opponents; 12.07 h; 6.74
ms/decision. Two independent tallies agree 200/200; **0 decision_errors, 0
mask_desyncs**.

**WE WERE NEVER LISTED, SO GXE AND GLICKO DO NOT EXIST FOR THIS RUN.** The
pre-registered PRIMARY read is UNMEASURED. `stopped_by_rule: false` is CORRECT
— the rule needs rd≤40 AND n≥200 AND being listed. **Quote the Elo; never
project a GXE in either direction.**

Obligation (ii) resolved AGAINST the interesting hypothesis: rematch opponents
are **~113 Elo stronger** (1311 vs 1198), the confound the pre-reg named while
result-blind. The lower rematch rate is opponent selection, not the
deterministic policy being memorised.

## The next task, and it is ONE pre-registration

The maintainer approved (2026-08-26): stop the ladder at 200 ✅, evaluate
outstanding finals, cheap value diagnostics ✅, pre-register the encoder fork,
and **WAIT on retraining until the yardstick changes**.

**Write ONE pre-reg covering the encoder fork AND the measurement change.**
Split them and the first result is ungradeable against the old numbers and the
second has no baseline. Per standing process this is a
2-Opus-agents-plus-review design.

- **Yardstick: promote FP@20 to the PRIMARY credit line, vs-SH to a
  non-regression guard.** CH4 R1 already paid for this — off-SH seed sd 0.0077
  is TIGHTER than vs-SH 0.0112, which is why STATUS has carried "off-SH credit
  line AFFORDABLE" for days without anyone spending it. FP@20 at 1.20 s/battle
  makes a full 3000×3 arm ≈ 3 h. Rationale: search read +0.081 vs SH and
  NEGATIVE on both off-SH opponents (MU-8 z = −2.80) — we have been fooled by
  an SH-facing gain once already, and the ladder is off-SH.
- **Encoder: the fixed-damage defect is the one worth acting on** (below).
- **SCOPE IN A PREREQUISITE:** measuring L2 off-SH is currently IMPOSSIBLE, see
  blockers below. The ensemble seat is part of this work, not before it.

## Blockers and landmines — each already cost time or nearly did

- **L2 CANNOT BE EVALUATED OFF-SH AS-IS. Two blockers.** (a)
  `ch3_fp_h2h.py`'s `ARM_KINDS = (greedy_seat, search_seat, sampled_seat,
  fp_vs_clone)` and it asserts on anything else; L2 is `kind: ensemble` from
  `ladder.py`'s `POLICY_KINDS`, a different namespace — there is no ensemble
  seat in the FP path at all. (b) `eval_checkpoint._opponent_from_checkpoint`
  seats the opponent in a **PoolPlayer that SAMPLES** by contract; building a
  clone h2h on it reproduces **exactly the A1 bias** (~26 points of implied
  rating — the whole "clone intransitivity"). `ch3_fp_h2h.py`'s `SeatPlayer`
  is the deterministic one and is the right home.
- **ENCODER DEFECT WORTH FIXING: fixed-damage moves.** poke-env gen-1 gives
  `seismictoss / superfang / nightshade / dragonrage / sonicboom`
  `basePower == 1`, so `_fill_move` writes 0.01 where Thunderbolt gets 0.95,
  and nothing in the 46-dim move block says "flat level damage". Measured cost
  on guaranteed holders: **Super Fang 0/59 for us vs 36% for humans**; Seismic
  Toss 0.141 vs 0.289 (z = −3.39). The multiplier is NOT wholly spurious —
  gen-1 Seismic Toss really is Ghost-immune, so only the 2×/0.5× is wrong.
- **ENCODER DEFECT THAT IS INERT — do not sell it as a win.** `bool([])` is
  False, so `_move_slots_aliased` returns "not aliased" on force-switch turns
  and four move blocks describe the FAINTED mon at `known=1.0` while `vec[5]`
  reads 0 (42/42 confirmed). Zeroing them flips **0/42** choices, and fixing it
  moves existing checkpoints OFF-distribution.
- **"Retrain longer" is the one lever with direct evidence against it.** D29r2
  at 50M read 0.70222 — R-B FLAT vs the 12M stack.
- **Don't scope a null result wider than the instrument.** `diag_encoder_live`
  concluded "no encoder bug" while gating on `if legal_moves:` — which excludes
  force-switch turns, exactly where the bug was.
- **Small n was re-paid twice this session.** An n=40 value probe gave AUC
  0.964; at n=300 it is 0.891. And a 10-battle probe suggested the critic was
  worse off-SH; at n=300 it is BETTER at every material level. Do not quote an
  AUC to three digits off tens of battles.
- **Changing `OBS_DIM` invalidates every checkpoint** — one fork, and evaluate
  what matters first. That list is small: 132 checkpoints on disk but only 13
  sha-pinned, and essentially all already carry banked vs-SH numbers.

## Open

- **13 commits are UNPUSHED.** The maintainer must be asked before any push.
  Worth raising early: the committed artifacts (readout, scripts, docs) exist
  only in this machine's local git, which is a durability gap of the same kind
  the ladder backups were built to close.
- `CLEANUP.md` — the audit backlog needing rulings (RESULTS.md staleness was
  fixed 2026-08-25; the rest stands).
- Seeds 66/67, 75/76, 83/84, 93/94 remain HELD.
