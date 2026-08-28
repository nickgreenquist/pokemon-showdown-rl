# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-28) — **LADDER R3 IS RUNNING**: one continuous run
to n=200, search@M on s80, `nickgen1rbrlbot2`, ETA **16-19 h + a 1-2 h tail**.
`ladder_r3.yaml` **RATIFIED** (six rulings), BI-1/2/3/5/6 landed (BI-4 waived),
all seven gates passed. CH5 R1 CLOSED. Pure self-play; THE NOVELTY IS THE LANE.

## DO NOT KILL THE R3 RUN
Killing mid-battle **forfeits a live rated game** and cannot be undone. An early
stop is an operational abort under G-BLIND (4): log the cause AND battle index.
If it dies on its own, relaunch with the **same `--battles 200`** — the JSONL is
truth. Watch `results/ladder/R3S.run.log`; **`s/battle` is the only honest
progress signal**, band **[250,400]**. **Do NOT open the profile, replays or
board before n=200.** After: `bash scripts/backup_ladder.sh`.

## Results | 12M **0.71825** vs SH · ensemble 0.74633 · search@M 0.79283 (12M) ·
**LADDER R1: GXE 59.6%, Glicko 1573+/-27, Elo 1292, n=200** · off FP@20: greedy
0.3960/0.3430/0.2730 · search 0.4470/0.4470/0.4210 · C0 0.3893 · **RS80 0.4390
(fresh, n=3000).** Ties=loss. **R1 CREDITS NOTHING.**

## R3 rulings in `ladder_r3.yaml: ratified_decisions`. Two not to re-litigate:
**D1 unattended is legitimate — R1 ITSELF RAN UNATTENDED OVERNIGHT** (SESSION_LOGS
2026-08-26). **D2: a THIRD rated account needs a courtesy note to PS staff.**

## Next actions (order CORRECTED 2026-08-28 03:10Z; SESSION_LOGS has both)
0. **Read R3 out when it stops** (BI-4 first; pass every flag — all three readout
   scripts default to R1's paths AND name). Then **rescore search@M on s81/s82 at
   n=3000** (~4.9 h eval, fits inside R3's window). **The ONLY thing gating R2**:
   it sets the policy form the arms are scored in.
1. **R2 = BATCH.** 3 new 50M lanes, banked s80/81/82 as the free control.
   **PRIMARY READ IS STRENGTH** against the 0.0717 bar; sigma_seed is a
   descriptive secondary with its **(2,2)-df disclosure**. Verify H&L's update
   count against SOURCE; hold minibatch at 256 and scale the COUNT; KL
   early-stop is a tripwire, not a lever.
2. **lambda: a CONFIG choice on the explained-variance diagnostic**, applied to
   BOTH arms — not an arm (it would compete with batch). Check EV is even
   logged; it is not in the locked metric names.
3. **THEN decide CURVE vs CREDITED WIN RATE** — a policy change (curve makes
   120/250M first-class). **It gates LANES AND SCALE, not batch.**
4. Around the training: **D4's anchors AMENDED to BC-clone h2h on ALL THREE
   lanes** (+1.5 h — a free replication of the equalisation test), cross-play,
   one R2 arm scored both ways. `CLEANUP.md`.

## Watch items
- **k ~ 24 kills lanes; (2,2) df kills the variance READ.** Bar =
  `2*sigma_seed/sqrt(k)` = 0.0717 at k=3, so the +0.025 floor needs **k>=24
  lanes** — C2 cannot credit a +0.02-0.05 lever at any realistic k (CHAPTER5 §5
  has a supersession note). **But sigma_seed across two 3-lane groups is F(2,2),
  crit 19.0 — batch must cut it 4.4x (0.0617 -> 0.014) to register.** So **batch
  is NOT the instrument fix** (RETRACTED); it is a strength lever.
- **SEARCH MAY EQUALISE THE LANES** — off FP@20 the search-minus-greedy gain is
  monotone in lane weakness 3/3 (+0.051/+0.104/+0.148), collapsing a 0.123 spread
  to 0.026. **2 df, p~0.06, CI contains greedy's 0.0617: HYPOTHESIS.** Read the
  rescore for **s81, not s82**. Scoring levers under search is a **scope change**
  — the mechanism that buys the variance masks value-head gains.
- Never quote an R1-vs-R3 delta as an effect (D5); never set 0.4390 beside the 12M
  0.79283 or read it as vs-SH; name the budget (FP@20). **R1's "217 s/battle" is
  wrong — 246.5. LADDER DATA IS UNREPEATABLE.** Never re-run a killed arm now.
