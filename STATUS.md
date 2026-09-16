# STATUS
## JOURNEY POSITION — step 11 (the final gen-1 ladder) **DONE 2026-09-16: LADDER R5 finished LISTED on the top-500**
**GEN-4 CLOSED (RESULTS §19):** steps 3/5 MET, vs SH 0.8788, CREDITS NOTHING. **LADDER R4:
GXE 65.2 / Glicko 1618 ± 25 / Elo 1354, n=200. From here it is all gen 1.**
**JOURNEY 7.5 engine port EXITED; A-1 PASSED TWICE** (0.66775 vs async 0.67211, **−0.00436 travels forever**; `docs/engine_port/NOTES.md`).
Engine rates at k=8, measured idle: **w3 1620, w6 1282 steps/s/lane** → 6×200M ≈ 43 h.
## **LADDER R5 — GXE 73.9 / Glicko-1 1697 ± 25 / Elo 1457, n=200, LISTED (cutoff 1354.2, ~103 clear)**
The committee of the 200M W finals (lanes w104/w112/w120), greedy, agent-launched 2026-09-16 00:07Z,
finished 14:17Z: **128–72 (0.640)**, played-only 125/197, rd 25.0, attempt 1, NO relaunch/resume,
mean decision 5.40 ms (band [1,30], no VOID), 0 decision errors, 0 mask desyncs, tallies agree, account
record reconciles 327–273/600 with ZERO unlogged games. **Entered 146/200 battles at or above the line,
9 excursions, peak 1541, finished listed**; 93–53 while listed vs 35–19 below (indistinguishable).
DISCLOSURES: warm-started account (400 prior games — GXE/Glicko/Elo are ACCOUNT properties);
STANDALONE DESCRIPTIVE; **no R1/R3/R4/R5 delta is an effect**; barred-language list is binding.
**Pool caveat (CLEANUP L1):** 102 distinct opponents, 63.5% of battles vs a repeat, top five = 34.5%;
two adaptation tests null (+0.003 at 0.03 se; +0.026 at 0.38 se). Full: `readouts/LADDER_R5_READOUT.md`,
`RESULTS.md` §20. **Anchor battery INCOMPLETE — BC-clone h2h PENDING; README row says so.**

## **ENS3 of the 100M finals CREDITS (+0.0349 vs SH; +0.067 off FP@20) — now the R5 FLOOR; the object is E3WF (below)**
**0.82356 (n=9000) vs fresh greedy A0 0.78867 = +0.03489 at 5.93 se → CREDIT** (floor AND 2·se_diff); beats the
gated search's in-sample peak (0.82400) at GREEDY SPEED. Disclosures: clustered se UNAVAILABLE by construction
(one committee; the binomial governs, anti-conservative); licenses THESE checkpoints, never "ensembling helps".
## SEARCH at DEPTH-1 and DEPTH >1 — BOTH NULL, banked (`docs/search_relook/`, RESULTS §"PRE-D5")
D5 gate (play search's action only if it beats the policy's argmax by > delta): in-sample peak 0.82400 at
delta 0.10, but **out of sample +0.016 at 2.19 se — MEETS 2*se_diff, MISSES the floor, NOT CREDITED**; never
quote s112's +0.0417. A better evaluator adds nothing at depth 1 (EG10 -0.0004). Off FP@20 the SELECTOR alone
bought +0.129 (gated 0.525 vs ungated 0.396). **DEPTH is a NULL, not a negative** (two implementations,
~14,000 battles, pooled -0.004 +/- 0.013; the matrix's -0.094 is an OVERRIDE-RATE effect: at matched override
depth 3 reads -0.017 +/- 0.023). Licensed: "no evidence depth helps at these budgets and this delta."
**LANDMINE: every search number before 2026-09-11 measures a BROKEN selector** (grep `PRE-D5`; LADDER R3 is a
D4 object). ENSG (committee as the search's prior+leaf, with the gate) is a NULL on both axes.

## ENSEMBLE SCALING (2026-09-11/12, `configs/eval/ens_width*.yaml`) — superseded in detail by the monster reads below
b0 member curve 1→6 vs SH: 0.78867 → 0.81678 → 0.82667 → 0.82767 → 0.83633 → 0.84400 (members 4–6 are 50M objects,
a lower bound); pooled E6MIX 0.83356 vs ENS3 0.82356 = +0.010 at 1.78 se (unresolved, NOT saturation). STEPS vs
MEMBERS: ENS3 of the 50M finals 0.82233 vs the 100M committee 0.82356 — the horizon was the weaker lever vs SH.
Off FP@20 (same session): greedy 100M re-draw mean 0.500; ENS3F 0.557 / ENS3FR 0.577 (+0.067 at 4.7 se — the
committee's off-FP transfer is verdict-grade); FP@500 (1 s/decision) costs the committee ~0.095 (0.472, n=500).

## THE MONSTER (JOURNEY 10) — DONE 2026-09-15, ZERO RESUMES; the reads picked the ladder object BY RULE
Fleet (ratified option C, launched 2026-09-13 10:35Z, six lanes k=8): **W trio = L2 + 1024-wide critic** (seeds
104/112/120, 46.3 h, `runs/showdown_monster200m_w_s*`, finals `ckpt_200000000/…12/…03.pt`); **L2LAM trio = L2 +
Monte-Carlo targets** (128/136/144, 38.7 h, `…_l2lam_s*`, finals `ckpt_200000046/…07/…06.pt`). Watchdog exits
`RESUMES=0 NODE_RESTARTS=0`. Reads: `configs/eval/monster_reads{,_offfp}.yaml`, `results/monster_reads/READOUT.txt`.
- **OFF FP@20, SAME SESSION, n=3000/arm — the read that picks the object (rule R1):** E3WF **0.5987** > E6MF
  0.5763 ≈ E9F 0.5760 > E3HF (100M ENS3 re-drawn) **0.5570 = its banked value** > E3LF 0.4960. Singles pooled
  n=9000: **W 0.5417**, 100M 0.4952, L2LAM 0.4481. **LADDER OBJECT = E3WF, ENS3 OF THE W TRIO** (+0.0417 over the
  floor at 3.27 se; the runner-up is 0.023 below, outside the 0.013 tie band). W 200M − 100M **+0.046 at 6.2 se**;
  L2LAM −0.047 at −6.3 se; the L2LAM and 100M members add NOTHING to the W committee. Load bridge −0.014 at
  −0.75 se (phase A ran beside the W trio; no measurable term). FP@20 disclosures travel.
- **vs SH, locked protocol:** GW **0.8217** (n=9000) vs the 100M A0 0.7887 = +0.033 at 5.6 se; GL 0.7778; E3W
  **0.8386** (+0.015 over the banked 100M ENS3 0.8236 at 2.7 se); E6M 0.8426; E9 0.8433; E3L 0.8130.
- **NOT A CREDIT (yet):** [RWL-3] registered these reads as DESCRIPTIVE. W-vs-100M meets the credit line's
  arithmetic on both instruments; the mechanism co-primary (critic srank99/width, dormant fraction, EV, l2init
  distances) is OWED first — srank/dormant are NOT logged; run `d22_collect_obs.py` + `d22_dormant_rank.py` on the
  finals (the plasticity probe asserts value_sizes 384 and needs a per-checkpoint allowance for W).
- **The recipe verdict in one line:** same L2, horizon, fleet — the wider critic beat the 100M baseline on both
  instruments and Monte-Carlo value targets lost to it on both. The value TARGET, not the horizon, moved the number.

## Next actions
0. **GOAL MET, ONCE (maintainer, 2026-09-15): "break top500 with self play", and stay rather than visit.**
   R5 finished LISTED at Elo 1457 against a 1354.2 line and spent 73% of its battles at or above it.
   It is ONE run on a warm-started account; nothing here is a projection, and the barred list stands.
1. **OWED BEFORE ANY CREDIT FOR THE WIDE CRITIC:** the [RWL-3] mechanism co-primary on the six finals —
   critic ctx srank99/width, dormant fraction at tau 0.025/0.1, explained variance, l2init distances.
   srank/dormant are NOT logged: run `d22_collect_obs.py` + `d22_dormant_rank.py` on the finals (the
   plasticity probe asserts value_sizes 384 — the W finals need a per-checkpoint trunk allowance).
2. **OWED FOR THE README ROW:** the BC-clone h2h (500) for the committee — the only missing anchor leg;
   it is reported PENDING and the row already says so. vs-SH (0.8386) and FP@20 (0.5987) are in hand.
3. **RULINGS OWED:** R6's SPLIT SCHEDULE (CLEANUP L1 — sessions across hours/days need their own
   stopping rule, since rd grows between sessions); the LR-anneal floor for the next fleet; the next
   fleet's shape (more W-recipe members vs 300M vs the LayerNorm arm); engine-native depth-2 (not the lever).

## Watch items
- **SUITE GREEN 1031 / 0 failed** on the DOCUMENTED invocation (encoder flags UNSET); 86 skip
  and pass with them SET, where 6 v1-shape tests fail by design. Engine 115 + 94 cargo.
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200. Read curves, never one rung.
- **SEEDS DO NOT PAIR BATTLES (2026-09-11 review; `docs/landmines.md`).** Per-battle agreement between
  arms on shared seeds is at the independence level (0.66–0.73): teams and rolls are server-rolled. "Matched
  seed-for-seed, McNemar se" was UNPAIRED all along (the se coincides, so no number moved). The 16:14
  "300-seed arm vs 3000-seed pooled mean" corollary was n=300 noise (se 0.023), not a block offset: the
  rule is "n=300 cannot resolve ±0.05", not "compare matched". Replicates are the instrument.
