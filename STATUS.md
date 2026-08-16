# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-16 — **D25-P DONE, 12M x5 CLEAN; FINALS EVAL IS THE GATE**)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). **D25 CREDITED (0.6185); the LADDER IS COMPLETE —
M1-M4 CLAIMED.** Open: claim SCOPE — without the placebo the claim is "an aux
opponent-action loss helps", NOT "an opponent model helps". **D25-P finished all five
lanes at 12M, every during-gate passes, and the pre-stated P3 dose read fires
DOSE-CAVEATED on 12/12 bins** (2026-08-16 log). Only the finals eval is outstanding.

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25 mech co-primary: LETTER at MIN p = 1/252, both spaces** | Δ +0.0426 |
| D25-P placebo — in-loop PREVIEW only, NOT a result (see item 1) | ~0.576 |

## Next actions, in order
1. **RUN THE FINALS EVAL — everything else waits on it.** `mkdir -p results/d25p`, then
   5x3000 sequential, BOTH env vars, no extra flags (the treatment used none;
   `seed_start=100` derives from `eval_episodes`). Maintainer's terminal, ~10 min.
   **PREVIEW, NOT A RESULT:** the in-loop `eval/win_rate` (n=100, opponent `heuristics`,
   same as locked) ends 0.58/0.50/0.57/0.63/0.60, 5-lane mean **~0.576**. On the
   TREATMENT arm that same statistic tracked the locked pooled number to +0.0025, so it
   is near-unbiased but noisy (se ~0.022). **0.576 sits just under R-1's credit boundary
   (<= 0.5935/0.5871/0.5800 at s_P = 0/0.026/0.036) — too close to call. Do not
   pre-announce a branch.** Note it is ABOVE the 0.545 the pre-reg expected.
2. **Grade: `python scripts/d25_grade.py --placebo results/d25p`** — attestation + era-
   attestation print first, then R-1/R-2 (+R-3/R-5 once their inputs exist). P7
   precedence: B7 (R-4 leak/never-trained) and B6 FIRST, then B1-B5/B8/B9. **B6 does NOT
   fire** (R1 clear 5/5, anchor 0.972-0.978 at 4M).
3. **Mech inputs — ALL THREE SCRIPTS EXIST; the fleet is DOWN, so collections can run.**
   (a) atoms: `d25_atoms.py --lanes 57,58,59,60,61 --run-prefix
   showdown_sp_actpred12m_placebo_s --out results/d25p/placebo_atoms.json` (defaults
   still reproduce the banked treatment atoms). (b) dormancy: `d22_collect_obs.py`
   (200 eps)/lane -> `d22_dormant_rank.py --lanes 57,58,59,60,61 --run-prefix
   showdown_sp_actpred12m_placebo_s --out results/d25p --tag d25_placebo` (NEVER the
   control tag). (c) R-4: `scripts/d25p_manipulation.py` — needs 300-ep mirror tapes at
   `results/d25p/oppact_s{57..61}.npz` first (`collect_oppact.py`); verified against the
   banked treatment g (reproduces s52's 0.7472 exactly).
4. **Readout entry** naming the P7 branch, discharging its STATUS/README obligation,
   re-measuring the ledger (~18.25/20, never increment). **The dose caveat below is
   BINDING on whichever branch fires.** Expected shapes, R-1 boundaries and R-3
   governance: 2026-08-15 night ADDENDUM — read before grading.

## Watch items
- **THE DOSE CAVEAT (pre-stated P3, fires 12/12 bins).** Placebo `aux/trunk_norm` bin
  medians fall 0.0137-0.0173 (bin 0) to 0.0011-0.0022 (bin 11) vs a frozen band of
  0.079-0.098 — 3-31% of the 0.7x threshold, never close. **The a-fortiori refutation of
  "a generic aux gradient is what helps" is NOT available on this arm**, and the caveat
  must be written into the readout. NOT a fault, NOT a void, direction predicted by the
  named §12 deviation; NO re-tune, NO relaunch (one-lever, D17).
- Trunk RATIO (= `aux/trunk_norm` ÷ `aux/policy_trunk_norm`, RATIO OF MEANS): placebo
  0.025-0.029 in bin 0 decaying to 0.0000-0.0031 by bin 11; treatment holds 0.094-0.108.
- **VOID clause does not fire:** placebo clip 0.8812-0.9705 vs treatment 0.9729-0.9929 —
  a naive 0.90 read voids the CREDITED arm too. Read at MATCHED STEPS.
- **Never read R0-8 off `time/steps_per_sec`** (mean 361 vs wall 312) — Δstep/Δruntime.
- **`results/d25/` IS THE ONLY COPY** of the sha256-frozen tapes + finals/grade artifacts
  (backup `../pokemon-showdown-rl-d25-backup-20260815/`); `results/d25p/` joins it.
- **808/828 seam:** 828 ckpts (placebo + treatment) eval with BOTH env vars; the v2/808
  clone with V2=1 only. A mixed chain dies at load.
- Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED; 14-22 RESERVED; 47-48 held; 52-56 = D25;
  **57-61 = D25-P (SPENT)**; 62-63 never needed; 64+ free.
