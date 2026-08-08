# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-08 — RUNG 2 CODE COMPLETE)

**Pure from-scratch self-play in gen1randombattle is the main chase** (novelty over
strength; revocable per D17; r7 RATIFIED, encoder frozen v2/808, comparator 0.3996±0.0052).
Rung 1 (SIGNAL) read out NULL (0.4131±0.0052, z +1.84; branch (b) binds: Rung 2 at gamma
1.0 / no shaping vs 0.3996). **RUNG 2 (STRUCTURE) CODE LANDED, ALL OFFLINE GATES GREEN:**
entity DeepSets trunk + pointer scorer (actor 626,059 ≤ ceiling 681,994), gated id-suffix
encoder (obs 828), R0-2/R0-3/R0-5/R0-7/K4 pass, suite **264 green**, live integration
smoke clean incl. the eval_checkpoint rebuild path. **NEXT: R0-4 throughput smoke.**
FP/BC BANKED. Origin == main at 9725816 pre-session (pushing stays ask-first).

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed per D2c; *probe: 1 seed/n=1000)

| result | win rate |
|---|---|
| PPO 12M flat / **+LR anneal — best vs-SH-trained RL** | 0.4330 / **0.4607** |
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

1. **R0-4 PASSED (2026-08-08 night): 552.7 steps/s** median steady-state (gate ≥380;
   MLP preview 537), S2 update share 14%, meta 828/ids exact, git_dirty false. **GO.**
2. **LAUNCH 3×12M seeds 26/27/28** (v2r nohup pattern, 90 s stagger, BOTH env vars).
   Verify per lane: fingerprint + battle PROGRESS. Finals evals in-session (~2 min
   each) vs 0.3996 tomorrow. K1 shrink unspent.
3. **Branch-(d) stack (maintainer to ratify; 2026-08-08 logs):** RECIPE rung (rollout
   →16-32k + λ0.75 vs 0.3996; ~38 eps/update vs refs' ~1,500) AND relax-purity/BC-arm
   hedge (VGC-Bench: scratch 0.51 vs BC 0.83 @64 teams; H&L pure-SP proof; warmrl iced).
4. Rung 0 E1-E4 measurement evening still owed (D12b/D14a); cheap wins on their numbers.
5. ON ICE, zero rework: warmrl (seeds 14-22), P4-scale GO (19.7 h), §11 D8/D9.
   D17 abandon criterion armed: below M1 after Rungs 1+2+50M, or >20 lane-days, or >8 wks.

## Watch items

- Seeds: 0-13 spent, 14-22 RESERVED (warmrl), 23/24/25 Rung 1, 26/27/28 Rung 2, 29/34
  smokes, 30 = R0-4 arch smoke, 31-33 v2r, 99 throwaway integration smoke; 35+ free.
  Distinct across lanes AND arms (username landmine). Showdown evals are UNPAIRED.
- **TWO env vars now, twice as forgettable (R0-1):** every lane's meta.yaml must show
  obs_dim 828, recharge_fix true, ids true. Rung 2 checkpoints need BOTH vars at eval too;
  a forgotten var now dies loudly at trunk construction (tokenizer assert), by design.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- Encoder FROZEN v2/808 (D13a); id suffix is a gated pure ADDITION (off = bit-identical;
  vec[:808] untouched). 0.3890/0.3800 are dead comparators (v2/807).
- `score_ladder.py` default `--opponents` raises on Showdown (use `eval_checkpoint.py`).
- H&L scale accounting (both seats?) unresolved — settle from metagrok before Rung 3 budget.
- BC-warm-start landmines (on ice with warmrl): entropy 0.063 from update 1; critic
  warmup 5 at rollout 512; grad clip binds harder on warm starts (0.67→0.94).
