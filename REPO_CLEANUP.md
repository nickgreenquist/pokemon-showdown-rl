# REPO_CLEANUP — sweep findings, 2026-08-28

**This is not a set plan — these are ideas. A fresh session that is tasked
with cleaning the repo should do its own audit.** Line numbers are as of
commit `d43293a` and will drift; re-verify every quote before acting (this
repo's standing rule for any external claim, and these came from two
subagent sweeps — the top ~8 were independently re-verified in the main
session, the rest carry the sweeping agent's line references).

**SEQUENCING CONSTRAINT (matters only while the RS81/RS82 wave runs, i.e.
2026-08-28 until ~18:25 EDT):** items marked ⏸ edit `ch5_r1_offsh.yaml` or
`ch5_r1_wave.sh`. The wave's arms each stamp `prereg_sha256`; editing the
config between arms hands RS82 a different sha than RS81 and voids the
comparison the wave exists to buy. `ch5_r1_wave.sh` is bash currently
executing — editing it can corrupt the running interpreter's read. After
the wave completes both are safe.

Overlap note: `CLEANUP.md` (the older list) is itself flagged below (A1 is
stale-executed; B5 and B7 remain valid standing items). This file does not
replace it; a cleaning session should reconcile the two.

## A. Misleading — wrong today, in load-bearing places (ranked)

1. ⏸ **Live pre-reg licenses a publishable sentence that is wrong three
   ways, test-locked.** `configs/eval/ch5_r1_offsh.yaml:1224`
   ("...only ladder rating (PS Elo 1311, n=200, never listed, no GXE)"):
   1311→1292; GXE 59.6% / Glicko 1573±27 exist (profile, corrected
   2026-08-26); R3 means it is not the only rating. Same "1311" at `:894`
   and `:1238`. `tests/test_ch5_prereg.py:284` ASSERTS "1311" is present
   (headline-protection test now protects a retraction). Fix all three
   lines with dated CORRECTED notes + the test tuple, ONE commit, after
   the wave.
2. **`LADDER_R1_READOUT.md:48` headline table: "PS Elo, final | 1311"**,
   contradicting the correction block at `:15-33` of the same file. Also
   `:3-7` "reproducible by re-running that script" is false — the
   generator has been fixed 3x since (profile read 055cf96, BI-4 0302051,
   c226621). Regenerate from the current script (AFTER item A3's fix);
   preserve the hand-written superseded-text block. Regeneration also
   gives the corrected R1 band cells their only committed provenance
   (today they exist only in README prose + SESSION_LOGS 14:40Z) and
   fixes the stale "n = 28-47" caveat range.
3. **`scripts/ladder_readout.py:259-262` emits R1-shaped rematch prose
   unconditionally.** R3's committed readout asserts "a lower rematch win
   rate is predicted" directly under a table showing rematch 0.548 >
   first 0.517. Make the sentence sign-conditional, regenerate BOTH
   readouts. Same defect class as the label-gated-disclosure bug BI-4
   caught ("a disclosure that attaches itself to the wrong run is worse
   than no disclosure").
4. **`scripts/eval_checkpoint.py` — the locked-protocol instrument
   defaults to 3% of the locked protocol.** Usage line `:3` says
   `best_checkpoint.pt --episodes 100`; the locked protocol is final
   checkpoint, 3000 battles. Bare output is indistinguishable from a real
   number at se~0.05. Make `--episodes` required; fix the docstring.
5. **`prior_work/README.md:174` — "implied ~1232 ... we score 0.340"** —
   superseded by BI-4 (1214 / 0.319), inside the block CLAUDE.md points
   every session at, and 1232 now collides with R3's actual final Elo.
6. **`RESULTS.md:207-212, 735` — the RETIRED ~40% GXE conversion stated
   live, twice**; `:232-234` "nobody has measured gen1randombattle on a
   human ladder at all" — measured twice, n=200 each.
7. **`CHAPTER5.md:3-5` "Nothing launched, nothing trained"** (R1 closed,
   R3 laddered); `:319-321` restates the retracted "stopping rule never
   fired because we were never listed" (the D19 failure mode, live);
   `:62-64` three `unmeasured`/`—` cells that C0 (0.3893), the A-arms
   (0.3960/0.3430/0.2730) and R3 (GXE 60.3%) filled; `:43-49` "ZERO
   complete pairs" — (0.3893 off FP@20, GXE 59.6%) is a complete pair.
8. ⏸(batching only — file is not currently running) **`scripts/
   ch5_watchdog.sh:22` has no `rs*` case** — RS arms fall to the 40.4/min
   greedy reference; a healthy search arm (realized 20.6/min) reads ~51%
   and false-alerts. Add `rs*) echo 20.6 ;;`. r9 patched the wave runner
   but not this file.

## B. Stale — superseded without a label where a reader lands

9. **R1-defaulting readout tooling should fail, not default.**
   `ladder_readout.py` / `ladder_classify.py` default to R1's paths AND
   `--name nickgen1rbrlbot`; forgetting only `--name` on an R3 readout
   fetches bot1's profile into an R3-labelled file, and `load()` then
   nulls `_true_rating` on every row while the exhaustiveness assert
   still passes. `ladder_move_audit.py:30,59` hardcodes R1 with no
   argparse. `ladder_supervise.sh:61` hardcodes ladder_r3.yaml while
   taking the arm as an argument (an R4 through it runs under R3's
   rules). Make the inputs required everywhere. (`scripts/ladder.py` is
   already correct — all required.)
10. **`RESULTS.md` has zero ladder content** while README designates it
    "the account ... every disclosure". Wants a §16 ladder chapter (R1 +
    R3 + the D5 non-comparability ruling + band tables) in the existing
    addendum pattern; the closing "open maintainer call" at `:750-751`
    predates three chapters. Also §1/§8 quote 0.6185 as the headline with
    only a weak as-written-at-the-time label (`:21, :83, :368`), and
    `:402` points at a prior_work caveat since rewritten twice.
11. **`CLAUDE.md:39`** — CHAPTER5 described as current with R3 in the
    future; **`:53`** — R3 absent from the ladder landmine and
    `ladder_r1.yaml` named as the template (ladder_r3.yaml is the one
    whose stopping rule can fire); **`:28`** — "520 passed, 17 skipped"
    stale by two test files: delete the count, keep the instruction.
12. **`DESIGN.md:1-27` enumerated supersession banner omits the ladder
    chapter**, leaving `:85-91` (40% conversion, "nobody has measured",
    D7(a) deferral) reading as live — an enumerated list that omits the
    biggest event since is worse than the generic warning. Same class:
    **`DESIGN2.md:3-6` "NOT RATIFIED. Nothing launched"** while D28/D29r/
    D29r2 sit in RESULTS §10-12 (cited by ppo.py:522, zeroinfo.py:1 and
    three configs; already CLEANUP.md B5). One banner bullet each.
13. **`CLEANUP.md:20-36` item A1 ("highest-value doc item outstanding")
    was executed 2026-08-25** — move to its §C done-list; its successor
    is item 10 above, filed fresh.
14. **SESSION_LOGS 2026-08-28 r9 entry is stamped ~55 min late** (says
    18:20Z; the ratifying commit/launch were 17:25Z/17:32Z). One-line
    correction in the next entry. (Disclosed by the session that wrote it.)

## C. Trivial / deadwood

15. **`scripts/score_ladder.py`** — the documented Connect-4-era false
    friend has NO in-file warning and runs plausibly on a Showdown dir
    before crashing (`--opponents heuristic` vs Showdown's `heuristics`).
    Backs no banked number; delete outright (or warning header).
16. **`assets/showdown_milestone3.png` (429 KB, "~0.4 vs SH / 611-dim") +
    `scripts/make_showdown_figure.py`** — referenced by nothing; the
    artifact most likely to be wrongly surfaced into the deferred README
    rewrite. Delete both.
17. **Orphans with zero references:** `ch3_r1_spike.py`,
    `d22_trajectories.py`, `make_bc_dataset.py`, `p3_team_luck.py`,
    `probe_type_multiplier.py` (superseded by diag_encoder_live.py) —
    safe deletes. `record.py` stays CLEANUP.md B7's candidate (sole
    reason imageio is pinned). Keep the three CH3 wave-runners
    (provenance) but add them to scripts/README.md.
18. **`scripts/README.md` is 37 of 96 scripts short** — the gaps are the
    newest ladder-ops + CH5 tooling, exactly what a sweeper needs
    provenance for. **`tests/test_showdown_env.py:840`** — the known
    flake is undocumented in-file (one comment). **`showdown_
    throughput.py`** — docstring carries the [64,64] disclosure but not
    the ~7x full-loop overstatement half.
19. **`README.md` minor:** `:29` mean opp Elo 1231 vs `:44` 1229 (same
    quantity, two values — pick from the replays);
    LADDER_R1_READOUT.md unlinked from every top-level doc (link it
    AFTER item 2's regeneration); `:233` shows only the R1 ladder
    invocation; the where-written-down table omits CHAPTER5 and both
    readouts.
20. **`CHAPTER5.md` migration assessment** (per its own lifecycle rule):
    §4, §5, §8, §1/§2 are migrated/superseded and deletable today; §3
    (C1-C6 provenance, maintainer-first-class), §6 (out-of-scope), §7
    (five rulings incl. the 50M ceiling) must survive into R2's pre-reg
    header before the file can be deleted.

## Verified clean — do not re-litigate

`configs/eval/ladder_r1.yaml` (genuinely result-blind; leave);
`ladder_r3.yaml:967-969` corrected-bands-beside-superseded pattern (the
model for fixes above); the 0.0717→0.1007 r9 corrections in
ch5_r1_offsh.yaml / CHAPTER5:375 / STATUS:34; all four
`ch3_r4_fp_runner.sh` landmine fixes; `ch5_seat_smoke.py` /
`ch5_seat_equiv.py` in-file warnings; `extract_history.py`;
`ladder_supervise.sh`+`ladder_watchdog.sh`+`ch5_watchdog.sh` are three
distinct live tools, not duplicates; repo root has no strays;
`configs/showdown_sp_actpred12m.yaml.c4prereg` is a deliberate
unlaunchable pre-reg record (invisible to `*.yaml` globs — remember it
exists).
