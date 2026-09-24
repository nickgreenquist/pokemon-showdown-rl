# Handoff — R7 runner, 2026-09-24 00:30Z (the maintainer asked: context at 91%, handoff + clear)

Resume as the single R7 runner (JOURNEY 14; CLAUDE.md binding). Worktree `../pokemon-showdown-rl-r7`, branch
`r7-native-search` (tip `0730f3e`), env `pkmn-engine-r7`. Main `4bd9374`+ (this file's commit). NOTHING PUSHED since
`a35ff9b` (branch) / `67f3d30` (main) — ask before pushing. Read STATUS first; the plan's AMENDMENT BOXES 5 and 6
(`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md`) hold every decision below with numbers.

## Running now (both self-terminating; do not touch)
- **G1b** — the belief arms of the engine mirror (`logs/r7_scripts/launch_g1b.sh`, pids 86094/86096, guard 86132
  `logs/r7_scripts/g1b_guard.sh` kills both when the last R6 lane exits or at Thu 07:30Z). At 00:16Z: 1,050/2,500 per
  seat, ~11 battles/min → ETA ~02:30Z. Rows `results/r7_g1b/g1b.rows.jsonl` (resume-safe; a guard kill resumes on the
  idle box). The re-runs of G1's true-world arms already reproduce G1's rows 2,500/2,500 on all three arms.
- **The R6 fleet** (the `r6-runner` session owns it): trio A's last lane exits ~05:00Z Thu; the reads queue's FP arms
  start ~15 min later; readout ~Thu 22:00 EDT.

## The quiet-box rule (agreed with r6-runner)
Every R7 job — instruments, tests, cargo builds, reviews that run code — STOPS when
`pgrep -f 'rl.train.*showdown_r6_trio'` returns nothing, and stays off until the R6 readout lands. Their queue HOLDs on
any process ≥ 50% of a core. Message `r6-runner` (SendMessage) before anything unusual.

## First actions on resume
1. When G1b ends: `cd ../pokemon-showdown-rl-r7 && /opt/anaconda3/envs/pokemon-showdown-rl/bin/python
   scripts/r7_g1_readout.py --out ../pokemon-showdown-rl/readouts/R7_G1_READOUT.md` (analysis env, seconds — do it
   before the last R6 lane exits, or after the R6 readout), then a box-5 item + SESSION_LOGS/STATUS with the paired
   belief-minus-true read (the peek at battle level). If the guard cut G1b, say PARTIAL and resume it Friday.
2. Fold this file into STATUS/SESSION_LOGS and restore the stub (CLAUDE.md).

## Done tonight (all committed; details in box 5/6 and SESSION_LOGS 09-23 22:10Z → 09-24 01:55Z)
- G1 READ (`readouts/R7_G1_READOUT.md`): the gated L-op +0.0504 ± 0.0050 over its own greedy in the engine mirror at
  9.6% override — its BEST case (true world + the foe's exact prior).
- Box 5: P3's fusion licence RE-READ at the working dials (the old read ran at τ 1.0) — holds, T-op stays B = 1; B2
  OUT of the fleet's base; the control never plays; the evaluator read (G0's 500 positions don't transfer).
- G2 built (`rl/search/lop.py`, the `native_seat` kind), reviewed twice by Opus, both MAJOR operator defects fixed (the
  bridge had handed the foe our whole team — `engine_bridge.our_side_reveal`; the worlds now sample the foe active's
  moves), pre-reg `configs/eval/r7_g2.yaml` r2 **RATIFIED**, runs AFTER the fleet (smoke Friday).
- `native.solve` `both_views` dial (the fleet's T-op renders one view); the donor-θ0 warm-start path (`7014f11`); the
  B0 bench reads its pass line at the fleet's form (`f640049`); **the mmap'd team bank** (ruling 6's precondition, built
  `7c6cb40`, its zero-copy test skips until the reinstall); **E2 LANDED** (ruled yes: the scorer factorization,
  `_GEN1_PIN` re-baselined, `38f7736`); two tests the merge would have broken fixed (`f23cfed`).
- **The fleet's lane configs are DERIVED**: `scripts/derive_r7_fleet.py` (+ `tests/test_derive_r7_fleet.py`, 10 green,
  `0730f3e`) writes one config per lane (each lane its own donor) with the full pre-reg in the header.

## Rulings taken (maintainer, 2026-09-24): R-F1 WARM + PAIRED by final, +100M, reduced-LR re-armed anneal; R-F2 3+3 if
B0 passes six-wide else 3+2; R-G2 ratified, after the fleet; R-E2 yes.

## Owed next (in order)
1. **Two Opus reviews of the fleet pre-reg** — the header template in `scripts/derive_r7_fleet.py` plus a sample
   derivation (e.g. `--base b --stage fleet --lr 1e-4 --b0 PASS --out <scratchpad>`, trio B's real finals exist);
   CPU-light, but finish before the last R6 lane exits or wait for the readout.
2. **Friday, the idle box, box 6's ordered checklist:** R6 readout → merge `r7-native-search` into main → reinstall
   the merged extension into `pkmn-engine-r7` AND `pkmn-engine-port` (no job alive in either), then the suite
   (`test_engine_bank_mmap.py` must PASS, not skip; `test_lop.py` none skipped) → B0 bench `--widths 5 6` at normal QoS
   (decides 3+3 vs 3+2) → pick the base from the 09-25 read → `derive_r7_fleet.py --stage lr-smokes`, run the three 2M
   smokes, `extract_history.py`, `--read-lr` → `--stage fleet` → the two 400k warm smokes → G2's two-battle smoke → the
   maintainer launches the fleet (the printed lines; over 5 h).
3. Own-lap items after the fleet: B2 with its own fusion read; the rollout-label evaluator CAMPAIGN (G0-scale is too
   small); G2 at a larger budget.

## Watch
- Pre-existing suite failures (NOT E2's; they fail identically on the unmodified branch): 9 in the analysis env, 19 in
  the engine env (poke_engine-less env, runs/ provenance files, flags-unset invocations) — don't chase them as new.
- Memory: `r7-runner-setup`, `r7-kitchen-sink-ruling`, `check-ratified-preconditions` (new: verify every ruling's
  precondition in CODE before calling a fleet ready — the mmap bank had slipped).
