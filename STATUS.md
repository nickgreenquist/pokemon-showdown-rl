# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED); **11.5 READ 2026-09-17: depth-2 NULL, and every earlier depth number was an OVERRIDE-RATE ARTIFACT**
**11.5 (`readouts/DEPTH2_R5_READOUT.md`, RESULTS §22):** depth-2 − depth-1 at MATCHED override rate
= **−0.0007 at 0.05 se (n=3000/arm) for 3.27× the compute** — NOT CREDITED. At the NAIVE δ the same
arm reads **−0.053 at 3.34 se**: same depth, same everything but δ, **+0.052 at 3.30 se apart**. A
deeper backup spreads values wider, so a δ tuned at one ply lets 2.4× as many overrides through.
**Every depth number before 2026-09-17 compared arms that differed in how often search was BELIEVED.**
Search at either depth is a null vs the greedy committee (−0.006 / −0.007). **SESSION OFFSET: the same
frozen committee reads 0.5987 (09-15) vs 0.5747 (09-17), −0.024 at 1.5 se — never difference across
sessions without a same-session anchor.** **MCTS IS NOT CLOSED** (pre-reg scope limit; ruling owed).
**FP'S OWN EVALUATOR IN OUR SEARCH (§23, `readouts/FPEVAL_R5_READOUT.md`): DEPTH BUYS NOTHING WITH IT EITHER**
(−0.0087 at 0.67 se), so **"depth fails because our critic is off-distribution" is NOT SUPPORTED** — that
story turned on having no training distribution to fall off, which their heuristic has. Theirs is also WORSE
than our critic at both depths (−0.020, −0.028) and worse than greedy. Session anchor −0.0027 at 0.15 se, so
none of it is drift. **Cost: their eval at depth 2 = our critic at depth 1 (81 ms), a third of ours at depth 2
— implementation-bound (they loop in Python, we batch a forward), not intrinsic.** **LIVE HYPOTHESIS IS NOW
THE GATE:** at 6.5% override the search changes ~2 decisions per battle, which BOUNDS any leaf-value effect;
our critic collapses at 16.3% (0.516 vs 0.569). Untested cell: does a STATIC evaluator collapse there too?
**GEN-4 CLOSED (§19):** vs SH 0.8788, CREDITS NOTHING. **LADDER R4: GXE 65.2 / Glicko 1618 ± 25 / Elo 1354,
n=200. From here it is all gen 1.** **JOURNEY 7.5 engine port EXITED; A-1 PASSED TWICE** (−0.00436 travels
forever; `docs/engine_port/NOTES.md`). Engine idle rates k=8: **w3 1620, w6 1282 steps/s/lane** → 6×200M ≈ 43 h.
## **LADDER R5 — GXE 73.9 / Glicko-1 1697 ± 25 / Elo 1457, n=200, LISTED (cutoff 1354.2, ~103 clear)**
The committee of the 200M W finals (lanes w104/w112/w120), greedy, agent-launched 2026-09-16 00:07Z,
finished 14:17Z: **128–72 (0.640)**, played-only 125/197, rd 25.0, attempt 1, NO relaunch/resume,
mean decision 5.40 ms (band [1,30], no VOID), 0 decision errors, 0 mask desyncs, tallies agree, account
record reconciles 327–273/600 with ZERO unlogged games. **Entered 146/200 battles at or above the STOP
cutoff (148 against the n=0 pull; the readout prints both), 9 excursions, peak 1541, finished listed**;
93–53 while listed vs 35–19 below (indistinguishable).
DISCLOSURES: warm-started account (400 prior games — GXE/Glicko/Elo are ACCOUNT properties); STANDALONE
DESCRIPTIVE; **no R1/R3/R4/R5 delta is an effect**; barred list binding. **Pool (CLEANUP L1):** 102 distinct
opponents, 63.5% repeats, top five 34.5%; both adaptation tests null. `readouts/LADDER_R5_READOUT.md`,
§20. **Anchor battery COMPLETE: BC-clone 0.9640 (n=500).**

## **ENS3 of the 100M finals CREDITS (+0.0349 vs SH; +0.067 off FP@20) — the R5 FLOOR**
**0.82356 (n=9000) vs fresh greedy A0 0.78867 = +0.03489 at 5.93 se → CREDIT** (floor AND 2·se_diff), at GREEDY
SPEED. Clustered se UNAVAILABLE (one committee; binomial governs, anti-conservative); licenses THESE
checkpoints, never "ensembling helps".
## SEARCH — depth NULL with BOTH evaluators; the gate is the only thing that ever paid
D5 gate: out of sample **+0.016 at 2.19 se — MISSES the floor, NOT CREDITED**; never quote s112's +0.0417.
Off FP@20 the SELECTOR alone bought +0.129 (gated 0.525 vs ungated 0.396) — **search has only ever paid here
as a RARELY-FIRED VETO**, and §22 shows why: let it speak 2.4x more often and it costs 0.052. EG10 -0.0004;
ENSG NULL on both axes. **LANDMINE: every search number before 2026-09-11 measures a BROKEN selector**
(grep `PRE-D5`; LADDER R3 is a D4 object).

## ENSEMBLE SCALING (2026-09-11/12, `configs/eval/ens_width*.yaml`) — superseded in detail by the monster reads
Member curve 1→6 vs SH: 0.78867 → 0.81678 → 0.82667 → 0.82767 → 0.83633 → 0.84400 (members 4–6 are 50M, a lower
bound). STEPS vs MEMBERS: ENS3 of the 50M finals 0.82233 vs the 100M committee 0.82356 — **the horizon was the
WEAKER lever vs SH.** Off FP@20 the committee's transfer is verdict-grade (+0.067 at 4.7 se); FP@500 costs it ~0.095.

## THE MONSTER (JOURNEY 10) — DONE 2026-09-15, ZERO RESUMES; the reads picked the ladder object BY RULE
Six lanes k=8 (launched 2026-09-13): **W trio = L2 + 1024-wide critic** (104/112/120, 46.3 h,
`runs/showdown_monster200m_w_s*`); **L2LAM trio = L2 + MC targets** (128/136/144, 38.7 h, `…_l2lam_s*`).
Reads: `configs/eval/monster_reads{,_offfp}.yaml`, `results/monster_reads/READOUT.txt`.
- **OFF FP@20, SAME SESSION, n=3000/arm — the read that picks the object (rule R1):** E3WF **0.5987** > E6MF
  0.5763 ≈ E9F 0.5760 > E3HF (100M ENS3 re-drawn) **0.5570 = its banked value** > E3LF 0.4960. Singles pooled
  n=9000: **W 0.5417**, 100M 0.4952, L2LAM 0.4481. **LADDER OBJECT = E3WF, ENS3 OF THE W TRIO** (+0.0417 over the
  floor at 3.27 se; the runner-up is 0.023 below, outside the 0.013 tie band). W 200M − 100M **+0.046 at 6.2 se**;
  L2LAM −0.047 at −6.3 se; the L2LAM and 100M members add NOTHING to the W committee. Load bridge −0.014 at
  −0.75 se (phase A ran beside the W trio; no measurable term). FP@20 disclosures travel.
- **vs SH, locked protocol:** GW **0.8217** (n=9000) vs the 100M A0 0.7887 = +0.033 at 5.6 se; GL 0.7778; E3W
  **0.8386** (+0.015 over the banked 100M ENS3 0.8236 at 2.7 se); E6M 0.8426; E9 0.8433; E3L 0.8130.
- **CREDITED 2026-09-16, for the RECIPE (§21, `readouts/MECH200M_READOUT.md`).** Critic FIRST-layer srank99
  **632/1024 (0.617) on W vs 27/384 and 5/384**, 8× the across-lane spread, both obs protocols agreeing:
  **width is LIVE, the ceiling branch did NOT fire**, so rule 6 permits no kill. But **EV DID NOT MOVE**
  (0.5881 vs 0.5919) — 2.67× width and 126× rank buy ZERO explained variance: **do not size the next fleet
  on EV.** Credit: W vs 100M **+0.046 (4.79 se)**, **+0.033 vs SH (5.59 se)**, seed-clustered se binding off
  FP. **The RECIPE AS SHIPPED is credited, never width alone** (no contrast isolates it); **E3W vs the 100M
  ENS3 floor is +0.015 at 2.01 se, NOT credited** — recipe gain and committee gain SUBSTITUTE.
- **Recipe verdict in one line:** the wider critic beat the 100M baseline on both instruments and MC value
  targets lost to it on both — the value TARGET, not the horizon, moved the number.

## Next actions
0. **GOAL MET, ONCE (maintainer, 2026-09-15): "break top500 with self play", and stay rather than visit.**
   R5 finished LISTED at Elo 1457 against a 1354.2 line and spent 73% of its battles at or above it.
   It is ONE run on a warm-started account; nothing here is a projection, and the barred list stands.
1. **DONE 2026-09-16/17 — the mechanism co-primary (§21) and JOURNEY 11.5 (§22).** Open: WHY the recipe
   pays (it is measurably not a better value fit — the Lyle Def-1 plasticity probe is the instrument, and
   it asserts value_sizes [384,384], so W needs a second arch family: CLEANUP L3).
2. **DONE 2026-09-16 — the BC-clone leg** (`readouts/MONSTER_BCCLONE_READOUT.md`): committee **0.9640**,
   W fleet 0.9467, 100M re-drawn SAME SESSION 0.9373 vs banked 0.9233. W vs 100M is a NULL here (+0.009 at
   1.1 se) — a ~0.94 ceiling. **Its runner had been BROKEN since 2026-09-05** (099c440).
   **SESSION OFFSET IS ~0.02 ON BOTH FP INSTRUMENTS (+0.014 clone, −0.024 off-FP@20): never difference a
   number against another session's without a same-session anchor. Two readouts would have been wrong.**
3. **NEXT, RANKED — `docs/proposals/WHATS_NEXT_2026-09-16.md`.** (1) 11.5 **DONE** (§22) and the
   evaluator follow-up **DONE** (§23). **(2) the critic LayerNorm arm** (built 2026-09-12, never run):
   a 50M run can resolve the MECHANISM legally under rule 6 even though its win rate could not.
   **(3) more W-recipe members. (4) 300M — weakest. (5) is EV 0.59 the IRREDUCIBLE ceiling?** Plus the
   GATE question §23 opened: does a STATIC evaluator survive a high override rate where ours collapses?
4. **RULINGS OWED:** R6's SPLIT SCHEDULE (CLEANUP L1 — needs its OWN stopping rule, rd grows between
   sessions); the LR-anneal floor ([RWL-4]; new datum: W's EV FALLS through the annealed tail,
   0.675→0.596 — the tail is not inert, which cuts both ways); the next fleet's shape — answer it AFTER
   the LayerNorm read, since the question has changed from "how much width" to "is width the cheap way".

## Watch items
- **SUITE GREEN 1090 / 0 failed, 87 skipped** (2026-09-17, encoder flags UNSET — the documented
  invocation). Engine 115 + 94 cargo. **FOUR defect-class fixes this week, all the same shape — a dial that
  runs and reports nothing:** the off-FP seat dropped 3 of 4 search vehicles; ch3_eval's merge dropped every
  depth2/* key; `search_dose` was never stamped; a new vehicle reached the writer and neither collector.
  Each now has a test that reads the source and fails on recurrence.
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200. Read curves, never one rung.
- **SEEDS DO NOT PAIR BATTLES (`docs/landmines.md`).** Per-battle agreement on shared seeds is at the
  independence level (0.66–0.73) — teams and rolls are server-rolled, so every "matched seed-for-seed,
  McNemar se" phrase was UNPAIRED (the se coincides, so no number moved). Replicates are the instrument.
