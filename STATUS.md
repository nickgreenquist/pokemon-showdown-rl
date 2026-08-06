# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06, after code evening 1 + Arm B)

DESIGN.md r6 RATIFIED (D1–D7 binding). Track 1 measured, warm-start settled, **Arm B RUN and
SCREENED OUT** (−0.0004; closed, not re-tuned). Suite 240 passed, no runs live. RL is LEVEL
with the BC clone (0.4607 vs 0.4657) — and per the ladder translation, that level is ~40% GXE.
**Queued: the Foul-Play-vs-SH measurement, staged and blocked only on a Rust/gen1 build.**

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *The Foul Play row is NOT locked-protocol: 1 lane, 1 seed, n=300, a scouting read.)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal (P5b) — **re-eval, Arm B's control** | **0.4308 ± 0.0052** (n=9000) |
| PPO 6M + faint shaping (Arm B) — **screened out** | 0.4303 (n=9000), Δ −0.0004 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
| **Foul Play (+our gen1 patch) — teacher candidate** | **0.8467** (254-46, n=300)* |

**LADDER TRANSLATION (derivation + caveats at the TOP of `prior_work/README.md`).** SH scores
**39.7/41.2% GXE** on gen7/gen9 randbats, so **0.489 parity ≈ 40% GXE, not "solved"**; the
pure-policy field STARTS at 72%. **D7(a) stands, ladder EXECUTION DEFERRED** until past SH.
PS Elo ≠ Glicko-1. All GXE readings are cross-format extrapolations, not measurements.

## Next actions, in order

0. **MAINTAINER DECISION — ratify §11 (D8/D9). Its gate is PASSED.** Foul Play 0.8467 vs SH
   (254-46, n=300), **5.54 se** over the 0.70 GO line (se under H0 0.0265; an earlier "7.05"
   used se at p-hat, wrong). Measured with an EARLIER patch — corrected bot reads 0.875
   (n=40); a 300-battle re-measure is owed. "+297 Elo / ~79% GXE" is an EXTRAPOLATION over
   three unmeasured bridges (see prior_work/README), not a measurement. Re-priced from
   measured 25.46 decisions/battle @ 6.03 s: **35.5k battles = 59 h solo, ~7.4 h 8-way**
   (won't scale fully; 3-wide already costs ~20%).
1. **MAINTAINER DECISION — Track 1's bars.** The ≥50k recent-era bar FAILS at every cutoff
   buying today's sets (≥2023 = 49,693 at 28% level match; ≥2024-04 = 44,391 at 91%); sizing
   ~6.06M decisions, ~3.4x P4 not §10's 11-22x. Counterweight: 2015-18 logs carry `|choice|`
   lines — ~21.5k battles, NO hidden-action problem, but the worst set drift.
2. **MAINTAINER DECISION — push or not.** `main` is well ahead of `origin/main`; never asked.
3. No 24M run (D4c). **Arm C parked permanently** — unparking condition was "iff Arm B
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
- Grad clip: scratch 1.00→0.50 over 5 updates, warm start HARDER (0.67→0.94). `loss/*` +
  `eval/loss_faint_*` postdate P5b: arm-vs-control there needs runs ≥2026-08-05.
- **Check: is our SH weaker than Metamon's?** poke-env 0.15.0's dead SH setup branch may
  postdate theirs — if so every vs-SH number here is inflated vs the ~40% GXE anchor.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix before any
  self-play rung. poke-env 0.15.0: SH's setup branch is dead (upstream, unfiled).
- Concurrency: solo ~734 steps/s; 3-wide ≈ −20%/lane (~553-600); 6-wide 465-506/lane.
