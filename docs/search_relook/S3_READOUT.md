# S3 READOUT — search relook on the 100M object (JOURNEY 11.5)

**MACHINE-WRITTEN by `scripts/search_s3_readout.py` at 2026-09-10T20:07:39+00:00.** Regenerated in place on every run — do not hand-edit; edit the script.

> **Credit line, verbatim:** "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals at read time"
>
> **S3 CREDITS NOTHING: descriptive screen; the cells route the relook.**
>
> ONE RUNG IS WORTH +-0.02 (three n=3000 redraws of ONE checkpoint spread 0.0200) — read the SHAPE across the three lanes, never one cell against its neighbour.

Pre-regs: `configs/eval/search_s3_100m.yaml` (sha256 `30d224b1048f89cb…`) · `configs/eval/search_s3_100m_offfp.yaml` (sha256 `9c82af2080aa7f48…`) · P-B's read: `docs/search_relook/DET_BLIND.md` §6 (P-B's read, verbatim). git HEAD `8c514210e3c8` (dirty: True).

## Arms

| arm | what | lanes | chunks | battles | pooled vs SH | status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| A0 | greedy, FRESH this session — the comparator | s104/s112/s120 | 30/30 | 9000 | **0.78867** | COMPLETE |
| S3M | depth-1 search, dose M (n_det 4, top_branches 6, leaf_cap 1296), as-is leaf encoding | s104/s112/s120 | 30/30 | 9000 | **0.72056** | COMPLETE |
| S3B | S3M with leaf_encoding: det_blind (DET_BLIND.md) | s104/s112/s120 | 30/30 | 9000 | **0.71178** | COMPLETE |
| S3L | dose L (n_det 16, leaf_cap 5184), s112 ONLY | s112 | 4/10 | 1200 | 0.72333 *(PARTIAL)* | PARTIAL |
| A1E | dose M with the leave-one-out CRITIC ENSEMBLE as the leaf evaluator (R4's E3 form) | s104/s112/s120 | 3/30 | 900 | 0.73778 *(PARTIAL)* | PARTIAL |

Per-lane (a PARTIAL cell is the running pooled rate over the chunks on disk and is **never** a cell input):

| arm | s104 | s112 | s120 |
| --- | ---: | ---: | ---: |
| A0 | 0.78933 (10/10) | 0.78233 (10/10) | 0.79433 (10/10) |
| S3M | 0.72167 (10/10) | 0.74767 (10/10) | 0.69233 (10/10) |
| S3B | 0.71267 (10/10) | 0.72933 (10/10) | 0.69333 (10/10) |
| S3L | *n/a* | 0.72333 PARTIAL (4/10) | *n/a* |
| A1E | 0.74333 PARTIAL (1/10) | 0.74667 PARTIAL (1/10) | 0.72333 PARTIAL (1/10) |

*Era note.* A0 is FRESH this session and is the ONLY comparator. The banked results/ch5_100m/final_s1xx.json (pooled 0.79589) are printed for CONTEXT ONLY — R3 measured a same-checkpoint era_diff of 0.0148 between a banked A0 and a fresh one, which is why the pre-reg forbids them as the comparator.

*Dose.* Dose is NOT matched between A0 and any search arm — the generic-compute confound survives, as in R2, and is disclosed rather than controlled. It IS matched between S3B and S3M (identical dose M, identical leaf caps), which is why P-B is the primary read of the det_blind screen.

## Pre-stated reads

| read | delta | Δ s104 | Δ s112 | Δ s120 | se_bin | se_clus | governing | 2·se_diff | CELL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| **P-M** (delta(S3M - A0)) | **-0.0681** | -0.0677 | -0.0347 | -0.1020 | 0.00639 | 0.01944 | clustered | 0.03888 | **NEG** |
| **P-B** (delta(S3B - S3M)) | **-0.0088** | -0.0090 | -0.0183 | +0.0010 | 0.00672 | 0.00558 | binomial | 0.01344 | **NEG** |
| **P-BA** (delta(S3B - A0)) | **-0.0769** | -0.0767 | -0.0530 | -0.1010 | 0.00643 | 0.01386 | clustered | 0.02771 | **NEG** |
| **P-E** (delta(A1E - S3M)) | *PENDING* | — | — | — | — | — | — | — | **PENDING — no cell on partial data** |

**P-M** (PRIMARY) — does depth-1 search@M pay on the 100M object at the locked protocol? NEG or FLAT -> the vacated depreciation ruling's PREMISE survives on the verdict axis and the relook's burden is the leaf evaluator + depth. POS -> the existing form is a live ladder-object candidate.

> **NEG** — pooled -0.0681 <= 0 and 3/3 lanes non-positive. Pooled rates 0.72056 (n=9000) vs 0.78867 (n=9000); 3/3 lanes non-positive. se_diff = **clustered** 0.01944 (binomial 0.00639, clustered 0.01944) — the LARGER of the two governs.

**P-B** (PRIMARY) — does removing the leaf-encoding artefact (det_blind) move the win rate? Dose MATCHED. Expected direction: det_blind >= as-is. A FLAT or NEG delta_B says the artefact was NOT the binding defect and the EVALUATOR is.

> **NEG** — pooled -0.0088 <= 0 and 2/3 lanes non-positive. Pooled rates 0.71178 (n=9000) vs 0.72056 (n=9000); 2/3 lanes non-positive. se_diff = **binomial** 0.00672 (binomial 0.00672, clustered 0.00558) — the LARGER of the two governs.

**P-BA** (SECONDARY) — SECONDARY: does searching at all beat greedy once the artefact is gone? (The question S1 was actually raised against.)

> **NEG** — pooled -0.0769 <= 0 and 3/3 lanes non-positive. Pooled rates 0.71178 (n=9000) vs 0.78867 (n=9000); 3/3 lanes non-positive. se_diff = **clustered** 0.01386 (binomial 0.00643, clustered 0.01386) — the LARGER of the two governs.

**P-E** (PRIMARY) — does a better leaf EVALUATOR pay on the 100M object? POS -> the monster train's evaluator lever (IDEAS 8.2 / 4.7) moves to the top of its config decisions. NEG/FLAT -> the ensemble form does not move the 100M object; 8.2 stays untested (different mechanism).

> PENDING — NO CELL ON PARTIAL DATA. Incomplete jobs: a1e_s104 1/10, a1e_s112 1/10, a1e_s120 1/10. The per-lane numbers above are running pooled rates over completed chunks (PARTIAL); they are printed so the run is readable as a RATE, and they are NEVER cell inputs.

| lane | A1E (partial) | S3M (partial) |
| --- | ---: | ---: |
| s104 | 0.74333 (1/10) | 0.72167 (10/10) |
| s112 | 0.74667 (1/10) | 0.74767 (10/10) |
| s120 | 0.72333 (1/10) | 0.69233 (10/10) |

**P-L** (SECONDARY, one lane s112, **sign only, no cell**) — SECONDARY, ONE LANE, SIGN ONLY, NO CELL: the sign of the n_det axis on the strongest object, against the +-0.02 one-lane redraw spread.

> PENDING — NO READ ON PARTIAL DATA; the rates shown are running pooled rates over completed chunks (PARTIAL). S3L 0.72333 (4/10) vs S3M — (10/10). ONE RUNG IS WORTH +-0.02; a one-lane delta inside +-0.02 is indistinguishable from a redraw of the same checkpoint.

## Search cost and decision counters — **CONTENDED**

> CONTENDED: 7-10 concurrent eval processes (torch_threads 1 each) shared the box while these arms ran. search/ms_mean and leaves are DESCRIPTIVE AND CONTENDED — they are NOT a budget number and NOT the clean decisions/sec that JOURNEY 11.5's exit condition asks for.

| arm | dose | leaf encoding | ms/decision (mean) | leaves/decision (mean) | searched decisions | flip rate | placeholder skip rate | basis |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A0 | — | — | — | — | — | — | — | COMPLETE |
| S3M | M | as_is | 62.3 | 277.4 | 471072 | 0.7277 | 0.0275 | COMPLETE |
| S3B | M | det_blind | 58.8 | 268.4 | 526292 | 0.7585 | 0.0233 | COMPLETE |
| S3L | L | as_is | 244.6 | 1083.4 | 68452 | 0.7502 | 0.0460 | PARTIAL |
| A1E | M | as_is | 73.1 | 288.4 | 43615 | 0.6991 | 0.0257 | PARTIAL |

**leaves_mean equality (S3B vs S3M)** — DIAGNOSTIC ONLY — never a cell. Exact equality holds at MATCHED decisions (DET_BLIND.md §4, 11.4% argmax flips at IDENTICAL leaf counts). Live, the arms diverge after the first flip and play different battles, so the live check is a stated tolerance on the relative difference.

> S3B 268.38 vs S3M 277.45 — relative delta -0.0327 within the stated +-5% tolerance. (PASS; diagnostic, no cell.)

**Decision-level flips.** Available: per-arm flip rate vs the arm's OWN policy argmax. NOT available: a paired S3B-vs-S3M per-decision agreement rate — the arms diverge after the first flip and never see the same decision set. DET_BLIND.md §4's 11.4% argmax-change figure is the OFFLINE matched-decision number and is not this.

> flip-rate delta (S3B − S3M) = +0.0307 (S3B 0.7585 on basis COMPLETE, S3M 0.7277 on basis COMPLETE).

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
| F3B112 | det_blind | **0.4054** | 999 | -0.0957 | 0.5830 | 0.0110 | COMPLETE |

> **F3B112 − F3M112 = +0.0094** (binomial se_diff 0.0219). Descriptive; credits nothing.

## Attestations

Overall: **PASS** (13/13).

| check | pass | detail |
| --- | --- | --- |
| pre-reg carries the credit line verbatim | PASS | configs/eval/search_s3_100m.yaml |
| A0 leaf encoding stamped | PASS | expected None, on disk None (no search counters yet) |
| S3M leaf encoding stamped | PASS | expected as_is, on disk as_is |
| S3B leaf encoding stamped | PASS | expected det_blind, on disk det_blind |
| S3L leaf encoding stamped | PASS | expected as_is, on disk as_is |
| A1E leaf encoding stamped | PASS | expected as_is, on disk as_is |
| A0 mask_desyncs == 0 | PASS | 0 |
| S3M mask_desyncs == 0 | PASS | 0 |
| S3B mask_desyncs == 0 | PASS | 0 |
| S3L mask_desyncs == 0 | PASS | 0 |
| A1E mask_desyncs == 0 | PASS | 0 |
| off-FP pre-reg sha256 stamped in F3M112 resolves to a committed pre-reg revision | PASS | stamped d8417eda194e… = commit 1d0e076c5ea4 ("Search relook S3: pre-reg the missing depreciation point — d"), SUPERSEDED by today's 9c82af2080aa…. This is the RECORDED amendment that added F3B112 before it ran, not drift — the arm's own read is unchanged. |
| off-FP pre-reg sha256 stamped in F3B112 resolves to a committed pre-reg revision | PASS | stamped 9c82af2080aa… == the file today (HEAD version) |

