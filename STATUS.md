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
**D5: play search's action only if it beats the POLICY's argmax by > δ** (absent = no-op, golden digest;
δ=inf = greedy). s112, n=3000/arm vs SH: **δ 0 → 0.74767, BELOW greedy's 0.78233** — the critic's own
argmax loses to the policy at ONE ply; search only ever paid as a rarely-fired veto; 0.05 0.80867, **0.10 0.82400**, 0.20 0.81000.
- **HONEST READ IS OUT OF SAMPLE: +0.016, NOT +0.042.** Held-out lanes at δ 0.10, n=3000 each:
  s104 +0.01967, s120 +0.01233; **pooled n=6000 = +0.01600 at 2.19 se_diff — MEETS 2·se_diff,
  MISSES the floor → NOT CREDITED.** Never quote s112's +0.0417.
- **EG10: a better evaluator adds nothing AT DEPTH-1** (LOO ensemble + same gate, 3×3000:
  −0.00044 at 0.05 se) — weakens arm B's premise. **ENS3 vs stack is a NULL** (+0.01078 at
  1.87 se; that figure includes the tuning lane, flattering SEARCH).
- **OFF FOUL PLAY THE GATE TRANSFERS** — BLM (gated@M, δ 0.10) vs FP@20, n=1000: **0.525** vs
  a **0.47** bar (greedy 0.50167, UNGATED 0.39600 — **the SELECTOR alone bought +0.129
  off-FP**). +0.023 vs greedy at 1.28 se is NOT significant. Both FP@20 disclosures travel.
**LANDMINE: every search number before 2026-09-11 measures a BROKEN selector** (grep `PRE-D5`; LADDER R3 is a D4 object).
## DEPTH IS MEASURED, AND IT IS A NULL, NOT A NEGATIVE — 2026-09-11 review of ~14,000 battles
Two implementations (`rl/search/tree.py`, decoupled-UCT with OUR prior and critic; `_look_further`,
N plies on the banked matrix); account + review addendum in `docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md`.
n=900 each vs S3G10 (0.8189 on the same 900 seeds), UNPAIRED se ≈ 0.019 (seeds do NOT pair — Watch items).
- **Tree: depth is a NULL.** Two exact-config replicates per depth. Depth 1: TSAMP1 0.8144, TQV 0.7778
  (0.037 apart at n=900); depth ~3: TSAMP 0.7900, TQV8 0.7944. **Pooled 0.7961 vs 0.7922 = −0.004 ± 0.013.**
  The 16:14 STATUS reported TSAMP1/TSAMP only; TQV/TQV8 were on disk since 13:50 and unreported. The
  depth-1 tree sits −0.023 (−1.7 se) under the banked matrix pooled — "the control reproduces the
  matrix" held for one replicate of two.
- **Matrix: the −0.094 (−4.6 se) at +2 plies is an OVERRIDE-RATE effect, not depth.** At δ 0.10 the deep
  arms override 16.5–20.1% of decisions vs S3G10's 8.3%; at matched override (D3G40, δ 0.40, 2.9%) depth 3
  reads **−0.017 ± 0.023 at n=600**. A deeper backup needs a recalibrated δ; nobody has swept it.
- Deep arms had 3–6× the compute (229 vs 40 ms; 330 vs 78 ms). **DEPTH CENSUS:** FP's iterative deepening
  reaches 2.44 / 3.08 / 3.56 plies at 20 / 200 / 2000 ms — FP@20 searches ~depth 2.4; our tree exceeds it.
- **Licensed: "no evidence depth helps at these budgets and this δ." Barred: "depth hurts", "monotone".**
  Engine-native depth-2 ruling still owed; a δ sweep for deep backups is the cheap first step.
- PokeAgent paper (re-verified from our PDF): Foul Play #1 Gen 9 OU / #8 Gen 1 OU; PA-Agent (no search)
  won Gen 1. That is an OU TEAM-BUILDING ladder rank — the paper calls set prediction "critical" there —
  so it does not show search underperforms in gen-1 randbats. Quote it; do not infer from it.

## ENSEMBLE SCALING — "members SATURATE at 3" is NOT established; members 4–6 are measured overnight
Pairs on b0: 0.81867 / 0.81100 / 0.82067 (mean 0.81678); triple 0.82667; singles mean **0.78867** (not
s112's 0.78233). Gains +0.028 then +0.010 — but ENS3's own batches spread **0.0147** (0.82667 / 0.81467 /
0.82933), so the 2→3 gain sits inside one batch swing. The last STEP doubling (50M→100M, RESULTS §18)
bought +0.024 off-FP (**NOT credited**) and +0.009 vs SH; three free members bought +0.035 vs SH.
**RUNNING (`configs/eval/ens_width*.yaml` → `results/ens_width*/`, `logs/ens_width/queue.log`):** E4 /
E5 / E6MIX with the 50M finals as members 4–6 (vs SH, minutes; off FP@20 ~4 h, sequential), plus a
SAME-SESSION greedy off-FP re-draw (the comparator ENS3F lacked) and an ENS3F replicate on a fresh pair.

## ENSG — ensemble AS the search's prior+leaf value, with the gate. **A NULL ON BOTH AXES.**
vs SH, n=3000 vs ENS3 b0: δ 0.05 **−0.002** (n=2900), **δ 0.10 +0.01500 at 1.6 se**, δ 0.20 **+0.008** —
the +0.015 is the tuned δ talking (swept on s112, which the committee contains). **Off FP@20, pre-registered
(`configs/eval/ens_offfp.yaml`): ENSGF 0.558 vs ENS3F 0.557 = +0.001, the "|δ| < 0.045 → ENS3 stays"
branch.** Search fired (override 7.5%, 31,085 searched decisions, committee shas stamped), so this is a
real null, not a void arm. The gate adds nothing to the committee anywhere. At n=900 it had read +0.030
at 1.7 se and was called a win; sub-2-se deltas are not wins.

## The monster (JOURNEY 10) — decisions owed; today's reads bear on two
1. **ARM B IS BITWISE ARM A** (24 rungs, 223 tensors / 3,428,015 elements, 0 differing, sha
   f156f232462e635b): separate net, own trunk, `autograd.grad` over its own params only.
   **Its ONLY consumer is a search leaf evaluator** — EG10 says a better evaluator adds
   nothing at depth-1 and today says no reachable depth pays. **Recommend DROP arm B**; its
   MC-target bug is fixed (b147f48) and that finding keeps regardless.
2. **ARM C IS CONTESTED BY BOTH REVIEWS** — D18's lever at λ 0.95 where the vacatur named
   λ=1.0; 30× less variance headroom at a 30,720-step update; falsifier conditions on an
   "uncollapsed critic" never exceeding 25/384 at any dose, so it cannot fire.
3. **k=3 × n=3000 gives P(credit | +0.025) = 0.45.** 6 lanes buys TWO committees (the clustered se
   the ENS3 credit lacks) AND the 6-member read; the "saturate at 3" reason for 3 lanes is withdrawn.

## Next actions
0. **GOAL: "AS HIGH AS POSSIBLE".** R4 hit Elo 1354 vs a 1358.999 cutoff. Targets: H&L 1677 / ps-ppo 1725 /
   **Wang 1756** (Metamon's 1761 used REPLAYS). **LADDER OBJECT TODAY: ENS3** (greedy speed, no confound).
1. **SATURDAY LAUNCH** (box packed ~2026-09-12 13:00 EDT, launch that night, unattended 3–4 days). Recommended,
   written as [RWL-1..6] at the top of `configs/showdown_monster200m.yaml` for the maintainer to ratify:
   `bash scripts/monster_fleet.sh configs/showdown_monster200m.yaml 200000000 104 112 120 128 136 144` —
   **6 × 200M, ALL ARM A** (B: bitwise A, head feeds nothing, its only consumer is search, null twice over;
   C: falsifier cannot fire — drop unless re-specified), k=8, ≈43 h at the idle w6 rate. PRIMARY read
   off-FP@20 vs a SAME-SESSION greedy 100M re-draw (protocol rehearsed tonight); vs SH secondary.
2. **BEFORE LEAVING (a password is needed):** `sudo pmset -c sleep 0 disksleep 0`; Software Update →
   "Install macOS updates" **OFF (it is ON)**; lid OPEN; quit VS Code/Chrome (6-wide ≈ 11 GB of 24).
   The launcher now holds its own caffeinate and the watchdog restarts Node (both tested 2026-09-11).
3. **RULINGS OWED:** 11.5 before 11; a per-decision cap for a searched ladder object (≤5 s); engine-native
   DEPTH-2 (above: not the lever; a δ sweep for deep backups is the cheaper first step).

## Watch items
- **SUITE GREEN 1031 / 0 failed** on the DOCUMENTED invocation (encoder flags UNSET); 86 skip
  and pass with them SET, where 6 v1-shape tests fail by design. Engine 115 + 94 cargo.
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200. Read curves, never one rung.
- **SEEDS DO NOT PAIR BATTLES (2026-09-11 review; `docs/landmines.md`).** Per-battle agreement between
  arms on shared seeds is at the independence level (0.66–0.73): teams and rolls are server-rolled. "Matched
  seed-for-seed, McNemar se" was UNPAIRED all along (the se coincides, so no number moved). The 16:14
  "300-seed arm vs 3000-seed pooled mean" corollary was n=300 noise (se 0.023), not a block offset: the
  rule is "n=300 cannot resolve ±0.05", not "compare matched". Replicates are the instrument.
