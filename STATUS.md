# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06, after code evening 1 + Arm B)

DESIGN.md r6 RATIFIED (D1–D7 binding). Track 1 measured, warm-start settled, **Arm B RUN and
SCREENED OUT** (−0.0004; closed, not re-tuned). Suite 240 passed, no runs live. RL is LEVEL
with the BC clone (0.4607 vs 0.4657) — and per the ladder translation, that level is ~40% GXE.
**Queued: the Foul-Play-vs-SH measurement, staged and blocked only on a Rust/gen1 build.**

## Results (vs SH; locked: final ckpt, 3 seeds pooled, ties=loss; n=3000/seed per D2c)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal (P5b) — **re-eval, Arm B's control** | **0.4308 ± 0.0052** (n=9000) |
| PPO 6M + faint shaping (Arm B) — **screened out** | 0.4303 (n=9000), Δ −0.0004 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |

**LADDER TRANSLATION (2026-08-06; derivation + caveats at the TOP of `prior_work/README.md`).**
SH scores **39.7/41.2% GXE** on gen7/gen9 randbats (Metamon Table 2), so **0.489 parity ≈ 40%
GXE, not "solved"**; we are ~20 Elo BELOW SH and the pure-policy field STARTS at 72%. **D7(a)
stands but ladder EXECUTION is DEFERRED** until we are past SH — predictable from vs-SH, so it
buys only confirmation. PS Elo ≠ Glicko-1: quote GXE across sources.

## Next actions, in order

0. **QUEUED AND STAGED — measure Foul Play vs SH** (approved 2026-08-06; the §11 D8/D9 gate).
   Pre-registration + SH seat: `scripts/foulplay_vs_sh.py`; GO ≥0.70 / MARGINAL 0.60–0.70 /
   NO <0.60 at n=300. Clone at `../foul-play`, our login patch applied. **Blocked on: no Rust
   installed, and the engine ships gen9 — rebuild `make poke_engine GEN=gen1`.** A wrong-gen
   build biases FP DOWN, the direction that wrongly kills (C): smoke 5 and read FP's log.
1. **MAINTAINER DECISION — Track 1's bars.** The ≥50k recent-era bar FAILS at every cutoff
   buying today's sets (≥2023 = 49,693 at 28% level match; ≥2024-04 = 44,391 at 91%); sizing
   ~6.06M decisions, ~3.4x P4 not §10's 11-22x. Counterweight: 2015-18 logs carry `|choice|`
   lines — ~21.5k battles, NO hidden-action problem, but the worst set drift.
2. **D8/D9 (DESIGN §11) — now GATED on item 0**; ratify once the teacher's strength is known.
3. **MAINTAINER DECISION — push or not.** `main` is well ahead of `origin/main`; never asked.
4. No 24M run (D4c). **Arm C parked permanently** — unparking condition was "iff Arm B
   credits", settled as no. Arm B closed; do NOT re-tune its coefficient.

## Watch items

- Seed ledger (lanes must not collide): 0/1/2 lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 the smoke.
- Showdown eval episodes are NOT reproducible: comparisons are UNPAIRED — buy precision with n.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **BC-warm-started runs sit at loss/entropy 0.063** (scratch: 1.69→0.317), FAILING the
  [0.2,1.0] R0 gate from update 1 permanently — any warm-started chapter picks its own
  entropy_coef BEFORE run 1. Critic warmup ~5 updates, not 10.
- **Design rule from Arm B — check before ANY shaping proposal:** a potential-based term whose
  potential is ~linear in features the encoder already emits is inert (Φ = 0.6·(obs[2]−obs[1])).
- Grad clip: scratch binds 1.00→0.50 over 5 updates, warm start HARDER (0.67→0.94). `loss/*` +
  `eval/loss_faint_*` postdate P5b: arm-vs-control on those needs runs ≥2026-08-05.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix before any
  self-play rung. poke-env 0.15.0: SH's setup branch is dead (upstream, unfiled).
- Concurrency: solo ~734 steps/s; 3-wide ≈ −20%/lane (~553-600); 6-wide 465-506/lane.
