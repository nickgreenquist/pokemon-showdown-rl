# mem_A — LADDER R4 pre-reg, MEASUREMENT-VALIDITY framing

Designer A, 2026-09-04. Independent of mem_B. Recommendations only; `<< MAINTAINER n >>` marks a suggested ruling. Object and lane are settled (BRIEF.md:16-28) and not re-opened.

**Verdict.** R4 is validity-cheaper than R3 in three ways (complete anchor battery, a selection rule that is unbiased by construction, no search seat) and validity-*dearer* in four the brief does not name: the selected lane is the fleet **argmax on both descriptive anchors**; greedy is the most memorisation-exposed policy form of the three runs; three runs invite a trend that does not exist; and the licensed band may no longer contain rank 500.

## 1. What R4 may claim — central ruling, decided result-blind

Carry ladder_r3.yaml:154-155 re-scoped: **R4 IS A STANDALONE DESCRIPTIVE MEASUREMENT. NO R1/R3/R4 DELTA MAY BE QUOTED AS AN EFFECT, IN ANY DIRECTION, BETWEEN ANY PAIR OR ACROSS ALL THREE.** "THIS RUN CREDITS NOTHING" travels (ladder_r3.yaml:97-101; RESULTS.md:822-825).

LICENSED, and this is the whole list: the server-computed GXE/Glicko-1/Elo off the profile at the stopping rule, with n, policy kind, lane, selection rule and same-day board position (ladder_r3.yaml:388-392); the replay-built band table with `sum(cell n) == n` asserted (ladder_r3.yaml:526-536); the [1300,1400) cell one-sided upward against ~0.50, no threshold (§4); every secondary at ladder_r3.yaml:396-399; and **one genuinely new sentence** — R4 is the first ladder measurement in this project whose object carries **all three anchors at locked protocols** (BRIEF.md:31-35; contrast readouts/LADDER_R3_READOUT.md:150-152, "ONE of three"). That is a claim about the *record*, never about the rating, and may not be phrased as strengthening it.

BARRED whatever the numbers say: anything about the 100M horizon (P3 is **not credited**, RESULTS.md:1163-1170); anything about greedy-vs-search on humans (R4S66 is dose M off FP@20 on **batch-50M lane s66** — a different lane, recipe and opponent: SESSION_LOGS.md:9861-9866, configs/eval/ch5_r2_offsh.yaml:609-614; search@M on a 100M lane was never measured, BRIEF.md:23-25); 100M-vs-50M or greedy-vs-ensemble on the board; any projection between a ladder number and a vs-SH or off-FP number in either direction (RESULTS.md:830-831, 1128).

**New barred item the brief missed — the (proxy, ladder) mapping.** R4 gives this repo its THIRD (off-FP@20, ladder rating) pair: C0/L2 0.3893 ↔ Elo 1292 (SESSION_LOGS.md:8466-8468), RS80 0.4390 ↔ Elo 1232 (SESSION_LOGS.md:8548; RESULTS.md:905-909), t112 0.50167 ↔ R4. The first two already run the "wrong" way — higher proxy, lower final Elo. Three points at k=1 each are not a calibration; fitting or eyeballing one is the retired 40%-GXE conversion in new clothes. Bar it by name: the temptation is larger now than when the rule was written.

## 2. Q6 and the median lane — recommend NO RE-SCORE, argued

Q6 (SESSION_LOGS.md:8463-8465): *"the selected object is RE-SCORED FRESH at n=3000; the selection score is not the published score."* It earned its keep on 2026-08-28 — argmax over m=5 at n=1000 gave 0.4470, the fresh n=3000 gave 0.4390, the winner's-curse direction, and publishing 0.4470 would have overstated the object (SESSION_LOGS.md:8556-8561).

**Three conditions made Q6 bite there; R4 satisfies none.**
1. *argmax, m=5.* R4's rule is the **median of k=3** (BRIEF.md:19-22). E[max of k] is upward-biased by construction; the median of three exchangeable draws is not. The rule was chosen for exactly this reason, on the record before any ladder object existed.
2. *Selection n ≠ publication n.* There: n=1000 selection against an n=3000 protocol. Here the selection statistic **is** the published number — n=3000, locked protocol, greedy seat, serial k=1 (configs/showdown_sp_100m.yaml:129-140), published at RESULTS.md:1153-1160.
3. *The selection score would have been the published score.* Here it would not: R4's primary read is GXE/Glicko off the profile. The off-FP number is an **anchor**, and anchors are descriptive, never verdict inputs (CLAUDE.md).

A fourth, stronger point: the median-lane statistic was itself **pre-registered result-blind** — configs/showdown_sp_100m.yaml:131-133, *"per-lane median (k=3: the median IS one lane), best/worst lane and per-lane deltas are RECORDED and NEVER govern."* The number a re-score would replace was declared recorded-and-non-governing before the fleet launched. That is the condition Q6 exists to create.

**The residual, named rather than waved away.** Conditioning on "this lane's observed score was the middle of three" is not a null conditioning: it shrinks the selected lane's observed score toward the fleet centre relative to its own true θ. Unlike argmax, **the sign is unknown**, and the magnitude sits under the instrument's own re-draw spread — three re-draws of ONE checkpoint spread 0.0200 (CLAUDE.md landmine). Put that sentence in the pre-reg; do not claim the estimate is unconditioned.

**RECOMMEND: no re-score.** Discharge Q6 with an explicit written finding rather than silence — silence reads as an oversight in six months — and with the *positive* obligation in §3, which is where the real risk lives.

**If re-scored anyway** (cheap: t112 ran 3000 battles in 4651.8 s = 1.29 h, results/ch5_100m/t112.json), the re-score is a validity *cost* unless its use is pre-committed: two legitimate n=3000 numbers for one object, no aggregator, on an instrument whose re-draw spread is 0.0200. Pre-commit one branch **before it runs**: (R-a) the fresh score REPLACES 0.50167 as the anchor; (R-b) pool to n=6000; (R-c) both reported, neither replaces. Recommend **R-a** — the only branch that cannot be gamed by looking. **BARRED: choosing after seeing the fresh number.** `<< MAINTAINER 1 >>`

## 3. Trap the brief missed: s112 is the fleet ARGMAX on both anchors

The brief treats the complete battery as closed (BRIEF.md:31-35). It is not:

| anchor | s104 | **s112** | s120 | pooled | source |
|---|---|---|---|---|---|
| off-FP@20 (primary) | 0.48633 | **0.50167** | 0.50733 | 0.49844 | RESULTS.md:1153-1160 |
| vs-SH (secondary) | 0.7913 | **0.8000** | 0.7967 | 0.79589 | RESULTS.md:1179 |
| BC-clone h2h | 0.912 | **0.930** | 0.928 | 0.9233 | RESULTS.md:1212-1213 |

The lane selected as the **median** on the primary is the **maximum of three** on both descriptive anchors. Not misconduct — the rule was pre-committed and orthogonal to those axes — but the battery as quoted for the ladder object sits at the flattering end of a ±0.02 instrument on both, and "0.8000 vs SH" will read as *the project's best number* the moment it leaves this file (one vs-SH rung is worth ±0.02, CLAUDE.md).

**MANDATORY in the pre-reg and every quote:** each anchor is quoted as the pair {lane value, fleet pooled value} with the selection rule named — "vs-SH 0.8000 (lane s112; fleet pooled 0.79589, n=3×3000)". Plus one standing sentence: *"s112 is the lane a pre-committed median-on-off-FP@20 rule named. It is not the best 100M lane and may not be described as one; that it is the highest-scoring of the three on both descriptive anchors is incidental to a selection made on a different axis."* Exact analogue of ladder_r3.yaml:73-76 for s80, owed for the same reason.

## 4. Licensed comparison cells and references

**Carry [1300,1400); add nothing.** Only cell with a common externally-fixed reference (ladder_r3.yaml:181-189). References printed, never subtracted: R1 **0.319 (n=47)** — the BI-4 replay-built corrected value (readouts/LADDER_R1_READOUT.md:81; ladder_r3.yaml:954-967), **never the published 0.340** — and R3 **0.444 (n=36)** (readouts/LADDER_R3_READOUT.md:84). No threshold attaches in any of the three, and none may be added later (ladder_r3.yaml:194-195); 2·se_diff at matched n is ~0.195, about twenty points of win rate.

**Trap the brief missed — the reference may have moved.** The cell's licence is "the band containing rank 500". Admission was Elo ~1359 on the R1/R3 pulls (readouts/LADDER_R1_READOUT.md:14; LADDER_R3_READOUT.md:14) — inside the band by 41 points, and set by the field's activity, not by us (RESULTS.md:1001-1007). Pre-register **both branches now**: pull and **archive** the cutoff at n=0 and again at stop, alongside the profile pulls (ladder_r3.yaml:481-484); if the n=0 cutoff is inside [1300,1400) the reference sentence stands; if outside, [1300,1400) is still reported for continuity with R1/R3 but the "band containing rank 500" clause is **struck** and the cell becomes purely descriptive, with the band containing the cutoff reported beside it, also with no reference and no threshold. The referenced band is never silently re-based — that breaks the commensurability that is the cell's only reason to exist. `<< MAINTAINER 2 >>`

**Disagreement with the brief (item 5).** Carry R1/R3 cells as *columns in the band table*, which the generator already emits (readouts/LADDER_R3_READOUT.md:79-85) — but with three runs, side-by-side printing is precisely what manufactures a trend. Require the **CONFOUNDED — NOT AN EFFECT** heading (ladder_r3.yaml:211-214) with the confound list adjacent on any table showing more than one run, and **bar any three-run figure or plot outright**. A line through three points is a claim; a table with a heading is a reference.

## 5. Headline sentence — fixed now, before any battle

> "Playing the real `gen1randombattle` ladder from a fresh rated account, the 100M final on lane s112 — 100M steps, pure self-play, greedy/deterministic, the lane a pre-committed MEDIAN-of-three rule named on the off-Foul-Play@20 primary — reached GXE X%, Glicko-1 Y ± RD and final Elo Z over n rated battles (server record W–L) against D distinct opponents. Against the 1300–1400 band — the band containing rank 500 on the same-day pull — it scored V (n=k). This run credits nothing."

Three deliberate changes from ladder_r3.yaml:197-202: (1) **the selection rule is inside the headline** — "the 100M final" invites "our best model", and the median clause is the only thing that stops it; (2) **"server record W–L"**, not the runner tally (§7); (3) **the band clause is conditioned on the same-day pull** (§4). The s112-is-not-the-best sentence (§3) is required adjacent, not by reference.

## 6. Stopping rule and n — carry `rd <= 40 AND n >= 200` unchanged

1. **Commensurability.** n=200 is what makes three runs comparable at all (ladder_r3.yaml:325-329); moving it either way spends the only thing they share.
2. **More n buys the licensed read nothing.** No threshold attaches to [1300,1400) (ladder_r3.yaml:194-195), so power is power for a test that does not exist. The binding limit is **cell** n, set by matchmaking, and no n this design can buy fixes it. *(Disagreement with brief item 1: this is the wrong axis to look for improvement on.)*
3. **rd is not the binding half** — it extrapolates to ≤40 by n≈88 (ladder_r3.yaml:333-336); R1 read 26.6, R3 25.4 at n=200. The floor binds.
4. **n is the footprint, and footprint is the etiquette argument** (ladder_r3.yaml:703, 826-829). Keep `max_battles_total: 300`.
5. **Greedy is cheaper per battle** (t112 mean turns 28.403 off FP@20 vs search s80's 36.824; ×0.944 → ~26.8 vs humans, near R1's 25.9). The right response to a cheaper battle is a **shorter run**, not a bigger one. Cost must not set n.

G-BLIND carries verbatim, four licensed stops (ladder_r3.yaml:366-369). **One addition to settle now rather than at 4am:** a wall-clock box ("stop by noon") is **not** among the four, so using one trips VOID (g). If wanted, add it before launch as a fifth licensed stop with its clock time declared, and report n and rd at that stop. `<< MAINTAINER 3 >>`

**Blind-breach licence the brief missed.** The courtesy note creates a new breach path: a staff reply plausibly sends the operator to the account page mid-run. Pre-license it — *answering staff contact may require opening the profile; doing so is a licensed operational view, logged with the battle index and reason, and changes no stopping decision because the rule is mechanical.* Strictly better than R3's two after-the-fact breach disclosures (readouts/LADDER_R3_READOUT.md:139-148).

## 7. Readout mechanics — the 106-102 lesson, correctly diagnosed

**Disagreement with the brief (item 6).** The readout was **right**: readouts/LADDER_R3_READOUT.md:137 states the profile's 106-102 (208 rated), the JSONL's 106-94 (200), the eight server-side losses from our dead sockets, and that the primary rating includes them. The failure was **propagation** — STATUS.md:50 still carries the unreconciled pair four days on, and the brief inherits it as an open RECONCILE item. A better table does not fix a propagation failure.

**(vii) NEW — RECORD RECONCILIATION, machine-checked.** At stop assert `profile_w + profile_l + profile_t == jsonl_rows`. On failure the readout does not pass silently: it emits a mandatory block naming the gap, its sign and its cause. Classification instrument: pull the account's server-side replay index at stop and diff against `save_replays` — the difference set **names** the unlogged games. If it cannot be built, the block says the gap is unclassified. (R3's gap was diagnosed by argument; a diff makes it evidence.)

**(viii) NEW — PROPAGATION RULE, with a test.** Every downstream quote — STATUS, README, RESULTS, session logs, commit messages — takes the record from the readout's headline row, and **that row is the PROFILE record**. The runner tally is always labelled `runner-logged subset (n_jsonl)`. Add a test in `tests/test_ladder.py` that greps committed docs for a W–L pair attached to a ladder run and fails if it is not the readout's headline pair. Mechanical, and the only thing that would have caught R3's drift.

**Three denominators, named in this order, every time:** `n_profile` (rating basis), `n_jsonl` (all descriptive rates and the band table), `n_played` (ratified cut, ladder_r3.yaml:508-525). The band table asserts against `n_jsonl`, never `n_profile` — pre-state this or the assert becomes the next false alarm.

**Instrument fixes owed** (licensed post-ratification edits, §9):
- `scripts/ladder_readout.py:116` `--compare-jsonl` is **single-valued**. With two priors, "opponents faced only in this run" would count R1's opponents as new. Extend to repeated flags; report pairwise (R4∩R1, R4∩R3) and the union. A correctness bug at R4, not a nicety.
- `scripts/backup_ladder.sh` verification is hardcoded per-run (ladder_r3.yaml:929). Extend to `R4G.battles.jsonl` / `replays_r4` **before launch** — the data is unrepeatable and gitignored, and the 3-copy rule is standing.
- All three readout scripts **default to R1** (ladder_r3.yaml:934): pass every flag; a bare run yields a plausible readout of the wrong account.
- Share `results/ladder/` as the root, arm id `R4G` (ladder_r3.yaml:808-822 — backup takes that root wholesale).
- Preserve hand-written correction appendices on regeneration (readouts/LADDER_R1_READOUT.md:152-170).

Record plan: R4 lands as **§16.5**, §16.3 re-scoped to three runs, §16.4 unchanged; README row in the same commit as the readout (battery complete, so R3's D4 deferral does not recur); STATUS quotes the profile record only.

## 8. The confounds list, R3 → R4 — it is ten, not seven

Print all of them adjacent to any multi-run table, and say the count is not the point.

1. **POLICY KIND** — single lane + search@M → single lane **greedy** (search removed).
2. **TRAINING SCALE** — 50M → 100M.
3. **TRAINING RECIPE** — `stack50m_r2` → batch (credited, RESULTS §17) + async collector + 100M horizon (P3, not credited, §18): three bundled deltas.
4. **ACCOUNT** — a third fresh account, a third path-dependent transient from Elo 1000.
5. **CALENDAR + POOL** — 2026-08-27/28 → 2026-09-xx on a board of ~93 players/day (ladder_r3.yaml:981).
6. **OPPONENT MEMORY** — two linked accounts, ~400 rated games, 141+116 humans (readouts/LADDER_R3_READOUT.md:155-156); R4 adds a third linked name.
7. **INSTRUMENTATION / OPS** — R3 took 10 runner launches, 8 SIGKILLs and 8 unlogged server-side losses (readouts/LADDER_R3_READOUT.md:128-137); R4 is expected clean. That changes **what the rating measures**, not only its precision.
8. **SELECTION RULE** — R3's lane came from a vs-SH tie-break (ladder_r3.yaml:69-76); R4's from an off-FP@20 median. Different statistics, different biases.
9. **COURTESY NOTE** — R4 is the first run played after staff contact; if staff act on it, the account's environment differs from R1's and R3's.
10. **DETERMINISM / REPLAYABILITY** — R3's search RNG was keyed on `(checkpoint_seed, battle_index, turn, decision_index)`, so the same state at a different battle index could produce a different action, making R3 *less* replayable than R1 (ladder_r3.yaml:495-505). **R4 greedy is fully state-determined**, so R4 is the **most** memorisation-exposed of the three. Pre-stated consequence: R4's rematch cell reads against **R1**, not R3, and the rating-matching confound still predicts a lower rematch rate with zero memorisation — opponent-Elo columns first, always (ladder_r3.yaml:487-494).

**NOT a confound — stated so nobody adds it or "fixes" it:** the 2026-08-31 `/timer on` change touched the training and eval seats. The ladder seat has sent `/timer on` since R1 (`scripts/ladder.py:694` reads `pacing.start_timer`, default true at scripts/ladder.py:480; both prior pre-regs set it — ladder_r1.yaml:260, ladder_r3.yaml:833).

VOID conditions carry (ladder_r3.yaml:600-650) with three edits: **(d)/(f) now span THREE project accounts**; **(e)** reads `kind=greedy, lane=s112, sha256=2ec16fbf…, obs_dim=828, encoder_v2="1", encoder_ids="1"` (obs_dim confirmed 828 on the 100M lanes — results/ch5_100m/t112.json `process_obs_dim`); and **the LG4 decision-ms tell INVERTS**. For R3, ~7 ms meant search was not running (ladder_r3.yaml:921); for R4, ~ms **is** correct. Pre-state `mean_decision_ms_band: [1, 15]` (R1's four-lane ensemble was 6.74; a single lane should be at or under that) and treat **≥ 30 ms as the failure** — a search wrapper got in, or the wrong arm loaded. Writing that band the wrong way round is the cheapest way to ladder the wrong object.

## 9. Amendment licensing and the one-run rule

**Licensed post-ratification**, each committed before it takes effect with a one-line reason (R3 precedent: BI-4 waived at launch, owed at readout — ladder_r3.yaml:930): readout/analysis instruments and their tests; backup verification lines; board and profile *pulls* (data, not decisions); the courtesy-note text until sent; resume relaunches with the same `--battles`; operational parameters appearing nowhere in the READ.

**Barred after ratification:** object, lane, sha, policy kind; the stopping rule and both constants; `max_battles_total` (downward at any time, upward after the first rated battle); the licensed cell and its reference; the headline template; the barred-language list; the aggregators; the three denominators; the VOID conditions. The confound list may **grow, never shrink**. **Barred absolutely after the first rated battle:** anything in the READ.

**THE ONE-RUN RULE — the sharpest multiplicity control available.** R4 is one run. A VOID or INCOMPLETE read does **not** license a quiet re-run: that is optional stopping at the level of runs, and it needs a fourth rated account and a second courtesy note under D2's trigger (ladder_r3.yaml:1012-1013). Any second attempt is a new pre-reg and a new ruling. This meets JOURNEY step 2's exit condition — *"the run itself — not a rating"* (BRIEF.md:10-14) — and the interaction should be ruled, not assumed: **does a VOID/INCOMPLETE run discharge step 2?** My reading is yes, and it is the reading that keeps the exit condition honest: the step asks for the capture, and a captured failure is a capture. `<< MAINTAINER 4 >>`

## 10. Barred-language list for R4

Carry every entry of ladder_r3.yaml:915 with "R1" read as "any prior run", then add: "our best model" / "the best 100M lane" / "the strongest lane" / "greedy beats search on the ladder" / "search does not work on humans" / "100M beats 50M on the ladder" / "the 100M horizon helped" (P3 is not credited) / "trend" / "trajectory" / "third point in a series" / any three-run curve, figure or fitted line / any mapping between an off-FP or vs-SH score and a ladder rating in either direction / "credited" applied to any ladder number / "on track for top-500". PERMITTED, unchanged: a multi-row table headed **CONFOUNDED — NOT AN EFFECT** with the ten-way list adjacent, and the sentence "these are three measurements of three different objects at three different times on a non-stationary board."

## 11. Brief items 3 and 4 — the validity slice only (ops is mem_B's)

**Courtesy note.** Validity-relevant properties: it must not solicit anything quotable as endorsement, and it must go out far enough ahead (≥24 h) that a reply can arrive **before** rated games start. Pre-register three branches result-blind so none is decided under launch pressure: no reply → proceed as planned, and the readout discloses the note went unanswered; reply objecting → do not launch; reply with conditions → maintainer ruling. Content: purpose (research measurement), single serial seat, ~5 s between games, bounded n≈200 with a hard cap of 300, the account name, a contact address, and the standing commitment to stop at the next battle boundary on contact (ladder_r3.yaml:757-759). `<< MAINTAINER 5 >>`

**Account.** Keep the **linked stem** (`nickgen1rbrlbot3`). Two validity reasons beyond transparency (ladder_r3.yaml:751-755): obligation (v) *depends* on the pool being identifiable as one that has met this project — an unlinked name would silently destroy the measurement it exists to make — and identity is now enforced in code rather than by the name (`_resolve_display_name` SystemExits on a disagreeing `PS_USERNAME`, ladder_r3.yaml:783-790). Registration is the maintainer's act; VOID (d)'s `ratings: {}` check runs before launch.

## 12. Maintainer markers, collected

1. Q6 re-score of s112's off-FP anchor: **NO** (recommended) / YES under R-a.
2. The two-branch admission-cutoff rule for the licensed band.
3. A fifth licensed stop (declared wall-clock box): none / a stated time.
4. Does a VOID/INCOMPLETE R4 discharge JOURNEY step 2? (recommended: yes.)
5. Courtesy-note text, recipient and send time.
