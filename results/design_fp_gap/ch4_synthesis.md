# CH4 synthesis — the Foul-Play-gap design cycle, memos A + B merged

> **READING ORDER NOTE (post-review):** §7 (revision after adversarial review)
> supersedes §0/§2/§4/§5/§6 where they conflict. The ratifiable artifact is
> `configs/eval/ch4_r1_offsh_instrument.yaml` (DRAFT r2, committed), not the
> r1 draft referenced below.

Written at the synthesis stage of the 2-agent design cycle (brief:
`evidence_brief.md`; memos: `design_input_A.md` 1436 lines, mechanism-first;
`design_input_B.md` 1529 lines, distribution-first). Adversarial reviews and
maintainer rulings follow this document. Nothing launches.

## 0. The one-paragraph outcome

Both memos, from opposite framings, independently landed on the same
recommendation: **do not launch a training lever now — ratify ONE eval-only
diagnostic/instrument pre-registration first** (zero maintainer terminal
hours, zero training seeds, zero lane-days), with a pre-registered decision
rule that maps its readout onto exactly one pre-named lever or onto closure.
They disagree about what the diagnosis will find — A predicts a real style
hole (and pre-designed an exploiter fine-tune for it); B predicts "no
anomaly: the FP gap is raw strength" (and pre-named that branch so a null
cannot be re-narrated) — and the merged pre-reg is built precisely so that
disagreement is settled by measurement, not adjudication. The synthesis
therefore asks the maintainer to ratify **CH4 R1 — the off-SH instrument +
diagnosis** (merged draft: `ch4_r1_prereg_draft.yaml`), and to rule the
small bracket set in §5. Both memos' lever designs (A's EXPL exploiter
fine-tune, complete with power arithmetic; B's τ-DIV / POOL-SPAN specs) are
banked as next-cycle inputs, selected among by R1's registered rule.

## 1. Where the memos agree (and the synthesis adopts without change)

1. **Diagnosis before lever.** A: cost-ratio argument (3 agent-hours to
   choose among ≥4 mutually-exclusive 17-hour bets). B: the instrument for
   ANY off-SH claim does not exist (s_T off-SH never measured; every FP
   number is one lane, s65 — the weakest D26 lane vs SH — at n=250).
2. **FP@20 as the working instrument, GATED.** The budget ladder's flatness
   is a 4.9× cost lever (1.46 vs 7.18 s/battle, verified in fp20.json /
   fg.json). Gates: B's G6 (FP@20 vs FP@100 against a common third party,
   SH) and G7 (concurrency neutrality — a starved FP is a weaker opponent
   and nothing else would notice); A's tape-side style-equivalence check
   (switch rate / turns / faints across budgets) folded into the
   archaeology as the advisory D-2 read.
3. **Off-SH power is brutal and must be said before data.** Both memos'
   independent arithmetic: an off-SH credit needs a true effect ≈ +0.05;
   more battles and more lanes cannot fix a heterogeneity-governed bar.
   The s_T off-SH measurement (4 lanes × 3000 at FP@20) is the single
   number that decides whether an off-SH credit line is feasible at all.
4. **The vs-SH credit line stays; an off-SH letter is a maintainer bracket;
   anchors stay descriptive until the instrument exists.**
5. **Tape archaeology runs, pre-registered, screen-grade, no letters** —
   with A's parse discipline (forced-replacement suppression after
   |faint|; |cant|/recharge/partial-trap exclusion from OUR decision
   denominator — the naive `grep -c '|switch|'` is wrong ~2× and
   asymmetrically) and B's read list (which found FP's own printed
   avg_score and mixing distribution in the committed logs — an external
   value trace on every lost battle, readable for diagnosis, barred from
   weights).
6. **Purity:** no FP/SH state, action, tape or derived quantity may enter a
   loss, target, prior, value bootstrap or dataset. Actor ExIt stays
   KILLED; both memos wrote the same boundary sentence for exploiter-style
   lanes (ordinary PPO vs frozen own weights, no search-derived quantity —
   different family on target source, fitting mode, failure mechanism).
7. **Era honesty:** banked FP numbers (0.388/0.312, n=250, s65) are
   tripwires/era-pins, never comparators; a future credit-grade arm needs a
   fresh same-session off-SH comparator (R4's −0.0148 precedent).

## 2. The factual disputes, adjudicated against source (all verified by the
synthesis session, named files)

1. **A's correction of the brief's C7-fix proposal — CONFIRMED.**
   `rl/search/matrix.py`: the oppact head already supplies the SWITCH
   column *weight* (col_w from q); the uniform part is the bench *target*
   (`_opp_bench_target`, one draw per determinization), and the L6 head
   (N_L6=6, single SWITCH class) has no vocabulary to fix it. The brief's
   "swap the head into the column" is struck; A's reformulation (C7-FIX =
   critic-scored bench target, ~5% overhead) is banked as a deferred
   screen, ceiling-bounded by the fact that search costs us only 0.020 vs
   FP.
2. **B's D22 read-5 archaeology — CONFIRMED** (SESSION_LOGS 2026-08-11
   night): a dedicated 6M best-responder vs the frozen s36-50M final
   pooled **0.4765 ± 0.0112**, never parity; DESIGN §12's exploitability
   routing (PFSP/R-NaD) never fired. A's memo did not cite this. Two
   consequences: (i) A's EXPL prior must be revised down — its own
   BLOCKING gate G-EXP (exploiter ≥ 0.60 h2h vs frozen s65) sits ABOVE the
   only measured BR curve's plateau (~0.45–0.49), so on banked evidence
   **G-EXP more likely fails than passes**, and the 10.6 h exploiter
   producer would be spent discovering that; (ii) B's cheap X-PROBE (a
   ~3.6 h D26-era re-run of the same probe, machinery built at
   `rl/train.py::_frozen_checkpoint_pool`) is exactly A's G-EXP
   feasibility check run before the spend. The synthesis routes it that
   way (§4, R3-c and the EXPL precondition).
3. **B's Bradley–Terry inputs — SPOT-VERIFIED.** FP takes 0.824/0.812/
   0.872 off Rung-2/50M/BC-SH (results/foulplay_vs_sh/*.json, read this
   session); D26 finals 0.72967/0.71867/0.72167/0.70300 (results/d26/);
   hub 0.8307 at n=7200 pinned in the ratified ch3_r2_fp_h2h.yaml. The BT
   arithmetic itself is DERIVED and must be reproduced by the R1 grader
   with a --selftest before any residual is quoted anywhere (BI-1).
4. **The clone pin** in B's draft (runs/bc_fp_v2r_soft_180k_s0, sha
   5e490ade…) — sha verified byte-exact on disk this session.
5. **What is NOT adjudicated here:** whether the FP gap is a style hole
   (A) or raw strength (B). That is R1's job. A's Δ_sw style test and B's
   BT-residual test are BOTH in the merged rule, and they can disagree —
   the rule says what happens if they do (§4).

## 3. What the synthesis changed relative to each memo

- **From A, adopted:** the parse rules (BI-D1 verbatim), the D-1..D-8
  measurement suite (merged with B's 8 archaeology reads into one
  deduplicated list), the D-6 hax-audit falsifier, the D-8 self-play
  style baseline off the R5b collection, the EXPL lever design + its
  10-item bracket list (banked for the lever stage), the B4/B5-cell vs-SH
  veto form (reuses land(); B's level-threshold form recorded as the
  declined alternative), the FP@100 bridge read pattern.
- **From A, deferred/demoted:** Stage-L (EXPL) ratification — not because
  the design is weak but because (i) R1 may route elsewhere, and (ii) the
  D22 read-5 fact (which A missed) inverts the expected value of paying
  the exploiter producer before probing. A's own Q1 answer ("diagnosis
  first, the case is close to arithmetic") endorses exactly this.
- **From B, adopted:** the CH4 R1 arm structure (H1/H2/L62-65/C1/S1/E1 +
  S0 slice), G6/G7/G8, the BT grader + P2-rider re-grade as an
  every-branch honesty obligation, the R1–R4 branch partition, the
  projected-bar table, the pinned-literal hub discipline, zero-seed
  accounting.
- **From B, modified:** (i) the R3 lever map gains A's cells — the
  archaeology pattern now selects among **five** pre-named routes: P-SHARP
  → τ-DIV; P-COVER → POOL-SPAN; P-BR → X-PROBE (which, if it fires ≥0.60,
  also unlocks EXPL as the follow-on lever with A's design as its
  pre-reg input); P-MECH (A's CELL-M: first-status swing ≥0.35 or sweep
  share ≥0.50) → mechanic mini-cycle; P-EVAL (A's CELL-E: ≥0.45 of losses
  mon-ahead at turn 20) → critic-family un-shelve, maintainer ruling
  required. (ii) B's τ-DIV default on R4-AMBIGUOUS stands, but the default
  is now explicitly a *recommendation to design*, not to launch — every
  lever still gets its own pre-reg and ratification.
- **Dropped from both:** nothing silently. A's Stage-D-only shape (no new
  battles) is subsumed — the merged R1 runs battles because s_T cannot be
  read from tapes. A's U-2/U-6/U-10 lever brackets travel with the EXPL
  skeleton, not with R1.

## 4. The merged decision rule (full text in the draft yaml)

Evaluated in order, first match wins; thresholds fixed at registration:
- **R1-INSTRUMENT-FAILURE**: s_T(FP@20, 4 lanes) ≥ 0.05 → no affordable
  off-SH credit line exists; letter to the instrument; maintainer chooses
  more lanes / descriptive-forever / close.
- **R2-NO-ANOMALY**: s_T < 0.05 AND |pooled BT residual| ≤ 0.03 at the
  improved se AND C1 shows FP over-beating its own clone by ≥ +0.10 AND
  the archaeology fires no P-cell → the FP gap is raw strength; no
  robustness lever; README Chapter-3 closing sentence corrected; the
  maintainer's pre-committed R2 action (bracket MU-4) executes.
- **R3-REAL-HOLE**: pooled BT residual ≤ −0.03 for us with |resid| ≥
  2·se, OR the archaeology fires a P-cell decisively while BT is ambiguous
  (the A-vs-B disagreement case — REPORTED as such, never averaged): the
  fired pattern selects ONE route from the five-way map; that lever's
  pre-reg is drafted next session with the corresponding memo section as
  input; maintainer ratifies before anything runs.
- **R4-AMBIGUOUS**: default recommendation τ-DIV (largest deliverable
  dose, cheapest implementation, structural mismatch is a source fact) —
  as a design recommendation to the maintainer, not a launch.

## 5. The maintainer bracket set for THIS ratification (lever brackets
deferred to the lever stage; each priced in the memos)

- **MU-1 (the hinge — A's U-1, B's U-1):** is an off-SH credit line a
  thing this project can have? Recommended ruling: **conditionally yes,
  decided by R1's s_T** (the R1 branch implements it). Ruling "no,
  descriptive forever" is free and R1 still pays for itself (instrument +
  BT re-grade + first multi-lane FP measurement).
- **MU-2:** FP@20 licensed as the standing cheap anchor, conditional on
  G6 (and the archaeology's style read as advisory)? Recommended: yes,
  budget named in every number forever.
- **MU-3 (A's U-11):** CH4 R1 execution delegated to the agent once
  ratified (eval-only, no terminal time)? Recommended: yes, standing
  delegation pattern.
- **MU-4 (B's U-7):** pre-commit the R2-branch action BEFORE readout:
  (a) close the off-anchor thread/chapter, or (c) treat "exhausted vs
  SH+FP" as approaching demonstrated and revisit the ladder ruling.
  Recommended: choose (a) or (c) now, on the record.
- **MU-5 (A's U-8-boundary, B's U-8):** exploiter-family lanes (X-PROBE,
  EXPL) are IN-FAMILY (not actor ExIt) under the boundary sentence both
  memos wrote — "may not consume any search-derived quantity; if it wants
  one, it is actor ExIt under a new name and it is KILLED." Recommended:
  rule in-family now so R3-c is not blocked at readout.
- **MU-6 (B's U-6):** clone anchor stays in the battery, permanently
  annotated with its BT residual (the board's largest intransitivity)
  pending C1. Recommended: keep-with-annotation.
- **MU-7 (B's U-5):** the over-broad PFSP block in the R0-1b seam
  (source's own comment: belt-and-braces, purity-inert). Recommended:
  leave as-is now; amend in a standalone reasoned commit ONLY if a pool
  lever is selected.
- **MU-8 (B's U-2):** the P2-rider re-grade (z=−2.9 FP, z=−6.0 clone
  against BT-commensurate transfer) lands via the R1 grader on every
  branch; the README Chapter-3 sentence is corrected only on R2, flagged
  in STATUS meanwhile. Recommended as stated.

## 6. Cost of what is being ratified

CH4 R1 total: **0 maintainer terminal hours, 0 training seeds, 0
lane-days; ~6.5 h agent-side battles serial (~3 h if G7 licenses 3-wide) +
~11–13 h agent-side build/analysis across 3–4 evening blocks.** Build items
BI-1..BI-6 per the draft (the tape parser is tested against a hand-checked
fixture battle before touching 250 MB; the BT grader carries --selftest).
The lever stage, whichever route fires, is priced in the memos (EXPL:
~16.6 h terminal; τ-DIV/POOL-SPAN: ~10–11 h terminal; X-PROBE: ~3.6 h
solo) and is NOT being ratified today.

---

# §7. REVISION AFTER ADVERSARIAL REVIEW (supersedes §0/§2/§4/§5/§6 where they conflict)

Reviews: `draft_review_1.md` (technical — 4 BLOCKER, 18 MAJOR) and
`draft_review_2.md` (process — 5 BLOCKER, 20 MAJOR). Full disposition of every
finding: `revision_log.md`. The ratifiable artifact is now
**`configs/eval/ch4_r1_offsh_instrument.yaml` (DRAFT r2, committed)** — the r1
draft in this directory is retained as the reviewed artifact of record. Both
reviewers independently re-verified all four §2 factual adjudications; the
core shape (diagnosis-before-lever, eval-only, zero terminal) survived both
reviews intact. What follows corrects this document's own errors.

## 7.1 Corrections to this synthesis's claims

1. **§0 over-claimed convergence** (review 2 m10): memo A recommended a
   BATTLE-FREE tape stage and, in its U-11, recommended delegating rather
   than ratifying it; A priced fresh diagnostic battles as REJECTED-FOR-NOW.
   The merged rung's new battles are B's design; A's endorsement extends to
   diagnosis-first, not to the battle bill. Stated here as the disagreement
   it is.
2. **§2 item 2(i) is an INFERENCE, not a verified fact** (review 2
   MAJOR-20): "G-EXP more likely fails than passes" extrapolates a 6M probe
   against the 50M-era s36 to a 12M producer against D26-era s65. The
   demotion of A's Stage-L rests on "R1 may route elsewhere" (sufficient on
   its own) plus this FLAGGED prior — not on a fact.
3. **Two memo-level disagreements were resolved silently in r1** — the exact
   failure the 2-agent process exists to prevent (review 2 BLOCKER-5,
   MAJOR-6):
   - **τ-DIV**: memo A's R-H rejected opponent-temperature levers on
     mechanism ("a noised opponent is a WORSE opponent… training against
     incompetent style variation teaches the skill we demonstrably already
     have — we beat exactly that agent 0.894"). Memo B's defense: τ<1
     SHARPENS the opponent (competence up, not down) — R-H's mechanism
     argument is about softening/jitter, not sharpening. The r1 draft made
     τ-DIV the ambiguous-branch DEFAULT without surfacing this. r2 deletes
     the default entirely (the restructured partition has no lever-
     recommending ambiguous cell) and attaches the dispute to the P-SHARP
     route as **bracket MU-11**, ruled at the lever pre-reg, before launch.
   - **Chapter-3 README correction on R2**: memo B obligates it; memo A
     obligates the opposite ("Chapter 3's closed section is untouched").
     It is also an edit to a maintainer-ratified, pushed narrative. r2 makes
     it **bracket MU-10**; A's position is the recorded declined-alternative
     if the maintainer rules for B's.
4. **A's G-FP20 gate was silently demoted in r1** (review 1 MA-17): restored
   as G6b with A's three numeric thresholds; it governs quotability of the
   FP@100-corpus archaeology onto FP@20 claims, and MU-2's standing-anchor
   licence now requires G6-PASS **and** G6b-PASS.
5. **The r1 cost line was wrong** (review 1 MA-15): battles are ~10.3 h
   serial (~3.5–4 h at k=3 if the rebuilt G7 passes), total ~21–24 h
   agent-side across **5–6** evening blocks, not 3–4. Still 0 maintainer
   terminal hours, 0 seeds, 0 lane-days — with the precedent for agent-side
   eval waves now cited (MU-3).

## 7.2 The restructured decision rule (r2, summary — full text in the yaml)

No-anomaly is now the DEFAULT cell; every anomaly cell is positively defined;
the rho orientation is fixed (positive = FP over-performs = anomaly). Branches:
**R1** instrument infeasible (s_T lower-CI ≥ 0.05) → maintainer menu, no arm;
**R1b** instrument unresolved (CI straddles) → maintainer menu, no arm;
**R3** real hole (rho_pooled ≥ +0.03 at 2·se, or an ordered P-cell fires at
threshold + 2 se) → route map {P-SHARP→τ-DIV design (carries MU-11),
P-MECH→mechanic mini-cycle, P-COVER→POOL-SPAN design, P-EVAL→critic un-shelve
(ruling required)}, with **R3-NULL** (BT fires, no cell) → mechanism-scoped new
cycle; **R2** no anomaly (the complement) → no robustness lever, MU-4
pre-commitment executes, C1 travels as the explanation (or open observation)
of the clone intransitivity. P-BR is deleted from the auto-map; the exploiter
question is bracket MU-11b. VOID-D restored for the archaeology.

## 7.3 The bracket set, revised (MU-1..MU-11b; each priced)

- **MU-1** off-SH credit line: conditionally yes, decided by R1's s_T CI —
  **its price depends on MU-9.**
- **MU-2** FP@20 as standing anchor: requires G6-PASS AND G6b-PASS, **and a
  CLAUDE.md anchor-battery edit** (budget 100→20, n; the FP@100/FP@500
  readiness-gradient rungs unchanged — FP@20 is an instrument, not a rung).
- **MU-3** delegated agent-side execution of the ~10 h eval wave: precedent
  cited (FP anchors, budget ladder, R5b pins all ran agent-side since
  2026-08-23); the CLAUDE.md >5-min rule's measured 10× penalty is about
  training. Maintainer confirms the precedent covers this wave.
- **MU-4** pre-commit the R2-branch action BEFORE readout: (a) close the
  off-anchor thread/chapter; **(b) return to a strength lever** (restored —
  B's original option; not recommended because scale is dead vs SH and the
  DESIGN §12 queue is spent, but it is the maintainer's to decline); (c)
  treat "exhausted vs SH+FP" as approaching demonstrated and revisit the
  ladder ruling.
- **MU-5** exploiter-family boundary (in-family vs actor-ExIt) — unchanged.
- **MU-6** clone anchor: keep, with its BT residual annotated on the README
  anchor row (scoped there; no CLAUDE.md edit unless desired).
- **MU-7** PFSP seam amendment — MOVED to the deferred lever-stage set (no
  action this cycle).
- **MU-8** P2-rider re-grade: the grader computes it on every branch but
  refuses to emit the superseding sentence until this is ruled.
- **MU-9** (restored — A's U-6): does a future off-SH bar use the two-term
  or A's three-term larger-of? A's arithmetic: the third (unpaired) term
  governed 67–84% of R4's simulated cells; the difference is power 0.70 vs
  0.95 at μ=+0.05.
- **MU-10** (new): on R2, may the agent edit the ratified Chapter-3 closing
  sentence, or does Chapter 4 get a superseding note? (A: untouched; B:
  correct it. Flag in STATUS meanwhile either way.)
- **MU-11** (new): the τ-DIV dispute (A's R-H rejection vs B's
  sharpening defense) — ruled at the lever pre-reg iff P-SHARP fires.
- **MU-11b** (new): the exploiter question — X-PROBE (a ~3.6 h D26-era
  re-run of the D22 probe, machinery built) may be ordered by the maintainer
  at any time to settle exploiter feasibility for 3.6 h instead of A's
  10.6 h producer; on banked evidence (D22 plateau ~0.45–0.49) it is
  expected to read low, which is exactly why it is cheap information. A's
  EXPL design (complete, priced, `design_input_A.md` §2/§7B) is the banked
  input if it ever unlocks.
