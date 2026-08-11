# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-11 evening — D22 reads 1–4 IN; read 5 ready to launch)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED: pooled 0.5802 ± 0.0052 CREDIT
(adjudicated 2026-08-11; seed-fragility a NAMED WEAKNESS), M1–M3 claimed at 12M, M4
unclaimed (+0.3σ), anchor guard complete (clone h2h 0.643, FP 0.812-against).
**D22 PLATEAU DIAGNOSTICS (§12) — reads 1–4 DONE 2026-08-11 (offline): EV flat
0.56–0.59 all lanes 5M→50M; entropy NOT collapsed (0.21–0.32 at 50M); weight norms
grow ×2.3–3.0 monotonically (embeddings fastest); dormant fraction climbs to 84–88%
(actor ctx layer, s35/s36); ctx feature srank99 collapses ~250→33–54 (actor), →7–11
of 384 (critic). §12's representation clause (flat EV + low rank) FIRES CLEANLY →
provisional routing: D18 first, AS QUEUED.** Seed-fragility explained mechanically:
s37 flatline = sustained actor grad blowup from ~20M (pre-clip median 1088, clip
pinned 1.0) + critic stall at 25M; s35 = same norm growth, one recovered spike, still
rising at 50M. Regenerative L2-toward-init named next-after-D18 (jumps queue if D18
reproduces an s37-class blowup). Read 5 (exploitability probe) pre-registered:
configs/showdown_br50m_s38.yaml — fresh entity learner vs FROZEN s36-50M final, 6M,
seed 38; frozen-ckpt opponent seam landed (rl/train.py, suite 269 green, live-smoked).

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

1. **LAUNCH D22 read 5** (maintainer terminal; launch = ratification of the header):
   configs/showdown_br50m_s38.yaml, ~3–4 h solo. Post-run: two-orientation h2h
   1000/orientation vs frozen s36-50M (commands in the config header).
2. **D18 privileged critic** (routing confirmed by reads 1–4; plumbing ~2–3 evenings;
   header MUST restate the FULL credit line incl. larger-of se_diff clause).
3. 250M decision: after read 5 + H&L seat accounting (gates any 250M quote).

## Watch items

- Seeds: 0-13, 23-38 SPENT/assigned (38 = BR probe), 14-22 RESERVED (warmrl), 99
  disposable; **39+ free.**
- **Entity ckpts need BOTH env vars at every eval** (v2+ids→828; dies loudly if not).
  Cross-encoder play needs the shim (808 ok; 807 refused). `simulator: 4` gitignored.
- Idle-box evals FAST (~3 min/3000); FP reads ~6.5-10 s/battle; solo lane ≥400 steps/s.
- D22 artifacts in results/d22/ (gitignored): binned trajectories, weight norms,
  dormant/rank CSVs, per-lane mirror obs tapes (obs_s3*.npz, 5.8-7.4k decisions).
- Laptop sleep kills session Monitors (not lanes/server); caffeinate for long jobs.
