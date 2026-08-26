# `scripts/` — what is here, and why almost none of it is safe to delete

Written 2026-08-25 after an audit of all 69 scripts. Read this before any
cleanup sweep of this directory.

## The one fact that governs everything here

**`results/`, `runs/` and `data/` are ALL gitignored, with zero tracked
files.** Verified: `git ls-files results | wc -l` → 0, same for `runs` and
`data`. Every readout JSON, every chunk file, every banked number lives on
one disk and is *not* in the repo.

The consequence is not obvious and it is the whole point of this file: **a
grader script is not "spent" once its rung closes — it is the only committed
provenance for the number it produced.** Deleting `scripts/d26_grade.py`
makes the project's headline (0.71825) unreproducible from the repo alone.
Roughly 30 files here are in that position. "Nothing references it" is
therefore *not* evidence that a script is dead.

Of 69 scripts, exactly **two** are genuine delete candidates
(`play_vs_agent.py`, `record.py` — 215 lines of 18,577, i.e. 1.2%).

## The trap: `ch3_*` is not all Chapter 3

A naive "Chapter 3 is closed, delete `ch3_*`" sweep destroys the **live
Foul-Play anchor machinery**. These three are current, not historical:

| file | why it is live |
|---|---|
| `ch3_r4_fp_runner.sh` | invoked by `configs/eval/ch4_r1_offsh_instrument.yaml`; its three landmines are documented in `CLAUDE.md` |
| `foulplay_vs_sh.py` | shelled out to by that runner; drives the FP side of every anchor |
| `patches/foulplay_gen1_local.patch` | a **G8 provenance-stamp input** — every FP number is "Foul Play + our patches" |

`ch3_fp_h2h.py` is likewise still the seat used by the CH4 R1 arms, and its
`SeatPlayer` is the pattern `ladder.py` was built from.

## Live machinery (reusable, not chapter-bound)

- `ch5_seat_equiv.py` — **CH5 R1 BUILD gate.** Proves the ensemble seat added
  to `ch3_fp_h2h.py` decides IDENTICALLY to `ladder.py`'s path, so an off-SH
  number for "L2" rates the object that actually played the 200 rated games.
  It re-implements `ladder.py::_load` verbatim rather than importing it, on
  purpose: an edit to either path then shows up here as a disagreement. E2's
  divergence percentages are OFF-DISTRIBUTION (random Gaussian obs) and are
  never an in-play flip rate — that number is `ensemble/flip_rate`, stamped
  into every ensemble arm's report.
- `our_style.py` (in `replay_audit/`) — puts US in the style table the anchor
  profiler built for SH and the clone. Its human row is bit-identical to
  `anchor_style.py`'s by construction.
- `ladder.py` — **the real Showdown ladder**. The only path that leaves
  localhost. Pre-reg `configs/eval/ladder_r1.yaml`.
- `ladder_classify.py` — readout obligation (iii) for that pre-reg: played
  games vs non-games. NOT optional and NOT reproducible by grep — the
  pre-reg's own grep was falsified at n=26 (a 32-turn abandonment and a
  1-turn no-show emit the SAME `lost due to inactivity` string). The ratified
  instrument is "did the opponent ever submit a move". Pinned by
  tests/test_ladder.py::TestGameClassification.
- `eval_checkpoint.py` — **the locked protocol** (final ckpt, 3000 battles,
  deterministic, ties as non-wins). This is the vs-SH instrument.
- `ch3_eval.py`, `ch3_fp_h2h.py`, `ch3_r4_fp_runner.sh`, `foulplay_vs_sh.py`
  — anchor machinery, see above.
- `extract_history.py`, `setup_showdown.sh`, `watch.py` — utilities.
- `ch3_r2_grade.py`, `d25_grade.py`, `d25_gates.py` — imported unmodified by
  later graders; these are the shared statistical law, not one-offs.

## `score_ladder.py` is a FALSE FRIEND

Connect-4-era *checkpoint-rung* scorer: every `ckpt_*.pt` against local
anchors at 400 episodes. It is **not** the locked protocol and has **nothing
to do with the Showdown ladder**. Kept for predecessor lineage only. Use
`eval_checkpoint.py` (locked protocol) or `ladder.py` (real ladder).

## Chapter → grader → banked output

Each closed rung's grader is the committed provenance for its number.

| chapter | grader | banked result |
|---|---|---|
| D18 | `d18_grade.py` | privileged critic NULL (killed) |
| D22 | `d22_dormant_rank.py`, `d22_weight_norms.py` | critic rank diagnostics |
| D23 | `d23_grade.py` | L2-init, letter-met, NOT credited |
| D24 | `d24_interp_null.py`, `d24_null_match.py` | interpretability null |
| D25/D25-P | `d25_grade.py`, `d25_gates.py`, `d25_atoms.py`, `d25*_manipulation.py` | aux-loss cycle |
| D26 | `d26_grade.py`, `d26_gates.py` | **headline 0.71825** |
| D28 | `d28_grade.py` | zeroinfo control |
| D29 / D29r2 | `d29_grade.py`, `d29r2_grade.py` | 50M scale = dead (0.70222) |
| CH3 R0 | `ch3_grade.py`, `ch3_audit.py` | **ensemble 0.74633** (the ladder primary) |
| CH3 R1 | `ch3_fidelity_check.py`, `ch3_harvest.py`, `ch3_turnorder_diag.py` | bridge fidelity |
| CH3 R2 | `ch3_r2_grade.py`, `ch3_r2_falsifier.py` | **search@M 0.79283** + the SH-facing falsifier |
| CH3 R3 | `ch3_r3_grade.py`, `ch3_oracle_diag.py` | dose/evaluator cells |
| CH3 R4 | `ch3_r4_grade.py`, `ch3_r4_anchor_grade.py`, `ch3_r4_anchors.py` | anchor battery |
| CH3 R5a/R5b | `ch3_r5a_grade.py`, `ch3_r5b_*.py`, `ch3_r5_power_sim.py` | B5 + KILL (search does not compile into weights) |
| CH4 R1 | `ch4_r1_grade.py`, `ch4_fp_tape_parse.py`, `ch4_sp_baseline.py`, `ch4_r1_wave.sh` | off-anchor NO_ANOMALY; **these four are named in the pre-reg's `instruments:` block** because they had zero references and looked like orphans |

## Known reproducibility gaps (not fixed, recorded)

- `d25_atoms.py` imports `rev1_check` / `gate_r012` from `results/d25/scripts/`
  — a **gitignored, untracked** directory. `d25_gates.py` deliberately
  re-implemented those rather than import them, for exactly this reason;
  `d25_atoms.py` did not get that treatment.
- `tests/test_opp_action.py` names `scripts/gate_r012.py` and
  `rl/networks/zeroinfo.py` names `scripts/z1_1.py`. Neither is in `scripts/`;
  both live under gitignored `results/`. A fresh clone cannot resolve either.

## Genuine delete candidates

- `play_vs_agent.py` — human-play toy. Its own docstring: "nothing here
  writes to `results/`". Zero references, no number depends on it.
- `record.py` — MinAtar GIF renderer; this repo has been Showdown-only since
  Phase 5. It is the sole reason `imageio` is pinned in `pyproject.toml`.

## One true duplicate

`d29_grade.py` vs `d29r2_grade.py`: 191 of 197 lines identical, differing
only in a seed tuple and two paths. Do **not** just delete one —
`RESULTS.md` cites `d29_grade.py` by path as the attestation record for the
D29r VOID verdict, a published negative result.
