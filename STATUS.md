# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D23 READ OUT: letter-met, NOT credited; mechanism strong)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (0.5802 CREDIT, seed-fragile).
D18 priv-critic: NULL, falsifier-killed. **D23 REGEN-L2 (λ=0.02 toward-init, 3
treatment + 2 fresh comparator lanes): Δ +0.0451 (0.5897 vs 5-seed comparator 0.5445)
— "letter-met, seed-fragile, NOT credited" per the pre-stated recording rule
(clustered 2·se 0.0650; treatment spread 0.0491, s44 0.6463 vs arm-mates 0.561).
MECHANISM: BOUND (species_emb ×4.10-4.17 vs control ×5.8-6.1), final→peak gap SHRANK
(+0.0114 vs D18 +0.0274, prediction realized vs adversarial confound), srank 2-3×
control (31/53/36 vs 11-17) but de-collapse letter NOT met (≥40 on ≥2/3). Falsifier
NOT fired — family neither killed nor closed.** MAJOR FINDING: fresh comparator lanes
(0.5763, 0.4937) show true Rung-2 12M seed sd ≈0.036 (3-seed estimate was 0.026) —
12M win-rate primaries are effectively un-creditable at advisory-scale effects;
mechanism reads must carry future 12M rungs. s49 died at 7.2M (exogenous eval
auto-tie crash), re-run as s51 pre-grading; zombie-battle relaunch landmine logged.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| PPO 12M flat / +LR anneal — best vs-SH-TRAINED RL | 0.4330† / 0.4607† |
| Self-play 12M control (v2/808, flat MLP) | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL | 0.4131 ± 0.0052 |
| Rung 2 STRUCTURE 12M (entity DeepSets ptr) — CREDIT | 0.5509 ± 0.0052 |
| Rung 2 comparator refresh (5 seeds, 2026-08-13) | 0.5445, sd 0.0356 |
| **Rung 3 50M finals — CREDIT (seed-fragile, see log)** | **0.5802 ± 0.0052** |
| D18 priv-critic 12M — NULL, falsifier-killed | 0.5364 ± 0.0066 |
| D23 regen-L2 12M — letter-met, NOT credited (s44 0.6463!) | 0.5897 ± 0.0066 |
| BC-of-FP clone graded final / val-peak = M4 bar | 0.5490 / 0.5777 ± 0.0090 |
| SH mirror parity 0.489 · FP engine 0.812-against* | clone h2h 0.643 pooled |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4: letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

1. **MAINTAINER CALL — what follows D23's recording-band readout**: (a) D19 as
   queued (aux opponent-model head, actor-side); (b) 50M regen-L2 carry — BOUND +
   gap-shrink + letter-met make a real case, but ~5 lane-days exceeds the 20-day
   cap (chapter ~17/20) → needs the cap conversation; (c) both, sequenced. The
   comparator-spread finding also reframes 12M rungs: mechanism-primary designs.
2. Post-chase bundle: comparator-spread finding + D23 mechanism story are
   publishable-negative-adjacent material; README updated, DESIGN §12 queue intact.
3. 250M: per §13 — still needs a credited lever at 50M + cap/rent answer (E1-E4
   cleared; Stage-2 collector measured 2.3× at entity width).

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED** (dead lane); 14-22 RESERVED;
  99 disposable; **47-48, 52+ free.**
- Entity ckpts need BOTH env vars; D23 treatment ckpts also fine on plain eval
  path (theta0 never needed at eval; theta0.pt lives in each run dir).
- Eval auto-tie crash (1-in-10⁴ eval battles) can kill a lane at eval; relaunch
  same-seed collides with zombie server battles — use a FRESH seed (log 08-12).
- Artifacts: results/d23/ (gitignored) — grade.txt, 8 eval JSONs, norms, ranks.
- Suite 293 green (R0-3 golden needs its own pytest process — 1-ULP flake, log).
