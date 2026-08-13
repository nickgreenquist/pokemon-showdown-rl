# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — carry rejected, D19 killed, D25 pre-registered; 0 lanes)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (era-graded, seed sd 0.0756); D18
NULL, falsifier-killed; D23 regen-L2 **"letter-met, seed-fragile, NOT credited"**;
Rung-2 12M seed sd ≈0.036. **THE 50M CARRY IS REJECTED** (2 designers + 2 reviews + 2
opposed advocates, 0 lanes) — no branch changes a decision, and the 50M win-rate credit
bar is **≥0.6675 unconditionally**, above the best lane ever (0.6593). Zero-lane work
landed (see the 08-13 log): rank tooling repaired (**two** NaN-sentinel cells fixed) and
the **GEOMETRIC-NULL STUDY** (results/d24_null/) re-grades D23 at matched distance —
**critic de-collapse SURVIVES (1.35/2.21/1.64×, robust to every aggregation); the actor
read is INCONCLUSIVE, not refuted** (median-null 1.57/1.18/0.74; the earlier "2 of 3
below geometry" used the max null, anti-conservative for retiring a claim).

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

0. **D25 (opponent ACTION prediction) PRE-REGISTERED, PROPOSED, NOT BUILT** —
   `configs/showdown_sp_actpred12m.yaml` (7 docs merged, 16 conflicts ledgered; body
   diff = seed, run_name, 5 aux keys). Premise: **0.544 nats realised, actor-visible,
   ~37% of the loss** vs D19's 0.347 (D19's kill stands; its recorded *reasoning* was
   wrong — see the 08-13 red-team entry). Letter Δ_ref-ctx, level 12/252 = 0.0476,
   **MDE(80%) 0.009-0.011, power 0.45-0.88** (range, not the 0.88 best case). Cost
   ~2.35 lane-days → 15.9/20; build ~200 lines. **BLOCKING: re-freeze the control
   distribution on a checkpoint in NEITHER arm** (the gate used comparator s26;
   s35@12M recommended). **YOUR CALL: placebo arm +2.24 lane-days** — "an opponent
   model helps" vs "an aux loss helps".
1. **LEDGER AUDITED — recorded ~17 was ~3.5 HIGH.** 392.8 lane-hours, 67.9 pre-chase →
   **chase = 13.54, headroom ~6.5**; drift was estimate-rounding. Re-measure, never
   increment.
2. **§13 DEFECT:** conditions 250M on "a credited lever at 50M"; none exists under
   today's line → restate or waive. CLAUDE.md's locked-eval line says 1000
   battles/seed, DESIGN §8 says 3000 — fix.

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable;
  **47-48, 52+ free**. Rank reads: margin over the matched-distance null — **MAX null
  to establish an effect, MEDIAN to retire one; not interchangeable**; `--tag` them.
- **Quote the range, not the best measured variant** — this session's systematic error.
- Entity ckpts need BOTH env vars. Eval auto-tie crash can kill a lane; relaunch on a
  FRESH seed (same-seed hits zombie battles; s49→s51, log 08-12).
- Aux head: own it on the AGENT; aux params get their OWN optimizer group (group-0
  append steals the critic's Adam moments) and SEPARATE clipping. `ctx` is max-pooled,
  logits are `scorer([ctx‖entity])` ⇒ heads and estimators must be scorer-shaped.
- Artifacts results/d23/, d24_design/, d24_null/ (gitignored). Suite 293 green. Process:
  2 Opus designers + 2 reviews per pre-reg.
