# Handoff — written 2026-08-15 ~21:00 EDT. **D25-P IS RUNNING. 5 LANES LIVE.**

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty
stub. STATUS.md and SESSION_LOGS.md are CURRENT through the D25-P launch record and
the M4 claim; this file carries only what the next session needs to *do*.

## State: placebo lanes s57-61 training, healthy, finals ~06:55 EDT Aug 16

`main` clean, suite **354 green**. D25 CREDITED (0.6185) with all four letters;
**M4 CLAIMED — the ladder is COMPLETE**. D25-P (shuffled-label placebo, header
RATIFIED in `configs/showdown_sp_actpred12m_placebo.yaml`, P11 = 5-and-no-more)
launched ~19:55 EDT in five DETACHED screens `d25p_s57`…`s61`. At launch+2min:
~315 steps/s 5-wide, R0-1 stamps correct, and THE SIGNATURE IS LIVE:
`aux/loss` 1.54-1.57 PINNED at `aux/marginal_nll` 1.51-1.54 on every lane,
`aux/shuffle_illegal_frac` 0.000000 x5, match_frac in the 0.243-0.330 chance band.

## Do this, in order

1. **VERIFY BY BATTLE PROGRESS** (re-extract history.csv — wandb offline, stale CSV
   is not a stalled lane). Watch: R1 `winrate_anchor` >= 0.75 by 4M (**<3 of 5 clear
   -> ARM STOPS = branch B6 PLACEBO-HARMS — that is a RESULT, record per P7's
   resolution rule, no re-tune**); K6 before 6M; R0-8 WALL (>=30-min window after
   1M; record <255, STOP <210); P-SHUF (per-1M-bin median of `aux/loss_mb0` -
   `aux/marginal_nll` < -0.03 for 3 bins -> investigate); VOID clause at MATCHED
   STEPS only. A lane lost BEFORE R1 relaunches on held seeds 62/63, never same seat.
2. **At the finals: locked eval** — `mkdir -p results/d25p`; 5x3000, BOTH env vars,
   sequential, `--out results/d25p/final_s{57..61}.json` (checkpoint.pt per lane).
   Maintainer's terminal (~10 min).
3. **Grade: `python scripts/d25_grade.py --placebo results/d25p`** — attestation +
   era-attestation print first, then R-1/R-2 (+ R-3/R-5 when their inputs exist).
   Branch precedence P7: B7 (R-4 leak/never-trained) and B6 first, then B1-B5/B8/B9.
4. **Mech inputs (fleet must be DOWN for collections):**
   (a) atoms — `scripts/d25_atoms.py` is HARDCODED to lanes 52-56 /
   `showdown_sp_actpred12m_s`; edit LANES + run prefix + output to
   `results/d25p/placebo_atoms.json` (grader expects that name);
   (b) dormancy — `d22_collect_obs.py` (200 eps) per placebo lane ->
   `d22_dormant_rank.py --lanes 57,58,59,60,61 --run-prefix
   showdown_sp_actpred12m_placebo_s --out results/d25p --tag d25_placebo` (NEVER the
   control tag); grader expects `results/d25p/dormant_d25_placebo.csv`;
   (c) **R-4 IS NOT WRITTEN**: adapt `scripts/d25_manipulation.py` for placebo lanes
   (own tapes via `results/d25/scripts/collect_oppact.py` at 300 eps; read g_P vs
   the 0.02 g-unit band; TRAINED-TO-FLOOR check NLL_head ~ A1 vs A0 1.773-1.780;
   read at 3M/6M/12M — RISING |g_P| is the leak signature).
5. **Readout entry** with the P7 branch named, its STATUS/README obligation
   discharged (every branch has one), and the ledger re-measured (~18.25/20).

## Do NOT rediscover

- **Expected outcome shapes:** placebo win rate near 0.545 + R-1 credits = B1
  UPGRADE ("explicit opponent-action model helps", with C3(b)/C4 caveats attached,
  NEVER "belief state"). R-1's credit boundary: placebo <= 0.5935/0.5871/0.5800 at
  s_P = 0/0.026/0.036. The modal non-null at wide spreads is the RECORDING BAND
  (B9). A null R-2 alone licenses NOTHING (the binding pre-statement, P0).
- **R-3 governance:** §5's banked letter NEVER loses its number/verdict; the
  LICENSE narrows iff R-3(a) fires AND (mean_P - 0.0150)/0.0426 >= 1/3 (fraction
  governs on disagreement).
- **The 808/828 seam:** placebo/treatment ckpts eval with BOTH env vars; the v2/808
  clone evals with V2=1 only; a mixed chain dies at load.
- **`aux/labelled_frac` during-band is [0.78, 0.88] whole-run MEAN** — the smoke
  band 0.84-0.88 applies to 100k smokes only (R0-P2 lesson; per-update reads fail
  healthy lanes 14-35% of the time).
- **grad_clip_frac ~0.99 mid-run NORMAL** (policy clip); the AUX clip never binds
  (dose table frozen in `results/d25/dose_bins.json`, bin-matched reads only).
- **`results/d25/` backed up** at `../pokemon-showdown-rl-d25-backup-20260815/`
  (verified post-copy). results/d25p artifacts should join the backup at readout.
- Screens survive agent jobs; `screen -r d25p_s57`, `ctrl-a d`. Server on :8000.
- The R0-P2 (c) update-1 bit-identity check is VOID-BY-PREMISE (server rolls fresh
  battles every run — measured 2026-08-05); do not re-run it or read its failure as
  a build defect. Wall noise at 100k-smoke scale is ~10%; R0-8 governs at 12M.
