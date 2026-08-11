# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-10 night — 50M READ OUT: CREDIT per ratified bar, seed-fragile)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). **RUNG 3 STEP 1 (50M structure-only) READ OUT
2026-08-10: s35 0.6593 / s36 0.5727 / s37 0.5087, pooled 0.5802 ± 0.0052 vs 0.5509 →
+0.0293, binomial z +3.99. CREDIT ADJUDICATED 2026-08-11 (maintainer, verbatim in
log): stands per the ratified header bar; seed-fragility (spread 0.151, seed-clustered
z +0.63) is a NAMED WEAKNESS carried in every narrative use — real on the registered
read, unreplicated at seed level.** M4 NOT claimed (+0.3σ margin, guard incomplete).
Anchor guard PARTIAL: clone-VP h2h (s36 final) 0.643 pooled ✓ moves; FP engine PENDING.
Best-ckpt secondaries (selection caveat): 0.633/0.619/0.594, pooled 0.6153 — every
lane ≥0.59; ckpt-selection policy question LIVE for the next pre-reg. M1–M3 CLAIMED at
12M (blessed 2026-08-09; adversarial prior-art search DONE — both novelty claims NOT
REFUTED, phrasing "no documented instance found"). README rewritten this session.

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
| SH mirror parity 0.489 · FP engine 0.8307* · clone h2h | 50M-vs-clone 0.643 pooled |

**LADDER:** M1/M2/**M3 (success claim) CLAIMED at 12M** · M4 ≥0.5777: letter-met at
50M, +0.3σ margin, guard partial — awaiting adjudication, NOT claimed.

## Next actions, in order

1. **FP engine read IN FLIGHT** (smoke PASSED 5/5; 250-battle read running, s36 final
   vs FP; marks: 0.824 taken off 12M, our take 0.172) — fold on landing, closes guard.
2. **D22 plateau diagnostics** (§12 RATIFIED 2026-08-11, D18–D22 binding; D22 first
   per its decision rule, then D18 privileged critic — plumbing ~2-3 evenings).
3. 250M: NOT auto-bought — slope seed-fragile; decision after D22 + seat accounting.
   Handoff on request. DONE 2026-08-11: credit adjudicated (header letter governs);
   §12 ratified; pushed through the ratification commit (maintainer-authorized).

## Watch items

- Seeds: 0-13, 23-37 SPENT, 14-22 RESERVED (warmrl), 99 disposable; 38+ free.
- **Entity ckpts need BOTH env vars at every eval** (v2+ids→828; dies loudly if not).
  Cross-encoder play needs the shim (808 ok; 807 refused). `simulator: 4` gitignored.
- Idle-box evals are FAST (~3 min/3000 battles); 3-wide training ~350-390 steps/s.
- Next pre-reg: consider val-peak-re-graded co-primary + n=1000 in-training evals.
- Laptop sleep kills session Monitors (not lanes/server); caffeinate for long jobs.
