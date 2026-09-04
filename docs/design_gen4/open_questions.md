# open_questions.md — every maintainer ruling the gen4 design needs, with a recommendation and the losing argument

> **design_gen4 status header.** Written 2026-09-04 on branch `gen4-design`,
> DOCS ONLY — nothing under `rl/` changed. **Arc position:** the target is
> JOURNEY step 3 (gen4 encoder + model). This design work is **maintainer-ruled
> PREPARATION running AHEAD of step 2 (gen1 ladder #3)**, written while ladder
> R4 is live; it is not a pre-registration and it launches nothing. **Read this
> file first**; the other four docs in this directory are its evidence.
>
> **Method, recorded honestly.** The brief asked for a parallel research sweep,
> two independent design memos plus an adversarial synthesis, and a completeness
> critic. What actually happened: three sweep attempts hit the usage limit (two
> with Fable agents, one with Opus agents in waves); ten of fourteen source-family
> notes landed; the maintainer ruled 2026-09-04 that the five docs be written by
> the session itself, sequentially, with no memo cycle and the four missing
> families kept as explicit deferrals (§7). The 2-Opus cycle is reserved for
> irreversible artifacts and these docs are free to rewrite; the house style
> (recommendation, losing argument, carried-to-ratification, refusal list) is
> kept, as one writer's adjudications. **No completeness-critic pass ran**;
> §8 lists the checks a reader should still make.
>
> **Verification status:** this doc makes no new factual claims; every item
> cites the doc and section that carries its evidence and tags. Where an item
> rests on a `[live]` check, that check is named there.
> **Sources:** `mechanics_delta.md`, `pokeenv_gen4_survey.md`,
> `encoder_requirements.md`, `anchors_and_eval.md` (this directory), and the
> project-record research note (`project_record.md`) for the standing rulings.

## 0. How to read this

- **Q-items** are rulings. Each has: the question; the recommendation in one
  sentence; the losing argument at full strength; what evidence would flip it.
- **D-items** (§7) are deferrals: source families the brief named that this cycle
  did not read. They are stated as "not read", not as findings.
- **M-items** (§9) are the merge checklist, including the SESSION_LOGS entry text
  and the one-line corrections owed to main-tree files that this docs-only branch
  did not touch.
- **R-items** (§10) are refusals: things this cycle deliberately does not decide.

## 1. Chapter-level rulings

**Q1 — Fresh net, or transfer from the gen1 final?** Recommendation: **fresh net**;
the gen4 encoder changes OBS_DIM (SpD, items, abilities, global state —
`encoder_requirements.md` §0), so a gen1 checkpoint cannot load; JOURNEY's standing
note "weights never transfer between generations" is maintainer-authored intent
(not a ratified ruling — `project_record.md` §5.1) and the two external data
points agree (Wang's bootstrapping variant: no significant improvement; H&L's
fine-tuned agent lost 77/500 to its parent). Losing argument: a padded layout
keeping gen1's blocks as a prefix would let the shared parts (types, stats, moves)
warm-start, and it is the only cheap warm start the arc will ever have; recipe
transfer (JOURNEY step 8) is the whole point of the gen4 detour, so proving
weight transfer fails is itself a finding. Flips if: a padded-layout design shows
the gen4 vector can keep gen1's 828 as a prefix at acceptable cost.

**Q2 — Shared or per-gen action head?** Recommendation: **shared**; poke-env's space
is 10 through gen 5, the landed seam derives `n_actions` per format and its refusal
list does not name an action head at gen 4, and the pointer head scores exactly
6 + 4 entities (`encoder_requirements.md` §0, §6). Losing argument: building the
per-gen head now (gimmick slots as extra pointer entities) makes the gen9 chapter
free and keeps the gen4 spec from baking "10" into a second place. Flips if: gen9 is
pulled forward.

**Q3 — Does step 3 start before or after ladder #3?** Recommendation: **docs and
tape-free code may start once R4's readout is committed; anything touching the box
(gen4 tapes, the Foul Play gen4 build, smoke battles) waits for the ladder run to
end.** STATUS already says gen4 is off the ladder critical path. Losing argument:
JOURNEY orders step 2 before step 3 for a reason — the readout and its record are
the maintainer's attention, and code landing on main during a live rated run is
exactly the kind of collision the hard bars exist to prevent; the honest sequence
is R4 readout → merge this branch → gen4 code. Flips if: the readout slips by
days and the box is idle.

**Q4 — The gen4 chapter's written exit condition** (JOURNEY.md:68, still
unwritten). Recommendation: completion-shaped, like the 100M header's: "the step-5
offline read at the locked protocol against the pinned Wang target, the full anchor
battery, and one gen4 ladder run, all recorded — the chapter closes on the record
whatever the numbers say." Losing argument: a numeric exit ("matched" defined by a
bound) is what stops "close enough" from becoming a rationalisation; a
completion-shaped exit lets a bad number close the chapter quietly. Flips if: the
maintainer wants gen4 to be a gate on step 8 rather than a measurement.

**Q5 — The Wang target: 0.786 or ≈ 0.836, and what "matched" means.**
Recommendation: **pin Table 4.1's 0.786 as the exit bar, quote the Figure 4.1
endpoint ≈ 0.836 (peak ≈ 0.849) as the stretch, and define "matched" as the pooled
3 × 3000 final whose lower 2·se_gov bound reaches 0.786** (`anchors_and_eval.md`
§6, A3). Losing argument: "roughly 85 %" is the number he headlines and the one a
reader remembers; matching 0.786 reads as matching the weaker of his two numbers.
Disclosures that travel regardless: stock SH with the +1-boost bug on both sides
(comparable only if his harness was stock — the thesis does not say), SB3's PPO
implementation, his encoder and batch shape.

**Q6 — Wang's hyperparameters: copy the point, or copy with the batch shape?**
Recommendation: **copy Table A.3 as the starting config, state the batch shape
beside it (≈ 40k steps ≈ 1,600 seat-episodes per update; our async recipe is
30,720 steps ≈ 959 episodes, the same order), and hold λ = 0.754 as its own later
arm** — γ 0.9999 / λ 0.754 / 273 gradient steps per update is a coupled operating
point tuned by Bayesian optimisation on a 3v3 surrogate under SB3, not a recipe
(`wang_thesis.md` §12). JOURNEY's "he ran SB3 with its defaults" is wrong: the 13
values are tuned, the implementation is SB3's. Losing argument: JOURNEY says start
from his recipe, and a partial copy is a new guess with his name on it.

**Q7 — The 3v3 hyperparameter surrogate.** Recommendation: **not before the first
6v6 run**; Wang publishes no evidence the 3v3 optimum transfers (no 6v6 control, no
trial counts). Losing argument: it is the only affordable path to tuning this
project has ever had.

**Q8 — Both-seat harvest (CHAPTER5 A2) in the first gen4 run?** Recommendation:
**no** — one lever at a time; the chapter's first deliverable is the encoder's
number. Losing argument: Wang and H&L both harvested both seats, and the gen1
argument against ("gen1 is luck-heavy") weakens in gen4; the gen4 chapter is a
clean place to build it. Carried to the gen4 pre-reg.

## 2. Encoder rulings (`encoder_requirements.md` §10–11; each has its losing argument there)

**Q9** Species key: forme-id strings, pool-local (300 rows) — vs dex `num`
(stable, gen-independent, warm-startable; loses Rotom/Deoxys/Arceus formes). A1.
**Q10** `ID_SCALE` stays 256 (docstring's `[0,1)` invariant rewritten) — vs 512/1024
now, since gen9's 1025 forces it anyway. A2.
**Q11** Items and abilities as embedding ids + class bits (12 + 5) + reveal state —
vs pure ids (no hand taxonomy to be wrong) or one-hots on the actives only. A3.
**Q12** The v1 set prior: role-conditioned marginals from `sets.json` plus an item
rule table — vs a faithful port of the gen4 sampler (gen1's own standard: "the
marginals are NOT a heuristic"). A6.
**Q13** Counters as scaled scalars — vs Wang's k+2 one-hot durations (his validated
Markov-restoring form). A7. Related: HP scalar and raw PP rather than his bins and
cube root. A8.
**Q14** No temporal features in v1 (last move, history) — vs adding them now, at the
one moment OBS_DIM is changing anyway; carried to JOURNEY's Markovianity redesign.
A11.
**Q15** Clean break: new OBS_DIM, no gen1 loading — vs a padded layout (see Q1). A12.
**Q16** Spec selection by F-07's `encoder:` block `spec:` key with `spec_for_format`
as a cross-check — vs the landed `spec_for_format` alone. **This bundles the eight
unruled F-07 questions** (`docs/proposals/F07_encoder_config_block.md` §7): the gen4
chapter is the moment to rule them at once. A15.
**Q17** No damage-calc feature in v1 — vs building one, since nothing off the shelf
computes gen4 damage (poke-env's calc is gen1/2 and gen9 only). A16.
**Q18** Stealth Rock keeps a side-block slot and the pre-reg pins the Showdown commit
(59da482) — vs taking the vendored pool (no SR on any set) as the spec.
`mechanics_delta.md` §16 Q1.
**Q19** When gen4 tapes may be collected: **the gen4 bit-identity gate cannot exist
without them, and nothing else in the encoder can be trusted until it does** —
post-ladder, first thing. `encoder_requirements.md` §8.
**Q20** Whether the generated vocab tables are tracked in git (F-21's precedent:
tracked, borrowed content, ruling pending) or regenerated by a stamped script.
**Q21** Whether the 12-ability / 5-item class taxonomy is pre-registered as data or
left to the implementer.
**Q22** Roost and the live type list: read `mon.types` in the gen4 fill path only,
leaving GEN1's path untouched — vs applying it to gen1 too (harmless in play,
perturbs the hash gate). A9. **Q23** Substitute HP as a scalar. A10. **Q24** An
"indefinite weather" flag distinct from zero turns. `mechanics_delta.md` §16 Q6.
**Q25** The gen4 spec as its own module with data files — vs a second constant in
`encoder_spec.py`. A17.

## 3. poke-env rulings (`pokeenv_gen4_survey.md` §10)

**Q26** Wrap poke-env (a subclass in `rl/envs/` reading `_replay_data`), never fork —
the four gen4-live gaps Wang's fork fixed and 0.15.0 lacks (weather stamp,
Sleep-Talk double bump, `maybe_trapped`, item memory) are all wrapper-fixable and
the exact pin stays. Losing: a vendored patch set is the documented precedent
(foul-play), and upstreaming is the clean fix for the hand tables.
**Q27** `maybe_trapped`: encode a bit, keep the mask permissive, count rejections —
vs masking (the only choice that keeps the mask a true legality mask, the harness
contract; the retry loop shares the deadlock's coroutine).
**Q28** Weather duration: wrapper-tracked start turn + an indefinite flag — vs
presence-only or a patched `-weather` branch.
**Q29** Opponent stats: a parallel table in the encoder from the closed form — vs
mutating `Pokemon.stats`.
**Q30** `strict_battle_tracking=True` for a short bring-up fleet only.
**Q31** `/offertie` for gen4 collection — and whether a tie corrupts the reward.
**Q32** The `Return` base-power override (102; happiness is always 255 in randbats)
— vs leaving poke-env's 0.

## 4. Mechanics and protocol rulings (`mechanics_delta.md` §16; `anchors_and_eval.md` §5)

**Q33** The turn cap and tie rule: gen4 randbats has no Endless Battle Clause and
auto-ties at turn > 1000; ties are non-wins under the locked protocol.
Recommendation: an explicit per-battle turn budget for the collector and a
disclosed tie rate in every gen4 readout. Losing: the cap is rare enough to
disclose rather than design around.
**Q34** Whether the first gen4 fleet sizes n from its own R0 read rather than
inheriting 3 × 3000 (gen4 games are longer and the seed noise is unknown).
`anchors_and_eval.md` A6.

## 5. Anchor rulings (`anchors_and_eval.md` §9–10)

**Q35** Do not patch SimpleHeuristicsPlayer for gen4; disclose its defects (dead
setup branch, `stealhrock` typo, +1-boost bug, gen5+ multi-hit value, Return at 0,
Explosion at 250, no `maybe_trapped` guard) beside every gen4 vs-SH number — vs
patching (a straw opponent otherwise; but comparability with Wang and the gen1
ledger dies). A1.
**Q36** Build most-damage-typed before step 3, as JOURNEY schedules, and admit it as
a fourth **descriptive** leg — vs keeping the battery at the ruled three. A2. The
spec is `anchors_and_eval.md` §2; it costs a registry key and a test edit
(`tests/test_showdown_env.py:411` asserts the key list).
**Q37** Authorise the gen4 Foul Play: `make poke_engine GEN=gen4` in the foul-play
env (the installed engine is the gen1 build: 7 `src/gen1/` module paths, 0
`src/gen4/`), the network fetch of `gen4randombattle.json` from pkmn.github.io, its
pin and hash, and a diff against the vendored `sets.json` — all after the ladder
run. A4.
**Q38** Re-run the FP budget ladder (20 ms, 500 ms, n ≥ 250) in gen4 before pinning
a gen4 FP budget; the gen1 flatness finding is explicitly gen1-specific. A5.
**Q39** The BC-clone leg: rebuilt from a gen4 Foul Play after tapes exist, or
dropped for the chapter's first readout (§4 of the anchors doc).
**Q40** One ladder run (step 6): pin FP budget, engine commit, n, and greedy vs
searched first; one unauthenticated pull of the gen4RB board before the run.

## 6. Record hygiene (`project_record.md` §3.1, §5, §8)

**Q41** `IDEAS_POST_100M.md` §2.5 calls the +0.051 / +0.104 / +0.148 deltas "12M";
they are the CH5 R1-B **50M** lanes s80/s81/s82 off Foul Play@20 at n=1000.
Recommendation: a one-line correction at merge (M4).
**Q42** `JOURNEY.md:116` still cites the 0.072 bar that r9 corrected to 0.1007 — the
maintainer's own file; flag, do not edit.
**Q43** `prior_work/README.md`: ps-ppo's in-code comment on the +1-boost bug is wrong
in direction (+1 acts like +2, not +0), and "encoder-relevant fixes upstreamed by
0.15.0" needs the amendment "four are not" (`pokeenv_gen4_survey.md` §6).
**Q44** The searched endpoint of the search-depreciation curve does not exist (no
searched arm of any 100M lane). Pre-register a search@20 arm on the 100M final at
n=3000 off FP@20 (~2.6 h, eval-only, post-ladder), or ship the depreciation
write-up with an admitted hole. See D5.
**Q45** The IDEAS §1 re-rank under SS-CLIMB is owed and not done; gen4 sequencing
should not lean on "50M was enough in gen1".
**Q46** `scripts/make_bc_dataset.py`'s docstring still says 611-dim obs — stale.

## 7. Deferrals — source families the brief named that this cycle did NOT read

Stated plainly so nothing here is mistaken for covered.

**D1 — Wang's Showdown fork** (`prior_work/wang_fork_diffs.md` §1, lines 13–3408:
`>getstate`/`>load`, the constrained set regeneration, hallucinated-move disabling).
Covered only through the thesis's description and the index. What it would add: a
second source for a gen4 set prior and the exact set constraints his MCTS assumed.
Its importance dropped: the vendored pool is a curated table (≤ 3 sets per
species), not the 2023 procedural generator he sampled.

**D2 — ps-ppo and Metamon observation design** (`obs_abilities.py`, `obs_pokemon.py`,
`obs_global.py`, `obs_transitions.py`; the Metamon tokenisation appendix). Only
index-level facts were used (`encoder_requirements.md` §5). What it would add: how
the two largest pure-policy systems encode items, abilities and stat belief ranges
— the direct comparators for Q11 and Q29.

**D3 — A full foul-play / poke-engine / pokejax audit.** Replaced by the cheap subset
verified directly (`anchors_and_eval.md` §3: gen4 mechanics table present, gen1
engine build installed, set data fetched at runtime). Not done: the foul-play
search core's gen4 paths, its tests, and pokejax's bridge-bug list turned into an
audit checklist for our gen4 bridge.

**D4 — The literature cross-check** (Bulbapedia / Smogon vs the vendored sim). The
sim is the authority for what we run, so the docs lose nothing on that axis; the
cross-check would have flagged sim-vs-cartridge divergences. One such class was
found by accident (the gen4 sleep-reset question, resolved in `mechanics_delta.md`
§6 from `sim/dex.ts`), which is evidence the check has value.

**D5 — `search_depreciation.md`** (the optional stretch). Not written. Its data set
is assembled with provenance in the project-record note (§3): 12M vs-SH +0.069
(SH-facing only, MU-8 z = −2.80); 50M off-FP +0.101 within-lane, monotone in lane
weakness; 50M-batch off-FP −0.093 (~10 se, n-matched); 100M **unmeasured**. The
record's own critic diagnosis is "calibrated but low-resolution, residual aleatoric
plus decision-ordering", narrower than JOURNEY's "deficient value head". Ladder R4
already deployed greedy on R4S66's evidence, so the write-up no longer feeds a live
ruling; recommend writing it beside Q44's arm.

**D6 — The completeness-critic pass** the brief's method (c) required did not run.
§8 is the reader's substitute.

## 8. Checks a reader should still make (the critic pass this cycle could not afford)

1. Every `showdown/` line number in `mechanics_delta.md` came from one research
   note's read; numbers quoted only from the compiled `dist/` move table should be
   re-grepped in the `.ts` before entering a pre-reg (§17 there).
2. The vocab counts (295 / 181 / 101 / 40) are exact counts of the vendored files at
   59da482; re-run the two `jq` lines in the pool note if the server is ever bumped.
3. The Sleep-Talk double-bump (survey G3) is a code read; a parse-only replay
   settles it and needs no server.
4. `encoder_requirements.md` §4's widths are illustrative; nothing should quote them
   as a spec until the tuples are frozen in a pre-reg header.
5. Two cross-note disagreements were reconciled in the docs (item vocabulary 40 vs
   ≈ 26; the sleep reset) — a third reader should look for more, especially between
   the abilities note's set-derived counts and the battle-state note's dex-derived
   counts (101 assignable vs 122 possible; 277/295 unique-by-set vs 161/134
   auto-known-by-dex — both are stated as distinct facts, not conflicts).

## 9. Merge checklist

**M1 — Rebase.** The branch has only new files under `docs/design_gen4/` and is 62
commits behind main; the rebase is a pure fast-forward and was blocked here by the
tool classifier. Maintainer's zsh, from any directory:
<command>
```
git -C /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-gen4design rebase main
```
</command>
then merge or cherry-pick into main at the maintainer's discretion; nothing here
touches STATUS, SESSION_LOGS, HANDOFF, README or RESULTS.

**M2 — SESSION_LOGS entry text** (to append at merge; STATUS gains one line pointing
here under "Next actions"):

> 2026-09-04 (gen4-design worktree, docs-only, maintainer-ruled preparation ahead
> of step 2; written while ladder R4 ran) — **GEN4 DESIGN DOCS LANDED under
> `docs/design_gen4/`**: `mechanics_delta.md` (gen1→gen4 rules delta, tree-verified
> against the vendored 59da482 sim: per-move category, 17 types, items/abilities,
> hazards — Stealth Rock on no vendored set — weather indefinite from abilities,
> sleep 1–4 acting on wake and NOT resetting on switch, no Endless Battle Clause,
> turn-1000 auto-tie); `pokeenv_gen4_survey.md` (0.15.0 has no gen4 code path;
> action space 10; fifteen gaps incl. `maybe_trapped` ignored, weather stamp
> restamped every turn, Sleep-Talk double bump, no item memory, Return BP 0,
> Hidden Power num 237, 18-key chart, no opponent stats / ability / item tables /
> gen4 calc; Wang's fork diffed: 15 upstreamed, 1 partial, 9 absent of which 4
> gen4-live); `encoder_requirements.md` (a gen4 EncoderSpec against the landed
> F-08 seam: 17 types listed, 6 stats, ~16 volatiles + 6 counters, item/ability
> ids + class bits, weather/field/side blocks, forme-keyed vocabs 300/182/101/40,
> `priority_scale`, test contract incl. the gen4 tape gate that cannot exist
> until post-ladder; 17 adjudications); `anchors_and_eval.md` (SH weaker and
> different in gen4 — do not patch, disclose; most-damage-typed spec; foul-play has
> first-class GEN4 mechanics but the installed engine is the gen1 build and set
> data is fetched at runtime; Wang target 0.786 exit / 0.836 stretch);
> `open_questions.md` (46 rulings, 6 deferrals, merge checklist). Method
> deviation: three sweep attempts hit the usage limit; 10/14 research notes
> landed; docs written single-writer by maintainer ruling; no memo cycle, no
> critic pass. Research notes are on disk only (scratchpad), not committed.

**M3 — Corrections owed to main-tree files, not applied here** (Q41, Q43, Q46): the
IDEAS §2.5 "12M" → "50M off-FP" line; the prior-work index's ps-ppo comment
direction and its "upstreamed" amendment; `make_bc_dataset.py`'s 611-dim docstring.

**M4 — Memory.** `subagents-use-opus.md` already records the Opus rule; add its
how-to-apply: fan out in sequential waves of ≤ 5 so completed agents are banked
before a limit hit (14-wide fan-outs lost everything twice).

**M5 — Overlap with the audit's open rulings** (`docs/archive/AUDIT_BRANCH_LOG.md`
§Open questions): F-07 (encoder config block) and F-21 (tracking the borrowed set
prior) are both re-raised here as Q16 and Q20; ruling them once covers both lists.

## 10. Refusals — what this cycle declines to decide

- The gen4 training recipe beyond Q6–Q8 (batch shape, anneal, pool composition,
  aux heads, shaping): a pre-reg with the 2-Opus cycle, after the encoder lands.
- Any gen4 pre-registration header, gate, bar, or number.
- The architecture question (entity trunk vs attention) and the temporal /
  Markovianity redesign: carried to JOURNEY's own items.
- Anything gen9.
- The searched 100M endpoint (Q44): pre-registration is the maintainer's; this cycle
  only records that the endpoint is missing.
