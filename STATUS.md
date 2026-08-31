# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
**Step 1 = gen1 retrain, batch lever (R2) — DONE AND CREDITED 2026-08-31.**
NEXT IS STEP 2 (ladder), then step 3 (gen4). SCOPE GUARD, binding: a read
inside the bar informs the INSTRUMENT, it does not licence another gen1
lever. **Name the JOURNEY step every work item serves.**

## Where things stand (2026-08-31) — **R2 COMPLETE, GRADED, CREDITED.**
Cell **P1**: off-FP@20 greedy delta **+0.13722** vs bar **0.07181** (se_gov
0.03591, clustered — the larger-of). Treatment 0.4740/0.4827/0.4670 (mean
0.47456, s_T 0.00785) vs banked control 0.3960/0.3430/0.2730 (0.33733, sd
0.0617). Secondary vs-SH 0.7813/0.7947/0.7833 (mean 0.78644) vs 0.70222 →
delta +0.08422 vs bar 0.07316 → **X1, credit stands**. F1 does not fire. All
gates green (G2 tallies agree per arm, G-SERIAL 0 overlaps, G-BUDGET 20 ms,
G-TERMINAL-RACE n_eff 3000, attest 16/16, R0-f, D-A bit-for-bit). Attestation
**3a31755**. **Pre-stated ~6.5% to credit (E1); it credited — treat the
surprise with MORE scrutiny.** Detail: SESSION_LOGS 08-31.

## Results | R2 50M: **vs-SH 0.78644** · **off-FP@20 0.47456** (P1, CREDITED)
Prior: 12M 0.71825 vs SH · ensemble 0.74633 · search@M 0.79283 · **LADDER R1
(ensemble) GXE 59.6%, Glicko 1573±27, Elo 1292** · **LADDER R3 (search@M, s80)
GXE 60.3%, Glicko 1579±25, Elo 1232 — STANDALONE; no R1-vs-R3 delta is a
quantity (D5)**; both n=200 · control off-FP 0.3960/0.3430/0.2730. Ties=loss.
**Ladders credit nothing; vs-SH/off-FP are NEVER ladder numbers.**

## Next actions
1. **MAINTAINER: R4S66 disposition.** OPS FAILURE (`r4s66.NO_PROGRESS`, rc=4)
   at 2,675/3,000 — two foul-play panics then the tie-crash wedge. Partial is
   NOT a result. Re-run needs the LICENSED PAIR-FLIP EDIT (ii) +
   `burned_pairs:`, own commit, LAST. R4S **routes nothing**; verdict stands.
2. **MAINTAINER: step 2 (ladder)** is the arc position. Candidates pre-named
   in R2 Q7; R3 chooses under its OWN pre-reg, incumbent-wins-ties.
   **R2's primary DOES NOT SELECT the ladder object.**
3. Riders R3c/R1i/R1ii NOT RUN — need `scripts/ch5_r2_crossplay.py`, unbuilt.
4. Fold R2 into RESULTS.md §16 + README row; CHAPTER5.md can be archived
   (§3/§6/§7 migrated). Residue: `CLEANUP.md`.

## Watch items
- **NEW, reproducible: LANES STALL.** s66 @68.9% and s75 @94.3%, ~10 h apart,
  identical signature — process ALIVE, **zero CPU**, stale logs, RSS bleeding
  out, sockets held. Liveness does NOT catch it; **sample CPU-time deltas**.
  Resumed; losses 190,776 and 170,680 steps (NOT the ≤30,720 once quoted —
  `checkpoint.pt` lags the last logged step by >1 update).
- **RESUME SPLITS HISTORY:** a resumed lane has TWO wandb offline runs with
  OVERLAPPING steps; `extract_history.py <run_dir>` HARD-FAILS on s66/s75. Use
  `history_merged.csv`. The verdict path never reads history.
- **D-E BREACH DISCLOSED:** resumed s75 alone peaked **5.87 GB** vs the 4.5 GB
  STOP line. Ruled continue — 2.68 GB/lane was measured 3-wide, box 85% free,
  swap FELL. Peak travels as a disclosure.
- **D-D passed but LOW:** 0.8584/0.8422/0.8607 — over the 0.75 floor, BELOW
  the pre-stated 0.90–0.96, far below control's ~0.971.
- **s_T 0.0078 vs 0.0617 is NOT a variance result** — (2,2) df, crit 19.0,
  needs ~4.4× to register; a null never reads "batch didn't help".
- **foul-play PANICs** (`Invalid PokemonMoveIndex: 4`) → tie-crash wedge; a
  killed pair stays poisoned for hours — re-run LAST on the rerun pair.
- **RECONCILE:** STATUS had LADDER R3 "106-94, n=200"; the readout (committed
  provenance) says "record 106-102", which sums to 208.
