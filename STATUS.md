# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-06, after the Foul Play day + the direction audit)

DESIGN r6 RATIFIED (D1–D7). Arm B closed (−0.0004). Suite 241 green, no runs live. RL LEVEL
with the SH clone (0.4607 vs 0.4657) — ~40% GXE. FP teacher measured; tapes gate-green; §11
awaits ratification. **Audit (last log entry): CONFIRMED w/ amendments; read WIN RATE.**

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *Foul Play rows are NOT locked-protocol: scouting reads.)

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

**LADDER TRANSLATION (derivation atop `prior_work/README.md`).** SH is 39.7/41.2% GXE on
gen7/gen9 randbats → **0.489 parity ≈ 40% GXE**; the pure-policy field STARTS at 72%. D7(a)
stands, ladder DEFERRED until past SH. PS Elo ≠ Glicko-1; all GXE rows are extrapolations.

## Next actions, in order

0. **MAINTAINER DECISION — ratify §11 (D8/D9). Gate PASSED and no longer SH-only:** teacher
   0.8333 vs SH (n=1200), 0.876/0.872 vs two non-SH opponents — the exploitation trap does
   NOT fire. The 30k clone (0.3683, agreement 0.42) is a 1/27th-scale smoke: the 0.86 bar
   cannot apply and the fitted 0.894 "ceiling" is an artifact (teacher self-greedy 0.892).
   Next rung ~120k rows (~2 h, 3-wide linear 3.02x), refit, read WIN RATE; P4-scale 19.7 h.
   Audit amendments to fold in: screen encoder-v2 + trunk on the SAME tapes (MOVE_DIM omits
   what FP conditions on); pre-register post-BC RL as self-play + KL-to-BC anchor, not vs-SH.
1. **MAINTAINER DECISION — Track 1's bars.** ≥50k recent-era FAILS at every cutoff buying
   today's sets (≥2023 = 49,693 at 28% level match; ≥2024-04 = 44,391 at 91%); ~6.06M
   decisions ≈ 3.4x P4, not 11-22x. 2015-18 `|choice|` logs: ~21.5k battles, worst set drift.
2. **MAINTAINER DECISION — push or not.** `main` is well ahead of `origin/main`; never asked.
3. No 24M run (D4c). **Arm C parked permanently.** Arm B closed; do NOT re-tune it.

## Watch items

- Seeds: 0/1/2 lra, 3/4/5 lra12m, 6/7/8 Arm B, 9 smoke. Distinct usernames per lane too.
  Showdown evals are NOT reproducible: comparisons are UNPAIRED — buy precision with n.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **Encoder SEMANTICS changed 2026-08-06 at constant OBS_DIM** (set prior default-ON +
  aliasing fix): pre-Aug-6 checkpoints now re-eval off-distribution; `POKEMON_RL_NO_SET_PRIOR=1`
  restores the prior only. Stamp encoder version in run meta before the next chapter's runs.
- **BC-warm-started runs sit at loss/entropy 0.063** (scratch 1.69→0.317), FAILING the
  [0.2,1.0] R0 gate from update 1 — pick entropy_coef BEFORE run 1. Critic warmup ~5, not 10.
- **Arm B rule:** potential-based shaping ~linear in already-encoded features is inert
  (Φ = 0.6·(obs[2]−obs[1])). Grad clip: warm starts clip HARDER (0.67→0.94).
- SH's setup branch is DEAD upstream (Target enum vs string) — SH never uses setup moves, any
  gen; same bug kills ps-ppo's `self_boost_sum`. Predates Metamon's window: GXE anchor OK.
- `rl/selfplay/pool.py` evicts index 1 on overflow — fix before any self-play rung.
  `score_ladder.py` default `--opponents` raises on Showdown (Connect-4 names); headline
  numbers came from `eval_checkpoint.py`. Solo ~734 steps/s; 6-wide 465-506/lane.
