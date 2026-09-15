# STATUS
## JOURNEY POSITION — step 10 (the monster) DONE 2026-09-15; **step 11 LADDER R5 is next, object decided by rule**
**GEN-4 CLOSED (RESULTS §19):** steps 3/5 MET, vs SH 0.8788, CREDITS NOTHING. **LADDER R4:
GXE 65.2 / Glicko 1618 ± 25 / Elo 1354, n=200. From here it is all gen 1.**
**JOURNEY 7.5 engine port EXITED; A-1 PASSED TWICE** (0.66775 vs async 0.67211, **−0.00436 travels forever**; `docs/engine_port/NOTES.md`).
Engine rates at k=8, measured idle: **w3 1620, w6 1282 steps/s/lane** → 6×200M ≈ 43 h.
## **ENS3 of the 100M finals CREDITS (+0.0349 vs SH; +0.067 off FP@20) — now the R5 FLOOR; the object is E3WF (below)**
**0.82356 (n=9000) vs fresh greedy A0 0.78867 = +0.03489 at 5.93 se → CREDIT** (floor AND 2·se_diff); beats the
gated search's in-sample peak (0.82400) at GREEDY SPEED. Disclosures: clustered se UNAVAILABLE by construction
(one committee; the binomial governs, anti-conservative); licenses THESE checkpoints, never "ensembling helps".
## SEARCH at DEPTH-1 — the gate is the whole effect, and it is NOT CREDITED
**D5: play search's action only if it beats the POLICY's argmax by > δ** (absent = no-op, golden digest;
δ=inf = greedy). s112, n=3000/arm vs SH: **δ 0 → 0.74767, BELOW greedy's 0.78233** — the critic's own
argmax loses to the policy at ONE ply; search only ever paid as a rarely-fired veto; 0.05 0.80867, **0.10 0.82400**, 0.20 0.81000.
- **HONEST READ IS OUT OF SAMPLE: +0.016, NOT +0.042.** Held-out lanes at δ 0.10, n=3000 each:
  s104 +0.01967, s120 +0.01233; **pooled n=6000 = +0.01600 at 2.19 se_diff — MEETS 2·se_diff,
  MISSES the floor → NOT CREDITED.** Never quote s112's +0.0417.
- **EG10: a better evaluator adds nothing AT DEPTH-1** (LOO ensemble + same gate, 3×3000: −0.00044 at 0.05 se).
  **ENS3 vs the searched stack is a NULL** (+0.01078 at 1.87 se, and that figure includes the tuning lane).
- **OFF FOUL PLAY THE GATE TRANSFERS** — BLM (gated@M, δ 0.10) vs FP@20, n=1000: **0.525** vs a **0.47** bar
  (greedy 0.50167, UNGATED 0.39600: the SELECTOR alone bought +0.129 off-FP); +0.023 vs greedy at 1.28 se is n.s.
**LANDMINE: every search number before 2026-09-11 measures a BROKEN selector** (grep `PRE-D5`; LADDER R3 is a D4 object).
## DEPTH IS MEASURED, AND IT IS A NULL, NOT A NEGATIVE — 2026-09-11 review of ~14,000 battles
Two implementations (`rl/search/tree.py`, decoupled-UCT with OUR prior and critic; `_look_further`,
N plies on the banked matrix); account + review addendum in `docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md`.
n=900 each vs S3G10 (0.8189 on the same 900 seeds), UNPAIRED se ≈ 0.019 (seeds do NOT pair — Watch items).
- **Tree: depth is a NULL.** Two exact-config replicates per depth. Depth 1: TSAMP1 0.8144, TQV 0.7778
  (0.037 apart at n=900); depth ~3: TSAMP 0.7900, TQV8 0.7944. **Pooled 0.7961 vs 0.7922 = −0.004 ± 0.013.**
  The 16:14 STATUS reported TSAMP1/TSAMP only; TQV/TQV8 were on disk and unreported. The depth-1 tree sits
  −0.023 (−1.7 se) under the banked matrix pooled: "the control reproduces the matrix" held for one of two.
- **Matrix: the −0.094 (−4.6 se) at +2 plies is an OVERRIDE-RATE effect, not depth.** At δ 0.10 the deep
  arms override 16.5–20.1% of decisions vs S3G10's 8.3%; at matched override (D3G40, δ 0.40, 2.9%) depth 3
  reads **−0.017 ± 0.023 at n=600**. A deeper backup needs a recalibrated δ; nobody has swept it.
- Deep arms had 3–6× the compute (229 vs 40 ms; 330 vs 78 ms). **DEPTH CENSUS:** FP's iterative deepening
  reaches 2.44 / 3.08 / 3.56 plies at 20 / 200 / 2000 ms — FP@20 searches ~depth 2.4; our tree exceeds it.
- **Licensed: "no evidence depth helps at these budgets and this δ." Barred: "depth hurts", "monotone".**
  Engine-native depth-2 ruling still owed; a δ sweep for deep backups is the cheap first step.

## ENSEMBLE SCALING (2026-09-11/12, `configs/eval/ens_width*.yaml`) — superseded in detail by the monster reads below
b0 member curve 1→6 vs SH: 0.78867 → 0.81678 → 0.82667 → 0.82767 → 0.83633 → 0.84400 (members 4–6 are 50M objects,
a lower bound); pooled E6MIX 0.83356 vs ENS3 0.82356 = +0.010 at 1.78 se (unresolved, NOT saturation). STEPS vs
MEMBERS: ENS3 of the 50M finals 0.82233 vs the 100M committee 0.82356 — the horizon was the weaker lever vs SH.
Off FP@20 (same session): greedy 100M re-draw mean 0.500; ENS3F 0.557 / ENS3FR 0.577 (+0.067 at 4.7 se — the
committee's off-FP transfer is verdict-grade); FP@500 (1 s/decision) costs the committee ~0.095 (0.472, n=500).

## ENSG — the committee AS the search's prior+leaf value, with the gate: A NULL ON BOTH AXES
vs SH δ 0.05/0.10/0.20: −0.002 / +0.015 (1.6 se, the tuned δ) / +0.008; off FP@20 pre-registered ENSGF 0.558 vs
ENS3F 0.557 (search fired: override 7.5%, 31,085 searched decisions). The gate adds nothing to the committee anywhere.

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
0. **GOAL (maintainer, 2026-09-15): "break top500 with self play", and STAY there, not visit it** (R4: Elo 1354
   vs a 1358.999 cutoff, ~40/200 visits). Nothing here projects a rating; vs-SH / off-FP are not ladder numbers.
1. **LADDER R5 — object decided, launch waits on one line.** `docs/proposals/ladder_r5.draft.yaml`: lanes
   w104/w112/w120 (nine member shas pinned), rulings 2–6 as recommended defaults (reuse nickgen1rbrlbot — RULED;
   200 battles one run; [1,30] ms band; 12–16 h plan, 22 h ceiling, idle box; README row waits on the battery).
   LG-2 profile parked at R4's stop (Elo 1353.96 / GXE 65.1 / Glicko 1617.7 / RD 33.4 / 199W-201L); LG-3 .env
   username verified. **On "go with the recs":** git mv → `configs/eval/ladder_r5.yaml` (Status: RATIFIED,
   markers cleared), `pytest tests/test_ladder.py`, `--local-smoke` ≥2 battles, STOP Node, caffeinate bound to the
   supervisor, `source .env && scripts/ladder_supervise.sh R5E 200 configs/eval/ladder_r5.yaml` (encoder env vars
   exported), LG-9 startup-line read from the log within 90 s. Agent-launched (ruled 2026-09-14). Results +
   readout due Saturday night 2026-09-19.
2. **After the ladder:** mechanism co-primary on the six finals; RESULTS addendum (fleet, reads, R5); README row
   (BC-clone leg for the committee PENDING); the plasticity probe on the W/L2LAM finals; STATUS/landmines.
3. **RULINGS OWED:** the LR-anneal floor for the next fleet; engine-native depth-2 (not the lever); the next
   fleet's shape (more W-recipe members vs 300M; LayerNorm arm).

## Watch items
- **SUITE GREEN 1031 / 0 failed** on the DOCUMENTED invocation (encoder flags UNSET); 86 skip
  and pass with them SET, where 6 v1-shape tests fail by design. Engine 115 + 94 cargo.
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200. Read curves, never one rung.
- **SEEDS DO NOT PAIR BATTLES (2026-09-11 review; `docs/landmines.md`).** Per-battle agreement between
  arms on shared seeds is at the independence level (0.66–0.73): teams and rolls are server-rolled. "Matched
  seed-for-seed, McNemar se" was UNPAIRED all along (the se coincides, so no number moved). The 16:14
  "300-seed arm vs 3000-seed pooled mean" corollary was n=300 noise (se 0.023), not a block offset: the
  rule is "n=300 cannot resolve ±0.05", not "compare matched". Replicates are the instrument.
