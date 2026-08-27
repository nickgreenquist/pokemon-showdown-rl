# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-27 late) — **CH5 R1 COMPLETE (9 arms, ZERO
VOIDS, G2 exact). `RS80`, the mandatory fresh re-score, STILL RUNNING.**
Tonight fixed two live ladder-runner defects and landed
**`configs/eval/ladder_r3.yaml` as a DRAFT with 6 open decisions. HANDOFF.md
is non-empty — read it first.** Pure from-scratch self-play; THE NOVELTY IS
THE LANE. CH3 + CH4-R1 CLOSED.

## Results | D26 12M **0.71825** vs SH · R0 ensemble 0.74633 · R2 search@M
0.79283 (**12M lanes**) · **LADDER R1: GXE 59.6%, Glicko-1 1573+/-27, Elo
1292, n=200** · **R1 off FP@20 — greedy s80/s81/s82 0.3960/0.3430/0.2730 ·
search@M 0.4470/0.4470/0.4210 · C0(L2) 0.3893 · CE3 0.3623 · CE7 0.3827.**
Ties=loss. **R1 CREDITS NOTHING.** RS80 pending.

## R1's answers (full detail in SESSION_LOGS 2026-08-27)
- **R1-A PRIMARY:** s82's collapse REPRODUCES off-FP, +0.0965 vs bar 0.0369 =
  **5.2 se** — a genuinely bad seed, not an SH artifact.
- **R1-A FLEET: WITHIN x NON-RESOLVING**, −0.0113 vs a REALIZED bar of
  **0.0717**. Action verbatim: buy LANES or drop the scale question. **"flat"
  is BARRED; the realized 0.0717 travels with any sentence.**
- **R1-B: SEARCH HELPS**, within-lane +0.1010, bar 0.0561, 3.6 se. **CEILING:
  R3 DEPLOYMENT CANDIDATE ONLY; does NOT reverse MU-8 (z=−2.80); never set
  beside the 12M cell.** **R1-C NOT DELIVERED**; L2 holds.

## Landed tonight (committed + pushed)
- **`ladder.py` read the rating off the LEADERBOARD, which lists only top-500
  accounts.** R1 ran unlisted, so its rule could never fire — **while R1 sat
  at rd 26.6 / n 200, i.e. SATISFIED.** Two tests PINNED the wrong behaviour:
  a green suite defended the bug. Now reads the USER PROFILE. Same class
  fixed in the readout generator (pre-battle "Elo 1311" emitted as final).
- **`PS_USERNAME` silently overrode the pre-registered account name** — a
  stale export would have laddered R3 on R1's account. **Config wins now.**
- **R3 pre-reg DRAFT** (2-Opus cycle; every claim re-verified against source).

## Next actions
1. **GRADE `RS80`** on landing: `python scripts/ch5_r1_grade.py`. The 0.4470
   is a SELECTION score and **MAY NOT BE PUBLISHED** (Q6).
2. **R3 needs 6 rulings** — `ladder_r3.yaml` `open_decisions`. Biggest is
   **D1: it is NOT one night**, 200 battles = **16-19 h** (+1-2 h auto-tie
   tail); recommend two sessions of ~100. `nickgen1rbrlbot2` registered,
   `.env` set.
3. **R2 retrain is COMMITTED, not optional.** Batch ruling owed (branch table
   routes to C2; batch is §3b A4). HANDOFF.md §5. Then `CLEANUP.md` rulings.

## Watch items
- **R1's "217 s/battle" IS WRONG** (session-scoped numerator / cumulative
  denominator). True rate **246.5**, from the JSONL's `finished_at` deltas.
- **`ladder.py` is still `max_concurrent_battles=1`** while the FP seat went to
  2 on 2026-08-27 to close a poke-env deadlock its own fix comment says SEARCH
  is exposed to. On a rated ladder that hang forfeits a live game against a
  human. `<< MAINTAINER 3 >>`; UNMEASURED on the ladder path.
- **The R3 object has ONE of three anchors** — vs-SH and BC-clone DO NOT EXIST
  for search on any 50M lane (0.79283/0.860 are 12M). RS80 gives FP@20.
- **Ladder readout scripts default to R1's paths AND name**: run bare they
  emit a normal-looking readout OF R1. Pass every flag.
- **NEVER re-run a killed arm IMMEDIATELY** — poisoned Showdown room. **LADDER
  DATA IS UNREPEATABLE AND GITIGNORED** (3 copies; R3 shares R1's root).
