# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06 23:45 — the probe answered)

DESIGN r6 RATIFIED (D1–D7). Suite 243 green. **The v2 Foul-Play clone (180k rows) scores
0.558 vs SH — the FIRST agent in this repo past SimpleHeuristics** (probe: 1 fit seed,
n=1000). Teacher 0.8307 (n=7,200). Encoder v2 = +0.107 win rate at matched data. Self-play
preview (sp12m_v2, s10/11/12) runs overnight vs the 0.3800 bar.

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *Starred rows are NOT locked-protocol: scouting/probe reads.)

| result | win rate |
|---|---|
| PPO 12M flat / **+LR anneal — best RL** (6M rows: logs) | 0.4330 / **0.4607** |
| BC clone of SH (P4, 813k rows) | **0.4657** re-scored in-repo |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
| **Foul Play (+patch) — teacher; SHIPPED bot** | **0.8307** (n=7,200)* |
| Foul Play vs our best RL / vs BC-clone-of-SH | **0.876 / 0.872** (n=250 each)* |
| BC-of-FP, v1 encoder: 30k / 180k rows | 0.3683 / 0.451* |
| **BC-of-FP, v2, 120k/180k — PAST SH** (val-peak ckpt) | 0.515 / 0.558 / **0.569*** |

**LADDER TRANSLATION (derivation atop `prior_work/README.md`).** SH is 39.7/41.2% GXE on
gen7/gen9 randbats → 0.489 parity ≈ 40% GXE; the pure-policy field STARTS at 72%. D7(a)
stands; ladder still DEFERRED until clearly past SH on protocol-grade reads. All GXE rows
are cross-format extrapolations.

## Next actions, in order

0. **MAINTAINER DECISION — ratify §11 (D8/D9) + P4-scale GO.** The pre-stated probe branch
   fired: agreement 0.5147 still climbing +3 pts/doubling; win rate 0.515→0.558 over one
   half-doubling (+7 pts/doubling, superlinear in agreement); v2 credited in win-rate terms
   (+0.107, z≈4.8). P4-scale = ~35k battles ≈ 900k rows ≈ **19.7 h at 3-wide** with v2.
1. **Protocol-grade the milestone:** refit 180k WITH early stopping (final==best; the 0.569
   val-peak read carries a selection caveat) + 2 more fit seeds + n=3000; head-to-heads owed.
   900k fit recipe settled: soft-BC + value-coef 0.5 (prior_work/DISTILLATION_OBJECTIVES.md).
2. **Read the self-play preview** (R0 → R1 by 4M → R2 finals vs 0.3800; tree in the config
   header). Launched 23:07, ~7 h; clone evals shared the server in its first half hour.
3. **MAINTAINER DECISION — push or not.** `main` is well ahead of `origin/main`; never asked.
4. RL-phase pre-reg (bc_kl coef, entropy from 1.12, opponent) before any warm start; Arm B
   stays closed, Arm C parked.

## Watch items

- Seeds: 0/1/2 lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 smoke, 10/11/12 sp12m_v2, 13 sp smoke.
  Showdown evals are NOT reproducible: comparisons are UNPAIRED — buy precision with n.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **Encoder SEMANTICS changed 2026-08-06 at constant OBS_DIM** (set prior default-ON +
  aliasing fix): pre-Aug-6 checkpoints re-eval off-distribution; `POKEMON_RL_NO_SET_PRIOR=1`
  restores the prior only. v2 runs stamp `encoder` in meta.yaml/bc_metrics.json — check it.
- **BC-warm-started runs sit at loss/entropy 0.063**, FAILING the [0.2,1.0] R0 gate from
  update 1 — entropy_coef + `bc_kl_coef` chosen BEFORE run 1. Critic warmup ~5, not 10.
- **Arm B rule:** potential-based shaping ~linear in already-encoded features is inert
  (Φ = 0.6·(obs[2]−obs[1])). Grad clip: warm starts clip HARDER (0.67→0.94).
- SH's setup branch is DEAD upstream (Target enum vs string) — SH never uses setup moves;
  same bug kills ps-ppo's `self_boost_sum`. Predates Metamon's window: GXE anchor OK.
- Pool eviction FIXED (ccae800). `score_ladder.py` default `--opponents` raises on Showdown;
  headline numbers come from `eval_checkpoint.py`.
