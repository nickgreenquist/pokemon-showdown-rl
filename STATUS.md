# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-12 early morning — D18 READ OUT: NULL, falsifier-killed)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED: pooled 0.5802 ± 0.0052 CREDIT
(seed-fragility a NAMED WEAKNESS), M1–M3 claimed at 12M, M4 unclaimed.
**D18 PRIVILEGED CRITIC (5 lanes, seeds 39-43, 12M): NULL — pooled 0.5364 (Δ −0.0145
vs 0.5509, z −0.65), AND the pre-stated falsifier FIRED: EV rose on every lane
(~0.50 → 0.60-0.62 final, control plateau 0.549-0.561) while wr stayed flat — the
critic fit information the policy could not exploit. RUNG KILLED per its own clause;
no tuning, no rerun.** Srank secondary: privileged input did NOT de-collapse the
critic (ctx srank99 at 12M: 7-25 of 384 ≈ the 50M controls' 7-11) — collapse is
training-dynamics-intrinsic, not information starvation. s41 reproduced an s37-class
grad blowup (bin-medians →1607 over final 4M; trigger letter NOT met — one bin >100,
not three; now 2-of-8 entity lanes with the phenomenon). Val-peak co-primary pooled
0.5638 (+0.0129, recorded only; final→peak gap +0.0274 within-lane). H&L seat
accounting RESOLVED (both-seat; prior_work). DESIGN §13 (250M budget memo) PROPOSED.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| PPO 12M flat / +LR anneal — best vs-SH-TRAINED RL | 0.4330† / 0.4607† |
| Self-play 12M control (v2/808, flat MLP) | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL | 0.4131 ± 0.0052 |
| Rung 2 STRUCTURE 12M (entity DeepSets ptr) — CREDIT | 0.5509 ± 0.0052 |
| **Rung 3 50M finals — CREDIT (seed-fragile, see log)** | **0.5802 ± 0.0052** |
| D18 priv-critic 12M (5×3000) — NULL, falsifier-killed | 0.5364 ± 0.0066 |
| 50M best-ckpts pooled (SELECTION CAVEAT, secondary) | 0.6153 (0.594–0.633) |
| BC-of-FP clone graded final / val-peak = M4 bar | 0.5490 / 0.5777 ± 0.0090 |
| SH mirror parity 0.489 · FP engine 0.812-against* · clone h2h | 50M-vs-clone 0.643 pooled |

**LADDER:** M1/M2/**M3 (success claim) CLAIMED at 12M** · M4 ≥0.5777: letter-met at
50M, +0.3σ margin — NOT claimed (adjudicated).

## Next actions, in order

1. **D23 RATIFIED (3+2) + BUILT + ALL LAUNCH GATES CLEARED (f9e4333) — READY TO
   LAUNCH**: configs/showdown_sp_l2init12m.yaml (λ=0.02 decoupled decay toward θ₀;
   mechanism co-primary critic srank ≥40 vs control 11-17; BOUND ≤4.452 frozen).
   Launch: 3 treatment lanes (l2init cfg, seeds 44/45/46) + 2 comparator lanes
   (struct12m verbatim, seeds 49/50), staggered, 5-wide ~10.6 h. Suite 293 green.
2. **E1-E4 DONE 2026-08-12 (D12b discharged)**: E1 FLAT (serialization confirmed,
   num_envs dead as a lever); E2 reset 5% (ignore); E3 race_get 54% (middle band);
   E4a node 7.6% of a core; E4b knee at K=8, ~1240 dec/s at entity width = 2.3×
   solo loop → Stage-2 async collector pays; 250M×3 post-Stage-2 ≈ 7-8 lane-days.
3. 250M decision: per §13 — needs a credited lever at 50M + the cap/rent question
   (E1-E4 gate now cleared).

## Watch items

- Seeds: 0-13, 23-43 SPENT, 14-22 RESERVED (warmrl), 99 disposable; **44+ free.**
- **Entity ckpts need BOTH env vars at every eval** (v2+ids→828; dies loudly if not).
  D18 ckpts additionally carry privileged_dim (make_agent rebuilds; plain-828 into
  the widened critic raises loudly). `simulator: 4` gitignored in showdown/config.
- Idle-box evals: 5×3000 concurrent ≈ 6 min/batch (measured at readout).
- Artifacts: results/d18/ (gitignored) — eval JSONs, grade.txt, obs tapes, rank CSVs.
- 4 commits local past origin (f55f0a3..): push NOT yet authorized — ask.
- Laptop sleep kills session Monitors (not detached jobs); caffeinate for long jobs.
