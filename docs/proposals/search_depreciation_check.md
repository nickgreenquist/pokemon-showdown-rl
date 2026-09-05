# Search-depreciation check — data assembled, decision rule PROPOSED (unruled)

**Status: PROPOSAL, 2026-09-05.** JOURNEY's second pre-step-3 add ("Plot search
gain against policy strength across the 12M and 50M checkpoints we already have.
No training, no new runs. … If gains are already declining as the policy
improves, the MCTS question closes here, before anything is spent on it",
JOURNEY.md:21-23; IDEAS_POST_100M §2.5). Everything below is rebuilt from the
eval JSONs on disk by `scripts/search_depreciation_table.py`; nothing new was
measured. **The rule in §2 is written AFTER the numbers were public** (every
input is in RESULTS §15/§17/§18 and the R1/R2 readouts) — stated the way
`ladder_r4.yaml` stated its lane rule; the cut points are the repo's standing
conventions (sign of an OLS slope; 2·se_diff), not values tuned to this table.
Ratification is the maintainer's; this file decides nothing.

## 1. The data (off Foul Play@20, ties as non-wins, dose M, this box)

| point | recipe | greedy | n | search@M | n | gain | se_diff | gain/se |
|---|---|---|---|---|---|---|---|---|
| s82 (50M stack) | stack50m_r2 | 0.2730 | 1000 | 0.4540 | 3000 | +0.1810 | 0.0168 | +10.8 |
| s81 (50M stack) | stack50m_r2 | 0.3430 | 1000 | 0.4487 | 3000 | +0.1057 | 0.0175 | +6.0 |
| s80 (50M stack) | stack50m_r2 | 0.3960 | 1000 | 0.4390 | 3000 | +0.0430 | 0.0179 | +2.4 |
| s66 (50M batch) | batch50m | 0.4740 | 3000 | 0.3807 | 3000 | -0.0933 | 0.0127 | -7.3 |
| s104 (100M batch async) | batch async 100M | 0.4863 | 3000 | unmeasured | — | — | — | — |
| s112 (100M batch async) | batch async 100M | 0.5017 | 3000 | unmeasured | — | — | — | — |
| s120 (100M batch async) | batch async 100M | 0.5073 | 3000 | unmeasured | — | — | — | — |
| s65 (12M, CH3 R2, FP@100 ms, n=250/arm — EXCLUDED from the fit) | recipe12m | 0.3880 | 250 | 0.3680 | 250 | -0.0200 | 0.0434 | -0.5 |

OLS slope of gain on greedy, matched-axis points (k=4): -1.358; zero-crossing at greedy = 0.415
same, stack-recipe points only (k=3): -1.120; zero-crossing at greedy = 0.435
strongest matched point: s66 (50M batch) greedy 0.4740, gain -0.0933 = -7.3 se_diff
(no verdict: the rule is applied only once ratified — see the proposal doc)

**Provenance.** s80/s81/s82 greedy = CH5 R1-B A-arms (n=1000, `results/ch5_r1_offsh/a8x.json`);
searched = the RS re-scores (n=3000, `rs8x.json`) — the banked per-lane deltas
+0.051/+0.104/+0.148 quoted elsewhere used the n=1000 B-arms and are the same
ordering. s66 = CH5 R2 T66 greedy vs R4S66 search@M (both n=3000,
`results/ch5_r2_offsh/`). 100M = the C1 finals (`results/ch5_100m/t1xx.json`);
search@M on a 100M lane was NEVER measured. The 12M s65 row is CH3 R2's
head-to-head vs Foul Play at its stock 100 ms budget (n=250/arm, RESULTS §15) —
excluded from the fit for budget and power; FP@20 was later measured equivalent
to 100 ms in strength, weakly powered, so the row is context, not an input.

## 2. The decision rule (PROPOSED — apply only once ratified)

Statistics, both printed by the script: **S** = OLS slope of gain on greedy
strength over the matched-axis points (k=4); **G** = the strongest matched
point's gain in units of its se_diff.

- **CLOSED** iff S < 0 AND G ≤ −2. Reading: search@M substitutes for a
  deficient value head and stops paying once greedy strength passes the
  zero-crossing; it is NOT a strength lever for gen1 at or above that strength.
  Consequences: no MCTS spend on gen1 before the gen1 return (JOURNEY steps
  8-11); JOURNEY 11.5 (depth-1 vs depth-2 on the strongest object) is re-framed
  as a value-head diagnostic, not a strength test; the 100M search measurement
  is NOT run to confirm what the rule already decided.
- **OPEN** iff S < 0 AND −2 < G < +2. Reading: declining, but the top point does
  not resolve the sign. ONE measurement decides: search@M on the median 100M
  lane (s112), off FP@20, n=3000 (~2.7 s/battle, ~2.5 h; eval-class, agent-
  runnable detached), pre-registered with this rule attached; its gain replaces
  G.
- **LIVE** iff S ≥ 0. Reading: the hypothesis is wrong; search stays a lever and
  JOURNEY 11.5 proceeds as a strength test.

## 3. Confounds and disclosures, adjacent to the table by design

- **Recipe moves with strength.** The three stack lanes share a recipe; the
  strongest matched point (s66) is a batch-recipe lane, and the 100M lanes are
  batch-async. So "gain declines with strength" is entangled with "gain
  declines across recipes". Mitigation, stated not assumed: the stack-only fit
  (k=3, one recipe) extrapolates to zero at greedy ≈ 0.435, BELOW s66's 0.474,
  so the batch point's negative gain is what the within-recipe trend predicts.
  Three points and one degree of freedom; read the sign, not the slope's value.
- **Greedy A-arms are n=1000** (se ≈ 0.015) against n=3000 searched arms; the
  se_diff column carries it.
- **Dose is fixed at M.** Nothing here speaks to other doses or to the FP-budget
  ladder, which is a different axis.
- **Per-rung noise.** One vs-SH rung is worth ±0.02; off-FP rungs are on the
  same instrument class. The stack lanes' gains are 2.4-10.8 se_diff, the batch
  lane's is −7.3; only s80's +0.043 is near the noise floor.
- **RESULTS §17 is stale on R4S66.** Its paragraph still says "OPS FAILURE, not
  graded" (the a-pair attempt); the promoted b-pair re-run completed 3000
  battles at 0.38067 (SESSION_LOGS 2026-09-01; `ladder_r4.yaml` quotes it as
  the greedy-over-search evidence). The log wins on conflict; §17 owes a
  one-line correction — flagged here, not edited, because it is a published
  section.

## 4. What ratifying this costs and buys

Nothing runs either way except, under OPEN, one 2.5 h eval. What it buys is a
written reason for not spending on MCTS in gen1 now, or a written reason to
keep it live — before gen4 work starts and the question would otherwise be
re-argued from memory.
