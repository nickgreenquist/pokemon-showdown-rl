# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-11 late night — D22 CLOSED; D18 BUILT, ready to ratify+launch)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED: pooled 0.5802 ± 0.0052 CREDIT
(adjudicated 2026-08-11; seed-fragility a NAMED WEAKNESS), M1–M3 claimed at 12M, M4
unclaimed (+0.3σ), anchor guard complete (clone h2h 0.643, FP 0.812-against).
**D22 PLATEAU DIAGNOSTICS (§12) — reads 1–4 DONE 2026-08-11 (offline): EV flat
0.56–0.59 all lanes 5M→50M; entropy NOT collapsed (0.21–0.32 at 50M); weight norms
grow ×2.3–3.0 monotonically (embeddings fastest); dormant fraction climbs to 84–88%
(actor ctx layer, s35/s36); ctx feature srank99 collapses ~250→33–54 (actor), →7–11
of 384 (critic). READ 5 (exploitability, ran 2026-08-11 night): fresh 6M
best-response vs frozen s36-50M final → pooled two-orientation h2h **0.4765 ± 0.0112
< 0.55 = equilibrium ROBUST at probe budget**. §12 routing FINAL: representation
clause fires, exploitability clause dead on both halves → D18 FIRST, AS QUEUED.**
Seed-fragility explained mechanically: s37 flatline = sustained actor grad blowup
from ~20M + critic stall at 25M; s35 = same norm growth, one recovered spike, still
rising at 50M. Regenerative L2-toward-init named next-after-D18 (jumps queue if D18
reproduces an s37-class blowup). Frozen-ckpt opponent seam landed (rl/train.py,
suite 269 green). BR color: exploiter hit ~0.56 vs SH in 6M vs one frozen opponent.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| PPO 12M flat / +LR anneal — best vs-SH-TRAINED RL | 0.4330† / 0.4607† |
| Self-play 12M control (v2/808, flat MLP) | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL | 0.4131 ± 0.0052 |
| Rung 2 STRUCTURE 12M (entity DeepSets ptr) — CREDIT | 0.5509 ± 0.0052 |
| **Rung 3 50M finals — CREDIT (seed-fragile, see log)** | **0.5802 ± 0.0052** |
| 50M best-ckpts pooled (SELECTION CAVEAT, secondary) | 0.6153 (0.594–0.633) |
| BC-of-FP clone graded final / val-peak = M4 bar | 0.5490 / 0.5777 ± 0.0090 |
| SH mirror parity 0.489 · FP engine 0.812-against* · clone h2h | 50M-vs-clone 0.643 pooled |

**LADDER:** M1/M2/**M3 (success claim) CLAIMED at 12M** · M4 ≥0.5777: letter-met at
50M, +0.3σ margin — NOT claimed (adjudicated).

## Next actions, in order

1. **D18 RUNNING (launched 16:03 EDT 2026-08-11; 5 lanes, seeds 39-43; ~300
   steps/s/lane → finals ETA ~03:30-04:30 EDT 08-12; 3.3M health check GREEN, s41
   270 sps record-and-continue)**: configs/showdown_sp_priv12m.yaml — critic =
   actor-obs ‖ opponent own-side block (408d). OPERATIVE bar: floor 0.5809, ~0.589
   at Rung-2-like spread (larger-of rule; 0.5759 binomial letter); recording rule
   pre-stated for the unclaimable band. At readout: 5×3000 finals + val-peak
   re-grades + EV/srank secondaries (d22 scripts need priv adaptation first).
2. Regenerative L2-toward-init: named next-after-D18; jumps queue if D18 lanes
   reproduce an s37-class grad blowup (D22-watch gate in the header, record-only).
3. 250M decision: after D18 + H&L seat accounting (gates any 250M quote).

## Watch items

- Seeds: 0-13, 23-38 SPENT, 39-43 ASSIGNED (D18 lanes), 14-22 RESERVED (warmrl),
  99 disposable; **44+ free.**
- **Entity ckpts need BOTH env vars at every eval** (v2+ids→828; dies loudly if not).
  Cross-encoder play needs the shim (808 ok; 807 refused). `simulator: 4` gitignored.
- Idle-box evals FAST (~3 min/3000); FP reads ~6.5-10 s/battle; solo lane ≥400 steps/s.
- D22 artifacts: results/d22/ (gitignored) — CSVs + mirror obs tapes (obs_s3*.npz).
- Laptop sleep kills session Monitors (not lanes/server); caffeinate for long jobs.
