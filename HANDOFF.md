# Handoff — written 2026-08-25 for a cleared-context session

You are picking up a project that just **closed two chapters cleanly and is
one step from its first ladder run.** Nothing is broken, nothing is
mid-flight, the tree is clean and pushed, and the test suite is green
(`pytest tests/` → 495 passed). Fold this file back to the empty stub on
pickup (`# Handoff` + the "(empty — write here only when the maintainer asks
for a handoff)" line).

## Read order

1. `STATUS.md` (authoritative, 60-line cap).
2. The **three 2026-08-25 SESSION_LOGS entries**: the CH4 R1 readout, the
   Amendment A1 entry, and the wave-part-1 entry. Index with
   `grep -n '^- 20' SESSION_LOGS.md`, then read by offset — never a broad
   keyword grep.
3. `CLAUDE.md` landmines, especially the **new Foul-Play runner block**.
4. **Do NOT read `DESIGN.md` for "what next"** — it now carries a banner
   saying it is historical and spent. Its queue is executed/killed/superseded.

## Where things actually stand

- **Headline: 0.71825 vs SH** (D26 12M, credited). **0.79283 with
  inference-time search** (credited, SH-facing caveat). Both UNTOUCHED by
  recent work.
- **Chapter 3 (search): CLOSED.** Search is real and **inference-only** —
  distilling it into weights made every lane worse (B5+KILL).
- **Chapter 4 R1 (off-anchor): CLOSED 2026-08-25.** The Foul-Play gap is
  **raw strength, not an off-distribution hole**: BT residual
  **+0.005 ± 0.013**, anomalies >2.6 points excluded at 95%, and **0 of 4**
  tape mechanism cells fired. The datum that motivated the whole hypothesis
  (we "crush" the FP clone 0.894) was a **policy-form measurement artifact**
  — match the clone's form to its own rating and the intransitivity vanishes.
- **Durable deliverable:** an off-SH credit line is now **affordable** —
  seed spread off-SH is 0.0077, *tighter* than vs-SH's 0.0112, so a future
  off-anchor bar sits at the ordinary 0.025 floor. That instrument did not
  exist before this rung.

## THE NEXT TASK: the ladder — and what is NOT built

The maintainer said "near ready for the ladder. I'm expecting to set it up
soon." The 2026-08-23 deferral (ladder waits until the models are exhausted
vs SH **and** Foul Play) is **satisfied** as of CH4 R1. So this is live —
**but confirm with the maintainer before building; it is their call, and
option (c) of the MU-4 ruling was deliberately left to them.**

**Three traps to know before you start:**

1. **`scripts/score_ladder.py` IS A FALSE FRIEND.** It is a Connect-4-era
   *checkpoint-rung* scorer (scores `ckpt_*.pt` against fixed local anchors).
   It has nothing to do with the Showdown ladder. Do not "reuse" it.
2. **Nothing in this repo connects to the real Showdown.** Every path is
   `localhost:8000` (`rl/envs/showdown.py`'s own docstring says so). Real
   ladder play needs: a genuine account + auth (note
   `scripts/foulplay_vs_sh.py:116` — play.pokemonshowdown.com demands an
   assertion **even in guest mode**, which the local `--no-security` server
   does not), rate/etiquette handling, and a results scraper. **This is new
   construction, not a config change.** Price it honestly.
3. **Do not project a GXE number.** The old "vs-SH ~40% GXE" rule of thumb
   is **RETIRED** — it was calibrated at the 0.4607 era. At 0.71825 we are
   ≈ **+163 Elo vs SH**, and the conversion has run out of road in *both*
   directions (vs-SH past parity over-reads as SH-exploitation; but CH4 R1
   showed there is no hidden off-distribution deficit either). The rewritten
   note is at the top of `prior_work/README.md`. **The whole point of the
   ladder is that this is the project's largest unmeasured quantity.**

## CLOSED — do not reopen without new outside evidence

- **Actor expert iteration: KILLED** (R5b). No policy+value, no
  multi-iteration, no temperature re-sweep, no larger-n retest.
- **Off-anchor robustness levers** (τ-DIV, POOL-SPAN, exploiter family):
  shelved — CH4 R1 showed there is no robustness gap to treat.
- **Critic-value family:** shelved by maintainer ruling ("a then c, skip b").
- **Scale: dead** (50M flat vs 12M). **Critic capacity: moot** (D22's
  "srank 7–11 of 384" is STALE; D26 measures 49/51/35/52 — ~88% idle).
- **Architecture (reviewed 2026-08-25, NOT recommended):** we are 626k actor
  / 1.17M total, no attention. The right comparable is **Huang & Lee at
  1.33M, also attention-free, also pure self-play randbats — 72% GXE. We are
  at 88% of its size, i.e. NOT undersized.** Attention here is **untested,
  not refuted** (killed pre-launch on a 34.6× CPU microbenchmark, never
  trained). If architecture is ever revisited, the ordered list is
  **temporal context first** (both large comparables have 64–256 turns of
  history; we are single-snapshot Markov; a cheap 22-dim design already
  exists at `prior_work/HISTORY_FEATURES_DESIGN.md`), then the **skipped
  middle rung** (explicit two-tower/DCN crossing — absent from the record
  entirely), then attention. Full numbers are in `prior_work/README.md`
  under the ps-ppo clone entry.

## Fresh landmines from this session (all fixed; do not reintroduce)

- **Runner orphan-on-kill:** `( ... ) &` made `$!` the subshell's pid, so
  every kill orphaned a live foul-play holding the **username** →
  `|nametaken|` deadlock → **3.6 h at zero progress that looked like slow
  progress.** Fixed with `exec` + username sweep + a deadlock detector.
- **A wall-clock ETA is not progress.** Sanity-check s/battle against a
  comparable completed arm (FP@20 ≈ 1.2–1.5 s, FP@100 ≈ 6–7 s).
- **FP's normal exit can be logged as a crash**, and the blind n_eff rule
  would then delete a real battle. G2's real test is that **two independent
  tallies agree** (FP's own `Winner:` lines vs the seat).
- **FP anchor is now FP@20** (CLAUDE.md amended): 5.1× cheaper, strength and
  style equivalent, but marginally *weaker* — **name the budget in every
  quote**, never mix FP@20 and FP@100 numbers.
- **A clone h2h is never style evidence**, and any anchor must match the
  policy form of the rating it is compared against.

## Git / artifacts

- Pushed through the CH4 R1 readout; tree clean; suite green (495 passed).
- `results/` is gitignored and is the ONLY copy — `ch4_r1_offsh` and
  `design_fp_gap` are mirrored to
  `../pokemon-showdown-rl-d25-backup-20260815/` (stdout tapes excluded:
  ~3.4 GB, regenerable).
- Ratified pre-reg: `configs/eval/ch4_r1_offsh_instrument.yaml` (carries its
  bracket rulings MU-1..MU-11b and Amendment A1). Readout:
  `results/ch4_r1_offsh/r1_readout.json`.
- **Training seeds 66/67, 75/76, 83/84, 93/94 are ALL still HELD** — CH4 R1
  burned none.
