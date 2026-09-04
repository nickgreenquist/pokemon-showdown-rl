# SYNTHESIS — LADDER R4 (runner, 2026-09-04)

Inputs: BRIEF.md, mem_A.md (measurement validity), mem_B.md (operations).
Adjudications below record the losing argument. Everything else in the two
memos was complementary and is adopted as written into the draft.

## ADJ-1 — Q6 re-score of the median lane: NO RE-SCORE (A adopted)
A's four grounds adopted (median-not-argmax at k=3; selection statistic IS
the published n=3000 protocol number; it is an anchor, not the ladder read;
the per-lane median was pre-registered recorded-and-never-governing before
launch), PLUS A's residual sentence (median-conditioning shrinks toward the
fleet centre, sign unknown, under the 0.0200 re-draw spread) goes in the
draft verbatim. B's cost datum (1.29 h) recorded as irrelevant either way.
LOSING ARGUMENT (hypothetical maintainer-override path): a fresh score is
never worse evidence; answered by A — two legitimate n=3000 numbers with no
aggregator on a 0.0200-spread instrument is a validity COST unless the use
is pre-committed; if overridden, branch R-a (replace) is pre-committed.

## ADJ-2 — Wall clock: B adopted, A's mechanism corrected
B measured R3's median 218.0 s/battle (211.5 excl. gaps) vs R1 greedy 229.5
from the JSONLs: the search seat was NOT slower per battle; our compute is
<1% of wall. A's §6.5 argued "greedy is cheaper per battle → shorter run";
LOSING HALF recorded: cheaper only through turns (~1–2 h over 200), and the
intercept (~114.5 s queue/matchmaking) plus the human's clock dominate.
Plan 12–16 h, budget 17 h, hard ceiling ~22 h at max_battles_total 300.
A's conclusion (do not change n for cost reasons) SURVIVES the correction.

## ADJ-3 — Stopping rule: carried unchanged (both memos agree)
rd <= 40 AND n >= 200, max_battles_total 300, G-BLIND four stops verbatim.
tests/test_ladder.py:574-576 hardcodes 40/200 — changing them edits a test
that pins a cross-run invariant (B), and n=200 is the commensurability and
etiquette argument (A). No fifth stop drafted; M3 offers one.

## ADJ-4 — Courtesy note: B's text + A's result-blind branches, merged
B's draft note (discloses both prior accounts, footprint, cap, stop offer;
notice not request) + B's channel recommendation (Help room → PM staff,
confirm on site first) + B's non-reply-is-not-a-block clause + A's three
pre-registered branches (no reply → proceed + disclose; objection → do not
launch; conditions → maintainer ruling) + A's blind-breach licence for
answering staff contact mid-run. Archived tracked at
readouts/LADDER_R4_COURTESY_NOTE.md, sent >= 24 h before launch.

## ADJ-5 — decision-ms band: B's calibrate-from-smoke over A's guess
Provisional band [1, 20) ms with >= 30 ms = wrong-object failure (the LG4
tell INVERTED — both memos); the band is FINALIZED from the LG-6 local
smoke's stamped mean_decision_ms as a licensed pre-launch edit. A's [1,15]
recorded as the losing guess: R1's 6.74 ms was a 4-lane ensemble, and B is
right that a measured band beats an inferred one when the smoke is free.

## ADJ-6 — 106-102 diagnosis: A's propagation rule adopted, B's ledger too
A: the R3 readout was right; the failure was propagation (STATUS carried
the stale pair 4 days). Draft gets A's (vii) machine-checked profile-vs-
JSONL reconciliation AND (viii) propagation rule with a grep test, plus
B's realized-cost/outage ledger as obligation (ix). No disagreement — the
brief's framing was wrong, both memos said so differently.

## Adopted without contest (source in parens)
Ten-confound list incl. determinism/memorisation, rematch reads vs R1 (A);
(proxy, ladder) mapping barred by name (A); s112-argmax-on-anchors pairing
rule + not-the-best sentence (A); [1300,1400) two-branch admission-cutoff
rule (A); three-run figure bar, CONFOUNDED table heading (A); headline
template with selection rule inside it (A); one-run rule + step-2 discharge
question (A); arms block verified minimal + exact-six-key provenance assert
(B); VOID (c) restated for the encoder set-pool copy (B); .env launch gate
(B); watchdog unchanged + 2xSTALL escalation line BI-R4-3 (B); backup
RUNS line BI-R4-1 + mid-run backup (B); readout two-prior flags BI-R4-2
(B); draft-path test trap BI-R4-4 (B); account nickgen1rbrlbot3, linked
stem, maintainer registers (both); ownership split — maintainer sends/
registers/.env/launches (LG-9 ~90 s human), agent babysits/backs up/reads
out/commits (B); no post-ladder anchor buying — battery complete (B).

## Collected maintainer markers (draft carries these; ratification clears)
M1 Q6: NO re-score (recommended) / override → R-a replaces.
M2 [1300,1400) two-branch admission-cutoff rule (recommended as drafted).
M3 Fifth licensed stop (declared wall-clock box): NONE (recommended) / time.
M4 A VOID/INCOMPLETE run discharges JOURNEY step 2: YES (recommended).
M5 Courtesy note text/channel/send-time + non-reply clause (B's draft).
M6 Account nickgen1rbrlbot3; maintainer registers; .env update.
M7 Schedule: ONE continuous run to n=200; plan 12–16 h, budget 17, ceiling 22.
M8 Ownership: maintainer launches (LG-9), agent owns babysit→readout→docs.
M9 BI-R4-1..4: landed or waived in writing with named fallbacks.
