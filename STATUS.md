# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06, after the Foul Play measurement + 3 reviews)

DESIGN r6 RATIFIED (D1–D7). Arm B SCREENED OUT (−0.0004, closed). Suite 240 passed, no runs
live. RL is LEVEL with the BC clone (0.4607 vs 0.4657) — ~40% GXE. **Foul Play measured as a
teacher and the demonstration tape pipeline is built and gate-green; §11 awaits ratification.**

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *Foul Play row is NOT locked-protocol: 1 lane, 1 seed, n=300, a scouting read.)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") / +LR anneal (P5b, Arm B's control) | 0.3923 / **0.4308 ± 0.0052** |
| PPO 6M + faint shaping (Arm B) — **screened out** | 0.4303 (n=9000), Δ −0.0004 |
| PPO 12M flat / **+LR anneal — best RL** | 0.4330 / **0.4607** |
| BC clone of SH | **0.4657** re-scored in-repo |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
| **Foul Play (+patch) — teacher; SHIPPED bot** | **0.8333** (1000-194, n=1200)* |
| Foul Play vs our best RL / vs BC-clone-of-SH | **0.876 / 0.872** (n=250 each)* |
| BC clone of Foul Play, 30k rows — **worse than the SH clone** | **0.3683** (n=600) |

**LADDER TRANSLATION (derivation + caveats atop `prior_work/README.md`).** SH scores 39.7/41.2%
GXE on gen7/gen9 randbats, so **0.489 parity ≈ 40% GXE, not "solved"**; the pure-policy field
STARTS at 72%. **D7(a) stands, ladder DEFERRED** until past SH. PS Elo ≠ Glicko-1. Every GXE
figure here is a cross-format extrapolation, not a measurement.

## Next actions, in order

0. **MAINTAINER DECISION — ratify §11 (D8/D9). Gate PASSED and no longer SH-only:** teacher
   0.8333 vs SH (n=1200) and 0.876/0.872 vs two non-SH opponents, so §11's exploitation trap
   does NOT fire. BUT the 30k-row clone scores 0.3683 — below the SH clone (0.4657) — because
   agreement is only 0.42 vs that clone's 0.86. Curve still climbing (+2.6 pts/doubling,
   ceiling 0.894). 3-wide collection measured LINEAR (3.02x): P4-scale = **19.7 h**.
   "+297 Elo / ~79% GXE" remains an EXTRAPOLATION over three unmeasured bridges.
1. **MAINTAINER DECISION — Track 1's bars.** The ≥50k recent-era bar FAILS at every cutoff
   buying today's sets (≥2023 = 49,693 at 28% level match; ≥2024-04 = 44,391 at 91%); sizing
   ~6.06M decisions, ~3.4x P4 not 11-22x. Counterweight: 2015-18 logs carry `|choice|` lines
   — ~21.5k battles, no hidden-action problem, but the worst set drift.
2. **MAINTAINER DECISION — push or not.** `main` is well ahead of `origin/main`; never asked.
3. No 24M run (D4c). **Arm C parked permanently** (unparking was "iff Arm B credits" = no).
   Arm B closed; do NOT re-tune its coefficient.

## Watch items

- Seeds: 0/1/2 lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 smoke. Distinct usernames per lane too.
  Showdown evals are NOT reproducible: comparisons are UNPAIRED — buy precision with n.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **BC-warm-started runs sit at loss/entropy 0.063** (scratch 1.69→0.317), FAILING the
  [0.2,1.0] R0 gate from update 1 — pick entropy_coef BEFORE run 1. Critic warmup ~5, not 10.
- **Arm B rule — check before ANY shaping proposal:** a potential-based term whose potential is
  ~linear in features the encoder already emits is inert (Φ = 0.6·(obs[2]−obs[1])).
- Grad clip: scratch 1.00→0.50 over 5 updates, warm start HARDER (0.67→0.94). `loss/*` +
  `eval/loss_faint_*` postdate P5b: arm-vs-control needs runs ≥2026-08-05.
- SH's setup branch is DEAD upstream (`move.target == "self"` vs a Target enum) — SH never
  uses a setup move, any gen. Predates Metamon's window, so the GXE anchor shares it: OK.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix before any
  self-play rung. Concurrency: solo ~734 steps/s; 3-wide −20%/lane; 6-wide 465-506/lane.
