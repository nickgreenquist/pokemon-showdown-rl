# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-28) — **LADDER R3 IS RUNNING.** One continuous
run to n=200, search@M on lane s80, account `nickgen1rbrlbot2`, launched
2026-08-27 evening EDT, ETA **16-19 h + a 1-2 h auto-tie tail**. All six R3
rulings taken, `configs/eval/ladder_r3.yaml` **RATIFIED**, BI-1/2/3/5/6
landed, BI-4 waived with fallback, **all seven launch gates passed.**
CH5 R1 CLOSED (ten arms, zero VOIDs). Pure self-play; THE NOVELTY IS THE LANE.

## DO NOT KILL THE R3 RUN
Killing mid-battle **forfeits a live rated game against a human** and
contaminates the rating R3 exists to measure. Unlike a poisoned local room it
**cannot be undone** by waiting or restarting a server. If it must stop, that
is an operational abort under G-BLIND (4): log the cause AND the battle index.
If the process dies on its own, relaunch with the **same `--battles 200`** —
the JSONL is the truth and a death costs one battle, not the run.

## Watching it
- `tail -f results/ladder/R3S.run.log` — one line per battle with a running W/n.
- **`s/battle` is the only honest progress signal**; a wall-clock ETA is not
  progress. Band **[250, 400]**, expect ~283-322. A 10x discrepancy = stalled.
- **G-BLIND: do NOT open the profile, replay list or board before n=200** — an
  honour-system blind. After it finishes: `bash scripts/backup_ladder.sh`.

## Results | D26 12M **0.71825** vs SH · R0 ensemble 0.74633 · R2 search@M
0.79283 (**12M lanes**) · **LADDER R1: GXE 59.6%, Glicko-1 1573+/-27, Elo
1292, n=200** · R1 off FP@20 — greedy s80/s81/s82 0.3960/0.3430/0.2730 ·
search@M 0.4470/0.4470/0.4210 · C0(L2) 0.3893 · **RS80 (fresh, n=3000,
PUBLISHABLE) 0.4390.** Ties=loss. **R1 CREDITS NOTHING.**

## The six rulings (full record in `ladder_r3.yaml: ratified_decisions`)
- **D1 ONE CONTINUOUS RUN, unattended.** The draft called this inadmissible on
  R1's moderator-contact commitment. **R1 ITSELF RAN UNATTENDED OVERNIGHT**
  (SESSION_LOGS 2026-08-26) — a new stricter position dressed as the standing
  rule, declined. It is also *better*: a per-session `--battles` target is not
  among G-BLIND's four licensed stops, so two sessions would have tripped VOID
  (g) or forced a launch-night amendment.
- **D2** sequential 2nd account inside the line; **a THIRD requires a courtesy
  note to PS staff** (pre-committed). **D3** BI-6 **and** BI-5 landed — the
  poke-env deadlock became load-bearing *because* D1 went unattended.
- **D4 DEFERRED TO READOUT** (unclosable before launch — anchors contend for
  CPU). **D5** ratified verbatim. **D6** search reversal on the record.

## Next actions
1. **Read R3 out when it stops** — pass every flag; the three readout scripts
   default to R1's paths AND R1's name. BI-4 (band table) is owed first.
2. Then **D4's anchors** (~2.7 h) before any R3 README row.
3. **R2 retrain is COMMITTED, not optional.** Batch ruling still owed (branch
   table routes to C2; batch is §3b A4). Then `CLEANUP.md` rulings.

## Watch items
- **R3's object has ONE of three anchors**: vs-SH and BC-clone DO NOT EXIST
  for search on a 50M lane (0.79283/0.860 are 12M). RS80 gives FP@20 only.
- **Never quote an R1-vs-R3 delta as an effect** (D5); never set RS80's 0.4390
  beside the 12M cell 0.79283 or read it as vs-SH. Name the budget: FP@20.
- **R1's "217 s/battle" IS WRONG.** True **246.5**, from `finished_at` deltas.
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED** (3 copies; R3 shares R1's root
  for exactly that reason). **NEVER re-run a killed arm IMMEDIATELY.**
