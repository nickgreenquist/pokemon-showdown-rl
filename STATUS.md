# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-07 — PIVOT RATIFIED)

**Pure from-scratch self-play in gen1randombattle is the main chase** (novelty over
strength; revocable per D17; r7 RATIFIED, encoder frozen v2/808, comparator 0.3996±0.0052).
**RUNG 1 (SIGNAL) READ OUT 2026-08-08: NULL — 0.4131 ± 0.0052, delta +0.0135, z +1.84,
misses both credit-line halves. Branch (b): Rung 2 at gamma 1.0 / no shaping vs 0.3996.**
Clean null (all gates green; S2 EV-easier confirmed; seed spread collapsed 0.050→0.004).
FP/BC BANKED. Suite 258 green. Pushed through 288a347 (ask-first; 8 local commits).

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *Starred rows are probe reads: 1 fit seed and/or n=1000.)

| result | win rate |
|---|---|
| PPO 12M flat / **+LR anneal — best vs-SH-trained RL** | 0.4330 / **0.4607** |
| Scratch self-play 12M: v1+broken pool / v2+fixed pool | 0.3800 / 0.3890 (dead, v2/807) |
| **Self-play 12M control on v2/808 — COMPARATOR (3×3000)** | **0.3996 ± 0.0052** |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL, branch (b) | 0.4131 ± 0.0052 (z +1.84) |
| BC clone of SH (P4, 813k rows) | **0.4657** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
| Foul Play (+patch) — teacher; banked anchor | **0.8307** (n=7,200)* |
| BC-of-FP v2 180k: final / val-peak — banked anchor | 0.558 / **0.569*** |

**MILESTONE LADDER (r7 §2, RATIFIED):** M1 ≥0.4400 (go/no-go) · M2 ≥0.489 parity ·
M3 ≥0.510 past SH (**the success claim, D10a**) · M4 ≥0.558 stretch. All at 3×3000,
non-SH-anchor guard from M2 up. vs-SH ADMISSIBLE (SH held out of training entirely).

## Next actions, in order

1. **RUNG 2 (STRUCTURE) implementation session:** entity DeepSets trunk + shared
   per-action scorer at the 681k param ceiling, per branch (b) at **gamma 1.0 / NO
   shaping vs 0.3996** (spec + amendments in `configs/showdown_sp_struct12m.yaml`).
   Then R0-4 arch smoke (1 lane × 1M, seed 30, ~35 min), then 3×12M seeds 26/27/28.
2. Rung 0 E1-E4 still owed (D12b); evals cost ~2 min (measured 2×); Rung 3/D15 waits on Rung 2.
3. **Rung 0 measurement evening (E1-E4, ≤10 min each, D12b/D14a):** decompose the loop at
   [512,512] per `prior_work/THROUGHPUT_SPEC.md`; cheap wins authorized on their numbers.
4. ON ICE, zero rework: warmrl (seeds 14-22 reserved), P4-scale GO (19.7 h), §11 D8/D9.
   D17 abandon criterion armed: below M1 after Rungs 1+2+50M, or >20 lane-days, or >8 wks.

## Watch items

- Seeds: 0-13 spent (see logs), 14-22 RESERVED (warmrl), 23/24/25 Rung 1, 26/27/28 Rung 2,
  29/30 smokes, 31-33 v2r lanes, 34 v2r smoke; 35+ free. Distinct across lanes AND arms
  (username landmine). Showdown evals are UNPAIRED — buy precision with battles.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **Encoder FROZEN at v2/808 (D13a, commit 0c83339):** live `mon.must_recharge` bool (both
  actives) + global aliased-turn flag at vec[5]. OBS_DIM 807→808 (v1 611→612) — pre-fix
  checkpoints can't re-eval on current code; fingerprint (+`recharge_fix: true`) is the
  guard, CHECK IT per lane (R0-1). Obs-fidelity PASS post-fix (215 decisions, exact).
- **Rung 1 shaping is NOT Arm B:** non-cancelled, zero-sum, 5-term, gamma 0.95, mirror play
  — Arm B's null (cancelled potential-based single term vs SH) does not transfer. Its R0
  gate: both seats' shaping sums to exactly 0 per event; shaping/terminal mass ratio logged.
- BC-warm-start landmines (on ice with warmrl): loss/entropy 0.063 from update 1; critic
  warmup 5 at rollout 512; grad clip binds harder on warm starts (0.67→0.94).
- `score_ladder.py` default `--opponents` raises on Showdown (use `eval_checkpoint.py`). H&L
  scale accounting (both seats?) unresolved — settle from metagrok before Rung 3's budget.
