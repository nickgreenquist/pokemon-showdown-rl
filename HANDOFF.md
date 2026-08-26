# Handoff — written 2026-08-26 (morning), for a fresh-context session

The first real ladder run is finishing at its pre-registered n=200 floor. This
file exists mainly to answer one question the maintainer asked explicitly:
**where does the ladder data live, and how do you get the numbers back if it
is gone?** Fold this into STATUS.md / SESSION_LOGS.md on pickup and restore the
empty stub.

## WHERE THE LADDER DATA IS — read this first

`results/`, `runs/` and `data/` are **gitignored with zero tracked files**. The
ladder JSONL and its 200+ replays are NOT in git and never will be. A rated
ladder game is also **unrepeatable** — you cannot re-play it — so unlike a
training run, losing these files loses the measurement permanently.

Three copies, kept in sync by `scripts/backup_ladder.sh` (run it after any
ladder session; it verifies the mirror matches and exits non-zero if not):

1. `results/ladder/` — the live working copy
2. `../pokemon-showdown-rl-d25-backup-20260815/ladder/` — rsync mirror
3. `~/pokemon-showdown-rl-ladder-archive/ladder_r1_*.tar.gz` — dated tarballs

**The NUMBERS survive separately from the files.** `scripts/ladder_readout.py`
writes **`LADDER_R1_READOUT.md`** to a TRACKED path in the repo, so even losing
all three copies leaves the readout, and the script leaves the method. This is
the same rule `scripts/README.md` records for grader scripts: a script is the
committed provenance for its number.

To regenerate everything from the artifacts:

    python scripts/ladder_readout.py      # all three obligations -> tracked md
    python scripts/ladder_classify.py     # the played/non-game cut

## What the run produced

Read **`LADDER_R1_READOUT.md`** — it is generated, current, and carries all
three pre-registered readout obligations. The headline that must travel with
every quote: **we never got listed on the top-500, so GXE and Glicko DO NOT
EXIST for this run and the pre-registered PRIMARY READ IS UNMEASURED.** The run
stopped at the n floor, not by the stopping rule (`stopped_by_rule: false` is
correct — the rule also requires being listed). Quote the Elo and the
descriptive rates; never project a GXE.

Obligation (ii) resolved cleanly and against the interesting hypothesis: the
rematch cell's opponents are **~118 Elo stronger** than first-encounter
opponents, which is the confound the pre-reg named in advance. The lower
rematch win rate is opponent selection, not the agent being memorised.

## What was decided this session (maintainer, 2026-08-26)

1. **Ladder stops at 200.** Done — it was launched with `--battles 200`.
2. **Evaluate all outstanding finals: yes.** Scoped and much smaller than it
   looks — 132 checkpoints on disk but only 13 sha-pinned, and essentially all
   already carry banked vs-SH numbers. **The one real hole: the L2 ensemble —
   the exact arm that just played 200 ladder games — has never been measured
   off-SH.** The pre-reg's own table says `unmeasured` vs both the BC clone and
   Foul Play. That is the outstanding eval, and it is ~3 h.
3. **Cheap value-head diagnostics: done, and both hypotheses FAILED** — see
   `scripts/diag_value_head.py` and the session log. The critic is well
   calibrated and gets *sharper* at low material (AUC 0.964 at 1 mon left), and
   it tracks progress rather than own-HP. So neither the heal loops nor the
   endgame collapse is a value-shape problem, and the gamma/horizon lever has
   no support. **Caveat: that ran vs the heuristics opponent, i.e. SH-like
   play. Re-run vs Foul Play before believing it applies to the ladder.**
4. **Pre-register the encoder fork: approved.** Per standing process this is a
   2-Opus-agents-plus-review design.
5. **Retrain: WAIT.** The maintainer's call, and it is the important one:
   *"only measuring vs SH is holding us back — we should also measure gain vs
   FP, which is closer to real humans."* This is right and the project already
   paid for the instrument (CH4 R1: off-SH seed sd 0.0077, TIGHTER than vs-SH
   0.0112 — hence STATUS's long-standing "off-SH credit line AFFORDABLE",
   never spent). FP@20 at 1.20 s/battle makes a full locked-protocol arm
   (3000 x 3) about 3 hours. **Proposal on the table: promote FP@20 to the
   PRIMARY credit line and demote vs-SH to a non-regression guard.** The
   encoder fork and the protocol change must be ONE pre-reg — changing the
   yardstick and the model separately leaves the first result ungradeable
   against the old numbers and the second with no baseline.

## Things that will bite you

- **`bool([])` is False.** `_move_slots_aliased` therefore returns "not
  aliased" on force-switch turns, and the encoder fills 4 move blocks from the
  FAINTED active with `known=1.0` while `vec[5]` reads 0. Confirmed 42/42.
  **Measured inert** — zeroing those blocks flips 0/42 choices — and "fixing"
  it moves existing checkpoints off-distribution. Do not treat it as a win.
- **Fixed-damage moves encode as base power 1.** Seismic Toss / Super Fang /
  Night Shade / Dragon Rage / Sonic Boom all have `basePower == 1` in poke-env
  gen-1 data, so the encoder describes an 80-damage Seismic Toss as 1/80th of a
  Thunderbolt. Measured cost: **Super Fang 0/59 for us vs 36% for humans.**
  This is the one encoder finding worth acting on.
- **Do NOT scope a null result wider than the instrument.** `diag_encoder_live`
  concluded "no encoder bug" while gating on `if legal_moves:` — which excludes
  force-switch turns, exactly where the bug was.
- **"Retrain longer" has been measured and was flat.** D29r2 at 50M read
  0.70222, R-B FLAT vs the 12M stack. More steps is the one lever with direct
  evidence against it at the current recipe.
- `REPLAY_AUDIT.md` was written at n=39 and its rates are **superseded** by the
  n~175 sweep recorded in SESSION_LOGS. Where they disagree, the sweep wins.
