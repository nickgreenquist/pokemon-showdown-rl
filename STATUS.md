# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06, after code evening 1 + Arm B)

DESIGN.md r6 RATIFIED (D1–D7 binding). Track 1 measured, warm-start settled, Arm A smoke green,
**Arm B RUN and SCREENED OUT** (delta −0.0004; closed, not re-tuned). Suite 240 passed, no runs
live. RL is LEVEL with the BC clone (0.4607 vs 0.4657), not past it — and per the ladder
translation below, that level is ~40% GXE. **Nothing queued; next move is a maintainer call.**

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

**LADDER TRANSLATION — what these win rates are worth (new 2026-08-06; full derivation and
caveats at the TOP of `prior_work/README.md`).** SH itself scores **39.7% / 41.2% GXE** on the
gen7/gen9 randbats ladders (Metamon Table 2), so **0.489 parity ≈ 40% GXE, not "solved"**; our
best agent is ~20 Elo BELOW SH (~38–40% GXE) and the published pure-policy randbats field
STARTS at 72%. **D7(a) stands, but ladder EXECUTION is DEFERRED** (maintainer, 2026-08-06)
until we are clearly past SH — the result is predictable from vs-SH, so it buys only
confirmation. PS Elo ≠ Glicko-1: quote GXE when comparing across sources.

## Next actions, in order

1. **MAINTAINER DECISION — Track 1's bars.** The ≥50k recent-era bar FAILS at every cutoff
   buying today's sets (≥2023 = 49,693 at 28% level match; ≥2024-04 = 44,391 at 91%); sizing
   ~6.06M decisions (~6.97M calibrated), ~3.4x P4 not §10's 11-22x. Counterweight: 2015-18
   logs carry `|choice|` lines — ~21.5k battles, NO hidden-action problem, worst set drift.
2. **D8/D9 — DESIGN §11 (search re-entry), PROPOSED, needs ratification.** Cheap poke-engine
   feasibility note, then expert iteration from Foul Play as teacher; rejects in-loop search.
3. **MAINTAINER DECISION — push or not.** `main` is well ahead of `origin/main`; never asked.
4. No 24M run (D4c). **Arm C stays parked — its unparking condition was "iff Arm B
   credits", now settled as no.** Arm B closed; do NOT re-tune its coefficient.

## Watch items

- Seed ledger (lanes must not collide): 0/1/2 lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 the smoke.
- Showdown eval episodes are NOT reproducible: comparisons are UNPAIRED — buy precision with n.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **BC-warm-started runs sit at loss/entropy 0.063** (from-scratch: 1.69 → 0.317), FAILING
  the [0.2, 1.0] R0 gate from update 1, permanently. The band does not transfer; the corpus
  chapter must pick its own entropy_coef BEFORE run 1. Critic warmup ~5 updates, not 10.
- **Design rule from Arm B — check before ANY shaping proposal:** a potential-based term whose
  potential is ~linear in features the encoder already emits is inert (Φ = 0.6·(obs[2]−obs[1])).
- Grad clip: from scratch binds 1.00 → 0.50 over 5 updates; warm start HARDER (0.67 → 0.94).
  `loss/*` + `eval/loss_faint_*` postdate P5b: arm-vs-control on those needs runs ≥2026-08-05.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix before
  any self-play rung. poke-env 0.15.0: SH's setup branch is dead (upstream, unfiled).
- Concurrency: solo ~734 steps/s; 3-wide ≈ −20%/lane (~553-600); 6-wide 465-506/lane. Corpus
  is local, pinned in corpus_survey.py. Run-dir `meta.yaml` git_shas are old-repo SHAs.
