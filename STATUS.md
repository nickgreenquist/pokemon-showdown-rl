# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06, after code evening 1 + Arm B)

DESIGN.md r6 RATIFIED (D1–D7 binding). Track 1 measured, warm-start settled, Arm A smoke
green, **Arm B RUN and SCREENED OUT** (delta −0.0004; closed, not re-tuned). Suite: 240
passed. No runs live. Standing correction: RL is LEVEL with the BC clone (0.4607 vs
0.4530/0.4657), not past it. **Nothing is queued — next move is a maintainer decision.**

## Results (vs SH; locked: final ckpt, 3 seeds pooled, ties=loss; n=3000 unless noted)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal (P5b) — **re-eval, Arm B's control** | **0.4308 ± 0.0052** (n=9000) |
| PPO 6M + faint shaping (Arm B) — **screened out** | 0.4303 (n=9000), Δ −0.0004 |
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
2. **D8/D9 — DESIGN §11 (search re-entry), PROPOSED, needs your ratification.** Recommends
   a cheap poke-engine feasibility note, then expert iteration from Foul Play as a teacher
   (~6 h at 8-way for a P4-scale dataset); rejects search-in-the-training-loop on cost.
3. No 24M run (D4c). **Arm C stays parked — its unparking condition was "iff Arm B
   credits", now settled as no.** Arm B closed; do NOT re-tune its coefficient.

## Watch items

- Commit docs BEFORE launching, from a clean tree. Distinct `--seed` per lane: 0/1/2
  lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 the smoke.
- Showdown eval episodes are NOT reproducible (measured): comparisons are UNPAIRED, buy
  precision with battle count. `eval_checkpoint.py` now reports env-supplied win rate.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **BC-warm-started runs sit at loss/entropy 0.063** (vs from-scratch 1.69 → 0.317), so
  they FAIL the [0.2, 1.0] R0 entropy gate from update 1, permanently. The band does not
  transfer to that regime and the corpus chapter must pick its own entropy_coef BEFORE
  its first run. Smoke also says: critic warmup ~5 updates suffices, not 10.
- **Grad clip:** from scratch binds 1.00 → 0.50 over the first 5 updates; warm start binds
  HARDER over time (0.67 → 0.94). Arm B's EV ran 0.24 (early) → 0.43 (late).
- **Design rule from Arm B, check it before ANY future shaping proposal:** a potential-based
  term whose potential is ~linear in features the encoder already emits is predictably inert
  — PBS leaves advantages exactly invariant, and here Φ = 0.6·(obs[2] − obs[1]) exactly. One
  line of algebra pre-launch would have predicted the null and saved 2.9 h.
- Metric namespace grew: `loss/{explained_variance,adv_std,grad_norm,grad_clip_frac}`,
  `eval/{loss_faint_diff,loss_faint_lead_frac}`.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix before
  any self-play rung. poke-env 0.15.0: SH's setup branch is dead (upstream, unfiled).
- Concurrency: solo ~734 steps/s; 3-wide ≈ −20%/lane (~553-600); 6-wide 465-506/lane.
  Run-dir `meta.yaml` git_shas are old-repo SHAs. Corpus: local, pinned in corpus_survey.py.
