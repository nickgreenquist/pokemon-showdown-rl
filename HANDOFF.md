# Handoff — JOURNEY STEP 3/4: the Wang-recipe pre-reg, its build items, the 50M hand-over run
Written 2026-09-05 evening, maintainer-ordered ("ready for handoff.md, make it
comprehensive"). Read STATUS.md, then this. Everything in §1 is DECIDED — do not
re-open it. Docs win on conflict in this order: CLAUDE.md (rules) →
JOURNEY.md (arc, maintainer's) → `docs/design_gen4/open_questions.md` §0.5
(gen-4 rulings) → this file → SESSION_LOGS (newest entry wins on facts).

## 0. WHERE THINGS STAND
- Steps 1–2 DONE (batch credited RESULTS §17; LADDER R4 discharged step 2:
  GXE 65.2 / Glicko-1 1618 ± 25 / Elo 1354, listed on the top-500 for 42/200
  battles, screenshot rank 369 filed). Nothing left on gen 1 until the return
  (JOURNEY steps 8–11).
- STEP 3 groundwork MERGED (`rl/envs/gen4/`, `docs/design_gen4/`) and REVIEWED
  2026-09-05 by three Opus reviewers; the encoder BLOCKER (ability holder via
  `[of]`) and four MAJORS are FIXED on main, pinned by 8 tests; reference
  replay sha **b72dcbc7…** over 42,191 decisions (`scripts/gen4_reference_replay.py`).
  encoder_requirements.md §13 lists the fixes and the recorded-not-fixed minors.
- NO gen-4 model has been trained. Every gen-4 number is a smoke or bot-vs-bot
  placement (FP@20 vs SH 226-24-0, FP@500 228-22-0, n=250; both budgets quoted).
- Tree clean; main is 28+ commits ahead of origin until the maintainer pushes.
  Local Showdown server UP (pid 50440, port 8000, `simulator: 4` confirmed).
  Worktrees: none left. E2 rungs deleted (11 GB freed); each lane keeps its
  completion + 12M rung + checkpoint.pt/best_checkpoint.pt/pool.pt.

## 1. DECIDED 2026-09-05 (maintainer rulings — treat as settled)
1. **First gen-4 run = Wang's recipe AS HE RAN IT** on our frozen encoder
   layout v0.1: Table A.3 + his LR schedule, pure mirror self-play
   latest-vs-latest, BOTH seats harvested, NO opponent pool; 50M per-seat
   decisions as a disclosed fraction of his ≈ 75M. Our pool / league / batch
   config / privileged critic are HELD BACK as later pre-registered levers
   against that baseline (maintainer expects latest-only → league to pay first).
2. **Step-3 milestone**: the run LEARNS — ≥ 0.60 vs SimpleHeuristics, locked
   protocol (final ckpt, 3000/seed, 3 seeds pooled, ties non-wins, deterministic).
3. **Chapter exit = step 5, "matched" is ONE-SIDED**: pooled 3×3000 vs-SH
   **≥ 0.756** (0.786 − one se of Wang's n=200), no ceiling. The anchors doc's
   lower-2·se-bound test is SUPERSEDED. Failure branch NAMES DOSE (50M vs ≈75M).
4. **Anchor battery per generation — CLAUDE.md is the list.** Gen 4: vs-SH
   (primary, the only verdict input) + most-damage-typed h2h 500 + FP@20 h2h +
   FP@500 h2h (both until Q38 pins) + BC-clone h2h 500. A missing leg reads
   PENDING and the README row WAITS; legs are never dropped; random /
   MaxBasePower are sanity rows, not legs.
5. **Freeze layout v0.1 AS BUILT** (the ~90 pool-unreachable dims KEPT); the
   freeze lives in the pre-reg header; relayout only on a measured defect.
6. **FP budget (Q38)**: two-rung ladder (20 / 500 ms, n ≥ 250) ONCE against the
   first trained checkpoint, then pin; quote both meanwhile.
7. **The gen-4 BC clone is KEPT and built ALONGSIDE the 50M run** (FP@20 teacher
   tapes, budget disclosed; ready by the readout).
8. **Search-depreciation rule RATIFIED as written; verdict CLOSED** (docs/
   proposals/search_depreciation_check.md): no MCTS spend on gen 1 before the
   gen-1 return; JOURNEY 11.5 is re-framed as a value-head diagnostic.
9. **Audit rulings**: F-21 keep the borrowed gen-1 set prior TRACKED; F-04
   minibatch tail: DEFAULT (keep) stands, proposal ARCHIVED; F-06 in-loop eval
   budget and F-07 encoder config block: DEFERRED — re-opened only if the gen-4
   header needs the knob; F-05 pool cadence stays 4 updates; F-03 900 s stays.
10. **crash_forfeit READ rule**: the frozen pre-reg meaning stands
    (`crash_forfeits` = relaunches; attribution recorded, not acted on); no
    retroactive re-read of any arm; future pre-regs define n_eff explicitly.
11. Courtesy notes are not required for ladder runs (M10); the ladder account is
    parked at 199-201 / Elo 1354; any future ladder run is a NEW pre-reg.

## 2. THE WORK, IN ORDER
### 2.1 The pre-reg header — `configs/gen4_wang50m.yaml` (pre-reg-grade: 2-Opus design review BEFORE commit; subagents on Opus, never Fable)
Pattern: `configs/showdown_sp_100m.yaml` (the last ratified training header) +
`configs/eval/ladder_r4.yaml` (build items with named fallbacks, ratified_decisions
foot, barred_language key). Must contain, verbatim where the rule says verbatim:
- `journey_step: 3→4` with JOURNEY step 3's milestone and step 5's exit quoted
  verbatim (JOURNEY.md:40, :60); the credit line verbatim incl. the larger-of
  se_diff clause — and the statement that this run CREDITS NOTHING (baseline).
- THE FREEZE: layout v0.1 tuples as built (`rl/envs/gen4/spec.py` LAYOUT,
  OBS_DIM 1,448), unreachable dims kept, reference sha b72dcbc7…, vocab stamps
  (`gen4_vocab.json` sets_sha256, showdown commit 59da482e).
- Wang's recipe (JOURNEY step 4): γ 0.9999, λ 0.754, 7 epochs, clip 0.0829,
  value clip 0.0184, ent 0.0588, vf 0.4375, grad-norm 0.543, n_steps 78×512,
  batch 1024, hidden 256, features 896, his LR schedule (check what our config
  exposes: `grep -n anneal rl/common/config.py` found no `lr_schedule` key —
  D26's anneal knob exists under another name; find it, else it is a build
  item). Mirror self-play latest-vs-latest = `selfplay.pool_size: 1,
  latest_prob: 1.0` (supported). Both seats harvested = BI-G4-1 (NOT built).
- Arms: ONE arm, 3 lanes, DISTINCT `--seed`s (landmine 2), 50M per seat.
- R0 sanity gates (as the 100M header: throughput band, RSS, first-250k band —
  gen-4 has NO measured bands; state them as PROVISIONAL from the first 250k).
- PRIMARY read: vs-SH locked protocol at the final; the milestone branch
  (≥ 0.60 / < 0.60) and the step-5 branch (≥ 0.756 / < 0.756, dose named
  first). SECONDARIES: the five-leg battery (§1.4), each descriptive.
- Disclosures: SB3 vs our PPO; dose fraction; stock SH with the +1-boost bug
  on both sides (Wang's harness unstated); the 40-species ±1–2 level drift of
  FP's pinned set file; FP@20's two standing disclosures.
- `barred_language`: "beats Wang", "matches Wang" (only "matched" per §1.3),
  any ladder projection from vs-SH, "credited".
- BUILD ITEMS with fallbacks (§2.2), ownership (hand-over launch, agent
  babysits/reads out), schedule (> 5 h → maintainer launches).

### 2.2 Build items (agent-side; no rulings needed)
- **BI-G4-1 Both-seat harvest.** Seat 2's trajectory is DISCARDED today
  (`rl/envs/showdown.py:798,813,917` `discard_seat2_obs`; IDEAS_POST_100M §4.1
  calls this the strongest lever). Wang harvests both seats. Design: seat 2's
  transitions enter the buffer as their own episode with the sign of ITS
  outcome; the gen-4 env already encodes seat 2 (`_emit_privileged` in
  `rl/envs/gen4/env.py`). Guard: gen-1 bit-identity when the flag is off
  (`tests/test_encoder_spec.py` hash gate; PPO goldens). Fallback: run
  single-seat and DISCLOSE "half of Wang's harvest" as a second dose term.
- **BI-G4-2 Entity trunk layout argument.** `rl/networks/entity_deepsets.py:169-170`
  hardcodes `species_vocab=152, move_vocab=166` (gen-1) and cannot serve gen 4;
  parameterise on a layout object (`rl/envs/gen4/spec.py` LAYOUT vs gen-1's)
  and add item / ability id embeddings from the id tail. Gen-1 bit-identity
  tests guard it. Fallback: the MLP trunk (smokes only — not fit for the run;
  say so if used).
- **BI-G4-3 Pinned gen-4 hash gate.** A test like `tests/test_encoder_spec.py:336`
  (`test_gen1_encoding_hash_is_pinned`) over the committed fixture + the local
  tapes t0–t6 (`data/gen4_tapes/`, gitignored; `scripts/gen4_reference_replay.py`
  prints the sha) asserting b72dcbc7…; lands WITH the freeze. Fallback: none —
  it is mechanical.
- **BI-G4-4 Format threading for the clone leg.** `scripts/make_bc_dataset.py`
  (defaults gen1randombattle, `--expert heuristics`) and
  `scripts/eval_checkpoint.py` cross-play (`:103` hardcodes gen1) → gen 4.
  `rl/collect.py` / `showdown_async.py` stay gen-1 (the async collector REFUSES
  gen-4 env ids at launch — keep `collector.mode: sync`).
- **BI-G4-5 The gen-4 BC clone.** FP@20 teacher tapes vs the FP eval bot
  (`scripts/gen4_fp_smoke.py`-style, ~7,200 battles ≈ 2.5 h at 1.18 s/battle;
  streamed tapes; detached), through the gen-4 encoder → the banked recipe
  (`runs/bc_fp_v2r_soft_180k_s0` is the gen-1 pattern: MLP 512/512, soft
  targets) → validate vs SH. Runs ALONGSIDE the 50M run. Never training data.

### 2.3 The 50M Wang-recipe run (hand-over: > 5 h)
- Template: `scripts/ch5_100m_wave.sh` (caffeinate -dims, nohup, `< /dev/null`,
  per-lane logs, CPU-delta stall check — landmines: a lane can STALL with the
  process alive; check `ps -o time=` deltas, not step counts; recover with
  `--resume runs/<dir>`; a resume SPLITS the wandb history — read `meta.yaml`).
- Pre-launch: docs committed, clean tree, RESTART the Showdown server fresh
  (R0-j hygiene), `simulator: 4` in `showdown/config/config.js`, encoder env vars
  are gen-1 only (the gen-4 path needs none — verify with `gen4_env_smoke.py`).
- Rung retention: keep every ~5M rung until the readout (S-SHAPE read); the E2
  rule applies after.

### 2.4 After the run (agent-side)
- FP budget ladder: FP@20 and FP@500, n ≥ 250 each, vs the final checkpoint
  (`scripts/gen4_fp_h2h.py`; seat form named); then Q38 pins the budget.
- Readout: primary vs-SH pooled 3×3000 (`scripts/eval_checkpoint.py --episodes 3000`
  per lane, `--no-shaping` if shaped); five legs; RESULTS addendum + README row
  + STATUS + SESSION_LOGS in ONE commit; barred language respected; the
  milestone and step-5 branches read off the header, never decided after.
- Then step 6: ONE gen-4 ladder run under a NEW pre-reg (the R4 pattern; the
  account question is a maintainer ruling — reuse rules apply).

## 3. STATE A FRESH SESSION MUST KNOW
- `conda activate pokemon-showdown-rl` — never base. Suite: 817 passed / 17
  skipped with the server up (`pytest tests/`).
- Gen-4 instruments: `scripts/gen4_smoke.py` (tapes, streamed), `gen4_env_smoke.py`
  (env + encoder), `gen4_fp_smoke.py` / `gen4_fp_h2h.py` (FP gen-4 env
  `foul-play-gen4`, port flag — the server is on 8000; FP runs in its own
  process group and is reaped), `gen4_reference_replay.py` (the sha),
  `setup_foulplay_gen4.sh` (recorded recipe + .so check).
- `.env` carries the ladder account bot1 (nickgen1rbrlbot); training ignores it.
- Memory rules (auto-memory): subagents on Opus; housekeeping without asking
  (fix stale docs yourself; escalate only rulings / pushes / deletions /
  published-number values); terse status while jobs run; never push unasked.
- STATUS.md hard cap 60 lines — check `wc -l` before every commit of it.

## 4. RULES THAT COST HOURS (unchanged)
Distinct seeds per lane; commit docs before launching; one command per fenced
block for the maintainer with `<command>` sentinels; zsh vs bash; `/timer on`
on every connecting seat; vs-SH / off-FP are never ladder numbers; one rung is
worth ±0.02 — read shapes over tens of millions of steps.
