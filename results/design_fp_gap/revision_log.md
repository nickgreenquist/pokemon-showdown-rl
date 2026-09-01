# Revision log — draft r1 -> r2 (disposition of every review finding)

r2 artifact: `configs/eval/ch4_r1_offsh_instrument.yaml` (COMMITTED — review 2
BLOCKER-1). r1 draft retained at `results/design_fp_gap/ch4_r1_prereg_draft.yaml`
as the reviewed artifact of record. Synthesis revised in place (§0/§2b/§3/§5).

## Review 1 (technical) — 4 BL, 18 MA, 9 MI, 4 N

- BL-1 rho orientation inverted — FIXED: rho = FP excess take, positive =
  anomaly; r3_rho +0.03 one-sided; selftest asserts banked D26 lands NEGATIVE.
- BL-2 C1 unbuildable (808-dim clone) — FIXED: BI-2b adopts the
  eval_checkpoint PrefixSliceActor shim; per-arm encoder env; realized dims
  stamped; clone pin carries the note.
- BL-3 C1 comparator unreachable on probability scale — FIXED: logit-scale
  read, comparator = pooled-orientation +0.60 logits, threshold +0.30 logits,
  ceiling named; det-seat recorded-only.
- BL-4 parse wrong on corpus (lead switches; partiallytrapped nonexistent) —
  FIXED: rules (ii) and (vii); fixture must exercise lead/faint/cant; absent
  mechanics reported ABSENT.
- MA-1 |cant| exclusion biased; FP Choice: ground truth unused — FIXED: rule
  (iii)/(iv): slp/frz/par/flinch KEPT, recharge + request-proven-choiceless
  excluded; sw_FP from Choice: lines; heuristic cross-validated (<=0.02 or
  parse VOID); asymmetric information quality disclosed.
- MA-2 E-b definitional artifact; SP rows ambiguous — FIXED: SP baseline
  recomputed (force-switch rows excluded, policy_argmax, filter pinned, BI-8,
  committed before grading); disclosed loose reference.
- MA-3 G7 passes by default — FIXED: timing-based, one-sided, <=5% relative
  slowdown, |t:| timestamps + Sampling lines; win rate recorded-only; k and
  duplicate arm (L65) pre-named.
- MA-4 G6 band incommensurate — FIXED: tiered PASS 0.02 / MARGINAL 0.05 /
  FAIL, propagation arithmetic and power stated in header.
- MA-5 s_T hard threshold at 3 df — FIXED: graded on 95% CI; new branch R1b
  (unresolved); multipliers stated.
- MA-6 pooled rho se (hub common-mode) — FIXED: decomposition formula in
  header + selftest.
- MA-7 no SH-side era pin — FIXED: V-arms (4x3000 vs SH in-session) feed rho;
  banked finals demoted to tripwire.
- MA-8 partition biased toward levers — FIXED: restructured; R2 no-anomaly is
  the DEFAULT/complement; R4 deleted.
- MA-9 P-COVER/P-BR undefined — FIXED: P-COVER numeric (top-tercile loss
  share >= 0.45 + 2-se rule); P-BR REMOVED from auto-map (-> bracket MU-11b).
- MA-10 FP budget never asserted — FIXED: G8 asserts Sampling lines vs
  declared budget; realized budget in JSON; budget read from pre-reg; key
  renamed search_time_ms (MI-8).
- MA-11 C1 form mismatch — FIXED: clone runs SAMPLING (form-matched); C1b det
  recorded-only.
- MA-12 clone_vs_sh unpinned — FIXED: pinned 0.5503 (falsifier header
  5x3000), 0.5777 sensitivity.
- MA-13 S0 no data path — FIXED: BI-7 per-battle records; slice defined on
  them; crash-forfeit interaction stated.
- MA-14 S1-S0 confound + wrong constant — FIXED: same wave same k (wave_plan);
  0.041 at p~0.31.
- MA-15 cost ledger wrong ~45% — FIXED: ~10.3 h serial battles / ~3.5-4 h at
  k=3; total 21-24 h agent-side, 5-6 evening blocks (synthesis corrected too).
- MA-16 hax falsifier misfires on exposure — FIXED: normalized rates, 2-se
  band, action (fixture re-run -> VOID-D if unresolved).
- MA-17 G-FP20 silently demoted — FIXED: restored as G6b with A's three
  thresholds; governs quotability + MU-2; demotion-vs-blocking rationale in
  header; synthesis records the r1 error.
- MA-18 BI mis-scoping — FIXED: BI-2a reuses foulplay_vs_sh.py (hub
  commensurability); BI-3 pinned seat_rng_seed + disclosure; BI-6 arm-scoped
  markers/logs.
- MI-1 L65 band — FIXED 0.061, grader re-derives. MI-2 family-wise break rate
  — stated + single-pin re-run rule. MI-3 budget semantics — in fp.quote_as.
  MI-4 two hubs pinned. MI-5 lane-consistent z (~-2.8) + pooling stated.
  MI-6 G8 wording fixed. MI-7 G3-vs-n_eff note. MI-8 key renamed.
  MI-9 handicapped-patch hub labeled conservative-for-us.
- N-2 delta_sw recoverability + underived threshold — DISCLOSED in R-6a;
  maintainer may re-derive at ratification. N-4 visit-fraction entropy —
  ADOPTED as recorded supporting read. N-1/N-3 no action needed (banked).

## Review 2 (process) — 5 BL, 20 MA, 12 m, 5 n

- BLOCKER-1 gitignored pre-reg — FIXED: r2 lives at
  configs/eval/ch4_r1_offsh_instrument.yaml, committed; G0 added (blob sha
  stamped).
- BLOCKER-2 P-cells unordered — FIXED: p_cell_order total order, first match
  wins, fired cells recorded.
- BLOCKER-3 R3 with no route — FIXED: R3-NULL cell (mechanism-scoped new
  cycle, not a lever).
- BLOCKER-4 thresholds missing / "decisively" — FIXED: numeric P-COVER; P-BR
  removed; "decisively" replaced by threshold + 2-se exclusion rule.
- BLOCKER-5 tau-DIV default is A's rejected R-H, silently — FIXED: R4 default
  DELETED (partition restructure); the A-vs-B dispute is bracket MU-11,
  attached to the P-SHARP route and adjudicated at the lever pre-reg;
  synthesis §2b records the disagreement verbatim.
- MAJOR-1 pooled-rho aggregator — FIXED (rho block). MAJOR-2 P-cell arms —
  FIXED (FG reference, FS recorded-only, reason stated). MAJOR-3 new tapes —
  FIXED (OUT, archived). MAJOR-4 bar formula + third term — FIXED (formula
  verbatim; MU-9 restored as a bracket; MU-1 priced against it). MAJOR-5 MU-2
  CLAUDE.md edit — FIXED (priced in synthesis §5). MAJOR-6 Ch-3 correction —
  FIXED: bracket MU-10; A's "untouched" obligation recorded as the declined
  alternative; R1-branch note added. MAJOR-7 MU-4 option (b) — RESTORED with
  the reason it is not recommended. MAJOR-8 G-FP20 — see MA-17. MAJOR-9 0.60
  transplant — FIXED (P-BR removed; exploiter question = MU-11b with honest
  framing: X-PROBE 3.6 h settles feasibility before A's 10.6 h producer).
  MAJOR-10 wave_plan + same-k rule + G7 arm named — FIXED. MAJOR-11 G7
  one-sided + gate power stated — FIXED. MAJOR-12 s_T lane contingency +
  VOID-D — FIXED. MAJOR-13 G0 — FIXED. MAJOR-14 mirroring — FIXED (obligation
  in Q8; mirror executed this session). MAJOR-15 licensed sentences inline —
  FIXED (Q6b). MAJOR-16 protocol clause — FIXED (Q1b). MAJOR-17 terminal-rule
  precedent — FIXED (Q8 + MU-3). MAJOR-18 p2_regrade PENDING_MU-8 — FIXED.
  MAJOR-19 null->lever gap — FIXED (C1 non-governing; R2 default). MAJOR-20
  §2 fact-vs-inference — FIXED (synthesis §2b; EXPL demotion restated as
  "R1 may route elsewhere" + flagged prior).
- m1 ddof=1 — FIXED. m2 era-pin sidedness — FIXED. m3 falsifier teeth —
  FIXED. m4 MU-4/Q7 tension — FIXED (Q7 exception clause). m5 MU-7 moved to
  deferred set; MU-6 annotation scoped to README anchor row. m6 STATUS cap +
  untouched headline — FIXED (Q6b). m7 pinned-literal discipline — FIXED.
  m8 loose reference — FIXED. m9 cadence 5-6 blocks — FIXED. m10 §0 wording —
  FIXED (convergence claim scoped). m11 avg_score seam sentence — FIXED (Q1).
  m12 fp_vs_rl.json 0.876 — FIXED (identified at build or excluded with
  reason, stamped).
- n1 A's U-7 recorded as resolved. n2 P-EVAL-leads-to-option-B sentence in
  synthesis §5. n3/n4/n5 no action needed.

## Declined / deferred (with reasons)

- Review 1 N-4's suggestion to make visit-fraction entropy P-SHARP's PRIMARY:
  adopted as supporting only — the entropy statistic has no banked reference
  and its threshold would be a fresh free number; delta_sw keeps primacy with
  its parse cross-validated against FP's ground truth.
- Review 2 m5's suggestion to fully re-price MU-6's annotation: scoped to the
  README anchor row instead (no CLAUDE.md edit unless the maintainer wants
  one).
