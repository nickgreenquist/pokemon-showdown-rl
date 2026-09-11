# STATUS
## JOURNEY POSITION — step 7.5 (engine port) **EXITED 2026-09-10**; next is gen-1 step 8/10
**GEN-4 CLOSED (RESULTS §19):** steps 3/5 MET, vs SH 0.8788, CREDITS NOTHING. **LADDER R4:
GXE 65.2 / Glicko 1618 ± 25 / Elo 1354, n=200. From here it is all gen 1.**
**JOURNEY 7.5 engine port EXITED. A-1 PASSED TWICE** (12M, n=12,000/seed: 0.66775 vs banked
async 0.67211, **−0.00436, a signed delta that travels forever**; `docs/engine_port/NOTES.md`).
Engine rates at k=8, measured idle: **w3 1620, w6 1282 steps/s/lane** → 6×200M ≈ 43 h.
## **ENS3 CREDITS (+0.0349) — STILL THE LADDER OBJECT, and the strongest FREE one**
**0.82356 (n=9000) vs fresh greedy A0 0.78867 = +0.03489 at 5.93 se → CREDIT** (clears floor
AND 2·se_diff). **Beats the gated search's IN-SAMPLE peak (0.82400) at GREEDY SPEED.** Two
disclosures travel: **clustered se UNAVAILABLE by construction** (3 lanes = ONE committee, so
the binomial governs — anti-conservative), and it licenses **"ensembling THESE three
checkpoints at 100M", NEVER "ensembling helps"**. README row WAITS on the anchor battery.

## SEARCH at DEPTH-1 — the gate is the whole effect, and it is NOT CREDITED
**D5: play search's action only if it beats the POLICY's argmax by > δ** (absent = exact
no-op, golden digest; δ=inf is exactly greedy). s112, n=3000/arm vs SH: **δ 0 → 0.74767,
BELOW greedy's 0.78233** — the critic's own argmax loses to the policy even at ONE ply, so
search has only ever paid as a rarely-fired veto; 0.05 0.80867, **0.10 0.82400**, 0.20 0.81000.
- **HONEST READ IS OUT OF SAMPLE: +0.016, NOT +0.042.** Held-out lanes at δ 0.10, n=3000 each:
  s104 +0.01967, s120 +0.01233; **pooled n=6000 = +0.01600 at 2.19 se_diff — MEETS 2·se_diff,
  MISSES the floor → NOT CREDITED.** Never quote s112's +0.0417.
- **EG10: a better evaluator adds nothing AT DEPTH-1** (LOO ensemble + same gate, 3×3000:
  −0.00044 at 0.05 se) — weakens arm B's premise. **ENS3 vs stack is a NULL** (+0.01078 at
  1.87 se; that figure includes the tuning lane, flattering SEARCH).
- **OFF FOUL PLAY THE GATE TRANSFERS** — BLM (gated@M, δ 0.10) vs FP@20, n=1000: **0.525** vs
  a **0.47** bar (greedy 0.50167, UNGATED 0.39600 — **the SELECTOR alone bought +0.129
  off-FP**). +0.023 vs greedy at 1.28 se is NOT significant. Both FP@20 disclosures travel.

**LANDMINE: every search number before 2026-09-11 measures a BROKEN selector** (grep
`PRE-D5`; **LADDER R3 is a D4 object**). Re-measure under D5 or do not cite it.

## DEPTH IS MEASURED NOW, AND IT DOES NOT PAY — 2026-09-11, ~14,000 battles
Two implementations (`rl/search/tree.py`, decoupled-UCT with our policy as PUCT prior and
**our critic at the leaves**; `_look_further`, N selective plies on the banked matrix),
matched seed-for-seed, McNemar se. Account: `docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md`.
n=900 each vs depth-1 gated: **tree capped to 1 ply (the CONTROL) −0.004 (−0.2 se)**; tree
uncapped (depth 3.15) −0.029; matrix +1 ply −0.039; **matrix +2 plies −0.094 (−4.6 se)**;
tree with a MINIMAX opponent (n=300) **−0.120 (−3.3 se)**.

- **The depth-1 control reproduces the banked matrix, so the implementation is not the
  story.** Deep arms got 3–6× MORE compute (229 vs 40 ms; 330 vs 78 ms), not a split budget.
  **Every intervention that let search wander further from the policy lost; every one that
  pulled it back recovered** (D3 at δ 0.10 −0.094 → at δ 0.40, 2.9% override, −0.006).
- **DEPTH CENSUS:** poke_engine's iterative deepening on our states reaches **2.44 / 3.08 /
  3.56 at 20 / 200 / 2000 ms** — 100× compute buys 1.1 plies. **FP@20 searches at ~depth 2.4
  and our tree already exceeds it**, so depth we cannot afford explains nothing.
- **BEARS ON THE ENGINE-NATIVE DEPTH-2 RULING** (owed; Ph.1-3 ≈ 6-8 blocks; P0/R1-E stand):
  depth was bought twice by cheaper routes and cost us both times. **Still NOT authorized.**
- **NOT Nau pathology** (2 of 3 factors say otherwise). **Verified verbatim from our own copy
  of the PokeAgent Challenge paper: Foul Play is #1 in Gen 9 OU and #8 in Gen 1 OU, and the
  Gen 1 winner (PA-Agent) uses NO test-time search** — Gen 1 is the generation where
  inference search underperforms, and it is ours (`prior_work/SEARCH_AT_INFERENCE_2026-09-11.md`).

## ENSEMBLE SCALING — members SATURATE at 3; the monster run should buy STEPS
All three 2-member pairs at ENS3's exact protocol on its own seed block: **1 member 0.78233 →
2 members 0.81678 (mean) → 3 members 0.82667.** Gain 1→2 **+0.0344**, gain 2→3 **+0.0099**,
and ENS3 separates from NO single pair (+0.8/+1.6/+0.6 se). Scope: the marginal value of a
member AT 100M ON THESE THREE CHECKPOINTS.

## ENSG — ensemble AS the search's prior+leaf value, with the gate. **A NULL.**
The last untested cell of PRIOR × SELECTOR, now built (`ensemble_members:` routes a search arm
through `EnsembleSearchAdapter`). n=3000 matched: **ENSG 0.84167 vs ENS3 0.82667 = +0.01500 at
1.6 se — MISSES the floor AND 2·se_diff.** Highest point estimate we own; not credited. **Also
IN-SAMPLE — δ 0.10 was swept on s112 and the committee CONTAINS s112** — so optimistic, not
conservative. ENSG05/ENSG20 running to separate gate-tuning from ensemble-leaves. At n=900 it
read +0.030 at 1.7 se and was quoted as a win; it regressed. Sub-2-se deltas are not wins.

## The monster (JOURNEY 10) — decisions owed; today's reads bear on two
1. **ARM B IS BITWISE ARM A** (24 rungs, 223 tensors / 3,428,015 elements, 0 differing, sha
   f156f232462e635b): separate net, own trunk, `autograd.grad` over its own params only.
   **Its ONLY consumer is a search leaf evaluator** — EG10 says a better evaluator adds
   nothing at depth-1 and today says no reachable depth pays. **Recommend DROP arm B**; its
   MC-target bug is fixed (b147f48) and that finding keeps regardless.
2. **ARM C IS CONTESTED BY BOTH REVIEWS** — D18's lever at λ 0.95 where the vacatur named
   λ=1.0; 30× less variance headroom at a 30,720-step update; falsifier conditions on an
   "uncollapsed critic" never exceeding 25/384 at any dose, so it cannot fire.
3. **k=3 × n=3000 gives P(credit | +0.025) = 0.45.** Members saturate at 3, so 6 lanes buys
   TWO committees — the only route to the clustered se the ENS3 credit lacks.

## Next actions
0. **GOAL: "AS HIGH AS POSSIBLE", not "clear top 500".** R4 hit Elo 1354 vs a 1358.999
   cutoff. Targets: H&L 1677 / ps-ppo 1725 / **Wang 1756** (Metamon's 1761 used REPLAYS).
1. **DECISIONS OWED BEFORE LAUNCH:** drop arm B?; keep/re-specify/drop C?; primary axis
   off-FP@20 vs the saturated vs-SH (at p 0.789 credit needs ≥ 0.81367)?; **horizon/width** —
   members saturate, so buy STEPS; 6 lanes buys 2 committees.
2. **LAUNCH TOOLING BUILT, DRY-RUN GREEN:** `monster_fleet.sh` (7 preflight gates, staggered,
   CPU-delta liveness) + `train_watchdog.sh` (auto-RESUME on the R2 alive-at-zero-CPU stall;
   every branch verified on real runs) + `derive_monster_config.py` (the lr_anneal trap —
   `rl.train` has NO --total-steps and a horizon past the anneal trains its tail at lr≈0;
   refused, not described). **k stays 8**, §(C) settles it.
3. **RULINGS OWED:** 11.5 before 11; a per-decision cap for a searched ladder object (≤5 s
   proposed); **whether to build engine-native DEPTH-2 at all** (see above — today argues no).

## Watch items
- **SUITE GREEN 1031 / 0 failed** on the DOCUMENTED invocation (encoder flags UNSET); 86
  skip and pass with them SET, where 6 v1-shape tests fail by design. Engine 115 + 94 cargo.
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200, larger than the
  gate's whole out-of-sample effect. Read curves, never one rung. **Corollary paid for
  2026-09-11: a 300-seed arm may NOT be read against a 3000-seed pooled mean** — on seeds
  100–399 greedy runs +0.054 above its own pooled value and the gated arm −0.024 below its
  own, a 0.078 swing against search on the exact block used to test it. Compare MATCHED.
