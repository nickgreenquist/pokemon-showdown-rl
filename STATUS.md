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

## ENSEMBLE SCALING — members 4–6 MEASURED (the 50M finals as extra members; `configs/eval/ens_width*.yaml`)
b0 member curve, 1→6: **0.78867 → 0.81678 → 0.82667 → 0.82767 → 0.83633 → 0.84400** (members 4–6 are WEAKER
50M objects, so a lower bound). Pooled n=9000: **E6MIX 0.83356 vs ENS3 0.82356 = +0.0100 at 1.78 se —
unresolved (pre-stated branch: 6 lanes still preferred; NOT saturation).** E6MIX's batches spread 0.024
(0.844 / 0.837 / 0.820) vs ENS3's 0.0147 — never read one batch. **STEPS vs MEMBERS:** ENS3 of the 50M finals
= **0.82233** vs the 100M committee's 0.82356 (+0.001 for the doubling, on the committee); ensemble gain
+0.038 at 50M vs +0.035 at 100M — additive, and the horizon is the weaker lever vs SH (saturated axis).
**OFF FP@20, SAME SESSION, n=1000 each (`scripts/ens_width_readout.py`):** greedy 100M re-draw 0.507 / 0.486 /
0.507 (mean 0.500; era term +0.002 vs 2026-09-03) → **ENS3F 0.557 and its fresh-pair replicate ENS3FR 0.577
(spread 0.020 = noise) pool to +0.067 at 4.7 se: the committee's off-FP transfer is verdict-grade.** E6MIXF
0.553 = −0.014 vs the pooled ENS3 (unresolved; three weaker members neither help nor hurt). E350F 0.537 vs
fresh 50M greedy 0.501 / 0.501 / 0.473: gain +0.045 at 50M vs +0.067 at 100M (additive); committee doubling
+0.030 ± 0.02. The R2-era 50M comparators (0.474 / 0.483 / 0.467) were a different FP build. FP@500 pending.

## ENSG — ensemble AS the search's prior+leaf value, with the gate. **A NULL ON BOTH AXES.**
vs SH, n=3000 vs ENS3 b0: δ 0.05 **−0.002** (n=2900), **δ 0.10 +0.01500 at 1.6 se**, δ 0.20 **+0.008** —
the +0.015 is the tuned δ talking (swept on s112, which the committee contains). **Off FP@20, pre-registered
(`configs/eval/ens_offfp.yaml`): ENSGF 0.558 vs ENS3F 0.557 = +0.001, the "|δ| < 0.045 → ENS3 stays"
branch.** Search fired (override 7.5%, 31,085 searched decisions, committee shas stamped), so this is a
real null, not a void arm. The gate adds nothing to the committee anywhere; sub-2-se deltas are not wins.

## The monster (JOURNEY 10) — three overnight reports converge on THE CRITIC; launch block rewritten
1. **Arm B dropped** (bitwise arm A; its head feeds nothing; its only consumer, search, is null twice over).
   **Arm C not recommended** (falsifier cannot fire; never run on the engine route with the oppact head).
2. **The critic is the bottleneck on every line:** ctx-stack srank99 7–10/384 vs the actor's 33–54, explained
   variance flat at ~0.59 from mid-run, three on-policy sources say widen the VALUE net, not the actor. The
   actor is 626,059 params, at parity with the closest pure-self-play comparable. Reports (2026-09-12):
   `docs/research_reports/MODEL_SCALE_*`, `SELFPLAY_RECIPE_*`, `MONSTER_BUNDLE_*`. **BUILT tonight:** gated
   LayerNorm in the ctx stack (tested; next fleet — it muddies L2's instruments), configs W and L2LAM.
3. **Plasticity probe running** (`PLASTICITY_PROBE_*`): does the 100M final still fit fresh targets like a
   fresh init? Its pre-stated branches re-weight the two trios; none blocks the launch. Smokes run ~07:00Z.

## Next actions
0. **GOAL: "AS HIGH AS POSSIBLE".** R4 hit Elo 1354 vs a 1358.999 cutoff. Targets: H&L 1677 / ps-ppo 1725 /
   **Wang 1756** (Metamon's 1761 used REPLAYS). **LADDER OBJECT TODAY: ENS3** (greedy speed, no confound).
1. **SATURDAY LAUNCH** (box packed ~2026-09-12 13:00 EDT, launch that night, unattended 3–4 days). Recommended
   OPTION C, written as [RWL-1..8] at the top of `configs/showdown_monster200m.yaml` for you to ratify:
   **every lane L2; trio W = L2 + 1024-wide critic (seeds 104 112 120, ~54 h); trio L2LAM = L2 + Monte-Carlo
   targets (128 136 144, ~45 h)**; two commands ([RWL-5]); k=8; anneal = horizon (the LR FLOOR is a ruling,
   both sides in [RWL-4]). Reads: mechanism co-primary; off-FP@20 same-session re-draw picks the committee.
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
