# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-28) — **LADDER R3 IS RUNNING.** One continuous
run to n=200, search@M on s80, account `nickgen1rbrlbot2`, launched 2026-08-27
evening EDT, ETA **16-19 h + a 1-2 h auto-tie tail**. Six rulings taken,
`ladder_r3.yaml` **RATIFIED**, BI-1/2/3/5/6 landed (BI-4 waived), **all seven
launch gates passed.** CH5 R1 CLOSED. Pure self-play; THE NOVELTY IS THE LANE.

## DO NOT KILL THE R3 RUN
Killing mid-battle **forfeits a live rated game against a human** and
contaminates the rating R3 exists to measure; unlike a poisoned local room it
**cannot be undone**. If it must stop, that is an operational abort under
G-BLIND (4): log the cause AND the battle index. If it dies on its own,
relaunch with the **same `--battles 200`** — the JSONL is truth, a death costs
one battle. Watch `results/ladder/R3S.run.log`; **`s/battle` is the only honest
progress signal**, band **[250,400]**. **Do NOT open the profile, replays or
board before n=200** (G-BLIND). After: `bash scripts/backup_ladder.sh`.

## Results | D26 12M **0.71825** vs SH · R0 ensemble 0.74633 · search@M 0.79283
(**12M**) · **LADDER R1: GXE 59.6%, Glicko-1 1573+/-27, Elo 1292, n=200** · R1
off FP@20 — greedy s80/81/82 0.3960/0.3430/0.2730 · search@M 0.4470/0.4470/
0.4210 · C0(L2) 0.3893 · **RS80 (fresh, n=3000) 0.4390.** **R1 CREDITS NOTHING.**

## The six R3 rulings — full record in `ladder_r3.yaml: ratified_decisions`
Two not to re-litigate: **D1 unattended is legitimate because R1 ITSELF RAN
UNATTENDED OVERNIGHT** (SESSION_LOGS 2026-08-26) — the draft's "inadmissible"
was a stricter new position dressed as the standing rule. **D2: a THIRD rated
account requires a courtesy note to PS staff.**

## Next actions (revised 2026-08-28 — derivation in SESSION_LOGS 02:30Z)
0. **DECIDE: SCALING CURVE or CREDITED WIN RATE.** A policy change, not a
   re-prioritisation — curve makes 120/250M runs first-class against the
   2026-08-23 ruling, drops the resolution bar, and **dissolves the owed
   C2-vs-batch ruling**. Everything below is downstream.
1. **Read R3 out when it stops** — pass every flag; all three readout scripts
   default to R1's paths AND name. BI-4 (band table) owed first.
2. **D4's anchors, AMENDED: BC-clone h2h on ALL THREE lanes** (~+1.5 h on the
   2.7 h) — a free independent replication of the equalisation test.
3. **Rescore search@M on s81/s82 at n=3000** (~4.9 h, eval), owed BEFORE R2's
   pre-reg: it sets the policy form. **R2 COMMITTED** — score one arm BOTH
   greedy and searched (eval-only). Then `CLEANUP.md`.

## Watch items
- **k ~ 24.** Bar = `2*sigma_seed/sqrt(k)` = 0.0717 at k=3, so the +0.025 credit
  floor needs **k>=24 lanes** (k=6 buys 0.051). **C2 cannot credit a +0.02-0.05
  lever at any realistic k** — CHAPTER5 §5 has a supersession note. Batch is now
  the instrument work AND **an unmeasured bet**.
- **SEARCH MAY EQUALISE THE LANES** — off FP@20 the search-minus-greedy gain is
  monotone in lane weakness 3/3 (+0.051/+0.104/+0.148), collapsing a 0.123
  spread to 0.026. **2 df, p~0.06, CI contains greedy's 0.0617: HYPOTHESIS.**
  Read the rescore for **s81, not s82** (s82 is the known-bad lane, 5.2 se).
  Scoring levers under search is a **scope change** — the same mechanism that
  buys the variance masks value-head gains.
- Never quote an R1-vs-R3 delta as an effect (D5); never set 0.4390 beside the
  12M 0.79283 or read it as vs-SH; name the budget (FP@20). R3 has ONE of three
  anchors. **R1's "217 s/battle" is wrong — 246.5.**
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED** (3 copies; R3 shares R1's root
  for exactly that reason). **NEVER re-run a killed arm IMMEDIATELY.**
