# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`, the arc: gen1→gen4→gen9)
**Step 1 = gen1 retrain, batch lever** (= R2 below). SCOPE GUARD, binding: a
read inside the bar is information about the INSTRUMENT, not a licence to
queue another gen1 lever — ladder anyway (step 2), then step 3 (gen4).
**Name the JOURNEY step every work item serves; off-arc work needs a ruling.**

## Where things stand (2026-08-29) — **LADDER R3 COMPLETE at n=200**, readout
committed, backup archived. `nickgen1rbrlbot2` RETIRES; iteration runs share
`nickgen1rbrlbot`; a FINAL fresh account is DEFERRED (courtesy note to PS staff
falls due there). CH5 R1 CLOSED. **r9 rescore IN FLIGHT: RS82 landed 0.454 (G2
exact); RS81 re-running on its r10 b-pair after an FP panic burned the first.**
Pure self-play; THE NOVELTY IS THE LANE.

## Results | 12M **0.71825** vs SH · ensemble 0.74633 · search@M 0.79283 (**12M**)
· **LADDER R1 (ensemble): GXE 59.6%, Glicko 1573±27, Elo 1292, n=200** ·
**LADDER R3 (search@M, s80): GXE 60.3%, Glicko 1579±25, Elo 1232, 106-94,
n=200 — STANDALONE; no R1-vs-R3 delta is a quantity (D5)** · off FP@20 greedy
0.3960/0.3430/0.2730 · C0 0.3893 · **fresh n=3000: RS80 0.4390, RS82 0.454.**
Ties=loss. **Ladders credit nothing.**

## Facts that travel with any R3 quote
- ONE of three anchors (FP@20 only); name the budget on every FP number.
- Profile 106-102 vs JSONL 106-94: 8 extra losses are battles OUR socket died
  under — IN the rating, not the tally; its 19 timeout_midgame are not R1's
  six. Two blind breaches disclosed; neither voids the read.
- R1 band cells: use the CORRECTED (BI-4) set — licensed cell 0.319, aggregate
  implied 1214. The pre-reg pins the superseded ones (REPO_CLEANUP A1).

## Next actions
0. **FINISH THE RESCORE** — RS81 lands ~03:15Z; then `ch5_r1_grade.py` on both
   arms and apply `policy_form_decision` MECHANICALLY (two keys; GREEDY on any
   void/partial). It sets R2's policy form and nothing else.
1. **R2 = BATCH** (JOURNEY step 1). 3 new 50M lanes, s80/81/82 the free
   control. **PRIMARY READ IS STRENGTH vs the 0.1007 bar** (r9-corrected: BOTH
   sides carry the clustered term). sigma_seed descriptive with its (2,2)-df
   disclosure. H&L is VERIFIED, an EXISTENCE PROOF not a target (m=7680 was "a
   completely arbitrary choice"); minibatch 256, scale the COUNT. Header carries
   `journey_step: 1` + the scope guard verbatim.
2. lambda = a CONFIG choice on the explained-variance diagnostic, both arms, not
   an arm; `loss/explained_variance` IS logged (ppo.py:1189).
3. THEN curve vs credited win rate — gates LANES AND SCALE, not batch.
4. Descriptive: D4 anchors on all three lanes, cross-play, one R2 arm both ways.
   Cleanup: `REPO_CLEANUP.md` (ideas only; audit first) + `CLEANUP.md`.

## Watch items
- **SEARCH MAY EQUALISE THE LANES** — off FP@20 search-minus-greedy monotone in
  lane weakness 3/3, spread 0.123 → 0.026. **2 df, p~0.06: HYPOTHESIS**; scoring
  levers under search is a SCOPE CHANGE.
- **k~24 kills lanes; (2,2) df kills the variance READ** — batch is a STRENGTH
  lever, NOT the instrument fix (RETRACTED; CH5 §5 superseded).
- **NEW: foul-play can PANIC** (`Invalid PokemonMoveIndex: 4`, Rust) twice in
  RS81 by 1580; a mid-battle death poisons the pair (`burned_pairs_r10`:
  fresh pair, re-run LAST). TIE-CRASH WEDGE: auto-tie + FP death on one
  battle hangs the seat with no JSON.
- **R4:** `.env` holds bot2's creds; VOID (f) INVERTS on a persistent seat.
