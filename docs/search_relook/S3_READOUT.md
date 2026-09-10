# S3 READOUT — search relook on the 100M object (JOURNEY 11.5)

**MACHINE-WRITTEN by `scripts/search_s3_readout.py` at 2026-09-10T18:04:59+00:00.** Regenerated in place on every run — do not hand-edit; edit the script.

> **Credit line, verbatim:** "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals at read time"
>
> **S3 CREDITS NOTHING: descriptive screen; the cells route the relook.**
>
> ONE RUNG IS WORTH +-0.02 (three n=3000 redraws of ONE checkpoint spread 0.0200) — read the SHAPE across the three lanes, never one cell against its neighbour.

Pre-regs: `configs/eval/search_s3_100m.yaml` (sha256 `30d224b1048f89cb…`) · `configs/eval/search_s3_100m_offfp.yaml` (sha256 `9c82af2080aa7f48…`) · P-B's read: `docs/search_relook/DET_BLIND.md` §6 (P-B's read, verbatim). git HEAD `808bc35d49b7` (dirty: True).

## Arms

| arm | what | lanes | chunks | battles | pooled vs SH | status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| A0 | greedy, FRESH this session — the comparator | s104/s112/s120 | 30/30 | 9000 | **0.78867** | COMPLETE |
| S3M | depth-1 search, dose M (n_det 4, top_branches 6, leaf_cap 1296), as-is leaf encoding | s104/s112/s120 | 27/30 | 8100 | 0.71654 *(PARTIAL)* | PARTIAL |
| S3B | S3M with leaf_encoding: det_blind (DET_BLIND.md) | s104/s112/s120 | 10/30 | 3000 | 0.71433 *(PARTIAL)* | PARTIAL |
| S3L | dose L (n_det 16, leaf_cap 5184), s112 ONLY | s112 | 2/10 | 600 | 0.71333 *(PARTIAL)* | PARTIAL |
| A1E | dose M with the leave-one-out CRITIC ENSEMBLE as the leaf evaluator (R4's E3 form) | s104/s112/s120 | 0/30 | 0 | — | PENDING |

Per-lane (a PARTIAL cell is the running pooled rate over the chunks on disk and is **never** a cell input):

| arm | s104 | s112 | s120 |
| --- | ---: | ---: | ---: |
| A0 | 0.78933 (10/10) | 0.78233 (10/10) | 0.79433 (10/10) |
| S3M | 0.71852 PARTIAL (9/10) | 0.74458 PARTIAL (8/10) | 0.69233 (10/10) |
| S3B | 0.72333 PARTIAL (4/10) | 0.72000 PARTIAL (3/10) | 0.69667 PARTIAL (3/10) |
| S3L | *n/a* | 0.71333 PARTIAL (2/10) | *n/a* |
| A1E | PENDING (0/10) | PENDING (0/10) | PENDING (0/10) |

*Era note.* A0 is FRESH this session and is the ONLY comparator. The banked results/ch5_100m/final_s1xx.json (pooled 0.79589) are printed for CONTEXT ONLY — R3 measured a same-checkpoint era_diff of 0.0148 between a banked A0 and a fresh one, which is why the pre-reg forbids them as the comparator.

*Dose.* Dose is NOT matched between A0 and any search arm — the generic-compute confound survives, as in R2, and is disclosed rather than controlled. It IS matched between S3B and S3M (identical dose M, identical leaf caps), which is why P-B is the primary read of the det_blind screen.

## Pre-stated reads

| read | delta | Δ s104 | Δ s112 | Δ s120 | se_bin | se_clus | governing | 2·se_diff | CELL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| **P-M** (delta(S3M - A0)) | *PENDING* | — | — | — | — | — | — | — | **PENDING — no cell on partial data** |
| **P-B** (delta(S3B - S3M)) | *PENDING* | — | — | — | — | — | — | — | **PENDING — no cell on partial data** |
| **P-BA** (delta(S3B - A0)) | *PENDING* | — | — | — | — | — | — | — | **PENDING — no cell on partial data** |
| **P-E** (delta(A1E - S3M)) | *PENDING* | — | — | — | — | — | — | — | **PENDING — no cell on partial data** |

**P-M** (PRIMARY) — does depth-1 search@M pay on the 100M object at the locked protocol? NEG or FLAT -> the vacated depreciation ruling's PREMISE survives on the verdict axis and the relook's burden is the leaf evaluator + depth. POS -> the existing form is a live ladder-object candidate.

> PENDING — NO CELL ON PARTIAL DATA. Incomplete jobs: s3m_s104 9/10, s3m_s112 8/10. The per-lane numbers above are running pooled rates over completed chunks (PARTIAL); they are printed so the run is readable as a RATE, and they are NEVER cell inputs.

| lane | S3M (partial) | A0 (partial) |
| --- | ---: | ---: |
| s104 | 0.71852 (9/10) | 0.78933 (10/10) |
| s112 | 0.74458 (8/10) | 0.78233 (10/10) |
| s120 | 0.69233 (10/10) | 0.79433 (10/10) |

**P-B** (PRIMARY) — does removing the leaf-encoding artefact (det_blind) move the win rate? Dose MATCHED. Expected direction: det_blind >= as-is. A FLAT or NEG delta_B says the artefact was NOT the binding defect and the EVALUATOR is.

> PENDING — NO CELL ON PARTIAL DATA. Incomplete jobs: s3b_s104 4/10, s3b_s112 3/10, s3b_s120 3/10, s3m_s104 9/10, s3m_s112 8/10. The per-lane numbers above are running pooled rates over completed chunks (PARTIAL); they are printed so the run is readable as a RATE, and they are NEVER cell inputs.

| lane | S3B (partial) | S3M (partial) |
| --- | ---: | ---: |
| s104 | 0.72333 (4/10) | 0.71852 (9/10) |
| s112 | 0.72000 (3/10) | 0.74458 (8/10) |
| s120 | 0.69667 (3/10) | 0.69233 (10/10) |

**P-BA** (SECONDARY) — SECONDARY: does searching at all beat greedy once the artefact is gone? (The question S1 was actually raised against.)

> PENDING — NO CELL ON PARTIAL DATA. Incomplete jobs: s3b_s104 4/10, s3b_s112 3/10, s3b_s120 3/10. The per-lane numbers above are running pooled rates over completed chunks (PARTIAL); they are printed so the run is readable as a RATE, and they are NEVER cell inputs.

| lane | S3B (partial) | A0 (partial) |
| --- | ---: | ---: |
| s104 | 0.72333 (4/10) | 0.78933 (10/10) |
| s112 | 0.72000 (3/10) | 0.78233 (10/10) |
| s120 | 0.69667 (3/10) | 0.79433 (10/10) |

**P-E** (PRIMARY) — does a better leaf EVALUATOR pay on the 100M object? POS -> the monster train's evaluator lever (IDEAS 8.2 / 4.7) moves to the top of its config decisions. NEG/FLAT -> the ensemble form does not move the 100M object; 8.2 stays untested (different mechanism).

> PENDING — NO CELL ON PARTIAL DATA. Incomplete jobs: a1e_s104 0/10, a1e_s112 0/10, a1e_s120 0/10, s3m_s104 9/10, s3m_s112 8/10. The per-lane numbers above are running pooled rates over completed chunks (PARTIAL); they are printed so the run is readable as a RATE, and they are NEVER cell inputs.

| lane | A1E (partial) | S3M (partial) |
| --- | ---: | ---: |
| s104 | — (0/10) | 0.71852 (9/10) |
| s112 | — (0/10) | 0.74458 (8/10) |
| s120 | — (0/10) | 0.69233 (10/10) |

**P-L** (SECONDARY, one lane s112, **sign only, no cell**) — SECONDARY, ONE LANE, SIGN ONLY, NO CELL: the sign of the n_det axis on the strongest object, against the +-0.02 one-lane redraw spread.

> PENDING — NO READ ON PARTIAL DATA; the rates shown are running pooled rates over completed chunks (PARTIAL). S3L 0.71333 (2/10) vs S3M 0.74458 (8/10). ONE RUNG IS WORTH +-0.02; a one-lane delta inside +-0.02 is indistinguishable from a redraw of the same checkpoint.

## Search cost and decision counters — **CONTENDED**

> CONTENDED: 7-10 concurrent eval processes (torch_threads 1 each) shared the box while these arms ran. search/ms_mean and leaves are DESCRIPTIVE AND CONTENDED — they are NOT a budget number and NOT the clean decisions/sec that JOURNEY 11.5's exit condition asks for.

| arm | dose | leaf encoding | ms/decision (mean) | leaves/decision (mean) | searched decisions | flip rate | placeholder skip rate | basis |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A0 | — | — | — | — | — | — | — | COMPLETE |
| S3M | M | as_is | 61.8 | 276.5 | 428402 | 0.7306 | 0.0267 | PARTIAL |
| S3B | M | det_blind | 58.6 | 277.6 | 164755 | 0.7434 | 0.0230 | PARTIAL |
| S3L | L | as_is | 241.3 | 1102.4 | 31318 | 0.7188 | 0.0319 | PARTIAL |
| A1E | M | as_is | — | — | — | — | — | PENDING |

**leaves_mean equality (S3B vs S3M)** — DIAGNOSTIC ONLY — never a cell. Exact equality holds at MATCHED decisions (DET_BLIND.md §4, 11.4% argmax flips at IDENTICAL leaf counts). Live, the arms diverge after the first flip and play different battles, so the live check is a stated tolerance on the relative difference.

> S3B 277.58 vs S3M 276.48 — relative delta +0.0040 within the stated +-5% tolerance; computed over COMPLETED CHUNKS ONLY (PARTIAL). (PASS; diagnostic, no cell.)

**Decision-level flips.** Available: per-arm flip rate vs the arm's OWN policy argmax. NOT available: a paired S3B-vs-S3M per-decision agreement rate — the arms diverge after the first flip and never see the same decision set. DET_BLIND.md §4's 11.4% argmax-change figure is the OFFLINE matched-decision number and is not this.

> flip-rate delta (S3B − S3M) = +0.0129 (S3B 0.7434 on basis PARTIAL, S3M 0.7306 on basis PARTIAL).

## Off-Foul-Play anchor (descriptive, never a verdict input)

> **Budget named: 20 ms.** `--search-time-ms 20` (gen 1). FP@20 is an INSTRUMENT, not a rung.
>
> **Standing FP@20 disclosure:** "the equivalence test is weakly powered"
> **Standing FP@20 disclosure:** "the point estimate flatters us"
>
> Pre-stated direction: NEGATIVE — the 50M batch lane read search@M 0.3807 against greedy 0.4740 off FP@20 (-0.0933, -7.3 se). A positive read is a finding to record, not a gate.

| arm | leaf encoding | our_win_rate | n_eff | Δ vs banked greedy t112 (0.50167, n=3000) | FP win rate | ties | status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| F3M112 | as_is | **0.3960** | 1000 | -0.1057 | 0.5950 | 0.0090 | COMPLETE |
| F3B112 | det_blind | **0.4060** | 999 | -0.0957 | 0.5830 | 0.0110 | COMPLETE |

> **F3B112 − F3M112 = +0.0100** (binomial se_diff 0.0219). Descriptive; credits nothing.

## Attestations

Overall: **PASS** (13/13).

| check | pass | detail |
| --- | --- | --- |
| pre-reg carries the credit line verbatim | PASS | configs/eval/search_s3_100m.yaml |
| A0 leaf encoding stamped | PASS | expected None, on disk None (no search counters yet) |
| S3M leaf encoding stamped | PASS | expected as_is, on disk as_is |
| S3B leaf encoding stamped | PASS | expected det_blind, on disk det_blind |
| S3L leaf encoding stamped | PASS | expected as_is, on disk as_is |
| A1E leaf encoding stamped | PASS | expected as_is, on disk None (no search counters yet) |
| A0 mask_desyncs == 0 | PASS | 0 |
| S3M mask_desyncs == 0 | PASS | 0 |
| S3B mask_desyncs == 0 | PASS | 0 |
| S3L mask_desyncs == 0 | PASS | 0 |
| A1E mask_desyncs == 0 | PASS | 0 |
| off-FP pre-reg sha256 stamped in F3M112 resolves to a committed pre-reg revision | PASS | stamped d8417eda194e… = commit 1d0e076c5ea4 ("Search relook S3: pre-reg the missing depreciation point — d"), SUPERSEDED by today's 9c82af2080aa…. This is the RECORDED amendment that added F3B112 before it ran, not drift — the arm's own read is unchanged. |
| off-FP pre-reg sha256 stamped in F3B112 resolves to a committed pre-reg revision | PASS | stamped 9c82af2080aa… == the file today (HEAD version) |

