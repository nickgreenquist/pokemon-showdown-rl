# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-15 night — **D25-P PLACEBO RUNNING, 5/5 HEALTHY**)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). **D25 CREDITED (0.6185, +0.0739 over the frozen
0.54453, bar 0.58273 cleared by +0.036); the LADDER IS COMPLETE — M1-M4 CLAIMED.** Open:
claim SCOPE — without the placebo the claim is "an aux opponent-action loss helps", NOT
"an opponent model helps". D25-P settles it. 50M CLOSED; D18 NULL; D23 not-credited.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| Rung 3 50M — CREDIT 0.5802 ± 0.0052 · D18 NULL 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25 mech co-primary: LETTER at MIN p = 1/252, both spaces** · D25-P RUNNING | Δ +0.0426 |

## Next actions, in order
1. **WATCH D25-P** (5 detached screens `d25p_s57`…`s61`, launched 19:55 EDT 2026-08-15,
   finals ~06:45-07:15 EDT Aug 16). Verify by battle PROGRESS — re-extract history.csv
   first, wandb is offline. Gates: R1 `winrate_anchor` >= 0.75 by 4M (**<3 of 5 -> ARM
   STOPS, B6 PLACEBO-HARMS: a RESULT, record per P7, no re-tune**); K6 (5-lane median
   entropy < 0.15 x5) before 6M; R0-8 WARM wall (>=30-min window after 1M: record <255,
   STOP <210); P-SHUF (per-1M-bin median `aux/loss_mb0` - `aux/marginal_nll` < -0.03 x3).
   A lane lost BEFORE R1 relaunches on seed 62/63, never the same seat. T+19min: 5/5 green.
2. **At the finals: locked eval** — `mkdir -p results/d25p`; 5x3000, BOTH env vars,
   sequential, `--out results/d25p/final_s{57..61}.json`. Maintainer's terminal, ~10 min.
3. **Grade: `python scripts/d25_grade.py --placebo results/d25p`** — attestation + era-
   attestation print first, then R-1/R-2 (+R-3/R-5 once their inputs exist). P7
   precedence: B7 (R-4 leak/never-trained) and B6 FIRST, then B1-B5/B8/B9.
4. **Mech inputs — fleet DOWN for collections.** (a) atoms: `d25_atoms.py` is HARDCODED
   to 52-56 / `showdown_sp_actpred12m_s`; edit LANES + prefix + output to
   `results/d25p/placebo_atoms.json` (grader expects that name). (b) dormancy:
   `d22_collect_obs.py` (200 eps)/lane -> `d22_dormant_rank.py --lanes 57,58,59,60,61
   --run-prefix showdown_sp_actpred12m_placebo_s --out results/d25p --tag d25_placebo`
   (NEVER the control tag) -> `dormant_d25_placebo.csv`. (c) **R-4 IS NOT WRITTEN — the
   owed build while lanes run:** adapt `d25_manipulation.py` for placebo lanes (own tapes,
   300 eps; g_P vs the 0.02 band; floor check vs A0 1.773-1.780; 3M/6M/12M, rising = leak).
5. **Readout entry** naming the P7 branch, discharging its STATUS/README obligation, and
   re-measuring the ledger (~18.25/20, never increment). **Expected shapes, R-1 credit
   boundaries, R-3 governance: the 2026-08-15 night ADDENDUM — read before grading.**

## Watch items
- **Trunk ratio (R0-10b) runs 0.045-0.056, three lanes under the [0.05, 1.5] floor — NOT
  a defect, NOT a failed gate.** During-RECORD per 1M bin; the header's named §12
  deviation predicts it (no zero-info placebo matches gradient magnitude — measured, not
  matched). Carry into B4 / the a-fortiori clause.
- **match_frac gate = closed form 0.243-0.330 ±0.05 = [0.193, 0.380], read on lane MEANS**
  (0.240-0.271 now). Sub-0.243 per-update reads are noise, not a breach.
- **`grad_clip_frac` ~0.99 mid-run is NORMAL** (policy clip; the AUX clip never binds).
  VOID's 0.90 is a WHOLE-RUN mean — read at MATCHED STEPS or every lane voids.
- **`results/d25/` IS THE ONLY COPY** of the sha256-frozen tapes + finals/grade artifacts
  (backup `../pokemon-showdown-rl-d25-backup-20260815/`); `results/d25p/` joins it at
  readout — losing either voids the mechanism co-primary.
- **808/828 seam:** 828 ckpts (placebo + treatment) eval with BOTH env vars; the v2/808
  clone with V2=1 only. A mixed chain dies at load.
- Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED; 14-22 RESERVED; 47-48 held; 52-56 = D25;
  **57-61 = D25-P**; 62-63 held for a pre-R1 relaunch; 64+ free.
