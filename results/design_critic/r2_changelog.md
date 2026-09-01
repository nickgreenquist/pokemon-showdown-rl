# CH3 R5 pre-registration — r1 -> r2 changelog

r2 written 2026-08-24 against `draft_review_1.md` (methods, 46 findings,
NOT-RATIFIABLE: 6 BLOCKERs / 23 MAJORs) and `draft_review_2.md`
(conventions/executability, RATIFIABLE-WITH-FIXES: 2 BLOCKERs / 8 MAJORs /
9 MINORs).

**Structural change:** the single `ch3_r5_prereg_draft.yaml` is SPLIT into
- `ch3_r5a_tgate_draft.yaml` — the T-GATE, standalone, non-crediting,
  runnable on `scripts/ch3_r4_anchors.py` with **zero driver changes**;
- `ch3_r5b_exit_draft.yaml` — Stage 2, explicitly BLOCKED ON
  [r5a == T-PASS] AND [RULE-1 ruled option 1].

New supporting artefact: `r5_power_sim.py` — the committed script that
generates every power/size/operating-characteristic cell in both files
(review 1 finding 14's fix). Its `s_C = 0.011177` column reproduces review
1's independent simulation to ±0.002 in every cell, which cross-validates
both.

---

## Review 1 (methods)

| # | sev | disposition |
|---|---|---|
| 1 | BLOCKER | D-3 upper edge re-derived: band is now `[0.25, (1 - a0_selfplay) + 0.05]`. A perfect distillation has `a1 = 1.0`, `F = 1 - a0_selfplay` exactly, which is INSIDE the band; the r1 `[0.15, 0.55]` STOPPED the arm at the ideal fit. Rationale restated so "overshoot" means overshoot. (r5b `d3_rule`) |
| 2 | MINOR | D-3 lower edge raised to 0.25 (above the D-2-implied floor of `a1-a0 >= 0.20`) AND the subsumption said out loud: it binds only in the strip `a1 in [a0+0.20, a0+0.25)` and is a mechanical redundancy check above it. |
| 3 | MAJOR | 0.598 / 40.2% / 34.6-per-battle are vs-SH. D-2/D-3 are now stated relative to `a0_selfplay`, MEASURED. Better than the review's fix: **r5a's T_S arms measure the self-play flip rate for free, before any build is spent** (r5a `feeds_r5b`), and the GATE-split value is cross-checked against it within 0.02. |
| 4 | MAJOR | D-4 given its consequence, adopted verbatim from `design_input_B.md:515` (see also #44). |
| 5 | MINOR | D-4's base quoted absolutely (0.2867 s62 / 0.3199 s65 nats -> absolute floor ~0.158-0.176 vs the 0.063 landmine) and the gate labelled PERMISSIVE, NOT TIGHT. |
| 6 | MAJOR | Selection/gate circularity broken: deterministic `sha256(lane:battle_id) % 20` split into SEL (5%, temperature only), GATE (5%, D-gates only), FIT (90%). Both pre-stated; F-L audits disjointness. |
| 7 | BLOCKER | +0.0746 (s63's single lane) replaced everywhere by the pooled **+0.06925**; ratio restated as **72%**, not "~2/3". The whole threshold argument in r5a Q2 is re-derived from the pooled number. |
| 8 | BLOCKER | Three-cell partition: T-PASS / T-UNRESOLVED (near-miss, honest sentence + named priced n=1500 both-arms re-run) / T-FAIL, with T-FAIL carrying TWO pre-written sentences selected by a numeric sub-rule (`mean <= 0` -> NULL closure verbatim; `mean > 0` -> SHORT closure with the "does not hold against its own greedy self" clause SUPPRESSED). |
| 9 | MAJOR | Review's fix (a) AND (b) both taken: `se_gov` (larger-of-three, `se_terms_r2` unmodified) enters the cell rule via `L = mean-2se`, `U = mean+2se`; AND n raised 500 -> 1000. Simulated OC published in-file: P(PASS) 0.965/0.837 at true +0.05, 0.007/0.020 at true 0.00; the irreversible cell fires on a true +0.05 with p 0.015-0.029 (was 0.74 at a true +0.04 under the r1 rule). |
| 10 | MAJOR | R4's F11 carried to Stage 1 as F-P (80% overlap of the shorter) plus a `waves:` block, plus a mechanical launch rule: **T_M starts when that lane's `ts_s6N.chunk04.json` exists**, so T_M's span sits inside T_S's. |
| 11 | MAJOR | F-C search-integrity gate added, VOIDING, on every T_S lane (r5a) and on the Stage-2a collection (r5b): `|leaves_mean-353|/353 <= 0.25` + chunk completeness, with the honest "no timeout counter, the watchdog RAISES" note. If it fires, the gate is not read and the family does not close. |
| 12 | MINOR | "MACHINERY: BUILT — the only change is seat2" withdrawn. r5a `BI-A0` states DRIVER CHANGES: NONE and evidences it against all four of the review's breakages (anchor_arms key, per-arm entries, explicit chunks, `--out-dir`); the two free wins the review named (the hard F8 assert at `:241`, the SF-13 chunk-0 sentinel at `:226-237`) are claimed as F-A8 and A-5. |
| 13 | MAJOR | BI-A1 builds `scripts/ch3_r5a_grade.py`, which writes `results/ch3_r5a/t_gate_readout.json` with `m_i`, mean, se terms, L, U, kpos and `cell`. r5b's D-1 asserts `cell == "T-PASS"` mechanically at the start of every Stage-2 job and every BI script. |
| 14 | MAJOR | Power table regenerated from the committed `r5_power_sim.py`, pinned in the grader `--selftest`; SIZE is now REPORTED, never bounded; the modelling assumptions are stated and "df=3 penalty applied" is withdrawn (**the credit line uses a fixed 2*se; no penalty is applied anywhere**). |
| 15 | MAJOR | Planning `s_C` = **0.0199** (worst of the three fresh re-measurements), all three quoted, the "inherits D26's spread" claim withdrawn as falsified. "EXPECTED OPERATIVE BAR: THE FLOOR" replaced by "~0.025-0.031, unpaired term the likely governor; it exceeds the floor whenever `s_T >= 0.01513`". |
| 16 | MAJOR | F-P disposition fully specified: the lane's `d_i` **REMAINS IN** the mean (never re-cut on a data-dependent subset); disclosure + struck era-immunity clause for that lane; R4's re-run policy carried verbatim. |
| 17 | MINOR | Expected `sd_d` named: **0.016**, basis R4's measured `sd(d_i)` over these same four lanes. `P(credit)` restated as 0.35 at that value, 0.23-0.39 across the tabled range. |
| 18 | NOTE | B1a simplified to `CREDIT AND F-T GREEN`; the never-binding `X1 > 0.71825` conjunct struck, with the reason stated. |
| 19 | MINOR | F-T reversal withdrawn: R4's F4 disposition adopted unchanged (DISCLOSURE + STOP, **never VOID**), including the deliberately asymmetric upper bound and its arm-swap rationale. |
| 20 | BLOCKER | Placebo rebuilt: **cross-BATTLE** pairing within the lane, partners restricted to identical legal-action count, target index-aligned -> **every target legal by construction, so the illegal-target case does not exist**. The "ZERO state-correct information" phrase is replaced by the honest "no state-correct information beyond the legal-action-count marginal", with the residual named. |
| 21 | MAJOR | Dose MEASURED, not asserted: `flip(PL)/flip(X1) in [0.80, 1.25]` on the GATE split at fit time, PL step count adjusted result-blind until in band, search transcribed. Unmatchable -> PL is DOSE-UNMATCHED and NON-BINDING, with the D25-P "survives UNTESTED" sentence. |
| 22 | MAJOR | Falsifier made se-aware with three named cells (PL-STRIKE / PL-UNCONFIRMED / PL-SURVIVE) and the residual false-strike rate pre-computed and quoted (0.003/0.006/0.015 vs the r1 rule's 5-12%). |
| 23 | MINOR | `letter_bearing_comparisons` restated as "1 primary + 1 conditional falsifier", and the falsifier's comparator (X0, paired by base lane) is stated for the first time. |
| 24 | MINOR | PL's 12,000 battles and its fit are in both the ledger and the build list (BI-5). |
| 25 | MAJOR | Named-successor forking path DELETED. The clause is now a pointer to `design_input_A.md` requiring its own pre-reg; no branch of r5b opens or closes it; the KILL collision and the override-precedence contradiction disappear with it. |
| 26 | MAJOR | `free_numbers` enumerates five: temperature (SEL-split rule), **KL-to-init resolved to ZERO / term dropped**, step count (SEL-CE minimum, patience 3, **no dose-based early stopping**, so dose is an outcome), LR 1e-3 and batch 512 (train_bc.py committed defaults). PL's step count is the one declared exception. |
| 27 | MAJOR | Pre-launch gate blocks added: r5a A-0..A-7, r5b B-0..B-13, both on R4's pattern (clean tree, suite green, grader selftest, sha preflight, encoder vars, FG-4/SF-13, determinism, username disjointness, fidelity tripwire, X0-first era pin). |
| 28 | MAJOR | F-P2 registered: the recorder runs through the same `_privileged is False` assert and chunk-0 battle2 sentinel; persisted obs width == 828; whitelist-only `info` keys; static grep transcript. Violation = PURITY INCIDENT. |
| 29 | MAJOR | `wall_hours_cap` renamed `battle_wall_hours_cap` and **what it counts is stated**: battle wall only, build and fit CPU tracked separately. r5a 1.8 h vs cap 3; r5b 3.1-4.5 h vs cap 6. Throughput priced from the review's measured rates with conservative margins (0.16 s greedy, 3.2 s search) and the collection called a FLOOR. |
| 30 | MINOR | BI-6 reuses `land()`, `check_partition()` **and** `se_terms_r2()` unmodified; the note that `grade()` itself is R2-shaped and cannot be called on this pre-reg is on the record. |
| 31 | MINOR | Q5 split into offline D-gates (Q6 in r5b) and run-time/read-time F-gates (Q9), with VOIDING vs non-voiding lists and "all co-occurring gates are reported". |
| 32 | MINOR | D-7 and D-8 get BI-4 (~1.0 h) which builds the srank99 probe pass and the LOO-pool `|v_LOO - v_own|` pass. |
| 33 | BLOCKER | "Both priors point +0.028" DELETED. `expectation_point_provenance` states it is design B's own actor-path prior, ONE prior; A produced no actor-path number; A's identical value is A's critic lever's point on a different read. |
| 34 | BLOCKER | RULE-1 restated: A recommends CLEAN, **B never raised engine purity** (zero hits, verified). All THREE of A's options quoted verbatim, including the deleted third; the consequence of each spelled out, with option 3 stated plainly as killing r5b and reviving A's search-read shape. A's counter-argument restored verbatim. "BLOCKS THE BUILD" restored. Present in both files. |
| 35 | MAJOR | RULE-1b added as its own open ruling with B's cost-asymmetry quote verbatim ("materially cheaper ... materially less honest ... DECIDE EXPLICITLY"). |
| 36 | MAJOR | T-GATE scope narrowed to the ACTOR family only, in both files, with the reason (A's teacher is a value backup; A registered its own KILL rule; no mirror-play action premise exists in A). |
| 37 | MAJOR | A's `e2_fit` key restored verbatim, plus the if-clause and the "DISCLOSED, IT COULD BE ZERO" sentence; the bridge is used as a CEILING device only. |
| 38 | MAJOR | PL target form fixed: same temperature applied to the PARTNER's `row_ev` vector (a shuffled DISTRIBUTION), so "same temperature" is true again and treatment and placebo share a target form. |
| 39 | MAJOR | C7 added quoting A's R-1 and FG-2 0.9092 and `matrix.py:14-17`; D-9 records the distilled actor's switch rate vs X0's; the disclosure travels on EVERY branch including B1a. |
| 40 | MAJOR | A's three gates registered as F-R (target provenance, 500 rows to 1e-9, placeholder rows absent), F-L (zero battle_id intersection), F-S (selection audit transcript). All VOIDING. |
| 41 | MINOR | Encoder env vars required at every job **including every offline one** (B-6 / A-4). |
| 42 | MAJOR | A's price written into `named_successor` including "IT DOES NOT FIT ONE EVENING"; build reconciled UP to 9.0 h (the synthesis's "~5 h" withdrawn); the "29-minute gate" framing replaced by ~1.8 h battles + ~1.5 h build. |
| 43 | MAJOR | B's rejection of the successor family quoted verbatim inside `named_successor`, beside A's escape and A's own +0.006-0.012 pricing; neither position adopted. |
| 44 | MINOR | `design_input_B.md:515` adopted verbatim as D-4's consequence, with the non-circularity note (re-resolution on SEL, re-check on GATE). |
| 45 | MINOR | Restored: M2 recording obligation on every branch (both files), "any VOIDing gate -> STATUS only, README untouched", B's U1 ("my named second-best is none"), U4 (anchor comparator cost + "Overrulable"), U6 ("a code change here is a new lever and a new pre-reg"). |
| 46 | NOTE | D-8 stays RECORDED (correct read of A); A's consequence sentence ("badly UNDER-REGISTERED ON THE UPSIDE") restored; the synthesis's "blocking" is noted on the record as wrong. |

**Closing structural remark (review 1):** a "WHERE A AND B DISAGREE" block
now heads BOTH files, listing all five divergences with both positions and
which one r2 adopted.

---

## Review 2 (conventions & executability)

| # | sev | disposition |
|---|---|---|
| BLOCKER-1 | X1 == X0 | `checkpoints:` gains `d62..d65` (and `p62..p65` for PL) with `path: runs/exit_s6N/checkpoint.pt` and `sha256: "<filled at fit time, before any battle>"`; `X1.lanes` points at them; D-6 keeps "identical except `lanes`" AND adds a per-lane `sha256(X0) != sha256(X1)` assert; `expected_pins: 13` + BI-7(a) parameterises the 5-pin assert. `source:` deleted (no driver reads it). |
| BLOCKER-2 | schema | `stage1_arms`/`stage2_arms` gone. r5a uses `anchor_arms:` with **eight explicit per-(arm,lane) entries**, real lane keys, explicit `chunks`, distinct output prefixes, `--out-dir`. r5b uses `arms:` for ch3_eval. "MACHINERY: BUILT — the only change is seat2" dropped. |
| MAJOR-3 | anchor specs | `anchor_arms: {CA, CB}` with `{kind, seat1, seat2, battles, chunks}`; `fp_anchor_arm: {FA {kind: greedy_seat, seat, battles, seat_username, fp_username}, fp{...}, crash_forfeit{...}}`; BI-7(b) builds the derived `configs/eval/ch3_r5b_fp_anchor.yaml` and the PREREG/ARM overrides for `ch3_r4_fp_runner.sh`. |
| MAJOR-4 | n=1000 | Flagged as a DISCLOSED DEVIATION from the 2026-08-23 ruling's 500, named as the R4 U2 approval that does **not** carry over, and put to the maintainer as U-B1 with a blocking bracket. |
| MAJOR-5 | README/STATUS | `readme_status_obligation` added to both files covering every cell, every VOID, KILL, the PL cells, PURITY INCIDENT — and **T-GATE FAIL explicitly**, whose closure sentence r5a argues is the whole value of Stage 1. |
| MAJOR-6 | unnamed cells | (1) D-4 consequence named; (2) anchor transfer defined numerically (TRANSFER-POSITIVE / NEGATIVE / AMBIGUOUS, MDEs pinned); (3) PL's survive side named (PL-SURVIVE) plus PL-UNCONFIRMED; (4) T-GATE partition is a total three-cell rule, grader-asserted on synthetic probes. |
| MAJOR-7 | PL dose | Measured; see review 1 #21. |
| MAJOR-8 | placeholder rows | **EXCLUDED** from the dataset, the fit and every D-gate; denominators stated as searched decisions only; the skip rate recorded beside every number. |
| MAJOR-9 | "terminal hours 0" | Rewritten as `execution_delegation`: the 2026-08-23 R4 ratification delegated eval execution to the agent; every wall number is a maintainer-terminal-grade number either way; **stated as a delegation, not a design property**. Handover blocks pre-written per CLAUDE.md. |
| MAJOR-10 | launch gates | R2-9 (committed + clean tree) and R2-6 (offline suite green at the launch sha) added as A-0/A-1 and B-2/B-3. |
| MINOR-11 | provenance | The 59.82% figures are attributed to **`results/ch3_r4`** by name, with the `results/ch3_r2` alternative (0.60508) noted. |
| MINOR-12 | line cite | `rl/search/matrix.py:254` (`:256` is `policy_argmax`). |
| MINOR-13 | crash-forfeit | `SESSION_LOGS.md:5509-5515` transcribed in full. |
| MINOR-14 | status | r5b `status:` names T-GATE **and** RULE-1; `blocked_on`, `rule_1`, `rule_1b` keys added. |
| MINOR-15 | P(credit) | See review 1 #17: sd_d named, number corrected to 0.35 at s_C=0.0199. |
| MINOR-16 | clone MDE | `anchor_mde.clone_1000_p: 0.86` named (0.028 at p=0.894). |
| MINOR-17 | D-5 object | "sha256 of the SERIALIZED CRITIC SUB-STATE_DICT **and** `torch.equal` over every critic tensor"; the file sha necessarily differs. |
| MINOR-18 | fp static gate | Folded into F-P2 with a required pre-launch grep transcript (the R2 FG-4 precedent). |
| MINOR-19 | payload | One line: base `cfg` verbatim + full agent state; D26 checkpoints are `normalize_obs: False` with no `normalizers`, so the frozen-normalizer trap does not fire — recorded so the distiller does not add one. |

Checklist items review 2 marked PASS (credit-line byte-equality, the five
pins, lessons 1/4/5, the band partition, the fresh-comparator argument, the
"already in stats" recorder claim, the T-M mirror control, pre-naming P(B5)
and B3-modal) are carried through unchanged except where a finding above
required a numeric correction.

---

## Programmatic verification of r2 (all re-run at write time)

- Both files parse under `yaml.safe_load`.
- `ch3_r5b.credit_line == scripts/ch3_r2_grade.CREDIT_LINE` -> **True**.
- r5a carries no `credit_line` key (it credits nothing); a
  `credit_line_not_applicable` key states why.
- Base checkpoint pins in both files are dict-equal to
  `configs/eval/ch3_r4_ensemble_critic.yaml:checkpoints` -> **True** (5/5).
- r5a's eight arms resolve against `ch3_r4_anchors._arm_spec` /`run_arm`:
  kinds valid, both seats are real checkpoint keys,
  `int(seat1.lstrip("s"))` succeeds, `chunks` explicit on every arm,
  `battles // chunks > 0`, no `evaluator` declared, eight distinct output
  prefixes, `len(checkpoints) == 5`. **Zero errors; zero driver changes.**
- r5b's arms expand to the twelve jobs `x0_s62..x0_s65`, `x1_d62..x1_d65`,
  `pl_p62..pl_p65` under `ch3_eval._jobs`; every lane key exists in
  `checkpoints`; `X0` and `X1` arm dicts are identical except `lanes`;
  every job named in `waves` exists.
- `[MAINTAINER RULING` bracket audit using the repo's own regex
  `(?<!")\[MAINTAINER RULING` (`ch3_r4_grade.py:63`): **r5a 0 active
  markers** (so it grades), **r5b 7 active markers** (RULE-1, RULE-1b,
  U-B1, U-B2 and their header/status restatements — all intentional, all
  blocking until ruled). Every quoted-literal mention is in the inert
  `"[MAINTAINER RULING"` form.
- `r5_power_sim.py`'s `s_C = 0.011177` column reproduces review 1's
  independent simulation to within 0.002 in all ten shared cells.

## Build-item list touching driver code (honestly priced)

Only one: **BI-7(a)**, ~part of a 1.0 h item — `ch3_r4_anchors._preflight`'s
hard `len(pins) == 5` becomes `len(pins) == prereg.get("expected_pins", 5)`,
because r5b carries 13 pins. R4's file is unaffected (it has 5). **r5a needs
no driver change at all.**
