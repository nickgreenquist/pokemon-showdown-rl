# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-07 — THE PIVOT)

**Maintainer decision: pure from-scratch self-play in gen1randombattle is the main chase**
(novelty over strength; revocable). **DESIGN r7 PROPOSED — D10–D17 await ratification.**
FP/BC chapter BANKED (eval anchors + fallback): teacher 0.8307 (n=7,200), tapes 180k rows,
v2 clone 0.558/0.569*, warmrl draft on ice. Suite 243 green. Pushed through 19a62c2.

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *Starred rows are probe reads: 1 fit seed and/or n=1000.)

| result | win rate |
|---|---|
| PPO 12M flat / **+LR anneal — best vs-SH-trained RL** | 0.4330 / **0.4607** |
| **Scratch self-play 12M: v1+broken pool / v2+fixed pool** | **0.3800 / 0.3890** (null, z +0.7) |
| BC clone of SH (P4, 813k rows) | **0.4657** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
| Foul Play (+patch) — teacher; banked anchor | **0.8307** (n=7,200)* |
| BC-of-FP v2 180k: final / val-peak — banked anchor | 0.558 / **0.569*** |

**MILESTONE LADDER (r7 §2, unratified):** M1 ≥0.4400 (go/no-go) · M2 ≥0.489 parity ·
M3 ≥0.510 past SH (success claim) · M4 ≥0.558 stretch. All at 3×3000, non-SH-anchor guard
from M2 up. vs-SH is ADMISSIBLE for self-play agents (SH held out of training entirely).

## Next actions, in order

0. **MAINTAINER — ratify DESIGN r7 (D10–D17).** Highest-leverage: D10 (ladder + which bar is
   "works"), D13 (freeze v2 vs land the MUST_RECHARGE Stage-0 fix + re-baseline 0.3890 for
   one night), D17 (abandon criterion: M1 miss after Rungs 1+2+50M, or >20 lane-days, or
   >8 weeks). Recommendations in the file.
1. **Rung 0 measurement evening:** decompose the loop at [512,512] production width
   (embed_battle measured ~1.7 ms/decision — the wall may be our Python, not the server).
   Throughput spec + Rung 1/2 pre-reg configs: drafts landing from the research agents.
2. **Rung 1 (SIGNAL) after ratification:** 0.3890 config verbatim + gamma 0.95 + H&L 5-term
   zero-sum shaping; 3×12M ≈ one overnight; comparator re-eval at 3000/seed owed first.
3. ON ICE, zero rework to resume: warmrl draft (seeds 14–22 reserved), P4-scale collection GO
   (19.7 h), §11 D8/D9 (moot for the main line). Self-play chase claims seeds 23+.

## Watch items

- Seeds: 0/1/2 lra, 3/4/5 lra12m, 6/7/8 ArmB, 9 smoke, 10-13 SP preview+smoke, 14-22
  RESERVED (warmrl), 23+ = the chase. Distinct across lanes AND arms (username landmine).
  Showdown evals are UNPAIRED and non-reproducible — buy precision with battles.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **Encoder v2/807 is the chase's frozen observation (pending D13).** Semantics changed
  2026-08-06 at constant OBS_DIM; fingerprint in meta.yaml/bc_metrics.json is the guard.
  KNOWN BUG (D13): Effect.MUST_RECHARGE structurally always 0 in v1 AND v2; recharge/trap
  placeholder turns encode as unexplained all-zero move blocks. Fix = Stage-0, 2 dims,
  re-baselines the 0.3890 comparator if landed.
- **Rung 1 shaping is NOT Arm B:** non-cancelled, zero-sum, 5-term, gamma 0.95, mirror play
  — Arm B's null (cancelled potential-based single term vs SH) does not transfer. Its R0
  gate: both seats' shaping sums to exactly 0 per event; shaping/terminal mass ratio logged.
- BC-warm-start landmines (on ice with warmrl): loss/entropy 0.063 from update 1; critic
  warmup 5 at rollout 512; grad clip binds harder on warm starts (0.67→0.94).
- `score_ladder.py` default `--opponents` raises on Showdown; headline numbers come from
  `eval_checkpoint.py`. H&L scale accounting (both seats or one?) unresolved — settle from
  metagrok before Rung 3's 250M budget is set.
