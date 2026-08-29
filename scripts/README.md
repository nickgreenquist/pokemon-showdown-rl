# `scripts/` — what is here, and why almost none of it is safe to delete

Written 2026-08-25 after an audit of all 69 scripts. Read this before any
cleanup sweep of this directory.

**Extended 2026-08-28.** The directory is now **94 `.py`/`.sh` files** (84 at
this level, 10 under `replay_audit/`); the 69-script counts below are as
written and are not re-derived. The additions are the ladder-ops chain, the
CH5 R1 instrument and the wave runners — the three newest groups, and exactly
the ones a sweeper finds with no provenance. Everything the 2026-08-25 audit
said still holds, including the governing fact immediately below.

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
- `ch5_seat_smoke.py` — **does a seat actually PLAY?** Runs `ch3_fp_h2h.run()`
  verbatim with a local `SimpleHeuristicsPlayer` standing in for Foul Play, so
  it needs only the local server. Run it whenever a new arm kind is registered,
  BEFORE spending a Foul Play arm on it — `ch5_seat_equiv.py` proves a seat
  DECIDES right and cannot prove it can play. Its win rates are not results.
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

## The ladder-ops chain (added 2026-08-28)

Everything that runs, supervises or reads a **real rated ladder run**. A rated
game is **unrepeatable** — you cannot re-play it — so this group is the one
place where losing an artifact loses a measurement permanently.

| file | what it is |
|---|---|
| `ladder.py` | the runner — the only path that leaves localhost. All inputs required (correct; do not add defaults). Pre-regs `configs/eval/ladder_r1.yaml` (R1), `ladder_r3.yaml` (R3, and the one whose stopping rule can fire) |
| `ladder_supervise.sh` | relaunch across websocket drops — poke-env's `ps_client.listen()` catches `ConnectionClosedError`, logs it and RETURNS, with **no reconnect**, leaving a live process at 0% CPU and no socket. `--battles` is a cumulative target, so relaunch-with-same-target is the resume |
| `ladder_watchdog.sh` | kills the HUNG runner the supervisor cannot see (the supervisor only acts when its child EXITS). **Its test is socket absence, not the clock** — a turn-1000 auto-tie is a real multi-hour game and killing one forfeits a rated match |
| `ladder_readout.py` | the R1/R3 readout: all three pre-registered obligations in one pass (rating trajectory from replays, the rematch cell with its opponent-rating confound, played-vs-non-games). Writes `LADDER_*_READOUT.md` to a **tracked** path — that markdown is the only provenance that survives losing `results/ladder/` |
| `ladder_classify.py` | obligation (iii), and **not reproducible by grep**: the pre-reg's own grep was falsified at n=26 (a 32-turn abandonment and a 1-turn no-show emit the SAME `lost due to inactivity` string). Ratified rule: "did the opponent ever submit a move". Pinned by `tests/test_ladder.py::TestGameClassification` |
| `ladder_move_audit.py` | descriptive: did we pick a materially worse damaging move when a better one was available? Gen-1 damage model, three disclosed approximations that set its error bars (no PP, no Atk/Def ratio, lower-bound movesets). The same-category count is the defensible number |
| `backup_ladder.sh` | the three-copy arrangement for `results/ladder/` (live / rsync mirror / dated tarballs). Run after any ladder session |

**⚠ THE THREE READOUT TOOLS DEFAULT TO LADDER R1 — PASS EVERY FLAG, ALWAYS.**
`ladder_readout.py` and `ladder_classify.py` default `--jsonl` and `--replays`
to `results/ladder/L2.battles.jsonl` / `results/ladder/replays`, `--name` to
**`nickgen1rbrlbot`** (R1's account), `--label` to `R1` and `--out` to
`LADDER_R1_READOUT.md`; `ladder_move_audit.py` has **no argparse at all** and
hardcodes both (`US = "nickgen1rbrlbot"`, `results/ladder/replays`).
`ladder_supervise.sh` takes the arm as an argument but **hardcodes
`ladder_r3.yaml`** — an R4 driven through it silently runs under R3's rules.
The failure is quiet, not loud: forget only `--name` on an R3 readout and you
fetch R1's profile into an R3-labelled file, `load()` nulls `_true_rating` on
every row, and the exhaustiveness assert still passes. Treat every default
here as R1-specific until the inputs are made required (`REPO_CLEANUP.md`
item 9).

## CH5 R1 — the live instrument (added 2026-08-28)

The current chapter's machinery. `ch5_seat_equiv.py` and `ch5_seat_smoke.py`
are described under "Live machinery" above; the wave chain is:

| file | what it is |
|---|---|
| `ch5_preflight.sh` | run IMMEDIATELY before the wave; exits non-zero on anything that would make it unquotable. Includes two CLAUDE.md landmine checks: `showdown/config/config.js` `simulator: 4` (gitignored, silently resets on re-clone, worth +81% collection throughput) and the G0 clean-tree check (one untracked `.md` stamps `git_dirty` on every arm) |
| `ch5_r1_wave.sh` | the wave driver, **strictly serial, k=1** — every CH5 arm enters a comparison, so overlapping arms contend and void it. It is also G-SERIAL's artifact: it writes the `wave.log` start/done timestamps that `ch5_r1_grade.py` asserts do not overlap |
| `ch5_r1_grade.py` | the off-SH gate/grade instrument. Before it existed the pre-reg's whole Q7 gate block was PROSE that nothing in the tree applied. Implements G2 as a **three-way exhaustive tally** against FP's own stdout — never a subtraction, and `Winner: None` IS the tie |
| `ch5_watchdog.sh` | polls the wave, appends `ALERT` lines, **never kills anything** (the runner owns that). Written after a wave where three arms died in 30 s each and a fourth stalled at 93%, unnoticed for hours |

## Wave runners — provenance for banked waves, not deadwood (added 2026-08-28)

Each is the committed record of HOW a closed wave was actually executed —
launch order, gates, stagger, relaunch policy — which the grader does not
capture. Keep them for the same reason the graders are kept.

| file | wave |
|---|---|
| `ch3_r4_run_sweep.sh` | CH3 R4 ensemble-critic sweep (`configs/eval/ch3_r4_ensemble_critic.yaml` SCHEDULE): A0 → F4 band read → WAVE_A → WAVE_B, chunk-file liveness, max 2 relaunches |
| `ch3_r5a_run_tgate.sh` | CH3 R5a T-GATE wave (`ch3_r5a_tgate.yaml`): per lane, T_M launches at T_S's midpoint chunk so its span nests inside T_S's |
| `ch3_r5b_run.sh` | CH3 R5b exit wave (`ch3_r5b_exit.yaml`), three resumable phases: `collect` → `fits` → `read` |
| `ch4_r1_wave.sh` | CH4 R1 — also named in that pre-reg's `instruments:` block (see the chapter table) |

All four are **bash-3.2-safe on purpose** (no `${var,,}`, no associative
arrays, no `mapfile`) and all stagger starts ~30 s: liveness is **chunk-file
progress, never directory existence**, and a cold start can SIGSEGV in torch
lazy static init before any log line exists. Both are CLAUDE.md landmines.

## `score_ladder.py` is a FALSE FRIEND

Connect-4-era *checkpoint-rung* scorer: every `ckpt_*.pt` against local
anchors at 400 episodes. It is **not** the locked protocol and has **nothing
to do with the Showdown ladder**. Kept for predecessor lineage only. Use
`eval_checkpoint.py` (locked protocol) or `ladder.py` (real ladder).

**It backs no banked number here**, and as of 2026-08-28 it says so itself —
the same warning now heads the file, so a reader who never opens this README
still gets it. Two specifics worth knowing before you run it on a Showdown
run dir: its default `--opponents random heuristic` is wrong for Showdown
(the env key is `heuristics`), so it prints the `random` row, flushed, and
then dies — and "fixing" that by passing `--opponents random` alone prints a
full page of plausible per-rung numbers and exits 0. It also scores
INTERMEDIATE checkpoints at 400 episodes, both of which the locked protocol
forbids. **Deleting it is a maintainer call, not an agent's.**

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

## Known reproducibility gaps — CLOSED 2026-08-29 (CLEANUP B1)

Both gaps recorded here are fixed by vendoring: `gate_r012.py`,
`rev1_check.py`, `analyze_oppact.py` (the d25_atoms import chain) and
`z1_1.py` (zeroinfo's construction reference) now live in `scripts/` as
byte-identical tracked copies of the gitignored `results/*/scripts/`
originals, each stamped with its origin. `d25_atoms.py` resolves the
vendored copies first; the originals remain the executed artifacts.

## The rest of the index (added 2026-08-29 — the 27 files the sweeps had no provenance for)

| group | files | provenance / banked output |
|---|---|---|
| CH3 R5b instrument chain | `ch3_r5b_collect.py`, `ch3_r5b_distill.py`, `ch3_r5b_gates.py`, `ch3_r5b_grade.py`, `ch3_r5b_placebo.py`, `ch3_r5b_diag.py`, `ch3_r5b_stamp.py` | the B5+KILL verdict's committed instruments (collection, distiller, offline gates, grader, placebo builder, diagnostics, pre-reg stamper) |
| CH3 R1 spike | `ch3_r1_spike.py` | backs `ch3_rung2.yaml`'s config constants (`leaves_expected: 353` is attributed to it) — a live-config citation, not deadwood |
| D22 instruments | `d22_collect_obs.py`, `d22_trajectories.py` | reads 1+2+4; `d22_trajectories.py` is the ONLY implementation of the D23-WATCH record-only statistic pre-registered in two live headers |
| D25/D25-P manipulation | `d25_manipulation.py`, `d25p_manipulation.py` | §6 manipulation check on treatment and placebo arms (banked in RESULTS §12's scope) |
| vendored provenance modules | `gate_r012.py`, `rev1_check.py`, `analyze_oppact.py`, `z1_1.py` | tracked copies of the gitignored D25 / Stage-0 fit machinery (CLEANUP B1) — see the closed-gaps section |
| BC / expert-data machinery | `train_bc.py`, `make_bc_dataset.py`, `tape_to_dataset.py` | the clone anchor's pipeline: the BC clone (a live anchor) was trained through these; `tape_to_dataset.py` reads the (now gzipped) fp_tranche tapes |
| corpus | `corpus_survey.py` | priced the human-replay corpus (prior_work's corpus figures); needs the `[corpus]` extra |
| diagnostics (banked reads) | `diag_encoder_live.py`, `diag_value_head.py`, `probe_type_multiplier.py`, `obs_fidelity_check.py`, `p3_team_luck.py` | `probe_type_multiplier.py` is cited by `diag_encoder_live.py`'s own rationale; `p3_team_luck.py` backs the banked team-luck variance decomposition; `obs_fidelity_check.py` proved offline tape replay == live obs |
| throughput / profiling | `showdown_throughput.py`, `profile_collect.py` | the simulator:4 +81% and D12b measurements — BOTH disclosures in `showdown_throughput.py`'s docstring travel with any quote |
| figures / smokes | `make_showdown_figure.py`, `hl_shaping_live_smoke.py` | the Phase-5 milestone figure; signal12m's live R0-2(b) gate |

(`analyze_oppact.py`, `rev1_check.py` above make the earlier "69 scripts"
counts drift by design — vendored copies, not new instruments.)

## Genuine delete candidates

- `play_vs_agent.py` — human-play toy. Its own docstring: "nothing here
  writes to `results/`". Zero references, no number depends on it.
- ~~`record.py`~~ — **DELETED 2026-08-29 with the MinAtar spine (CLEANUP
  A3/B7):** a MinAtar-era GIF renderer whose default input was the (also
  deleted) best_checkpoint.pt; the `pillow` pin went with it.

## One true duplicate

`d29_grade.py` vs `d29r2_grade.py`: 191 of 197 lines identical, differing
only in a seed tuple and two paths. Do **not** just delete one —
`RESULTS.md` cites `d29_grade.py` by path as the attestation record for the
D29r VOID verdict, a published negative result.

RESOLVED 2026-08-29 (CLEANUP B8): kept as deliberate near-duplicates, each
now carrying a header note pointing at the other — a bug fix lands in BOTH.
