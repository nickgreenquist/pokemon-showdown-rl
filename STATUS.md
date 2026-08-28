# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-28) — **LADDER R3 COMPLETE at n=200.** Stopping
rule met mechanically (rd 25.4); readout committed (`LADDER_R3_READOUT.md`,
every flag passed, all disclosures in); backup mirror-verified + archived.
`nickgen1rbrlbot2` RETIRES; iteration runs share `nickgen1rbrlbot`; a FINAL
fresh account is DEFERRED (the courtesy note to PS staff falls due there).
CH5 R1 CLOSED. Pure self-play; THE NOVELTY IS THE LANE.

## Results | 12M **0.71825** vs SH · ensemble 0.74633 · search@M 0.79283 (**12M**)
· **LADDER R1 (ensemble): GXE 59.6%, Glicko 1573±27, Elo 1292, n=200** ·
**LADDER R3 (search@M, s80): GXE 60.3%, Glicko 1579±25, Elo 1232, 106-94,
n=200 — STANDALONE; no R1-vs-R3 delta is a quantity (D5)** · off FP@20 greedy
0.3960/0.3430/0.2730 · search 0.4470/0.4470/0.4210 · C0 0.3893 · RS80 0.4390.
Ties=loss. **Ladders credit nothing.**

## Facts that travel with any R3 quote
- ONE of three anchors (FP@20 only); name the budget on every FP number.
- Profile 106-102 vs JSONL 106-94: the 8 extra server-side losses are battles
  OUR socket died under — IN the rating, not in the tally. Its 19
  timeout_midgame are not R1's six; never pool them.
- Two blind breaches disclosed (battle-10 rating print; battle-200 board
  watch). Mechanical rule → neither voids the read.
- R1 band cells: use the CORRECTED (BI-4) set — licensed cell 0.319, aggregate
  implied 1214. The pre-reg pins the superseded ones; readout+README fixed.

## Next actions (order per SESSION_LOGS 2026-08-28 03:10Z)
0. **Rescore search@M on s81/s82 at n=3000** (~4.9 h, eval; agent-side OK if
   detached + resume-safe + rate-checkable). The ONLY thing gating R2 — it
   sets the policy form. **Read s81, not s82** (s82 known-bad at 5.2 se).
1. **R2 = BATCH.** 3 new 50M lanes, s80/81/82 the free control. **PRIMARY READ
   IS STRENGTH vs the 0.1007 bar** (r9-corrected: BOTH sides carry the clustered
   term; R1-A's 0.0717 had the near-zero-sd 12M comparator); sigma_seed
   descriptive with its (2,2)-df disclosure. Verify H&L's update count against SOURCE; minibatch stays 256,
   scale the COUNT.
2. lambda = a CONFIG choice on the explained-variance diagnostic, both arms —
   not an arm. Check EV is logged (absent from the locked metric names).
3. THEN decide CURVE vs CREDITED WIN RATE — a policy change; gates LANES AND
   SCALE, not batch. k~24 needed for the +0.025 floor at current sigma_seed.
4. Around the training: D4 anchors AMENDED to BC-clone h2h on ALL THREE lanes
   (free equalisation replication), cross-play, one R2 arm scored both ways.
   Then `CLEANUP.md`.

## Watch items
- **SEARCH MAY EQUALISE THE LANES** — off FP@20 search-minus-greedy is
  monotone in lane weakness 3/3 (+0.051/+0.104/+0.148), spread 0.123 → 0.026.
  **2 df, p~0.06: HYPOTHESIS.** Scoring levers under search is a SCOPE CHANGE.
- **k~24 kills lanes; (2,2) df kills the variance READ** — batch must cut
  sigma_seed 4.4x to register (F crit 19.0), so batch is a STRENGTH lever,
  NOT the instrument fix (RETRACTED; CHAPTER5 §5 superseded).
- **R4 gotchas:** `.env` still holds bot2's credentials; VOID (f) INVERTS on a
  persistent seat — an existing rating is EXPECTED, its absence is the alarm.
- 19 commits unpushed; **ask before pushing.**
- Never set a ladder number beside the 12M 0.79283 or read it as vs-SH. R1
  s/battle is 246.5 ("217" is the wrong division); R3's median is 218.
