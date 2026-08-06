# Handoff — written 2026-08-06, end of the Foul Play day

**⚠ Run the next session on OPUS at HIGH effort** (`/model`, `/effort`). If it is not on that
setting, say so before doing anything else.

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

## State: green, committed, nothing running

Suite **241 passed**. Tree clean. No processes alive. Showdown server **UP on :8000** — reuse
it, do not start a second one. **40 commits unpushed**; pushing has never been asked for and is
still the maintainer's call.

Today was one long day (the maintainer lifted the >5min handover rule and was remote). Nine
SESSION_LOGS.md entries dated 2026-08-06 are the record — **do not restate them**; they contain
the numbers, the pre-registrations, and roughly a dozen self-corrections.

## What exists now that did not this morning

- **Foul Play is a working, measured teacher.** Patched into gen1 (7 files,
  `scripts/patches/foulplay_gen1_local.patch`, applied to `../foul-play`), engine rebuilt for
  gen1, **0.8333 vs SH (n=1200)**.
- **A demonstration pipeline, gate-green at scale.** FP tapes every protocol frame + each
  decision with its full pre-truncation search policy and per-action values;
  `scripts/tape_to_dataset.py` replays tapes OFFLINE through poke-env's own parser. Six gates,
  all passing on 29,844 decisions. `scripts/obs_fidelity_check.py` proves offline replay
  reproduces LIVE observations bitwise, with a coverage gate.
- **1,200 battles of tapes on disk** (`data/fp_tranche`, 111 MB) and their reconstruction
  (`data/fp_tr_*.npz`, 29,844 rows). Tapes are the durable artefact: an encoder change is a
  re-embed (minutes), not a re-collection.
- `scripts/train_bc.py` does soft targets, teacher-value critic, shard merging, by-battle
  learning-curve rungs, and agreement conditioned on opponent-reveal fraction.

## The three numbers that matter

    Foul Play (teacher)     0.8333 vs SH (n=1200) | 0.876 vs our RL | 0.872 vs the BC-SH clone
    BC clone of Foul Play   0.3683 vs SH (n=600, 30k rows) — BELOW the SH clone's 0.4657
    BC agreement curve      0.343 / 0.351 / 0.398 / 0.4215 at 3.75k / 7.5k / 15k / 30k rows

**The teacher is NOT SH-exploiting** — it is *stronger* off the SH board, so §11's own trap
does not fire. That was the red-team's central objection and it is answered.
**The clone is currently the FLOOR, not the ceiling** — agreement 0.42 against the SH clone's
0.86 explains it, and 30k rows is 1/27th of P4's 813k.

## The open question, and the cheapest way to answer it

**Does agreement convert to win rate fast enough to ever clear 0.4657?** We have exactly one
point on that line (0.42 → 0.368). Collect to ~120k rows (~4x the tranche, **~2 h at 3-wide**),
re-fit, re-score the clone. Two points tell you whether this chapter can reach the field, for a
fraction of a full commitment. Do that before buying P4-scale (35,471 battles, 19.7 h).

Commands: 3 lanes of `foulplay_vs_sh.py --seat heuristics` + `run.py --bot-mode challenge_user`
with `FP_TAPE_DIR` set (exact form in the 2026-08-06 tranche log entry), then
`tape_to_dataset.py`, then `train_bc.py --target soft --max-rows N`.

## Do NOT rediscover these

- **The set prior is INERT on agreement.** All three path reviewers converged on "the encoder
  deletes the opponent-set information the teacher conditions on"; I implemented it (zero
  OBS_DIM, faithful to Showdown's generator, supplies 3.16 certain opponent moves/decision) and
  then **ablated it on the same tapes: 0.4215 vs 0.4189, z +0.21. No benefit.** The
  reveal-conditioned falsifier is flat in both conditions. Keep it (free, removes a real
  asymmetry) but **do not quote it as an improvement**, and do not re-derive the hypothesis.
  Ablate with `POKEMON_RL_NO_SET_PRIOR=1`.
- **Soft targets do not improve agreement** (0.4215 vs hard 0.4212) — they were adopted for
  ENTROPY and they deliver there: fitted 1.449 (soft) vs 1.255 (hard) vs teacher 1.098.
- **The [0.2, 1.0] R0 entropy band is wrong in BOTH directions for warm starts.** Measured
  teacher entropy is **1.092 nats** (top-1 prob 0.603). Re-derive the band from that before the
  first warm-started run; do not inherit it.
- **3-wide collection is LINEAR** (3.02x, 5.7-5.9 s/battle/lane vs 6.03 solo) — unlike our own
  collection's -20%. 8-wide is still untested arithmetic.
- **A gen9 engine build fails LOUDLY**, not silently: 2-5 over 7 battles then a
  `pyo3_runtime.PanicException`. Verify the build by MODULE PATHS in the compiled `.so`
  (`src/gen1/` present, `src/genx/` absent); move-name tables are shared and prove nothing.
- **SH never uses a setup move, in any generation** (poke-env's dead `move.target == "self"`
  vs a Target enum, since 2024-04). Consequence beyond SH's strength: an SH-vs-SH run cannot
  emit `|-boost|`, which is how the first obs-fidelity proof came out ~half a proof.
- **`--drop-trap` is dead code**: trap_kind is `{slp, frz}` only, never `trap`, across every
  tape. Untested mitigation for the one poke-engine modelling defect we know about.
- Foul Play needs its OWN conda env (`foul-play`, py3.11). Never the repo env.

## Still open, deliberately

1. **§11 (D8/D9) is still unratified.** The gate is passed and now non-SH-corroborated.
2. **Push or not** (40 commits).
3. No measurement anywhere in this repo shows **RL from a BC warm start improving on its
   starting checkpoint** (SH clone 0.4657 → RL 0.4607). This is the chapter's real risk and it
   is unaddressed.
4. `train_bc.py` still needs an explicit RL-phase design: `entropy_coef`, a KL-to-BC penalty
   instead of an entropy bonus, and R0 gates derived from the measured entropy.
5. The next encoder candidates (STAB, secondary-effect status + probability) are unscreened —
   and given the set prior came back inert, screen them on the tranche before believing them.
