# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-05, after code evening 1)

DESIGN.md r6 RATIFIED (D1–D7 binding). **HANDOFF item 1 is DONE and green** — Track 1
measured, warm-start semantics settled, Arm B built, **Arm A smoke RUN and green** (all
four reads passed; see below for its one surprise). Suite: 240 passed. No runs live;
server may still be up on :8000. Arm B is launch-ready. Standing correction: RL is
LEVEL with the BC clone (0.4607 vs 0.4530/0.4657), not past it.

## Results (vs SH; locked: final ckpt, 1000 battles/seed, 3 seeds pooled, ties=loss)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal (P5b, Arm B's control) | 0.4433 ± 0.0091 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
(D2c: future finals move to 3000 battles/seed, arm AND re-evaluated control.)

## Next actions, in order

1. **MAINTAINER DECISION — Track 1's bars.** The ≥50k recent-era bar FAILS at every
   cutoff that buys today's set distribution: ≥2023 = 49,693 battles but only 28% level
   match; ≥2024-04 (the level table's step change) = 44,391 at 91%. Sizing also drops —
   ~6.06M decisions corpus-wide (~6.97M calibrated), ~3.4x P4, not §10's 11-22x. Smaller
   lever than assumed; numbers in the session log, not decided unilaterally. Counterweight:
   2015-18 logs carry literal `|choice|` lines (both seats' true actions), so ~21.5k
   battles have NO hidden-action problem — cheap labels, but the worst set drift.
2. **Arm B at 6M** — `configs/showdown_faint6m.yaml`, seeds 6/7/8, 3-wide, ~2.9 h;
   pre-registration in the config header. Run the R0 shaping gate before launching:
   `pytest tests/test_showdown_env.py -k "shaped_return or shaped_episode"`. Futility
   screen: advance to 12M iff pooled delta ≥ +0.009 vs the P5b control RE-EVALUATED at
   3000 battles/seed in-repo.
3. No 24M run (D4c). Arm C parked. Open: un-gitignore `prior_work/wang_fork_diffs.md`?

## Watch items

- Commit docs BEFORE launching, from a clean tree. Distinct `--seed` per lane: 0/1/2
  lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 the smoke.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **BC-warm-started runs sit at loss/entropy 0.063** (vs from-scratch 1.69 → 0.317), so
  they FAIL the [0.2, 1.0] R0 entropy gate from update 1, permanently. The band does not
  transfer to that regime and the corpus chapter must pick its own entropy_coef BEFORE
  its first run. Smoke also says: critic warmup ~5 updates suffices, not 10.
- **Grad clip:** from scratch it binds 1.00 → 0.50 over the first 5 updates (batch 4096,
  grad_norm 3.30 → 0.47), but the warm-start regime binds HARDER over time (0.67 → 0.94).
  Value EV from scratch starts strongly NEGATIVE (−2.72 → −1.22) — the Arm B baseline.
- Metric namespace grew: `loss/{explained_variance,adv_std,grad_norm,grad_clip_frac}`
  and `eval/{loss_faint_diff,loss_faint_lead_frac}`.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix before
  any future self-play rung (recovered bug).
- P6 arms seed-UNPAIRED; per-seed comparison meaningless. poke-env 0.15.0: SH's setup
  branch is dead (upstream bug, report unfiled).
- Concurrency: solo ~734 steps/s; 3-wide ≈ −20%/lane (~553-600); 6-wide 465-506/lane.
- Run-dir `meta.yaml` git_shas are old-repo SHAs — provenance via SESSION_LOGS.
- Corpus stays on the local box; revision + sha256 pinned in scripts/corpus_survey.py.
