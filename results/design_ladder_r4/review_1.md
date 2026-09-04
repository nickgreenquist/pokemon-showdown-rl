# REVIEW 1 — ADVERSARIAL ARITHMETIC AND INTERNAL CONSISTENCY
Target: `results/design_ladder_r4/ladder_r4.draft.yaml` (frozen draft, 2026-09-04).
Method: every load-bearing number recomputed from disk or read at its cited line.
Line numbers below are the draft's own.

## What I could not break (recorded so it is not re-checked)

- **Median-lane selection.** `results/ch5_100m/t104.json:our_win_rate` 0.48633333,
  `t112.json` 0.50166667, `t120.json` 0.50733333. Median = 0.50167 → s112. **Correct.**
- **sha256.** `shasum -a 256 runs/showdown_sp_100m_s112/ckpt_100000008.pt` =
  `2ec16fbf85a9046d360328e50cdee5c732d8529599aafa2215a2a56128abcbb3`. Matches draft:33
  and :330, and `configs/eval/ch5_100m_offfp.yaml:26`. **Correct.**
- **Set-pool pin.** `showdown/` HEAD = `59da482eabc87245eb62313593e468e81ca537d9`;
  `data.json` = `85fc2743…5380f`; `teams.ts` = `277d5a37…c059`. All three match
  draft:341-343. **Correct.**
- **off-FP pooled 0.49844** = (1459+1505+1522)/9000 = 0.4984444 = `grade.json:mean_T`.
  **BC-clone 0.930 / pooled 0.9233** = (0.912+0.930+0.928)/3 (`bcclone/ca{104,112,120}.final.json`).
  **R1-corrected [1300,1400) 0.319 n=47** and **R3 0.444 n=36** — exact against
  `readouts/LADDER_R1_READOUT.md` and `LADDER_R3_READOUT.md` band tables. **All correct.**
- **R1/R3 timing refs.** Recomputed from `results/ladder/L2.battles.jsonl` and
  `R3S.battles.jsonl`: R1 mean 246.5 / median 230.0 / median-excl-gaps 229.5 (n=198 of
  199) / gaps>900 sum 0.41 h; R3 mean 277.5 / median 218.0 / median-excl 211.5 (n=194 of
  199) / gaps>900 = 5, sum 2.87 h. Draft:351 and :353 values are all on disk (but see F12).
- **Turn projection arithmetic.** 28.403 × 0.776 = 22.04; × 0.946 = 26.87 → "22.0 – 26.9"
  is right. Ceiling: 299 × 235 s = 19.5 h + ~2.5 h outage ≈ 22 h (mem_B §1). Sound.
- **journey_step quote** is verbatim against `JOURNEY.md:31-33`.
- **Code contracts.** `scripts/ladder.py:79` POLICY_KINDS includes `greedy`;
  :358-369 stamps exactly the six keys draft:204 requires and `dose` only on the search
  branch (:406); :808 gates board polling on `len(records) >= rule_n_min`, so draft:328's
  "polling starts ONLY at min_battles" is code-backed; supervisor/watchdog argument forms
  at draft:277-279 match `ladder_supervise.sh:3` and `ladder_watchdog.sh:2`;
  `backup_ladder.sh:40` `RUNS=("L2:replays" "R3S:replays_r3")` confirms BI-R4-1 is a
  one-line change; `nickgen1rbrlbot3` is 16 chars and contains "bot", passing
  `tests/test_ladder.py:535,539`.

---

## MUST-FIX

**F1 — MUST-FIX. The vs-SH lane triple is wrong, and the triple as printed does not
average to the pooled value printed beside it.**

> draft:46 — `(vs-SH 0.8000 of 0.7913/0.8000/0.7967; BC-clone 0.930 of`

`results/ch5_100m/final_s104.json` reads `"eval/win_rate": 0.791` — exactly 2373/3000
(cross-checked: `return_mean` 0.58966667 and `ties_from_returns` 0.00766667 ⇒ W=2373,
L=604, T=23). **0.7913 is not attainable at n=3000** (0.7913 × 3000 = 2373.9), and
`grade.json:vs_sh.mean_T` = 0.79588889 reproduces only from 0.791
((0.791+0.8+0.7966667)/3 = 0.7958889); the printed triple averages to **0.79600**, not
the 0.79589 quoted at draft:52. The error originates in `RESULTS.md:1178` and is
propagated here. Fix: `0.7910/0.8000/0.7967` at draft:46, and file a correction against
`RESULTS.md:1178` in the same commit so the ratified pre-reg and the account agree.

**F2 — MUST-FIX. G-BLIND's licensed stops are NOT carried verbatim: the VOID-condition
stop was dropped and replaced with a moderator-contact stop.**

> draft:176-178 — `G-BLIND carries verbatim: four licensed stops (rule satisfied;
> max_battles_total; operational abort logged with cause and battle index; moderator
> contact -> stop at next battle boundary, do not argue).`

`configs/eval/ladder_r3.yaml:366-369` reads: "(1) the pre-registered rule fires;
(2) `max_battles_total`; **(3) a VOID condition**; (4) an operational abort — crash, ban,
**moderator contact** — logged with its cause AND the battle index". The draft silently
promotes R3's *example* of an operational abort to a stop of its own and deletes the VOID
stop. Consequence, and it is live: draft:204 says the sha is "asserted at every runner
launch" and draft:200-201 makes set-pool drift VOID (c). A VOID discovered at battle 90
is then a stop *not on the draft's list*, i.e. VOID (g) "an unlicensed stop" — the run
voids itself for correctly refusing to continue. Fix: restore "(3) a VOID condition" and
return moderator contact to the operational-abort clause where R3 put it, or make it a
fifth stop explicitly and say so instead of claiming verbatim carriage.

**F3 — MUST-FIX. "INCOMPLETE" is load-bearing in three places and is never defined,
because the sentence that defines it was dropped from the "verbatim" carriage.**

> draft:189-192 — `THE ONE-RUN RULE: R4 is ONE run. A VOID or INCOMPLETE read does NOT
> license a quiet re-run`
> draft:25-27 — `M4: a VOID or INCOMPLETE run DISCHARGES step 2 (recommended YES …)`

`ladder_r3.yaml:370-373` carries the operative half, which the draft omits entirely:
"**BARRED: stopping because the number looks good, or continuing because it looks bad.**
n is never trimmed to a round number and never extended after looking. **A run ended any
other way reports as INCOMPLETE and may not be quoted as R3's primary read.**" As drafted,
nothing in R4 bars stopping on a good number, and nothing says an INCOMPLETE run's GXE is
unquotable — while draft:94-97 licenses "the server-computed GXE / Glicko-1 / Elo off the
PROFILE at the stopping rule" with no clause for a run that never reached one, and M4
tells the maintainer such a run still discharges step 2. Fix: paste
`ladder_r3.yaml:370-373` verbatim into the STOPPING/BLINDNESS block, with "R3's" → "R4's".

**F4 — MUST-FIX. `max_battles_total` may be lowered mid-run — the draft bars only the
upward move, and mem_A barred both.**

> draft:308-309 — `max_battles_total upward after the first rated battle;`

`mem_A.md:116` reads "`max_battles_total` (**downward at any time**, upward after the
first rated battle)". The downward half was lost in drafting. With draft:177's disclosed
leak ("the per-battle running W/L print is the known, disclosed leak") this is a complete
optional-stopping path the bars do not catch: at n=230 with a poor running record, amend
`max_battles_total` 300 → 230 under the amendment-licensing procedure, and licensed stop
(2) fires immediately on a number chosen after looking. Fix: restore
`max_battles_total` — **downward at any time, upward after the first rated battle** — to
the BARRED list at draft:308.

**F5 — MUST-FIX. The draft bars amending "the aggregators and denominators" but never
states either, and states no tie convention.**

> draft:310 — `the aggregators and denominators; the VOID conditions.`

There is no `aggregators:` key anywhere in the file. `ladder_r3.yaml:911-914` had one, and
CLAUDE.md's "five pre-reg rules the D25/D25-P cycle paid for" begins "name the across-lane
aggregator". Three concrete gaps: (a) "fleet pooled" at draft:52-54 is used three times
and never defined — `grade.json:aggregator` is `equal_weight_mean_of_lane_rates`, which
happens to coincide with the pooled proportion only because the lane n's are equal;
(b) the descriptive rate over unequal-n sessions is undefined (R3 pinned it: "unweighted
pooled proportion over ALL rated battles, NOT a mean of per-session rates");
(c) **the tie convention is absent** — draft:219 asserts `profile_w+profile_l+profile_t ==
jsonl_rows`, so ties exist, but the headline at draft:144 is "server record W-L" with no
statement that ties are non-wins or that the server's tie handling differs from ours. Fix:
add an `aggregators:` block copying `ladder_r3.yaml:911-914` with R4's values.

**F6 — MUST-FIX. The fixed headline template's `n` is unpinned across three denominators,
and the band cell's `n=k` sits on a different one.**

> draft:143-147 — `reached GXE X%, Glicko-1 Y +/- RD and final Elo Z over n rated battles
> (server record W-L) against D distinct opponents. Against the 1300-1400 band[, …] it
> scored V (n=k).`

Draft:217-220 names three denominators (`n_profile` / `n_jsonl` / `n_played`) and asserts
the band table against `n_jsonl`; draft:222-224 makes the headline record the **profile**
record. So in the template, `n` is `n_profile`, `W-L` is `n_profile`, and `k` is a subset
of `n_jsonl` — three quantities under two symbols with no label. This is exactly R3's
106-94/106-102 failure re-created inside the template the propagation test (viii) is
supposed to protect: R3's profile n was 208 while its band table summed to 200, so a
reader subtracting cell n's from the headline n loses eight battles silently. Fix: write
the template as "over n_profile = N rated battles (server profile record W-L; runner-logged
subset n_jsonl = M)" and "it scored V (n=k of n_jsonl = M)".

**F7 — MUST-FIX. The decision-ms band has an unowned interval, [20, 30) ms, and the prose
and the YAML disagree on whether 20 is inside it.**

> draft:206-208 — `mean_decision_ms INVERTED TELL: provisional band [1,20) ms, >=30 ms =
> a search wrapper or wrong arm loaded`
> draft:358 — `mean_decision_ms_band: [1, 20] # PROVISIONAL … >=30 ms = WRONG OBJECT`

A stamped 24 ms is outside the expected band and below the VOID threshold: the pre-reg
says nothing about it, so the operator decides at launch time what a 24 ms greedy seat
means. The prose writes the band half-open `[1,20)`, the YAML writes it closed `[1, 20]`.
For calibration, R1's *four-lane ensemble* stamped 6.74 ms (`L2.report.json`) and R3's
search stamped 93.44 ms (`R3S.report.json`), so a single greedy forward pass lands ~1-3 ms
and the gap is unlikely to be exercised — but it is a VOID condition with a hole in it.
Fix: make the band's upper bound and the VOID threshold the **same number**
(`mean_decision_ms >= band_max ⇒ VOID (e)`), and state that ADJ-5's smoke finalization sets
that one number.

**F8 — MUST-FIX. The "all three readout scripts default to R1" trap is not carried
forward, and BI-R4-2 makes R4 the run most likely to hit it.**

`ladder_r3.yaml:934` carries, in capitals: "** ALL THREE READOUT SCRIPTS DEFAULT TO R1 **
(--jsonl results/ladder/L2.battles.jsonl, --replays results/ladder/replays, --name
nickgen1rbrlbot). Run bare they produce a readout OF R1 and it looks perfectly normal.
Pass all three flags, always." The draft's readout obligations (draft:211-234) and
BI-R4-2 (draft:295-297) do not mention it. Since R4 is the first run with **two** priors
and BI-R4-2 adds per-prior `--compare-jsonl` flags, the flag surface grows exactly where
this trap lives — and a bare run publishes R1's GXE 59.6 / Elo 1292 under R4's headline
with no assertion tripping. Fix: carry the `readout_scripts_default_to_r1` warning
verbatim as a YAML key, and add to (vii) a machine check that the readout's `--name`
equals `arms.R4G.display_name` and its `--jsonl` basename matches `primary_arm`.

**F9 — MUST-FIX. The one licensed new sentence overclaims: the object's vs-SH number is
not a locked-protocol number.**

> draft:107-110 — `ONE new sentence: R4 is the first ladder measurement here whose object
> carries ALL THREE anchors at locked protocols`

CLAUDE.md's locked protocol is "final checkpoint, **3000 battles/seed, 3 seeds pooled**",
and `RESULTS.md:1178` says of the vs-SH read "this is 3×3000 exactly" — i.e. the
locked-protocol number is the **fleet** number 0.79589. The object here is one lane, and
`final_s112.json` is `episodes: 3000, seed_start: 100` — a single 3000-battle read, one
component of the protocol, not the protocol. The draft's own honesty elsewhere (draft:43,
:49-54) depends on this distinction; the licensed sentence quietly discards it, and it is
the *only* new claim R4 is permitted to make. Fix: "R4 is the first ladder measurement
here whose object is drawn from a fleet carrying all three anchors at locked protocols;
the lane values quoted are single-seed components of those protocols, never the protocols
themselves." Keep the "claim about the RECORD, never the rating" clause.

**F10 — MUST-FIX. The headline's "same-day pull" and M2's branch test key off different
board pulls, and the two can disagree.**

> draft:113-115 — `the admission cutoff is pulled and ARCHIVED at n=0 and at stop; if the
> n=0 cutoff is inside [1300,1400) the reference sentence stands`
> draft:146-147 — `Against the 1300-1400 band[, the band containing rank 500 on the
> same-day pull,]`

Two pulls are archived; the branch test reads the **n=0** pull; the headline says
"same-day", which for a 12-16 h run spanning midnight is ambiguous and most naturally
reads as the **at-stop** pull. RESULTS.md:1013 states the cutoff "moves with field
activity and must be re-pulled before quoting", and both prior pulls landed at 1359.09 —
nine points inside the band boundary. A cutoff that crosses 1400 between the two pulls
puts the branch test and the headline in direct contradiction. Fix: pin one pull by name
in both places ("the n=0 pull, archived at `readouts/LADDER_R4_READOUT.md`"), and add: if
the two archived pulls fall in different bands, the rank-500 clause is STRUCK and both
cutoffs are reported.

---

## SHOULD-FIX

**F11 — SHOULD-FIX. R3's realized wall clock is stated as both 17 h and 15 h in the same
file, and 17 h is not on disk — it is R3's *planned* budget.**

> draft:245-246 — `R3's 17 h was NOT search-dominated (median 218.0 s/battle …`
> draft:275 — `MID-RUN BACKUP (once; R3 ran 15 h with no snapshot)`

Measured: `R3S.battles.jsonl` first→last `finished_at` span = **15.34 h**;
`R3S.supervisor.log` runs 2026-08-27 22:23:54 → 2026-08-28 12:48:21 (14.41 h from n=10);
`R3S.run.log` battle 1 at 22:07:48. mem_B's own table gives 15.3 h. The "17 h" traces to
`ladder_r3.yaml:832`'s comment "worth 17 min of ~17 h", i.e. R3's pre-launch budget.
Fix: use 15.3 h in both places and say it is the realized span.

**F12 — SHOULD-FIX. `r1_greedy_median` mislabels both the estimator and R1's object, and
the prose then compares two different estimators.**

> draft:351 — `sec_per_battle_refs: {r1_greedy_median: 229.5, r1_mean: 246.5,
> r3_median_excl_gaps: 211.5, r3_mean_outages_in: 277.5}`

229.5 is R1's **median excluding gaps > 900 s** (`LADDER_R1_READOUT.md`, obligation (vi));
R1's median is **230.0**. The R3 key is honestly named `r3_median_excl_gaps` while R1's
identical estimator is named `r1_..._median` — so draft:246's "median 218.0 s/battle vs R1
greedy 229.5" compares R3's plain median against R1's excl-gaps median. Like-for-like is
218.0 vs 230.0 or 211.5 vs 229.5 (the conclusion survives either way). Separately, R1's
object was a **4-lane ensemble** (`RESULTS.md:833-836`), not greedy; calling it
"R1 greedy" in a ratified config key is quotable to support "greedy-vs-greedy across runs",
which draft:89-91 bars. Fix: rename to `r1_ensemble_median_excl_gaps: 229.5` and add
`r1_median: 230.0`; correct draft:246 to a matched pair.

**F13 — SHOULD-FIX. 0.946 and 0.944 are the same ratio at two roundings, presented as two
quantities in one clause.**

> draft:352 — `t112 proxy 28.403 x ratios 0.946 R1 / 0.776 R3 — the 0.944 calibration
> overshot R3 by 18%; carry both`

mem_B §1: R1 25.95/27.44 = 0.946; `ladder_r3.yaml:253-255` computes the same ratio as
25.9/27.44 = 0.944. "Carry both" reads as "carry 0.946 and 0.944" when it means "carry
0.946 (R1) and 0.776 (R3)". Also worth stating explicitly: each ratio is against **its own
object's** off-FP turns (27.44 for R1's C0, 36.824 for R3's search@M), which is what makes
applying them to t112's 28.403 legitimate; the readouts' bare "36.824 … 0.944" phrasing
invites the wrong reading. Fix: "ratios 0.946 (R1, = the 0.944 of `ladder_r3.yaml:255` at
one more digit) and 0.776 (R3); each is ladder-turns ÷ that object's own off-FP@20 turns;
the R1 ratio overshot R3's realized turns by 18%."

**F14 — SHOULD-FIX. "~10 se" divides by a single-arm se, not an se_diff.**

> draft:38-40 — `search@20 hurt the batch recipe (0.38067 vs greedy 0.4740, ~10 se, …)`

Δ = 0.09333; per-arm binomial se at n=3000 ≈ 0.00887/0.00912, so Δ/se_arm = 10.5 but
**Δ/se_diff = 7.3**. The repo's credit line is defined on `2·se_diff`, so an unlabelled
"se" in a pre-reg header is a denominator a hostile reader can pick. Carried from
`SESSION_LOGS.md:9864`, but this file is where it gets ratified. Fix: "~7.3·se_diff
(10.5 per-arm se)" — name the denominator.

**F15 — SHOULD-FIX. "binds" is used in opposite senses two lines apart.**

> draft:338 — `min_battles: 200  # THE BINDING HALF (rd extrapolates <=40 by n~88)`
> draft:350 — `hard_ceiling_h: "~22 (rd binds AND the run reaches max_battles_total)"`

At :338 "binding" means *this is the constraint that stops the run*; at :350 "rd binds"
means *rd is still above 40 and forces continuation*, i.e. min_battles is **not** binding.
(The n~88 extrapolation itself checks out against `ladder_r3.yaml:333-336` and R1's rd 26.6
/ R3's 25.4 at n=200.) Fix: ":350 → `~22 (rd still > 40 at n=200 AND the run reaches
max_battles_total)`".

**F16 — SHOULD-FIX. LG-9 asks the maintainer to read a checkpoint sha the runner never
prints.**

> draft:270-273 — `LG-9 maintainer at the terminal ~90 s reading startup lines:
> kind=greedy, the s112 sha, the userid character-by-character, "starting rating: none yet"`

`scripts/ladder.py:700-701` prints exactly `seat '<name>' (userid <id>) kind=<kind> -> N
battles`, then the rating line. The sha is *asserted* at :346 but never emitted; R3's
actual startup lines (`results/ladder/R3S.run.log:1-2`) confirm it. The last human gate
before rated games names an artifact that does not exist, so in practice it is skipped and
the operator learns nothing about which of the three 100M lanes loaded. (The assert covers
correctness; the gate covers *the operator having checked*.) Fix: add a one-line build item
— print `sha256` and `obs_dim` from `provenance` at startup — or strike the sha from LG-9
and say the assertion at `ladder.py:346` is what covers it.

**F17 — SHOULD-FIX. The encoder env vars are named in no launch gate, and `.env` does not
carry them.**

`scripts/ladder.py:361-362` stamps `encoder_v2` / `encoder_ids` from
`POKEMON_RL_ENCODER_V2` / `POKEMON_RL_ENCODER_IDS`, and VOID (e) (draft:203-204) requires
both to be `"1"`. `.env` contains only `PS_USERNAME` and `PS_PASSWORD`;
`ladder_supervise.sh` exports nothing (unlike `ch5_100m_offfp_wave.sh:42` and eight sibling
runners, which all `export POKEMON_RL_ENCODER_V2=1`). So `source .env &&
scripts/ladder_supervise.sh …` launches at OBS_DIM 612 against an 828-dim checkpoint. It
fails loudly rather than silently — but under the supervisor it fails *repeatedly*, burning
`MAX_NOPROGRESS=12` relaunches and back-offs before anyone reads a log. R3 got away with it
by hand. Fix: put `POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1` into LG-3 (or into
`ladder_supervise.sh` as a fifth build item) and into the handed-over command block.

**F18 — SHOULD-FIX. BI-R4-1 is "blocking" in one place and waivable in another.**

> draft:291-293 — `BACKUP: backup_ladder.sh RUNS gains "R4G:replays_r4" (BI-R4-1,
> blocking — without it the verification says nothing about R4)`
> draft:270 — `LG-8 BI-R4-1..4 landed or waived in writing with fallbacks`

LG-8 licenses waiving the item that draft:291 declares unwaivable. Given that the
replay-built band table (obligation iv/vii) is the only exhaustive source for the licensed
cell, an unverified replay copy is the failure mode R1's BI-4 correction existed for. Fix:
"LG-8 BI-R4-2..4 landed or waived in writing with named fallbacks; **BI-R4-1 is blocking
and may not be waived**." And name each fallback, as R3 did at `ladder_r3.yaml:930`
(BI-4's fallback is written out there; R4's four have none).

**F19 — SHOULD-FIX. Five of the nine maintainer markers are not complete decision
statements, and M4's unrecommended branch deadlocks against the one-run rule.**

Audited against "options + recommendation + what binds on each branch":

| marker | options | recommendation | branch bindings |
|---|---|---|---|
| M1 (:69-72) | yes/no | NO re-score | **both** (override → branch R-a, pre-committed) — COMPLETE |
| M2 (:120) | one only ("ratify as drafted") | as drafted | none if declined |
| M3 (:181-183) | none/declared box | NONE | partial — see below |
| M4 (:25-27) | yes implied | YES | **no NO branch** |
| M5 (:256-257) | text/channel given; **send time blank** | mem_B §4 + Help room | none |
| M6 (:258-262) | one only (bot3) | bot3 | none if a non-linked name is chosen |
| M7 (:249) | **bare marker, no sentence** | — | — |
| M8 (:273-276) | one only | as drafted | none |
| M9 (:270) | "landed or waived" | — | fallbacks not named (see F18) |

Two of these have teeth. **M4:** if the maintainer rules NO, a VOID/INCOMPLETE run does not
discharge step 2, while draft:189-192's one-run rule bars a second attempt without a new
pre-reg — step 2 becomes undischargeable by this pre-reg, which is a deadlock the draft
does not acknowledge. **M3:** the recommended-against branch is under-specified — if a
wall-clock box fires at n=150 with rd 45, the run stopped licensed but off-protocol, and
draft:94-97 licenses only the read "at the stopping rule". Fix: give M2/M6/M7/M8 an explicit
alternative and what binds under it; give M5 a recommended send time; state M4's NO branch
("then step 2 remains open and a re-run requires a new pre-reg, a fourth account and a
second courtesy note — the cost the one-run rule is pricing"); and state that a run stopped
under M3's box reports as INCOMPLETE per F3.

**F20 — SHOULD-FIX. The entire provenance chain the draft cites is gitignored, and M5
binds the courtesy note by reference to an untracked file.**

> draft:11-15 — `shared brief results/design_ladder_r4/BRIEF.md; independent memos
> mem_A.md … synthesis_r4.md`
> draft:256-257 — `M5: the note text (mem_B §4 draft), …`

`git check-ignore -v` resolves all of these to `.gitignore:20  results/*`, and
`git ls-files results/design_ladder_r4/` is empty. `ladder_r3.yaml` handled this by
inlining its rulings; `readouts/` is the repo's committed-provenance convention (draft:215
even says "readout is the committed provenance"). A ratified pre-reg whose six adjudications
and whose *sent text of a public communication* live only in gitignored files has no
provenance after the next `rm -rf results/`. Fix: either un-ignore
`results/design_ladder_r4/` (precedent: `.gitignore:22-31` already carve out four
`design_*` directories) or inline the note text at `readouts/LADDER_R4_COURTESY_NOTE.md`
— which draft:251-253 already requires to be tracked — and make M5 point there.

**F21 — SHOULD-FIX. The credit line is not restated verbatim.**

> draft:83-86 — `THIS RUN CREDITS NOTHING. No A/B, no control, no paired comparator, no
> se_diff, no 0.025 bar.`

CLAUDE.md: "**Credit line:** … **The header must restate this verbatim, including the
larger-of (binomial vs seed-clustered) se_diff clause.**" R3 discharged this while making
the same not-applicable point, in a dedicated key
(`ladder_r3.yaml:907 credit_line_not_applicable`, which quotes the line in full and then
says describing any R3 number as credited is a category error). The draft asserts the
conclusion without the text. Fix: add `credit_line_not_applicable:` copying
`ladder_r3.yaml:907` with "R3" → "R4".

**F22 — SHOULD-FIX. The barred-language list is called grep-enforceable but exists only in
a comment.**

> draft:134-135 — `BARRED LANGUAGE (grep-enforceable, carries R3's list with "R1" read as
> "any prior run", plus): …`

`ladder_r3.yaml:915` is a real YAML key `barred_language: [...]`. The draft's list is
prose inside `#` comments, so nothing can load it; draft:310 then bars amending "the
barred-language list", and draft:227 promises a test that greps committed docs. Also
"carries R3's list with 'R1' read as 'any prior run'" leaves the substitution to the
reader — R3's list contains "better than R1", "worse than R1", "50M beats 12M on the
ladder" and "any arithmetic difference between R1's and R3's GXE, Glicko or Elo presented
as a quantity", each of which needs a decided R4 form. Fix: add `barred_language:` as a
key with R3's entries **expanded** for three runs plus the draft's eleven new ones.

**F23 — SHOULD-FIX. Confound 3 undercounts the recipe deltas, and the "NOT a confound"
timer line is quotable to dismiss the one it omits.**

> draft:152-154 — `3 TRAINING RECIPE (stack50m_r2 -> batch+async+100M-anneal, three
> bundled deltas, one credited, one P3, one G9-nulled);`
> draft:166-167 — `NOT a confound, stated so nobody "fixes" it: /timer on — the ladder
> seat has sent it since R1 (pacing.start_timer, both prior pre-regs).`

The seat-side claim is correct and verified (`ladder_r1.yaml:260`, `ladder_r3.yaml:833`,
`ladder.py:694`). But there is a **second, distinct** timer change: the training-side fix
`9a0e54d`, which `RESULTS.md:1233` records as "post-dates the 50M control's training" and
which G9 tested *jointly* with the async collector. R3's object (`stack50m_r2` s80) trained
before it; R4's object after it. So the recipe bundle is four deltas, not three, and
draft:166's flat "the timer … NOT a confound" is exactly the sentence someone quotes to
avoid listing the fourth. Fix: "four bundled deltas (batch — credited; async wire —
G9-nulled jointly with the timer fix; the training-side `/timer on` fix 9a0e54d, which
post-dates R3's object; 100M horizon+anneal — P3)", and narrow draft:166 to "the **ladder
seat's** `/timer on` is not a confound; the **training-side** timer fix is, and it is
inside confound 3."

**F24 — SHOULD-FIX. The readout's cross-run columns are neither in the licensed list nor
under the CONFOUNDED heading.**

> draft:97-98 — `the replay-built band table with sum(cell n) == n_jsonl asserted;`
> draft:131-133 — `**any three-run figure, plot or fitted line** — multi-run numbers appear
> ONLY as columns in a table headed CONFOUNDED — NOT AN EFFECT`
> draft:163-165 — `the rematch cell reads against R1, not R3;`

`scripts/ladder_readout.py` emits, by construction, an `R1 (n, rate)` column inside the
band table (see both readouts, obligation iv), an opponent-overlap cell against the other
run (obligation v), and a game-category table "beside R1's" — and BI-R4-2 adds a second
prior. Those are multi-run numbers inside tables the licensed list treats as R4's own
secondaries, so as drafted the CONFOUNDED heading requirement applies to a table nobody
will build and not to the three that exist. Draft:163's "reads against R1" makes it worse:
it licenses a specific cross-run reference that the licensed list (draft:94-110) does not
contain and draft:89-91 bars in general. Fix: name the three generated cross-run artifacts
explicitly in the licensed list, and require the CONFOUNDED — NOT AN EFFECT heading and the
ten-confound list on each of them, including the rematch comparison.

**F25 — SHOULD-FIX. M2's second branch strikes the rank-500 clause but keeps the ~0.50
reference whose only justification was rank-500.**

> draft:116-118 — `the cell is still reported for continuity but the rank-500 clause is
> STRUCK, the cell becomes purely descriptive`
> draft:99 — `the [1300,1400) cell, one-sided upward against ~0.50`

`RESULTS.md:978-980` derives ~0.50 as "the rate holding rank 500 requires, since rank 500
lives in that band". Strike rank-500 and ~0.50 is an unargued round number that a reader
will treat as a null hypothesis. Fix: in branch 2, drop the "one-sided upward against
~0.50" framing too — report the cell as a rate with its n and binomial se and no reference
at all, which is what "purely descriptive" should mean.

**F26 — SHOULD-FIX. "2*se_diff at matched n is ~0.195" is carried as though it applies to
R4's cell, whose n is unknown by the draft's own admission.**

> draft:100-102 — `2*se_diff at matched n is ~0.195 — this cell resolves only what needs
> no statistics; its n is set by matchmaking, not by us;`

~0.195 corresponds to matched n ≈ 52-53 per arm at p = 0.5; the actual references are
n=47 (R1) and n=36 (R3), whose se_diff is 0.107, i.e. 2·se_diff = **0.215**. The figure is
carried verbatim from both readouts, so it is not a new error — but stating it as a
property of R4's yet-unplayed cell is. Fix: "2·se_diff is ~0.20 at the n's these cells
have run at (0.215 for R1's 47 vs R3's 36); it will be recomputed at R4's realized n and
is illustrative only."

**F27 — SHOULD-FIX. The ratification recipe omits the string the test requires.**

> draft:6-9 — `The ratifying commit `git mv`s it to configs/eval/ladder_r4.yaml, clears the
> markers, and records rulings in ratified_decisions at the foot.`

`tests/test_ladder.py:560-561` asserts both `not re.findall(r"<< MAINTAINER \d+ >>", raw)`
**and** `"Status: RATIFIED" in raw`. A ratifier following draft:6-9 literally does the mv,
clears the markers, adds `ratified_decisions`, and leaves line 3 reading "Status: DRAFT" —
red suite, at the one moment CLAUDE.md's "end every session green" is most inconvenient.
Fix: "…, **replaces line 3's `Status: DRAFT …` with `Status: RATIFIED`** (asserted by
tests/test_ladder.py:561), clears the markers, and records rulings…".

**F28 — SHOULD-FIX. Three of the four `expected_instrument_values` bands name no estimator
and carry no action on breach.**

> draft:357-361 — `sec_per_battle_band: [190, 300]` … `mean_turns_band: [18, 32]`

Obligation (ix) (draft:230-232) requires s/battle "three ways (whole-run mean, median,
median excl. gaps>900s)". The band applies to which? R3's whole-run mean was **277.5** and
its median 218.0; a merely R3-like outage tail pushes the whole-run mean past 300 while the
median sits comfortably mid-band. And unlike (e), no consequence is attached to any of the
three bands — the block's stated purpose ("pre-stated so a silent wrong-object run is
visible") gives no rule for what a visible breach licenses. Fix: name the estimator
(`sec_per_battle_band` applies to the **median excluding gaps > 900 s**) and add one line:
"bands other than `mean_decision_ms_band` are DIAGNOSTIC — a breach is disclosed in the
readout and voids nothing."

**F29 — SHOULD-FIX. The profile-unreachable procedure is said to "carry" but only one of
its three clauses is present.**

> draft:179-180 — `Profile-unreachable procedure carries: a hand pull showing rd<=40 at
> n>=200 satisfies the rule.`

`ladder_r3.yaml:376-386` has three steps; the draft reproduces only (2) and drops (1)
"hand-pull the profile" and, more importantly, (3) "**If the hand pull ALSO fails, stop at
the next battle boundary and wait — do not burn rated games you cannot evaluate**". Without
(3) the pre-registered response to a dead endpoint at n=205 is to keep playing rated games
toward `max_battles_total`. Fix: cite `ladder_r3.yaml:376-386` and carry all three steps.

**F30 — SHOULD-FIX. The mandated BC-clone quote drops its mandatory disclosure.**

> draft:53-54 — `"BC-clone 0.930 (lane s112; fleet pooled 0.9233, n=3x500)".`

CLAUDE.md's anchor battery: "**Match the policy form to the rating you compare against —
a clone number is never style evidence.**" `RESULTS.md:1213` carries it on the same number.
The off-FP quote at draft:51-53 carries both of its standing disclosures; the clone quote
carries none. Fix: append "; a clone number is never style evidence" to the mandated
BC-clone quote form.

**F31 — SHOULD-FIX. What to do at `max_battles_total` with rd still above 40 is dropped.**

> draft:171 — `max_battles_total 300.`

`ladder_r3.yaml:337-341`: "If 300 is reached with rd still above 40, **STOP AND REPORT with
n and the observed rd stated. Do not extend** — a fleet whose rd will not converge in 300
rated games is saying something structural, and the response is to think, not to grind 700
more games." The stop itself is licensed (stop 2), but the reporting obligation and the
explicit no-extend are gone, and the licensed-read list (draft:94-97) reads the profile
"at the stopping rule" — which was never satisfied in this branch. Fix: carry
`ladder_r3.yaml:337-341` and say the read reports as INCOMPLETE per F3 with n and observed
rd stated.

---

## Count

**31 findings: 10 MUST-FIX (F1-F10), 21 SHOULD-FIX (F11-F31).**

Highest leverage, if only a few are taken: **F4** (a live optional-stopping path the bars
do not catch), **F3** (INCOMPLETE undefined while M4 leans on it), **F2** (a VOID discovery
is currently an unlicensed stop), **F1** (a wrong published number the ratified file would
freeze), **F8** (a bare readout command publishes R1's numbers as R4's).
