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

15. ~~**`scripts/score_ladder.py`** — no in-file warning.~~ **DONE
    2026-08-28 (warning header added; NOT deleted — deletion is a
    maintainer call).** Correction to this item as originally filed: the
    dangerous invocation is `--opponents random` ALONE, which prints a
    full page of plausible numbers and exits 0. The `random heuristic`
    default prints ONE row and then dies on the bad key, because the loop
    flushes per row — so the original framing had the failure mode
    backwards.
16. **RETRACTED 2026-08-28 — DO NOT DELETE.** The claim "referenced by
    nothing" was FALSE and checking cost nothing: the PNG is a RENDERED
    MARKDOWN EMBED at `SESSION_LOGS_PREDECESSOR.md:1403` (deleting it
    breaks an image in a frozen doc), it is described at `:818`, and
    **`SESSION_LOGS.md:408` already RULED that it stays.** Proposing its
    deletion was a live doc contradicting a recorded ruling — the D19
    failure mode, committed by this very file. The real defect is that
    the figure is UNLABELLED (it asserts ~0.4 vs SH and a 611-dim encoder
    against production 828-dim / 0.71825); the fix is a caveat line beside
    the embed, which needs the owner of that frozen file.
17. **RETRACTED 2026-08-28 — ALL FIVE HAVE REFERENCES; NONE IS A SAFE
    DELETE.** Verified individually: `ch3_r1_spike.py` backs live config
    constants (`ch3_rung2.yaml:9,58,119` attribute `leaves_expected: 353`
    to "the R1-0 spike"); `d22_trajectories.py` is the ONLY
    implementation of the D23-WATCH record-only statistic pre-registered
    in two live headers; `probe_type_multiplier.py` is quoted in
    `diag_encoder_live.py:4-9`'s own rationale (it is cited BY its
    claimed successor, not superseded by it); `make_bc_dataset.py` and
    `p3_team_luck.py` are cited in the predecessor log as the
    instruments behind a live anchor and a banked variance
    decomposition. **The lesson, and it is the one `scripts/README.md`
    already states: "nothing greps it" is not evidence a script is
    dead** — provenance for a banked number is a reference. `record.py`
    remains CLEANUP.md B7's candidate. The CH3 wave-runners are now in
    scripts/README.md (done 2026-08-28).
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

## D. Structure (maintainer question 2026-08-28: "is the repo structure good?")

Assessment: the LIVE-doc protocol is good and must not be touched (STATUS's
60-line cap + rewrite-in-place; SESSION_LOGS append-only + grep-index;
HANDOFF stub contract; pre-regs in config headers WITH TESTS — the best
structural idea here). What rots is every free-form essay with no consumer
and no cap: DESIGN, DESIGN2, RESEARCH_BRIEF, CHAPTER5 all decayed in place,
compensated by hand-written trap warnings in CLAUDE.md that themselves
drift (twice in this sweep). Root = 16 .md / ~15k lines; only ~7 are live;
naming/location distinguish nothing.

Ideas for the cleaning session (same disclaimer as the header):
- `docs/archive/` for spent docs (DESIGN, DESIGN2, RESEARCH_BRIEF,
  REPLAY_AUDIT; CHAPTER5 once §3/§6/§7 migrate into R2's pre-reg header).
  The MOVE is the supersession marker (one tombstone line each); CLAUDE.md's
  per-file trap warnings collapse to one rule: anything under docs/archive
  is history, never "what next". git mv keeps history; budget a link pass.
- `readouts/` for LADDER_*_READOUT.md — committed provenance for gitignored
  data, one per run, will accumulate (R4 foreseeable).
- ONE cleanup ledger: fold CLEANUP.md and this file together.
- Root keeps only the always-live set: README, CLAUDE, STATUS, HANDOFF,
  SESSION_LOGS(+predecessor, or archive it), RESULTS, current chapter.
- Direction, already proven by the pre-regs: when doc content has a natural
  artifact to live beside (config/script/test), migrate it there and delete
  the essay — CHAPTER5's own lifecycle rule, just unexecuted.
- Counterpoint, honestly: with CLAUDE.md as index, flatness is survivable;
  the defect is LIFECYCLE. Moving files is merely the cheapest lifecycle
  marker that cannot drift.

### D2. The objective, sharpened (maintainer, 2026-08-28): TOKEN COST, not tidiness

Every new session or agent wastes tokens reading things that should be
archived and only re-read explicitly. Three cost channels, three fixes —
success metric: "tokens before useful work" and "tokens an agent can waste
by wandering" both go DOWN.

1. **CLAUDE.md is the only unconditionally-loaded file** (every session,
   every context-inheriting agent, ~180 dense lines) — and much of it is
   war-story narrative around few-line rules (the FP ops landmine: ~30
   lines of incident history for ~4 lines of rule). TOP-VALUE ITEM: diet
   it to rules-with-one-clause-whys + pointers; move narratives to an
   on-demand `docs/landmines.md`. Caution: the stories exist because bare
   rules got violated — keep the one-clause why, cut the incident log.
2. **Exploratory reads landing on dead docs** (DESIGN 905 lines,
   predecessor logs 1,939, frozen readouts): `docs/archive/` fixes this
   MECHANICALLY — default sweeps do not descend, and ONE CLAUDE.md line
   ("nothing under docs/archive is read unless the maintainer names the
   file") replaces every per-file trap warning. ~4k lines leave the
   default surface. (D19 shows the cost is correctness, not just tokens.)
3. **Agents re-reading the same reference material** (2026-08-28 sweep
   agents: ~120k/~160k tokens each, mostly reads): structure helps less
   than briefing discipline — write down the convention: subagent briefs
   carry explicit file:line ranges; reference material lives in small
   single-topic files so a targeted read is 50 lines, not 9,000.

The repo already invented the right pattern twice: STATUS's 60-line cap
and the SESSION_LOGS grep-index are pay-per-use designs. The rot is
everything that grew outside those two mechanisms.
