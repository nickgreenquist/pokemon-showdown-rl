# Handoff — 2026-08-24 (afternoon)

Written per the maintainer's standing instruction this morning ("handoff
when context gets too full") at a clean decision boundary; box idle,
server healthy on :8000, tree clean and committable through the T-GATE
readout commit, nothing mid-flight, all results mirrored to
`../pokemon-showdown-rl-d25-backup-20260815/`. NOT yet pushed since
`e3bca48` — push authorization was granted for the morning batch only;
ask before pushing the rest. Read STATUS.md — headline: **T-GATE T-PASS,
decisive (mirror margin +0.1515, 3× the bar, 4/4 lanes) — the offline
actor expert-iteration family is ALIVE and ch3_r5b is ELIGIBLE, blocked
ONLY on maintainer rulings.** Then the 2026-08-24 SESSION_LOGS entries
(eight of them, one day: R4 B3 readout → oracle diag (BARRED) → speed
ruling → critic-thread design cycle → srank-diagnosis correction → R5
cycle complete → r5a registered+run → T-PASS).

DECISIONS THE MAINTAINER OWES (all in
results/design_critic/ch3_r5b_exit_draft.yaml as 7 active
`[MAINTAINER RULING PENDING` brackets; the grader refuses until ruled):
(a) **RULE-1, the big one** — purity of poke-engine-derived targets
    entering the WEIGHTS (R2 licensed inference-time only). THREE
    options, consequences spelled out in the file: CLEAN / NOT-CLEAN
    (kills r5b entirely) / CLEAN-for-search-deployed-only (kills r5b's
    greedy read, revives design A's critic-distillation successor,
    design_input_A.md, complete and priced).
(b) RULE-1b — confirm the SH-state prohibition reading (recording
    search play vs SH for training = seam break + train-on-test).
(c) U-B1 clone anchor n=1000 (R4's U2 precedent, needs re-approval
    here); U-B2 the 4×3000 deviation disclosure.
On CLEAN + ratification the next session runs: ~9 h result-blind build
(BI list in the draft: recorder BI-2, distiller BI-3, offline gate
harness BI-4, grader BI-5, runner BI-6, plus BI-7(a) parameterising
_preflight's pin-count assert), then ~2.7 h collection + ~1 h fit +
offline temperature resolution (grid transcribed pre-launch) + 16-min
greedy read X0/X1. Zero training seeds. Expectation band [+0.010,
+0.045] point +0.028, P(credit) ~0.35, B3 modal below the point —
pre-stated, do not re-narrate.

FRESH LANDMINES/FACTS from this block (all logged, pointers): the r5
draft revision was forced by reviews — see r2_changelog.md before
touching the drafts; the synthesis step itself introduced 2 of 6
blockers (keep the two-review discipline); critic srank "7-11" is
STALE (D26 measures 49/51/35/52 — scope quotes by era); T-GATE numbers
are MIRROR-regime, never vs-SH strength; the anchors driver
(ch3_r4_anchors.py) runs mirror matches unmodified (no seat1!=seat2
assert — verified); ts_flip_rate came back null in the r5a readout
(finals key-name mismatch, cosmetic, grader unaffected — fix
opportunistically).

Also open, lower priority: R4 follow-ups (all-4 / single-foreign-critic
/ U8 k=4→8) legal but unproposed; U9 T2b contamination flag; E2(σ=0.2)
upgrade maintainer-buyable; oracle-diag numbers stay BARRED.

Fold this back to the empty stub on pickup.
