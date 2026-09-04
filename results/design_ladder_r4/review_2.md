# REVIEW 2 — REPO CONSISTENCY AND EXECUTABILITY
Target: `results/design_ladder_r4/ladder_r4.draft.yaml` (LADDER R4, greedy 100M final, lane s112).
Method: read every named script and test path against the draft's claims key-by-key; no test was
run with a copy of the draft under `configs/eval/` (forbidden by the brief). Checkpoint sha, set-pool
pins and every quoted number were recomputed or read from their source file.

## WHAT PASSES (stated once, so the MUST-FIX list is not read as a verdict on the whole file)

Against `tests/test_ladder.py` as written, with the file at `configs/eval/ladder_r4.yaml`:
`kind: greedy` ∈ `ladder.POLICY_KINDS` (`scripts/ladder.py:79`); `lane: s112` resolves into
`checkpoints` (test:526-533); `nickgen1rbrlbot3` is a 16-char userid and contains `bot`
(test:535-542); no banned credential token (test:544-547); `glicko_rd_max 40` / `min_battles 200`
(test:510-517, 574-576); `max_battles_total 300 > 200` (test:578-579); both `set_pool_pin` hashes
recomputed on disk 2026-09-04 and BYTE-IDENTICAL (`85fc2743…`, `277d5a37…`, test:581-601); all nine
`instruments:` paths exist (test:387-401). The greedy branch of `_build_policy`
(`scripts/ladder.py:365-372`) reads exactly `arm["kind"]`, `arm["lane"]`,
`prereg["checkpoints"][lane]["path"|"sha256"]` — everything the arms block provides — and stamps
exactly the six keys VOID (e) names, no `dose` (ladder.py:358-369). Checkpoint sha recomputed:
`2ec16fbf85a9046d360328e50cdee5c732d8529599aafa2215a2a56128abcbb3` MATCHES. `_resolve_display_name`
behaves as claimed (SystemExit on a disagreeing `PS_USERNAME`, ladder.py:273-283). Ping budget
60/120/60 is real (ladder.py:461-463). Every quoted prior number checks out: s112 off-FP 0.50167 /
vs-SH 0.8000 / BC-clone 0.930 and the three pooled values (RESULTS.md:1164, 1179, 1212;
`results/ch5_100m/final_s112.json` `eval/win_rate` 0.8; `bcclone/ca112.final.json` 0.93;
`t112.json` `mean_turns` 28.403); R1 GXE 59.6/1573±27/1292 and R3 60.3/1579±25/1232, 106-102 over
208, band 0.444 n=36 (readouts/LADDER_R3_READOUT.md:16, 84, 137); R1 corrected 0.319 n=47
(ladder_readout.py:70-71); admission ~1359 on both pulls (LADDER_R1_READOUT.md:14,
ladder_r3.yaml:978); C0 0.3893 / RS80 0.4390 (SESSION_LOGS.md:8412, RESULTS.md:804); ~93
players/day (ladder_r3.yaml:981). JOURNEY step 2 is quoted VERBATIM (JOURNEY.md:31,33).

## MUST-FIX

**1. The ratification instruction omits the string the suite actually asserts — as written, the
ratifying commit leaves `pytest tests/test_ladder.py` RED.**
Draft:3-9 — `"# Status: DRAFT — carries << MAINTAINER n >> markers M1..M9. NOT ratified."` … `"The
ratifying commit `git mv`s it to configs/eval/ladder_r4.yaml, clears the markers, and records
rulings in ratified_decisions at the foot."`
`tests/test_ladder.py:559-561` asserts BOTH: `assert not re.findall(r"<< MAINTAINER \d+ >>", raw)`
**and** `assert "Status: RATIFIED" in raw`. The draft's own note names the `git mv` and the marker
clearing and stops there. Flipping `Status:` is the second half of the same test and is nowhere in
the file. LG-4 ("pytest tests/test_ladder.py green") then fails at the last gate, on launch night.
Minimal fix: draft:6-9 → "…`git mv`s it to configs/eval/ladder_r4.yaml, **replaces `Status: DRAFT`
with `Status: RATIFIED` (tests/test_ladder.py:561 asserts the literal string)**, clears the nine
markers, and records rulings in `ratified_decisions` at the foot."

**2. "pre-committed" is not supported anywhere in the repo, and the Q6 discharge leans on it.**
Draft:34-37 — `"LANE SELECTION RULE, pre-committed before any ladder object existed: the MEDIAN of
the three 100M finals on the off-FP@20 primary"`.
No median-based lane-selection rule exists in any committed file before the 2026-09-04 ruling. The
100M pre-reg names the per-lane median only as a NON-governing record of the primary read
(`configs/showdown_sp_100m.yaml:131-133`: "per-lane median (k=3: the median IS one lane), best/worst
lane and per-lane deltas are RECORDED and NEVER govern") and the only pre-existing mention of ladder
lane choice runs the other way — `configs/showdown_sp_100m.yaml:184`: `"a best-of-six ladder
candidate"`. The rule's first appearance is `BRIEF.md:17-22`, dated 2026-09-04, i.e. after all three
lanes' off-FP numbers were published in RESULTS §18. Draft:65-68 then rests the Q6 residual on the
rule's construction. The median-over-max argument survives; the word does not.
Minimal fix: draft:34 → "LANE SELECTION RULE, maintainer-ruled 2026-09-04 with all three lane
numbers already published (RESULTS §18) — median, not best-of-3, exactly to avoid selection-on-noise
on a ±0.02 instrument; it is NOT a rule that predates the numbers, and Q6's residual below is stated
on that basis."

**3. No `aggregators:` block, while the amendment clause bars amending one.**
Draft:310 bars, after ratification, `"the aggregators and denominators"` — there is no aggregators
key in the file. CLAUDE.md's five pre-reg rules require naming the across-lane aggregator and leaving
no unnamed cells; R3 discharged it explicitly at `configs/eval/ladder_r3.yaml:909-913`
(`across_lanes: "NONE — one lane (s80), one arm. Stated rather than omitted."`, plus `primary`,
`descriptive_rates`, `ties`).
Minimal fix: add R3's four-key `aggregators:` block with `across_lanes: "NONE — one lane (s112), one
arm. Stated rather than omitted."` and the same `primary` / `descriptive_rates` / `ties` lines.

**4. The credit line is not restated verbatim.**
Draft:83-86 — `"THIS RUN CREDITS NOTHING. No A/B, no control, no paired comparator, no se_diff, no
0.025 bar."` CLAUDE.md is explicit that the header must restate the credit line verbatim *including*
the larger-of (binomial vs seed-clustered) se_diff clause; R3, which also credits nothing, still did
it (`configs/eval/ladder_r3.yaml:907`, `credit_line_not_applicable: "… For the record the line reads:
'a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the
pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals
at read time.' … Stated rather than omitted."`).
Minimal fix: add that key verbatim, s/R3/R4/.

**5. Readout obligation (vii) is not executable: the reconciliation block is hardcoded to R3.**
Draft:216-221 — `"(vii) RECORD RECONCILIATION, machine-checked at stop: profile_w+profile_l+profile_t
== jsonl_rows, else the readout emits a mandatory block naming the gap…"`.
`scripts/ladder_readout.py:412` gates the entire existing profile-vs-JSONL block on
`if args.label.upper() == "R3":`, and the gap sentence inside it (readout.py:426-433) is R3-specific
prose ("battles in flight when our socket died"). Run with `--label R4` the readout prints NO
reconciliation at all — silently, which is the exact 106-94/106-102 failure (viii) exists to stop.
Obligation (viii)'s doc-grep test does not exist either, and neither (vii) nor (viii) appears in
BUILD ITEMS (draft:294-298, BI-R4-1..4) or in LG-8 (draft:270).
Minimal fix: add `BI-R4-5 (readout): un-gate the record-reconciliation block from
label=="R3" and generalise its cause sentence` and `BI-R4-6 (test): the committed-docs W-L grep`, both
owed at readout with R3's BI4 fallback pattern ("built by hand, still asserting, and the readout says
so"); name them in LG-8.

**6. LG-3 covers the username but not the password, and the smoke cannot catch the password.**
Draft:264-266 — `"LG-3 .env updated to bot3 (the bot2 value aborts the runner — correct but
4am-shaped; the smoke catches it)."`
`.env` is two lines: `export PS_USERNAME=nickgen1rbrlbot2` and `export PS_PASSWORD=<redacted>` — the
password is bot2's. `run()` reads `PS_PASSWORD` at ladder.py:648 and then, on the local-smoke path,
sets `password = None` (ladder.py:655) and connects to localhost with no auth. So the smoke exercises
`_resolve_display_name` (which is what "the smoke catches it" is true of — the USERNAME) and never
touches the password. A stale bot2 password on the real run fails at first login, after LG-1..LG-8 are
all green, with the maintainer at the terminal and the courtesy note already sent.
Minimal fix: draft:264-266 → "LG-3 .env updated to bot3 — **BOTH `PS_USERNAME` and `PS_PASSWORD`;
the smoke catches only the username (it sets `password = None`, ladder.py:655), so the password is
verified for the first time at LG-9's live login."

## SHOULD-FIX

**7. `--battles 200` gives no path to `max_battles_total 300`.**
Draft:347 `battles_target: 200  # passed ONCE as --battles 200` vs draft:350
`hard_ceiling_h: "~22 (rd binds AND the run reaches max_battles_total)"`. `run()` stops at
`remaining = battles - len(done)` (ladder.py:673) and the supervisor breaks at `n1 >= TARGET`
(ladder_supervise.sh:75-77), so with TARGET 200 the run cannot reach 201 — and if rd > 40 at n=200 it
exits with `stopped_by_rule: false`, which is R1's published-embarrassment shape. The amendment
licence (draft:305) permits only "resume relaunches with the SAME --battles".
Minimal fix: add to `schedule:` — "if the rule is UNMET at n=200, the licensed continuation is a
relaunch of the supervisor with TARGET 300 (still inside `max_battles_total`, which may not move
upward); this is pre-committed here, not decided at 4am."

**8. BI-R4-3's trigger cannot fire against the watchdog as written.**
Draft:284-286 — `"NEW BI-R4-3: at 2xSTALL with the socket UP, a distinct escalation line"`.
`scripts/ladder_watchdog.sh:80-82`: the socket-up branch does `last_t=$now`, so `idle` is reset at
every stall notice and never reaches 2×STALL. Implementing "2xSTALL" means changing the stall clock —
which contradicts the same sentence's "no kill-path change".
Minimal fix: re-word to "on the SECOND CONSECUTIVE socket-up stall notice (a counter beside the
existing reset), print a distinct escalation line" — no clock change, no kill-path change.

**9. R1's seconds-per-battle is mislabeled and compared against a different statistic.**
Draft:245 `"median 218.0 s/battle vs R1 greedy 229.5"`; draft:351
`sec_per_battle_refs: {r1_greedy_median: 229.5, …, r3_median_excl_gaps: 211.5, …}`.
`readouts/LADDER_R1_READOUT.md:127-128`: R1's MEDIAN is **230.0**; **229.5** is the median EXCLUDING
gaps > 900 s. The draft pairs R3's plain median (218.0, LADDER_R3_READOUT.md:161) with R1's
excl-gaps figure. Matched pairs are 218.0 vs 230.0, or 211.5 vs 229.5. The conclusion (greedy buys
1-2 h, not the night) is unchanged.
Minimal fix: `r1_greedy_median: 230.0` and add `r1_median_excl_gaps: 229.5`; draft:245 → "median
218.0 vs R1 greedy 230.0 (excl-gaps 211.5 vs 229.5 — the pairs are matched)".

**10. The licensed cell's R3 reference cannot be printed by the readout.**
Draft:99-102 licenses the cell with `"R1 CORRECTED 0.319 (n=47…) and R3 0.444 (n=36)"`.
`scripts/ladder_readout.py:70-73` hardcodes `R1_BANDS` / `R1_CATS` only, and the band table's column
header is literally `"| R1 (n, rate) |"` (readout.py:326-333). An R4 readout prints this-run-vs-R1;
the R3 column needs a code change or a hand appendix, and neither is a build item.
Minimal fix: add to BI-R4-2 (or a new BI): "`ladder_readout.py`: add an R3_BANDS column beside
R1_BANDS; fallback — a hand-written appendix carrying R3's cell, preserved on regeneration."

**11. `barred_language` is prose only, though the draft calls it grep-enforceable.**
Draft:134-139 — `"BARRED LANGUAGE (grep-enforceable, carries R3's list…)"` lives in a comment.
R3 carries a machine-readable `barred_language:` list at `configs/eval/ladder_r3.yaml:915`. A grep
over the config for a phrase can't be automated against a comment block that also contains the
phrases embedded in explanatory sentences.
Minimal fix: add a `barred_language:` YAML list with R3's items plus the ten new phrases, and keep
the prose as the why.

**12. CLEANUP's B9 names R4 as the decision point and the draft is silent.**
`CLEANUP.md:29-34`: "**B9 — poke-env sporadically drops `battle.rating`** … ACCEPTED, not fixed …
**Optionally patch `ladder.py` before R4 — never mid-measurement.**" R4 is the last moment this can
be touched, and readout obligation (i) (rating trajectory) is what the dropped field degrades.
Minimal fix: one line under BUILD ITEMS ruling B9 — patch pre-launch, or carry R3's
rating-loss disclosure verbatim and say the readout reads the replays.

**13. The object's checkpoint sits inside a deletion that is already permitted.**
Draft:32 pins `runs/showdown_sp_100m_s112/ckpt_100000008.pt` — a gitignored file. `STATUS.md:20-22`:
"**E2 rung retention DISCHARGED** — … deleting the ~600 treatment + 300 control rungs is now
permitted (keep completion + 12M rungs; maintainer call)." The completion checkpoint is inside the
"keep" set, but a `ckpt_*.pt` glob over that directory is exactly how it goes.
Minimal fix: one line in `checkpoints:` — "FROZEN until the R4 readout lands; explicitly EXEMPT from
the E2 rung deletion permitted at STATUS.md:20-22."

**14. Both relative paths in the file are CWD-relative and nothing cds.**
`checkpoints.s112.path` is opened relatively (ladder.py:342) and `save_replays` is resolved by
poke-env against the process CWD (`abstract_battle.py:532-539`, which does
`mkdir(parents=True, exist_ok=True)` — so a wrong CWD silently creates a wrong replay tree).
`scripts/ladder_supervise.sh:31-66` computes `$REPO` but never `cd`s. Draft:277-279 gives the
supervisor line without a working directory or `source .env`.
Minimal fix: draft:277 → "`cd <repo root> && source .env && nohup scripts/ladder_supervise.sh R4G 200
configs/eval/ladder_r4.yaml …` — the checkpoint path and `save_replays` are both CWD-relative."

**15. The README prose R4 falsifies is not named, breaking R3's own precedent.**
`configs/eval/ladder_r3.yaml:991` set the pattern: `readme_owed: "README.md:117 says 'The ladder
therefore runs the ensemble, not search'. R3 reverses that; update it in the ratifying commit."`
R4 reverses it again, and `README.md:158-164` now reads "**LADDER R3 REVERSES that deployment call and
ladders search**". `README.md:249` also hands a reader
`python scripts/ladder.py --prereg configs/eval/ladder_r3.yaml --arm R3S --battles 200` — a
copy-paste hazard on launch night. Draft:235-238 (RECORD PLAN) names only the README row.
Minimal fix: add `readme_owed:` naming README.md:158-164 and README.md:249.

**16. BI-5's `max_concurrent_live_battles` EXPECTED 1 is dropped, and the etiquette premise leans on
it.** Draft:281 keeps `"max_concurrent_battles 2 kept (poke-env deadlock is generic)"` but never
carries the artifact-side assertion. D3 ratified precisely that split
(`configs/eval/ladder_r3.yaml:1015-1020`: "BI-5 stamps `max_concurrent_live_battles` so this is
ASSERTED from the artifact, not read off a config value"), and R4's courtesy note discloses serial
single-account play.
Minimal fix: add `max_concurrent_live_battles_expected: 1` to `expected_instrument_values:`.

**17. The power disclosure drops the n it was computed at.**
Draft:102 `"2*se_diff at matched n is ~0.195"`. R3's ratified wording is "at matched **n=47**"
(`configs/eval/ladder_r3.yaml:903`). R4's other reference cell is n=36, where the figure is larger.
Minimal fix: "≈0.195 at matched n=47 (R1's cell); larger against R3's n=36".

**18. D5's `mu8_ceiling` was ratified "CARRIED VERBATIM" and is not in the carried list.**
`configs/eval/ladder_r3.yaml:906`: `mu8_ceiling: "CARRIED VERBATIM: R1-B 'licenses search as an R3
DEPLOYMENT CANDIDATE and nothing else; does NOT reverse MU-8 (z = -2.80)…'"`. The draft carries D5's
verdict, RD refusal and licensed cell (draft:88-110) but not this clause. Its operative content —
"a good number does not vindicate the policy kind, a bad one does not condemn it" — is exactly what a
greedy R4 needs after R3 laddered search.
Minimal fix: one line under WHAT R4 MAY CLAIM: "R3's `mu8_ceiling` is carried; whatever R4 reads, it
neither vindicates greedy nor reverses MU-8."

**19. Two of the three anchor values are attributed to s112 by column position only.**
Draft:46-48 quotes `"vs-SH 0.8000 of 0.7913/0.8000/0.7967; BC-clone 0.930 of 0.912/0.930/0.928"`.
RESULTS.md:1179 and :1212 print those triples WITHOUT lane labels (only the primary table at :1162
carries the `s104 / s112 / s120` header). Both values are correct — verified in
`results/ch5_100m/final_s112.json` (`eval/win_rate` 0.8) and `results/ch5_100m/bcclone/ca112.final.json`
(0.93) — but the draft's provenance is positional inference off an unlabelled row.
Minimal fix: cite the two per-lane artifacts beside the numbers.

## COUNT

6 MUST-FIX, 13 SHOULD-FIX (19 findings).
