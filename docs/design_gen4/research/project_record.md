# project_record.md — what the committed project record already says about gen4, Wang, anchors, search and process

Agent: project-record researcher (gen4 design sweep, stage 1)
Date: 2026-09-04
Scope: **the project's own decision record only.** No external sources, no live checks, no
code execution against a server. Everything below is from the read-only snapshot
`main_snapshot` (= `main @2738025`) plus two gitignored on-disk files in MAIN.

## Status legend (every finding carries exactly one)

- **tree-verified** — checked against a file in the repo tree (SNAP: `rl/`, `scripts/`,
  `configs/`, `tests/`, `docs/`, or the committed `.md` record) or the vendored `showdown/`
  data/sim, i.e. the project as we actually run it.
- **source-verified** — checked against an external primary source on disk (PE source,
  Wang's diffs or thesis text, H&L text or MG code, PSPPO, FP, Metamon text).
- **literature-only** — from a secondary write-up, a web page, memory, or the prior-work
  index without re-checking the primary.
- **needs-live-verification** — only a running server or battle can confirm it; BARRED until
  the ladder run and any later fleet complete.

**Note on my own status tags:** almost everything here is *tree-verified in the sense that I
read the committed record*. Where the record itself is reporting a verification of an
external primary (e.g. "we re-read Wang's thesis PDF and confirmed X"), I tag the finding
**source-verified** and name the record entry as the chain of custody — I did **not** re-open
the PDFs or the ps-ppo clone this session. Where the record reports a claim it did *not*
verify, I say so.

## Sources read this session (path + line ranges)

Snapshot root
`SNAP = /private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/b1478b5b-c556-4e2e-9100-b0db7e234069/scratchpad/main_snapshot`
(= repo `main @2738025`; cite repo-relative paths + "(main@2738025)").

| file | lines read |
|---|---|
| `SESSION_LOGS.md` | index (`grep -n '^- 20'`, 2 pages); entries at 270–290, 2121–2162, 2647–2683, 2704–2730, 5027–5063, 5391–5470, 5486–5530, 5554–5578, 5702–5745, 5908–5935, 6470–6484, 7181–7223, 7446–7484, 8415–8472, 9205–9224, 9855–9891, 9932–10127 |
| `SESSION_LOGS_PREDECESSOR.md` | index; entries at 963–1035 (Wang/ps-ppo verification) and 1066–1112 (Wang's GitHub forks) |
| `RESULTS.md` | section index; 580–616 (§13), 884–1022 (§16.2–16.4), 1022–1143 (§17), 1143–1269 (§18) |
| `CHAPTER5.md` | section index; 239–310 (§3b), 487–572 (§6/§7/§8) |
| `JOURNEY.md` | 1–120 (whole file, 119 lines) |
| `STATUS.md` | 1–59 (whole file) |
| `docs/IDEAS_POST_100M.md` | section index; 1–140 (§1–§3, incl. 2.5/2.6); 175–190 (λ block); 276–308 (§7 corrections) |
| `docs/CLEANUP.md` | 1–60 |
| `CLAUDE.md` | 160–215 (landmines tail + Conventions) |
| `README.md` | 160–185 |
| `docs/prior_work/README.md` | 100–140 (ladder table + retired conversion), 385–430, 460–500, 560–575, 618–632, 655–700 |
| `readouts/LADDER_R1_READOUT.md` | 1–35 |
| `configs/eval/fp_budget_ladder.yaml` | 1–32 (whole file) |
| `configs/eval/ch3_r4_fp_anchor.yaml` | 1–40 |
| `configs/eval/ch3_r4_ensemble_critic.yaml` | 405–440 (anchor-battery block) |
| `configs/eval/ch5_100m_offfp.yaml` | clone/anchor lines 28–31, 133–135 |
| `configs/eval/ch5_r2_offsh.yaml` | 358–375 (R3c clone anchor, R4S selection rule) |
| `configs/eval/ladder_r3.yaml` | 70–95 (D6 / s80 selection disclosures) |
| `configs/showdown_sp_100m.yaml` | 1–70 (header only, per task) |
| `docs/archive/AUDIT_BRANCH_LOG.md` | 303–348 (F-08), 488–499 (consolidated open questions) |
| `scripts/make_bc_dataset.py` | 1–40 (module docstring) |
| grep-only (paths/line numbers, no bulk read) | `rl/envs/showdown.py:50,61,63`, `rl/envs/showdown_async.py:71,306-307`, `tests/test_showdown_env.py:405,411` |

MAIN (gitignored, allowed): `results/design_ch5_100m/synthesis_100m.md` (1–85, whole file),
`results/design_ch5_100m/BRIEF_100M.md` (1–60). I also read
`results/design_fp_gap/ch4_synthesis.md` 165–178 and 276–290 (in SNAP, tracked) for MU-2.

**NOT read** (per the hard bars or out of scope): `configs/eval/ladder_r4.yaml`, anything
under `results/ladder`, `MAIN/runs`, `MAIN/logs`, the Wang/H&L/Metamon PDFs and their text
dumps, `docs/prior_work/wang_fork_diffs.md`, the ps-ppo / foul-play / metagrok clones,
`mem_A.md` / `mem_B.md` / `review_1.md` / `review_2.md` of the 100M cycle (only the
synthesis and brief were in scope), `rl/envs/encoder_spec.py` itself (its landing record
only).

---

# 1. Wang 2024 — everything the record says, and where the record is wrong

## 1.1 Where the Wang verification actually lives (a correction to my own brief)

**tree-verified.** The task brief pointed me at "the 2026-08-03 prior-work entries" in
`SESSION_LOGS.md`. They are not there — `SESSION_LOGS.md`'s first entry is 2026-08-04. Both
Wang verification entries live in **`SESSION_LOGS_PREDECESSOR.md`** (committed here
2026-08-05, frozen; `SESSION_LOGS.md` wins on conflict):

- 2026-08-03 "prior-work verification" — `SESSION_LOGS_PREDECESSOR.md:963-1034`
- 2026-08-03 "latest: Wang's GitHub forks read" — `SESSION_LOGS_PREDECESSOR.md:1066-1111`

Downstream docs should cite the predecessor file by name, not `SESSION_LOGS.md`.

## 1.2 What was VERIFIED verbatim about Wang

**source-verified (chain of custody: one Opus subagent re-read the thesis PDF from DSpace;
recorded at `SESSION_LOGS_PREDECESSOR.md:963-1034`).** Verbatim from the entry:

> "*Wang (Source A)*: every core claim verified verbatim — the LR-anneal ablation (constant
> lr stuck ~0.55 vs ~0.80 annealed, §3.1.4; the ONLY controlled single-variable ablation
> found anywhere in this literature, decay constants admittedly untuned), the exact
> hyperparameter table, sparse terminal reward, no recurrence (durations one-hot instead),
> the non-lockstep race-condition note, both-players collection, 3v3 surrogate tuning."
> (`SESSION_LOGS_PREDECESSOR.md:969-972`)

So: hyperparameter table VERIFIED; LR ablation VERIFIED (and it is the only controlled
single-variable ablation in this literature); sparse terminal reward VERIFIED; no recurrence
(one-hot durations instead) VERIFIED; both-seat collection VERIFIED; 3v3 surrogate tuning
VERIFIED.

**tree-verified.** The hyperparameters themselves are transcribed into the record at
`JOURNEY.md:45`:

> "Use his hyperparameters as the starting config, not a from-scratch guess (Table A.3): γ
> 0.9999, λ 0.754, 7 epochs, clip 0.0829, value clip 0.0184, ent 0.0588, vf 0.4375,
> grad-norm 0.543, n_steps 78×512, batch 1024, hidden 256, features 896. Plus his LR
> schedule 10^-4.23/(8x+1)^1.5 — the only controlled annealing ablation in this literature."

I did **not** re-check these against the thesis PDF this session; they are
**literature-only** at the level of individual digits, though the *table as a whole* was
verified 2026-08-03.

## 1.3 What was CORRECTED about Wang

**source-verified**, verbatim (`SESSION_LOGS_PREDECESSOR.md:972-977`):

> "Corrections: 'search bought ~12 points' is arithmetic on a table with no stated N and no
> error bars, and Fig 4.1 reports ~0.85 vs SH for what Table 4.1 scores at 0.786 —
> unreconciled in the thesis; the env-stepping-bottleneck quote is about MCTS inference
> rollouts, not training collection; action count is ~495 and 'switch-by-species' was an
> inference."

Four corrections, all load-bearing for gen4:

1. **"search bought ~12 points" is not a measurement** — table arithmetic, no N, no error
   bars. Any gen4 search-value claim sourced to Wang must say this.
2. **The 0.786-vs-0.85 discrepancy is UNRECONCILED IN THE THESIS.** Table 4.1 = 0.786;
   Fig 4.1 ≈ 0.85. This is *Wang's* inconsistency, not ours. The record repeats it in the
   sources index: "Pure network 0.786 vs SimpleHeuristics (Table 4.1; Fig 4.1 says ~0.85 —
   unreconciled)" (`docs/prior_work/README.md:396-397`), and the DESIGN r6 fact-check hedged it
   further: "Wang 0.786 provenance hedged (no step count in our index; Fig 4.1 ~0.85
   unreconciled)" (`SESSION_LOGS.md:279-280`, entry 2026-08-05).
3. **The env-stepping bottleneck is about MCTS rollouts, not training collection.** Do not
   import it as a throughput fact.
4. **Action space ≈ 495, identity-coded; "switch-by-species" was an inference, not a read.**

**tree-verified — and this is the ruling that closed the action-space question.** The record
sets Wang's 494-way space against ps-ppo's 14 and Metamon's 9 and calls Wang the outlier:

> "**Action space: 14, positional** … Same family as ours. With Metamon's 9 (4 move + 5
> switch) this is the evidence that closed the action-space question on 2026-08-04: the
> strongest pure policies are positional; Wang's 494-way identity space is the outlier and
> his headline needed MCTS." (`docs/prior_work/README.md:467-471`)

**Consequence for gen4:** we should NOT copy Wang's action space. The seam already derives
ours from the format — F-08 landed `Discrete(10)` "derived from the format (10 through gen
5, 26 at gen 9)" (`SESSION_LOGS.md:10026-10027`, 2026-09-04 audit-close entry). Gen4 is
inside the 10-action regime. **Cross-ref: encoder_requirements.md, pokeenv_gen4_survey.md.**

## 1.4 The Fig 4.1 digitization — new data the briefing missed

**source-verified** (`SESSION_LOGS_PREDECESSOR.md:977-982`), verbatim:

> "**New, missed by the briefing: Fig 4.1 digitized (calibration self-validates against the
> thesis's stated 40M→0.80 / 150M→0.85 anchors) — winrate vs SH ≈ 0.30 at 2M, crosses 0.50
> at ~4M, 0.575 at 6M, 0.64 at 8M** — the reference gen4 agent, with tuned hyperparameters
> and annealed lr, was at 0.575 at our exact budget; nearly all its remaining gain was
> bought 6M→60M."

This is the only *curve* we have for a gen4 pure-self-play agent, and it is ours (digitized
here), not the thesis's numbers. It is the natural target curve for JOURNEY step 5.

## 1.5 Other Wang facts recorded

**source-verified**, all from `SESSION_LOGS_PREDECESSOR.md:982-990`:

- **NO opponent pool** — "pure latest-vs-latest self-play, SH the only external anchor, no
  pathologies reported".
- **Curriculum negative result** — "k-Pokémon specialist bootstrapping tried, 'no
  significant improvements' over scratch 6v6" (thesis §5.1.3).
- **Total PPO loss ROSE all run** (entropy + shrinking advantages) — "not a progress signal".
- **Eval determinism never stated.** Relevant: our locked protocol *is* deterministic, so a
  gen4 "matched" claim inherits an unstated-protocol gap on his side.
- **Wang explicitly rejected Gen 1 as a format** ("no real counters to strong
  Psychic-types") — the one place the record has Wang commenting on our current format.

## 1.6 The forks: what is upstream, what Wang actually added, and the poke-env claim

**source-verified** — maintainer-supplied full fork diffs, archived as
`docs/prior_work/wang_fork_diffs.md`, read and checked against our tree
(`SESSION_LOGS_PREDECESSOR.md:1066-1111`).

**Headline correction, verified at file:line in our own checkout:**

> "**battle serialization is upstream Showdown, not Wang's work** — `State.serializeBattle`/
> `deserializeBattle`, `Battle.toJSON`/`fromJSON`, `resetRNG(seed=null)` (fresh chance draws
> per rollout), `restart()`, `undoChoice` all exist in our vendored checkout
> (`showdown/sim/state.ts:61,84`; `showdown/sim/battle.ts:318,322,360,1968,3029`)."
> (`SESSION_LOGS_PREDECESSOR.md:1071-1075`)

What Wang *added*: "two stream commands — `>getstate` (state → JSON) and `>load`
(deserialize + restart + undo pending choices + resetRNG(null) + reroll the opponent's
unrevealed team under revealed constraints + re-request) — plus
`SetCriteria`/`rerollTeam`/`replaceSet` and **~370 lines of gen4 constrained team-gen**
(hallucinated Hidden Power types, weather-probability ability sampling, volatile-aware move
disabling)" (`SESSION_LOGS_PREDECESSOR.md:1075-1080`). Wang's search stack cost: "20
workers, 1000–2000 rollouts/move, ~10 s/move — evals go ~100× slower"
(`SESSION_LOGS_PREDECESSOR.md:1082-1083`).

**THE "poke-env fixes upstreamed by 0.15.0" CLAIM AND ITS EVIDENCE — source-verified,
verbatim:**

> "*poke-env fork (36 commits)* — state-tracking corrections, almost no architecture. **Both
> encoder-relevant fixes verified ALREADY UPSTREAMED in our 0.15.0** (`[from] lockedmove` →
> `use=False`; sleep `status_counter` incremented in `cant_move`); most of the rest is
> structurally impossible in gen1 (Max PP tables, Sleep Talk, Curse ???-type, ability
> weather, Trace, `_orig_item`, choice lock)."
> (`SESSION_LOGS_PREDECESSOR.md:1091-1095`)

**This is the single most important qualification in the whole Wang record for the gen4
chapter, and it is routinely mis-stated.** The verified claim is:

- **exactly TWO fixes were checked** — `[from] lockedmove` → `use=False`, and sleep
  `status_counter` in `cant_move` — and *those two* are upstreamed in 0.15.0;
- **"most of the rest is structurally impossible IN GEN 1"** — Max PP tables, Sleep Talk,
  Curse ???-type, ability weather, Trace, `_orig_item`, choice lock. **Every one of those is
  LIVE in gen4.** They were dismissed as irrelevant *because we were in gen1*. That
  dismissal does not survive the move to gen4.
- The record itself keeps the risk class open: "The risk CLASS stays live — our own gen1
  findings prove it (SH setup branch dead on the 0.15.0 enum bug; Light Screen →
  `Effect.UNKNOWN`) — but is bounded by the clone (0.453 through this exact encoder)"
  (`SESSION_LOGS_PREDECESSOR.md:1095-1098`). The *bound* is a gen1 bound and does not carry.
- **Unregistered optional item, still unregistered:** "a differential obs audit, encoder
  fields vs the raw protocol log over sampled battles" (`:1098-1099`).

**tree-verified.** `JOURNEY.md:40` turns this into a step-3 instruction and names *seven*
of the fixes, i.e. more than the two ever checked:

> "**Mine Wang's forks first.** quadraticmuffin/poke-env is ~36 gen4 state-tracking fixes
> found the expensive way — Max PP, Sleep Talk double-decrementing, weather-from-abilities
> persistence, sleep counters, Trace base-ability parsing, maybe_trapped, _force_switch as a
> list. Diff it against our pinned 0.15.0 and check which survived upstreaming. A silently
> wrong observation field looks exactly like a training problem."

The prior-work index compresses the same thing to "36 poke-env state-tracking fixes
(encoder-relevant ones upstreamed by 0.15.0)" (`docs/prior_work/README.md:568-570`) — **that
parenthetical is the sentence most likely to be over-read.** "Encoder-relevant" there means
*gen1*-encoder-relevant, and the population checked was two.

**Also in the fork, and directly reusable for a long gen4 run — source-verified:** "RL server
hygiene for long runs: clear players from finished rooms (usernames train*/eval*), gutted
`onEnd` (no ladder/replay work per battle), tie-restriction removed — the fix pattern if a
long run ever shows the poke-env-#332 slowdown signature"
(`SESSION_LOGS_PREDECESSOR.md:1084-1087`). And: "Notably absent from all three forks: the
non-lockstep parallelization (it lives in his unpublished training code, as do **masking and
the LR schedule**)" (`:1102-1104`) — i.e. **Wang's masking implementation and his LR
schedule code are NOT public**; only the schedule's formula is, from the thesis.

**SB3 fork:** "pure throughput instrumentation … confirms stock SB3 PPO; the thesis
hyperparameters are tuned values in SB3's knob shape" (`:1104-1106`). This is the basis of
`JOURNEY.md:47` and `:56` — "He ran SB3, so any residual gap partly measures SB3's
implementation against ours. State it in step 5 rather than let a reader find it."

## 1.7 Wang's gen4 constrained team-gen — the MCTS cost estimate

**source-verified.** "**MCTS cost estimate revised DOWN: the forking interface is a few
hundred lines against existing machinery** (gen1 port target
`showdown/data/random-battles/gen1/teams.ts`); the remaining cost is the search stack
itself" (`SESSION_LOGS_PREDECESSOR.md:1080-1082`). Note the gen4 asymmetry: **Wang's ~370
lines of constrained team-gen are already gen4**, so a gen4 MCTS would inherit them rather
than need a port — but `JOURNEY.md:108` rules against building search in gen4 anyway:
"Building search in gen4 would have meant forking Showdown for >getstate/>load plus
gen4-specific constrained team regeneration — infrastructure that does not carry forward.
Gen9 is where the effort compounds."

## 1.8 Later mentions of Wang (post-migration)

**tree-verified.** All of them, from a `grep -n -i wang` over the five current-era docs:

| where | what it says |
|---|---|
| `docs/prior_work/README.md:123` | Ladder board row: "Wang 2024 — PPO + test-time MCTS \| Gen4RB \| **1756** \| **79.5%**" (Glicko-1 / GXE). Sourced from Metamon's appendix, not from Wang. |
| `RESULTS.md:246` | The same row in the published-field table (GXE only). |
| `docs/prior_work/README.md:405-411` | VGC-Bench correction: "Their recipe (Table 7): gamma 1.0, lambda 0.95, ~3k steps/update — OUR gamma/lambda, **not Wang/ps-ppo's 0.75**, so the 'convergent recipe' prior has a third system on the other side." |
| `docs/prior_work/README.md:420-424` | Metamon appendix A.1/A.2 is the *source* of the 1756/79.5% row. |
| `docs/prior_work/README.md:490-493` | ps-ppo's "Wang MLP replication plateaued ~1100 Elo" has **ZERO code support** — no MLP anywhere in ps-ppo's history. "Treat as anecdote." |
| `docs/prior_work/README.md:625-628` / `CHAPTER5.md:266` | The "~30 → 100–300 episodes/update" target was calibrated against Wang (~1,600) and ps-ppo (~1,500), and the index argues **those are not our comparable** (both use human data); H&L is, at ~15,360 episodes/update. |
| `SESSION_LOGS.md:1991,1995` | "Wang's numbers match our verified index (0.575@6M, LR ablation 0.55→0.80)"; "~38 completed episodes per update vs Wang's ~1,600 and ps-ppo's ~1,500". |
| `SESSION_LOGS.md:2277` | "Wang's 36 poke-env commits verified 2026-08-03 — both encoder-relevant fixes …" (the two-fix reading confirmed in a later triage). |
| `SESSION_LOGS.md:2334-2336` | Architecture survey: "H&L/Wang symmetric PPO"; "Wang gen4 AND test-time MCTS". |
| `docs/IDEAS_POST_100M.md:180` | λ: "ps-ppo 0.75 and Wang 0.754 sit against **VGC-Bench at γ1.0/λ0.95 (our exact values)** and H&L at λ0.9/γ0.95" — the external field is **split, not convergent**. |
| `docs/IDEAS_POST_100M.md:247` | "JOURNEY step 3, Wang's one-hot duration counters" — cited as an encoder idea for step 3. |
| `JOURNEY.md:9,40,42,44-45,51-58,63,118` | The gen4 chapter's whole Wang program (below). |

**tree-verified — the encoder items JOURNEY says to steal** (`JOURNEY.md:42`): "Steal his
observation design where it fits (Tables A.1/A.2): multi-turn effect durations as one-hot
counters to restore Markovianity, HP binned, PP as floor(pp^(1/3)). Our encoder is ours, but
these are solved problems." **Cross-ref: encoder_requirements.md.** I have *not* verified
Tables A.1/A.2 against the PDF this session — **literature-only** at that granularity.

## 1.9 The gen4 exit condition and its unresolved target

**tree-verified**, `JOURNEY.md:51-58`, verbatim:

> "### 5. Gen4 offline evals vs Wang
> **Exit condition: 'close enough' to his offline numbers.**
> **Pin the target before starting.** His Table 4.1 says 0.786 vs `SimpleHeuristicsPlayer`;
> his Figure 4.1 reads closer to 0.85. Our own prior-work index flags this as unreconciled.
> Choose which one we are matching, in writing, and define what 'matched' means numerically
> — deciding afterward is how a comparison becomes a rationalization.
> **Disclose the confound:** he ran Stable-Baselines3 with its defaults. Any gap partly
> measures SB3's tuned recipe against our from-scratch PPO, not only architecture and scale."

**This is an OPEN MAINTAINER RULING** (0.786 vs 0.85, and the numeric definition of
"matched"). It is unruled anywhere in the record I read. **Cross-ref: open_questions.md.**

Note a second, quieter confound the record already names but JOURNEY does not: **Wang's
numbers are vs the STOCK `SimpleHeuristicsPlayer`, boost bug included.**
`SESSION_LOGS_PREDECESSOR.md:1023-1027`: "**poke-env 0.15.0's SimpleHeuristicsPlayer
`_stat_estimation` carries the boost bug ps-ppo patched** (`boosts[stat] > 1`: a +1 boost
falls to the else branch and evaluates 2.0× — the +2 multiplier — instead of 1.5×) — our
numbers and Wang's are vs the stock bot, ps-ppo's vs a patched one — comparability caveat".
Same-bot-same-bug means Wang and we are comparable **iff we also stay stock** — but SH's
boost branch is far more live in gen4 than in gen1, so the bug's *magnitude* is not
generation-invariant. **Cross-ref: anchors_and_eval.md, pokeenv_gen4_survey.md.**

---

# 2. The anchor-battery convention, verbatim

## 2.1 The convention as it stands today

**tree-verified.** `CLAUDE.md:189-200` (main@2738025), verbatim and complete:

> "- **Anchor battery** (2026-08-23; FP budget amended 2026-08-26 per MU-2):
>   every headline-grade result reports vs-SH (locked protocol) **plus** two
>   descriptive anchors — BC-clone h2h (500) and Foul Play h2h — before its
>   README row lands. Anchors are descriptive, **never verdict inputs**.
>   - **Match the policy form to the rating you compare against** — a clone
>     number is never style evidence.
>   - FP anchor at `--search-time-ms 20`. **Two disclosures travel with every
>     FP@20 number, forever:** the equivalence test is weakly powered, and the
>     point estimate flatters us. **Name the budget in every quote.** FP@20 is
>     an instrument, not a rung — the readiness gradient is the FP budget
>     ladder (`configs/eval/fp_budget_ladder.yaml`)."

## 2.2 The 2026-08-23 origin ruling

**tree-verified.** The battery is first stated as mandatory in the 2026-08-23 late-evening
ruling entry (`SESSION_LOGS.md:5723-5742`), verbatim:

> "(a) R4 ensemble-critic pre-reg APPROVED TO DESIGN — a LETTER-BEARING credit test of
> depth-1 search@M with an ensemble-critic evaluator (pure, zero training; E3's +0.036
> screen-grade directional at the credited dose); the 2-Opus design cycle runs this session,
> fresh pre-reg + maintainer ratification required before any battle, the ANCHOR BATTERY
> mandatory (locked SH + clone 500 + FP@100 250 — after P2, off-SH transfer is THE
> question)." (`SESSION_LOGS.md:5730-5735`)

So the original battery was **locked SH + clone n=500 + FP@100 n=250**.

The same day's ruling that sets its *purpose* is the deferral ruling, maintainer verbatim
(`SESSION_LOGS.md:5556-5563`):

> "Rec: (c), as for ladder: its still going to happen, we just dont need to do it until we
> think we are ready, Rec: (a) and once we have a ladder ready model THEN we can try a 120
> or 250M run just to see if we squeeze more from it. summary: ladder still will happen, but
> why waste time until we have exhausted models playing against SH and FP. huge runs can
> still be usefull but ONLY for things we might think are truly ready (or if we relaly see
> training is still climing in logs). push what we have after."

That single quote carries **three** standing rulings: (1) ladder deferred-until-ready,
readiness = "exhausted models playing against SH and FP"; (2) 120/250M runs reserved for a
ladder-ready model or visibly-climbing logs; (3) the anchor board is what defines readiness.
Executed as: "(2) D7(a) — ladder execution DEFERRED-UNTIL-READY (readiness = maintainer
judges the models exhausted vs the SH and FP anchors)" (`SESSION_LOGS.md:5568-5570`).

**Restatement inside a pre-reg** (`configs/eval/ch3_r4_ensemble_critic.yaml:408-412`),
tree-verified: "ANCHOR BATTERY (MANDATORY by the 2026-08-23 standing ruling; DESCRIPTIVE,
NEVER a verdict input; n too small to credit). RUNS IFF the primary cell is B1a/B1b/B2 and
no VOIDing F-gate fired. … **U3 RULED 2026-08-23: the iff-B1/B2 reading is CONFIRMED by the
maintainer.**" — i.e. **the battery fires only on a positive primary.** Same file records
"U2 RULED 2026-08-23: n=1000 APPROVED (a disclosed upward deviation from the battery
ruling's 500)" (`:437-438`), so the 500 is a floor that has been deviated upward with
disclosure.

## 2.3 The MU-2 amendment (2026-08-26)

**tree-verified.** MU-2 comes out of the CH4 FP-gap 2-Opus cycle. The bracket text
(`results/design_fp_gap/ch4_synthesis.md:280-283`):

> "**MU-2** FP@20 as standing anchor: requires G6-PASS AND G6b-PASS, **and a CLAUDE.md
> anchor-battery edit** (budget 100→20, n; the FP@100/FP@500 readiness-gradient rungs
> unchanged — FP@20 is an instrument, not a rung)."

and the recommendation (`:169-171`): "**MU-2:** FP@20 licensed as the standing cheap anchor,
conditional on G6 (and the archaeology's style read as advisory)? Recommended: yes, budget
named in every number forever."

Execution record (`SESSION_LOGS.md:6476-6478`), verbatim: "MU-2 EXECUTED separately
(8da9193): the CLAUDE.md anchor battery moves to FP@20 (5.1x cheaper) with both disclosures
attached."

**So: the battery's FP leg went 100 → 20 ms for cost (5.1×), and the FP@100/FP@500 rungs
survive as the readiness gradient, not as the battery.**

## 2.4 The locked vs-SH protocol

**tree-verified**, `CLAUDE.md:185-188`, verbatim:

> "- **Locked eval protocol:** final checkpoint, **3000 battles/seed**, 3 seeds
>   pooled, ties as non-wins, deterministic policy, vs `SimpleHeuristicsPlayer`.
>   Every arm from D23 on has pooled **5×3000** — a disclosed DEVIATION
>   (conservative, 5 ≥ 3); say so when quoting it."

Note the 100M readout explicitly says the deviation *does not* apply to it: "(deviation
disclosure inherited from D23 onward does not apply: this is 3×3000 exactly)"
(`RESULTS.md:1180-1181`).

## 2.5 What the BC clone actually is

**tree-verified.** The object pinned in the current battery is
`runs/bc_fp_v2r_soft_180k_s0/checkpoint.pt`, sha256
`5e490adecf70b480edcde9a6080ffc34049c16bf77b295c0e2a8bd43299a0683`
(`configs/eval/ch5_100m_offfp.yaml:31`), described there as "the anchor-battery clone, sha
identical to the [ch3_r4] pin" (`:28-30`). The h2h arms are
`{kind: greedy_h2h, seat1: s<lane>, seat2: clone, battles: 500}` (`:133-135`).

**Teacher, data, and build — tree-verified**, from the F1 re-fit entry
(`SESSION_LOGS.md:2121-2130`), verbatim:

> "**(1) Re-embed** of the six-tape corpus on v2/808 (data/fp_all_v2r, tape_to_dataset one
> invocation): 7,200 battles / 180,440 rows, ALL SIX GATES PASS. **(2) Re-fit** with the
> banked recipe (soft, 512/512, seed 0, 20 epochs, batch 512, lr 1e-3; ONE deviation: no
> --max-rows cap → all 180,440 rows vs the banked 180,000): val free-agreement 0.517 vs
> banked 0.5147 — recipe reproduced. **(3) Protocol-grade** (n=3,000, deterministic, ties
> non-wins, vs SH, v2/808 process): FINAL 0.5490 ± 0.0091, VAL-PEAK **0.5777 ± 0.0090**"

So the clone is: **teacher = Foul Play (the engine, with our patches), NOT SimpleHeuristics**;
data = a six-tape corpus of FP's own play, 7,200 battles / 180,440 decisions, re-embedded
through **encoder v2 at OBS_DIM 808**; model = MLP 512/512 on soft targets, seed 0, 20
epochs, batch 512, lr 1e-3; graded 0.5490 (final) / 0.5777 (val-peak) vs SH at the locked
protocol. `RESULTS.md:695` carries the row "Behaviour clone of Foul Play (graded final /
val-peak) | 0.5490 / 0.5777".

**Two facts that matter for gen4:**
- **The clone is frozen at OBS_DIM 808 while the live encoder is 828.** The 100M ladder
  smoke stamps `obs_dim 828` (`SESSION_LOGS.md:10105-10106`). A gen4 battery needs a
  *newly built* gen4 clone — the gen1 clone is not portable, and JOURNEY's standing note
  says weights never transfer anyway.
- **The generic BC-dataset tool is SH-facing by default and its own docstring warns about
  the state distribution.** `scripts/make_bc_dataset.py:47-48` defaults `--expert
  heuristics` / `--opponent heuristics`; its docstring (`:19-27`) says: "These are the
  expert's OWN visited states against `--opponent`, which is not the state distribution an
  RL learner visits against the same bot. Phase 4 measured exactly this gap and found it
  enormous (2026-07-29: 0.855 optimal-move agreement in-distribution against 0.44-0.62 on
  differently-distributed positions)". Note the docstring still says **611-dim** obs
  (`:11`) — a stale number in a live script.

**Purity note (tree-verified):** the BC clone is an *anchor*, never training input.
`CHAPTER5.md:497-498` lists "Expert data, human replays, teacher distillation, ladder
replays as training data" as out of scope: "The lane's purity constraint. Unchanged."

## 2.6 The FP@20 protocol and its two standing disclosures

**tree-verified.** The two disclosures, verbatim in the most recent readout
(`RESULTS.md:1216-1219`):

> "**FP@20** is the primary axis this round (E1 promotion, this round only). **Budget:
> --search-time-ms 20.** The two standing disclosures travel with every FP@20 number,
> forever: the equivalence test is weakly powered, and the point estimate flatters us. FP@20
> is an instrument, not a rung."

Fuller phrasing of *why* the estimate flatters us (`RESULTS.md:920-926`): "Two disclosures
travel with every **FP@20** number, forever: the equivalence test backing the 20 ms budget
is weakly powered, and the point estimate has **FP@20 marginally weaker than FP@100** — the
direction that flatters us."

**The runner-side protocol** (`configs/eval/ch3_r4_fp_anchor.yaml:12-35`), tree-verified:
deterministic listening seat vs "Foul Play + our patches" at `--search-time-ms N
--search-parallelism 1`, n=250 for the anchor; comparator frozen and threshold **pinned as a
literal** so it "cannot move with the data"; explicitly "NON-CREDITING: descriptive anchor,
never a verdict input". Gates carried: "G1 5-battle smoke first; G2 two independent tallies
agree; G3 every challenge resolved; G4 the seat accepts from the FP username only; G5
mask_desyncs reported, nonzero disclosed" (`:31-35`). Crash-forfeit read rule, verbatim
(`:23-30`): "an FP crash forfeits the in-flight battle TO US server-side, so crash-forfeited
battles are EXCLUDED; n_eff = seat-finished minus crash-forfeits, our_wins reduced by the
same count; the seat and FP tallies must agree on n_eff EXACTLY (G2); every crash point and
the relaunch count disclosed beside the number; >= 30 relaunches VOIDs the arm."

## 2.7 The FP budget ladder — built, run, and it found NO gradient

**tree-verified.** `configs/eval/fp_budget_ladder.yaml:1-32` (whole file). Maintainer-directed
2026-08-23 ("FP budget ladder for sure, add it"); "DESCRIPTIVE THROUGHOUT: no branches, no
credit; these rungs place the readiness gradient the 2026-08-23 rulings need ('exhausted vs
SH and FP' -> beat FP@100, then face FP@500)". Arms: FP20 and FP500, 250 battles each, our
seat = s65 greedy; anchor `fp100_greedy_s65: 0.388`. Expected ordering pre-stated:
"our_wr(FP20) > 0.388 > our_wr(FP500). A violation is a finding to record, not a gate."

**The readout killed the gradient** (`SESSION_LOGS.md:5702-5717`), verbatim:

> "NUMBERS (our greedy s65 side): FP@20 **0.312** (78-172, 1.46 s/battle), FP@100 0.388
> (same-day h2h), FP@500 **0.332** (83-167, 35.5 s/battle). Expected 0.312<0.388>0.332 vs
> pre-stated FP20 > FP100 > FP500 — the point estimates are NON-MONOTONE and every pairwise
> gap is ~1-2 se (se_diff ~0.042): consistent with FP's realized strength being FLAT in
> budget on gen1's small trees (20 ms already searches deep enough) plus sampling noise.
> RECORDED CONSEQUENCE for the rulings' readiness gradient: 'beat FP@100 then face FP@500'
> does not buy a staircase — FP at any budget takes ~62-69% off us; the readiness anchor is
> simply 'FP h2h at stock budget' until our number moves enough that budget differentiation
> becomes measurable (or n is raised)."

**Gen4 consequence, and it is a real one:** the reason FP is flat in budget is explicitly
"gen1's small trees (20 ms already searches deep enough)". **Gen4 trees are not small**
(items, abilities, weather, hazards, a real switch calculus), so *the flatness finding is
generation-specific and must be re-measured in gen4 before any gen4 FP budget is pinned.*
**Cross-ref: anchors_and_eval.md.** This is **needs-live-verification** for gen4 — the check
is: re-run the two-rung ladder (20 ms and 500 ms, n≥250 each) against a gen4-capable FP
build and see whether the ordering separates.

## 2.8 "Match the policy form"; "anchors are descriptive"; the ladder+FP pairing

**tree-verified.**

- *Match the policy form* is `CLAUDE.md:194-195` (above). Its live instance:
  `RESULTS.md:1260-1262` — "The 100M final vs the CH3 search number (0.7959 vs 0.7928
  vs-SH) are different policy forms measured in different sessions; they may not be ranked
  against each other."
- *Anchors are descriptive, never verdict inputs* is `CLAUDE.md:193`, restated at
  `RESULTS.md:1210` ("Anchors (descriptive, never verdict inputs)") and in every anchor
  pre-reg (e.g. `ch3_r4_fp_anchor.yaml:19`).
- **The ladder-plus-Foul-Play pairing rule**, `JOURNEY.md:117`, verbatim:
  > "**'Ladder' always means ladder + Foul Play**: Any checkpoint good enough to ladder gets
  > a full FP head-to-head at pinned settings in the same pass. FP is the incumbent and the
  > reproducible one; the ladder is legibility. Pinned before the first run: FP time budget,
  > engine + poke-engine commit, sample size, and greedy-vs-searched on our side. Unpinned
  > FP numbers are incomparable to each other."
- **Never project between the two boards** (`CLAUDE.md` landmine; `RESULTS.md:1252`):
  "vs-SH and off-FP are **never ladder numbers**, in either direction." The full retirement
  is at `docs/prior_work/README.md:102-110`: "**never project a ladder number from a vs-SH
  number, in either direction.** … a directional exemption is how a projection habit
  survives its own retirement." The ~40% GXE conversion is RETIRED (2026-08-28).

## 2.9 The disclosure lines that travel with the current headline (RESULTS §18)

**tree-verified**, `RESULTS.md:1220-1247`. Four named disclosures:

- **A-COLL** — VOID this round (it fires iff cell P1). Verbatim: "the async wire's
  contribution on the primary axis at 12M remains unmeasured; the only wire bound is **G9's
  vs-SH null with SIGNED delta +0.02322** (93% of its band, positive, at 12M, on the vs-SH
  axis) — G9 tested the async collector AND the timer fix jointly. A bare 'G9 passed' is not
  an attribution."
- **G9 delta** — the +0.02322 signed figure above; it is the *only* bound we have on the
  wire, and it bounds async **and** timer jointly.
- **N-TIMER** — "owed since 2026-08-31, discharged here beside this run's headline numbers:
  every connecting seat sends `/timer on` (9a0e54d, wire-visible, post-dates the 50M
  control's training). Both seats are ours and answer in ms; the longest collector pause is
  the eval+checkpoint block, fleet-max `time/eval_sec` 26.18 s — an ~11× margin against the
  300 s/turn challenge budget. Honest limit: never measured as a training-data effect".
- **N-ANNEAL** — the named leading alternative explanation for the positive sign
  (`RESULTS.md:1205-1209`): "a 100M run trains hotter at every matched step and integrates
  2× the lr; the separating arm (100M under a 50M anneal) was not run."

Plus **σ_seed descriptive** ("An F-test across two 3-lane groups has (2,2) df and critical
value 19.0, so the horizon must cut sigma_seed ~4.4× before the comparison registers; a null
is NEVER readable as 'the horizon did not help variance'"), **D-A anneal liveness**, and the
never-a-ladder-number line.

---

# 3. Search depreciation — the full data set with provenance

## 3.1 THE PROVENANCE ERROR IN THE CURRENT DOCS (fix before writing search_depreciation.md)

**tree-verified.** `docs/IDEAS_POST_100M.md:95-97` says:

> "The points exist: 12M per-lane search deltas +0.051/+0.104/+0.148 (monotone in lane
> weakness), 50M batch-lane R4S66 search@20 **0.38067 vs greedy 0.4740 (~10 se — search
> hurts)**, and the 100M primary adds the endpoint."

**"12M" is wrong.** Those three deltas are the CH5 R1-B arms on the **50M D29r2 fleet**,
lanes **s80 / s81 / s82**, measured **off Foul Play@20 at n=1000 per arm**, not vs SH and not
at 12M. Source (`SESSION_LOGS.md:8436-8442`), verbatim:

> "**R1-B — SEARCH HELPS, AND IT IS THE LARGEST EFFECT IN THE WAVE.** Within-lane d: s80
> **+0.0510**, s81 **+0.1040**, s82 **+0.1480**; mean **+0.1010**, sd(d_i) 0.0486, se =
> max(binomial 0.0123, 0.0280) = **0.0280**, bar **0.0561**, **3.6 se, one-sided positive ->
> HELPS.** Note the ordering: **search helps MOST on the WORST lane** (s82 +0.148 vs s80
> +0.051), i.e. it partially rescues the bad seed — which is why the fleet's off-FP spread
> narrows under search (0.0617 greedy -> 0.0149 searched)."

The arms behind it (`SESSION_LOGS.md:8424-8429`): greedy A80 1000 **0.3960**, A81 1000
**0.3430**, A82 1000 **0.2730**; searched B80 1000 **0.4470**, B81 1000 **0.4470**, B82 1000
**0.4210**; "G2 seat/fp/tie — all three tallies agreeing exactly". Cross-checked at
`SESSION_LOGS.md:8681-8682` (the same per-lane table with greedy/searched/delta columns) and
at `configs/eval/ladder_r3.yaml:78-79` ("s82 +0.148, s81 +0.104"). That the lanes are 50M is
tree-verified from `CHAPTER5.md:283-284` ("s80/81/82 are a banked 3-seed 50M fleet") and
`RESULTS.md:884-886` ("search@M on lane s80 — a 50M-step pure-self-play lane").

`JOURNEY.md:21` is *not* wrong in the same way — it says "across the 12M and 50M checkpoints
we already have … the per-lane deltas were monotone in lane weakness (+0.051 / +0.104 /
+0.148)" without asserting the deltas are the 12M ones. But it is easy to misread, and
`IDEAS §2.5` already did.

**The ceiling that travels with these numbers** (`SESSION_LOGS.md:8443-8447`), verbatim:
"**CEILING HONOURED** … this licenses search as an **R3 DEPLOYMENT CANDIDATE and nothing
else.** It does NOT reverse MU-8 (pooled transfer z = -2.80), and the positive 50M delta is
NOT set beside the 12M cell in any sentence here."

## 3.2 The 12M search numbers (the ones that ARE 12M)

**tree-verified**, CH3 R2 readout (`SESSION_LOGS.md:5391-5406`), verbatim:

> "A0 fresh 0.73233/0.71833/0.73233/0.71133 (pooled 0.72358; R2-10 PASS vs 0.71825, diff
> 0.0053); A1S 0.78200/0.79300/0.80400/0.79233 (pooled **0.79283**); per-lane paired deltas
> +0.0497/+0.0747/+0.0717/+0.0810, equal-weight mean **+0.06925**; se terms binom 0.00551 /
> paired 0.00681 / unpaired 0.00691 -> se_gov 0.00691 (unpaired governs, the disclosed third
> term), 2*se_gov 0.0138 < floor -> operative bar 0.025 … **worst lane alone clears the
> floor**."

Form and budget: **depth-1 (one-ply) expectation search at Dose M**, dose frozen in
`rl/search/matrix.py` (`n_det` 4, `top_branches` 6, `leaf_cap` 1296, `node_cap` 1500)
(`RESULTS.md:886-888`); ~65 ms/move (`ms_mean 65.3-68.4`, `SESSION_LOGS.md:5403`); 4 lanes ×
3000 vs SH. The greedy comparator for the headline is D26's **0.71825**; the searched
headline is **0.79283**.

**So: the two search data sets are different axes.** 12M / vs SH / +0.069 pooled; 50M / off
FP@20 / +0.101 within-lane. The record forbids setting them side by side
(`README.md:157-166`; `SESSION_LOGS.md:8445-8447`).

## 3.3 The SH-facing ceiling (MU-8) — the reason "search helps" is fenced

**tree-verified.** The falsifier that produced it (`SESSION_LOGS.md:5425-5470`), verbatim
numbers: "GA s65-greedy-det vs clone **0.8940**; GB clone-det 0.3000 (ties 0.004) →
s65-from-sampling-seat 0.6960; G pooled **0.7950**" and "SA s65+depth-1 search@M vs clone
**0.8600** (500, 5×100 chunks…)"; "**PRIMARY: delta SA−GA = −0.0340, se_diff 0.0207 → P2
FIRES (delta ≤ 0)**: the +0.081 vs-SH search gain on this lane does not appear against the
clone; 95% CI upper bound +0.0075, so transfer commensurate with the vs-SH jump is EXCLUDED,
not merely unproven."

The pooled form is quoted throughout as **MU-8's pooled transfer z = −2.80**
(`RESULTS.md:976`; `CHAPTER5.md:139,223`; `SESSION_LOGS.md:6635,8445,8571,8618`).
The chapter-3 close states it plainly (`RESULTS.md:588-591`): "**0.793 vs SH, +0.069 over
the same checkpoints played greedily** (credited, all lanes positive). Caveat, measured not
assumed: the increment is SH-facing — it does not transfer to the BC-clone or Foul Play
anchors."

## 3.4 The 50M-era search reads

**tree-verified.**

- **LADDER R3's object** — "**search@M on lane s80** — a 50M-step pure-self-play lane with
  one-ply expectation (depth-1 matrix) search at inference. Dose M is frozen in
  `rl/search/matrix.py` … checkpoint sha `8b6546e2…`, asserted before the seat connects"
  (`RESULTS.md:885-889`). Primary read: **GXE 60.3%, Glicko-1 1579 ± 25, final Elo 1232,
  record 106–102, n=200** (`RESULTS.md:899-901`). **Its anchor battery is ONE of three:
  FP@20 only** — "no vs-SH at the locked protocol and no BC-clone h2h exists for search on
  any 50M lane" (`RESULTS.md:921-923`).
- **How s80 was picked, and the disclosure that cuts against us** — "s80 is the lane search
  helped LEAST on (+0.051 against a +0.1010 within-lane mean; s82 +0.148, s81 +0.104). The
  deployed object is not the one that would flatter the search story."
  (`configs/eval/ladder_r3.yaml:77-81`)
- **RESULTS §16 rows** (`docs/prior_work/README.md:118-122`, the field table): "ours — LADDER R1
  object: 4-ckpt log-prob ensemble, 12M (0.74633 vs SH) | gen1RB | **1573 ± 27** | **59.6%**"
  and "ours — LADDER R3 object: one-ply search@M on 50M lane s80 | gen1RB | **1579 ± 25** |
  **60.3%**", with the standing bar directly under them: "**NO ARITHMETIC DIFFERENCE BETWEEN
  THOSE TWO ROWS MAY BE PRESENTED AS A QUANTITY, IN EITHER DIRECTION** — ruling D5"
  (`:132-134`).
- **R4S66 — the reversal.** Selected by a data-orthogonal rule, "the LOWEST-NUMBERED
  SURVIVING TREATMENT SEED" (`configs/eval/ch5_r2_offsh.yaml:369-373`), n=3000 both ways
  ("the greedy half is that lane's primary arm at the same n=3000, so the within-lane delta
  is n-MATCHED", `:374-375`). It ops-failed twice (`RESULTS.md:1110-1119`) and then landed
  (`SESSION_LOGS.md:9861-9868`), verbatim:
  > "**R4S66 (search@20 on batch-lane s66 vs foul-play, 3000 battles, the timer fix's first
  > real workload): 0.38067 off-FP (1142W-1836L-22T, n_eff read 1141/2999 = 0.38046 after
  > the one crash_forfeit)** vs the SAME lane's greedy 0.4740 — **search@20 HURTS the batch
  > lane by ~0.093 (~10 se)**; the arm answers its question: search does NOT stack on the
  > batch recipe at the 20 ms budget; the ladder object question routes to the maintainer
  > with this number."
  **There is no vs-SH counterpart to R4S66 in the record I read.** The greedy 0.4740 is the
  s66 primary arm from RESULTS §17's table (`RESULTS.md:1043`).

## 3.5 Chapter 3's close numbers

**tree-verified**, `RESULTS.md:580-614`, the four bullets in full:

1. one-ply expectation search over a validated gen-1 forward model (transition agreement
   0.909) "is the project's best number: **0.793 vs SH, +0.069 over the same checkpoints
   played greedily**"; increment is SH-facing.
2. "**The advantage is real in self-play too**: in mirror games, search beats its own greedy
   self by **+0.15** (4/4 lanes) — twice its vs-SH increment."
3. "**But it does not compile into weights.** One iteration of expert iteration (494,603
   own-search decisions, actor-only offline distillation, frozen critic, self-play
   collection) made every lane WORSE vs SH (**−0.055 pooled, 4/4 negative** — B5+KILL…) …
   The actor expert-iteration family is closed for this chapter."
4. "**The critic is not the bottleneck in the ways we guessed**: it is not rank-collapsed
   (srank99 ~47/384 on the headline lanes), a 3-critic ensemble evaluator inside search was
   flat (+0.022, uncredited), and on-distribution critic disagreement is small (|v_LOO−v_own|
   ≈ 0.05–0.07 over 500k real decision points)."

And the closing sentence (`RESULTS.md:611-614`): "**search@M's value is real, and it is
inference-only.** … The open problem the next chapter inherits: everything here is strong
against SH-like play and still loses to Foul Play (0.39 h2h) — off-anchor strength, not more
search, is the path to ladder readiness."

## 3.6 The "search substitutes for a deficient value head" hypothesis, and the evidence against

**tree-verified.** The hypothesis is stated in JOURNEY, twice:

> "The hypothesis is that search substitutes for a deficient value head — the per-lane
> deltas were monotone in lane weakness (+0.051 / +0.104 / +0.148) and nearly equalized the
> lanes. If gains are already declining as the policy improves, the MCTS question closes
> here, before anything is spent on it." (`JOURNEY.md:21`)

> "Why here and not earlier: if search substitutes for a deficient value head, the honest
> test is against our best critic, after the special sauce and the massive train. A large
> depth gain here means search depth genuinely pays even with a good value function. A small
> one means full MCTS is not worth building. **This gates the gen9 search decision.**"
> (`JOURNEY.md:92-94`)

**The critic diagnostics the hypothesis has to survive** (all tree-verified):

| diagnostic | number | citation |
|---|---|---|
| D18 privileged critic | NULL and self-killed: pooled 0.5364, Δ −0.0145, z −0.65; "**FALSIFIER FIRED (the epitaph): EV rose on EVERY lane** … while win rate stayed flat" | `SESSION_LOGS.md:2647-2662` |
| D18 srank secondary | "the privileged input did NOT de-collapse the critic — critic ctx srank99 at 12M: s39 14 / s40 14 / s41 25 / s42 17 / s43 7 of 384"; "Collapse is training-dynamics-intrinsic, not information starvation" | `SESSION_LOGS.md:2664-2670` |
| D22-era srank — **STALE, do not quote** | "D26'S CRITIC IS NOT RANK-COLLAPSED: critic ctx srank99 measured 49/51/35/52 of 384 on the four headline finals; D22's '7-11 of 384' described D25-era nets and is STALE as a premise"; ladder "D23 control mean 14.8 -> D23 treatment 35.3 -> D25 12.6 -> **D26 46.8**" | `SESSION_LOGS.md:5908-5917` |
| the residual diagnosis | "The critic's residual weakness per the standing evidence is ALEATORIC fit limits (D18 zero-defect audit) plus decision-ordering quality (E2/E3/R4), NOT representation rank." | `SESSION_LOGS.md:5926-5929` |
| **Brier / Murphy decomposition (CH3 R0, Z1)** | "Z1: Brier 0.1567 = reliability 0.0117 (well calibrated) + resolution 0.0594 vs uncertainty 0.2050; aleatoric floor of EV 0.290 (V-bins explain ~29% of outcome variance — first-ever decomposition)" | `SESSION_LOGS.md:5049-5052` |
| what Z1 is and is not | "'Reliability 0.0117' is CH3 R0's Murphy decomposition of the *search* value head vs SH (Brier 0.1567 = 0.0117 + resolution 0.0594 / uncertainty 0.2050) — not a fleet-R0 read." | `docs/IDEAS_POST_100M.md:284-287` |
| the deficit's shape | "the deficit is resolution" (reliability 0.0117 = calibrated; resolution 0.0594 vs uncertainty 0.2050) | `docs/IDEAS_POST_100M.md:88-90` |
| hidden-information ceiling | "D18 says the outcome residual is largely aleatoric (entire hidden team worth +0.045 EV) and the value head is calibrated (Z1 reliability 0.0117)" | `docs/IDEAS_POST_100M.md:176-178` |

**Reading:** the value head is **calibrated but low-resolution**, and the record's own
standing diagnosis is that the residual is *aleatoric + decision-ordering*, not
representation. That is a *narrower* version of "deficient value head" than the JOURNEY
sentence implies, and search_depreciation.md should say so rather than importing the
hypothesis whole.

## 3.7 Is there a search read of the 100M final? — **NO. The endpoint is still pending.**

**tree-verified.** I read all of `RESULTS.md` §18 (`:1143-1269`). It contains **no searched
arm of any 100M lane.** The only search mention is the non-comparability line
(`:1260-1262`): "The 100M final vs the CH3 search number (0.7959 vs 0.7928 vs-SH) are
different policy forms measured in different sessions; they may not be ranked against each
other." The frozen eval schedule as executed (`SESSION_LOGS.md:9946-9958`) has five items —
vs-SH finals, the off-FP primary greedy, S-SHAPE, S-ANNEAL, BC-clone h2h — and no search arm.
`docs/IDEAS_POST_100M.md:97-98` says "the 100M primary adds the endpoint", which is true only for
the *greedy* curve; **the searched endpoint of the depreciation curve does not exist.**

**So: search_depreciation.md must state that its own endpoint is missing.** The curve today
is: 12M vs-SH +0.069 (search helps, SH-facing only); 50M off-FP +0.101 within-lane (search
helps, monotone in lane weakness); 50M-batch off-FP −0.093 (search HURTS, ~10 se, n=3000
matched); 100M — **not measured either way**. The measurement that would close it is a
search@M or search@20 arm on the 100M final at n=3000 off FP@20, n-matched to the existing
greedy primary — **needs-live-verification, barred until the ladder run completes.**

## 3.8 The ladder-object question

**tree-verified.** Current state, `STATUS.md:30-33`: "**LADDER R4 — LAUNCHED 2026-09-04
18:03Z** … Object: 100M final s112, **GREEDY**". Rationale, `README.md:166-171`: "**LADDER R4
(pre-registered and ratified 2026-09-04 …) returns to a greedy deployment** — the 100M final
on lane s112 — on R4S66's evidence (search@20 hurt the batch recipe); the MU-8 ceiling still
travels, and no run-to-run delta is an effect." Object selection: "median-of-3 on the off-FP
primary — ruled 2026-09-04 with the numbers already published, stated honestly per review_2
MF-2; Q6 discharged in writing, NO re-score" (`SESSION_LOGS.md:9988-9990`).

**And JOURNEY says the question is still formally open for step 11** (`JOURNEY.md:88`):
"Decide before launching whether the laddered object is greedy or searched. Depth-1
expectation search is currently deployed, so this is a live choice, not a default. … This is
the policy-form scope question that has been open since R2; step 11 is where it stops being
deferrable."

---

# 4. most-damage-typed

## 4.1 There is NO ruling or spec beyond JOURNEY and IDEAS §2.6

**tree-verified.** A repo-wide grep for `most-damage|most_damage|damage-typed` over `*.md`,
`*.py`, `*.yaml` returns exactly six hits: `JOURNEY.md:15,17`, `docs/IDEAS_POST_100M.md:102`,
`SESSION_LOGS_PREDECESSOR.md:404` and `configs/showdown_heur_512_s0.yaml:13` (both quoting
Metamon's "929/1000 vs most-damage" model-size datapoint, unrelated), and
`docs/prior_work/README.md:662,688-690`. **No pre-reg, no config, no script, no maintainer ruling,
no session-log entry.** It is an unbuilt proposal.

## 4.2 What the two proposal texts say

**tree-verified.** `JOURNEY.md:15-19`, verbatim:

> "Implement `most-damage-typed` as a standing anchor. Highest-damage move with type
> awareness, nothing else. One afternoon. We already have MaxBasePowerPlayer (no type
> awareness); this is the stronger sibling.
> Why it earns its place: it is the only anchor whose own strength doesn't drift across
> generations. SimpleHeuristicsPlayer has hazard branches that are inert in gen1 and live
> from gen4 on, so an SH-denominated number partly measures SH getting stronger as we move
> up the arc. Most-damage-typed has no generation-dependent code. That makes it the right
> denominator for a gen1 → gen4 → gen9 comparison.
> Secondary: H&L reported 0.829 against this bot in gen7. That's a cross-generation
> comparison and carries a confound (a pure damage bot is relatively weaker in gen7, where
> more mechanics exist for a good player to exploit), but it holds the opponent fixed, which
> no ladder comparison can."

`docs/IDEAS_POST_100M.md:102-104`, verbatim: "**2.6 most-damage-typed anchor — BUILD BEFORE STEP
3 (one afternoon; JOURNEY's own item).** The only anchor whose strength doesn't drift across
generations; H&L report 0.829 against it in gen7. Sibling of MaxBasePowerPlayer with type
awareness."

**The H&L 0.829 provenance and its caveat — tree-verified**,
`docs/prior_work/README.md:661-663` and `:687-690`: "Their bot table does NOT transfer: 0.829 is
vs a max-damage-typed bot **far weaker than SH**, and their 0.612 is vs the 2019 ancestor of
foul-play, pre-Rust." … "their strongest scripted baseline (most-damage-typed, 0.829) is far
weaker than SH — the bot-table non-transfer above now cuts BOTH ways: it removes 'we are
behind H&L' as a framing, and most-damage-typed is trivial to implement if that comparison
ever needs to be measured rather than argued."

**Caution for anchors_and_eval.md:** JOURNEY calls most-damage-typed "the stronger sibling"
(of MaxBasePowerPlayer) and the prior-work index calls it "far weaker than SH". Both can be
true — stronger than MaxBasePower, weaker than SH — but the note should say which comparison
it means. **The "no generation-dependent code" claim is JOURNEY's assertion and is
unverified anywhere in the record**; a type-aware damage bot in poke-env necessarily reads a
per-generation type chart and (from gen4) `move.category`, so "no generation-dependent code"
is a claim about *our* implementation, not a fact. **literature-only / needs source check by
the poke-env survey agent.**

## 4.3 How MaxBasePowerPlayer is used today

**tree-verified** (grep only, file:line):

- Registered in the opponent registry: `rl/envs/showdown.py:50` imports it;
  `rl/envs/showdown.py:61-64` defines `OPPONENT_PLAYERS: dict[str, type[Player]]` with the
  key `"max_power": MaxBasePowerPlayer` (`:63`).
- The registry has exactly three keys — pinned by test:
  `tests/test_showdown_env.py:411` asserts `sorted(OPPONENT_PLAYERS) == ["heuristics",
  "max_power", "random"]`; `:405` asserts `opponent_player("max_power", fmt)` is a
  `MaxBasePowerPlayer`.
- Reachable from the async collector too (`rl/envs/showdown_async.py:71,306-307`) and from
  the opponent-mix path (`rl/envs/showdown.py:942-956`) and single-opponent path (`:1167-1172`).
- **The only config that trains against it is the Phase-5 milestone-1 file**:
  `configs/showdown_maxbp_ppo.yaml:1` — "Phase 5 milestone 1: PPO vs MaxBasePowerPlayer on
  gen1randombattle."
- `scripts/make_bc_dataset.py:47-48` exposes it as an `--expert`/`--opponent` choice.
- **No eval config in `configs/eval/` uses it.** It is not part of the anchor battery. Its
  last recorded use as an anchor is the 2026-08-09 F1 line "MaxBasePower +9.2"
  (`SESSION_LOGS.md:2140,2153`) — a descriptive delta, not a battery leg.

**So a gen4 most-damage-typed anchor is a new `OPPONENT_PLAYERS` key plus a registry-pinning
test edit** (`tests/test_showdown_env.py:411` is a hard assertion on the exact key list and
will fail the moment a fourth opponent lands). **Cross-ref: anchors_and_eval.md,
encoder_requirements.md.**

---

# 5. Standing rulings that bind gen4 work

## 5.1 Cross-generation transfer — a JOURNEY standing note, NOT a ratified ruling

**tree-verified.** `JOURNEY.md:118`, verbatim:

> "- **Weights never transfer between generations** — only recipe. Wang tried a
>   bootstrapping variant and reported no significant improvement (§5.1.3); H&L's specialized
>   agent won 77/500 against its own predecessor after a short fine-tune. Mechanics differ
>   too much and the observation space changes anyway."

**Its status matters and is easy to overstate.** `JOURNEY.md` is the *maintainer's own
document*, "Committed VERBATIM (d43a512), unedited" on 2026-08-28
(`SESSION_LOGS.md:9211-9213`) — so the sentence is the maintainer's, not an assistant's. But
`CLAUDE.md:106-109` classifies the file: "the maintainer's high-level goals … **NOT a pre-reg
— intent, not claims; no gates, figures not authoritative.**" And `JOURNEY.md:5` says
"**Not a spec.** Chapter documents, config headers, and STATUS.md remain authoritative for
anything currently in flight."

**Therefore:** "weights never transfer between generations" is a **maintainer-authored
standing intent**, strong enough that nobody should propose gen1→gen4 warm-starting without
a ruling, but it is *not* a ratified pre-reg decision and it carries no gate. The same entry
that committed the file flags an unresolved question about it: "the open question about its
altitude (it mixes arc-level story with execution-level detail, and its standing note still
cites the **0.072 bar that r9 corrected to 0.1007**) belongs to the grill-me session"
(`SESSION_LOGS.md:9213-9216`). **That correction is still un-applied in `JOURNEY.md:116`,
which still says "against a 0.072 bar".** Flag it. **Cross-ref: open_questions.md.**

Related and consistent: `RESULTS.md`/`CHAPTER5.md` treat "expert data, human replays, teacher
distillation, ladder replays as training data" as permanently out of scope
(`CHAPTER5.md:497-498`); a gen1 teacher distilled into a gen4 learner would be the same
class of violation of the pure-self-play lane.

## 5.2 The 2026-08-23 ladder and big-runs rulings — both still in force

**tree-verified.** Maintainer verbatim at `SESSION_LOGS.md:5556-5563` (quoted in §2.2 above).
Executed as three items (`:5564-5576`). Their current status:

- **Ladder deferral** was later spent by execution — R1, R3 and now R4 have run; JOURNEY
  step 2 is "Gen1 ladder #3 — record. Happens regardless of what step 1's offline read says"
  with "**Exit condition: the run itself** — not a rating, not top-500" (`JOURNEY.md:31-33`).
- **The 120/250M reservation STAYS IN FORCE.** `CHAPTER5.md:508-513` (ruling 3): "**MOOT —
  dissolved by ruling 4, not decided.** … With 50M as the chapter ceiling, no run in Chapter
  5 is large enough for that ruling to bind. **It stays in force, untouched, and nothing here
  re-opens it.**" Then the 100M pre-reg re-checked it: "with ruling 4 fallen, §7 ruling 3
  un-moots — the 2026-08-23 big-runs ruling reserving 120/250M for ladder-ready polish or a
  visibly climbing log **STAYS IN FORCE, untouched**: 100M sits below that ruling's 120M
  threshold" (`configs/showdown_sp_100m.yaml:50-56`). And §18 repeats it: SS-CLIMB "does not
  license an extension (barred mid-run and after: a new pre-reg, a maintainer decision, the
  un-mooted 2026-08-23 big-runs ruling's territory)" (`RESULTS.md:1256-1258`).

**Consequence for a gen4 training pre-reg:** anything ≥120M steps in gen4 needs the
2026-08-23 ruling satisfied (ladder-ready polish, or logs visibly climbing) plus its own
pre-reg. **CHAPTER5 §7 ruling 4's 50M ceiling is CHAPTER-SCOPED and already superseded**
(`configs/showdown_sp_100m.yaml:43-49`), so it does not bind gen4 — say so explicitly rather
than letting someone import it.

## 5.3 The pre-registration conventions

**tree-verified**, `CLAUDE.md:171-184`, verbatim:

> "- **Pre-register every experiment** in the config header before launching —
>   pattern: `configs/showdown_r512_lra.yaml`. **Every header names its
>   `journey_step` and restates that step's exit condition verbatim.** Arms, R0
>   sanity gates, PRIMARY read with explicit credit line, secondary reads,
>   action on each branch.
> - **Credit line:** a lever is credited iff pooled delta ≥ +0.025 **and**
>   ≥ 2·se_diff. **The header must restate this verbatim, including the
>   larger-of (binomial vs seed-clustered) se_diff clause.**
> - **Five pre-reg rules the D25/D25-P cycle paid for** (each cost a maintainer
>   ruling — SESSION_LOGS 2026-08-11 onward): name the across-lane aggregator;
>   leave no unnamed cells in a partition; decide up front whether dose is
>   matched and how you'd know; restate the credit line verbatim; say which side
>   each band reads."

**The full credit line as a header must restate it** (`BRIEF_100M.md:56-60` S7, verbatim):

> "S7. Credit line VERBATIM in the header, exactly once: 'a lever is credited iff pooled
> delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the pooled-binomial
> se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals at
> read time.' Clustered formula: sqrt(s_arm^2/k_arm + s_cmp^2/k_cmp)."

and as it appears in a ratified header (`configs/showdown_sp_100m.yaml:59-66`), identical
text plus "BAR = max(0.025, 2*se_gov)".

**A live example of the `journey_step` requirement being met for OFF-ARC work**
(`configs/showdown_sp_100m.yaml:27-38`): "journey_step: **OFF-ARC WORK UNDER AN EXPLICIT
MAINTAINER RULING** (SF-17; CLAUDE.md's off-arc clause) — equivalently JOURNEY step 10
… Exit condition, completion-shaped (SF-17) … JOURNEY step 1's own scope-guard sentence —
'The trap is the retrain after this one.' (JOURNEY.md:29) — names THIS run; it is quoted here
so the ruling that overrides it is visibly deliberate."

**The 2-Opus rule** — origin, tree-verified (`SESSION_LOGS.md:2704-2706`): "**REGENERATIVE
L2-TOWARD-INIT pre-registration drafted, 2-agent-designed and 2-agent-reviewed (maintainer
instruction 2026-08-12: design decisions get 2 Opus agents + reviews)**". Restated as a
standing process at `CHAPTER5.md:556-558`: "**The standing process (maintainer, 2026-08-12)
is 2 Opus designers plus reviews for any pre-registration, lever design, protocol change or
roadmap choice.**" Scoped down by the user's own memory note (`MEMORY.md`: "full cycle ONLY
for irreversible artifacts (pre-regs, bars, published numbers); not for docs that are free to
rewrite") — **that scoping lives in maintainer memory, not in the repo record**, so a
gen4 doc that wants to skip the cycle should cite the memory note explicitly and say it is
not in the record.

**The §8 warning that governs how to run the cycle** (`CHAPTER5.md:559-568`), verbatim:

> "1. **§3's ranking and §4's sequencing are the assistant's** … Give the designers the
> candidate set, NOT this ranking, or the cycle ratifies a conclusion instead of testing it.
> That exact failure ('the synthesis hid the dispute') is on the record from the FP-gap
> cycle.
> 2. **§5's branch table is the load-bearing part** and is the part most likely to contain
> an unnamed cell."

## 5.4 STATUS's re-rank instruction

**tree-verified.** `STATUS.md:47-49`: "Standing rulings (3 left): CLAUDE.md:71 MPS wording;
pool.py:88 fix; stall-kill crash_forfeit read rule. **IDEAS_POST_100M re-rank per its §1
(SS-CLIMB: 'more steps' competes; extensions need a new pre-reg).** gen4-design resume:
maintainer's call, off the ladder critical path."

The §1 rule it points at (`docs/IDEAS_POST_100M.md:29-33`): "The 100M grade re-ranks §4: **if
S-SHAPE is still rising at 100M** (quote it with the mandatory anneal sentence), **'more
steps' competes with every lever and the standing fewer-bigger-runs order favors it**; if it
is bending, the per-step levers below rise. Write the §4 pre-reg *after* the grade." SS-CLIMB
fired (`RESULTS.md:1186-1196`), so **the "more steps" branch is the live one and the re-rank
is OWED and NOT DONE.**

**Direct consequence for gen4:** the horizon question is unsettled in gen1, and gen4's
episodes are longer, so any gen4 budget argument that leans on "50M was enough in gen1" is
leaning on a re-rank that has not happened.

## 5.5 Where gen4-design stands

**tree-verified.** `STATUS.md:25-27`: "**`gen4-design` PAUSED (maintainer, 2026-09-04
evening) — NOT a ladder blocker.** As found: ZERO commits of its own, worktree
`docs/design_gen4` EMPTY, base 58 commits behind main — rebase onto main when resumed."
Maintainer's words (`SESSION_LOGS.md:10046-10047`): "audit worktree is done, gen4-design is
paused (i can resume it later at any time, its not a blocker for our ladder work here)".

## 5.6 The encoder seam landing (F-08) — the fact gen4 encoder work builds on

**tree-verified.** `SESSION_LOGS.md:10024-10028`: "F-08 `EncoderSpec` per-gen seam, gen-1
encoding sha256-pinned identical on 6000 tape decisions at 612/808/828, `Discrete(10)`
derived from the format (10 through gen 5, 26 at gen 9)."

Branch-log detail (`docs/archive/AUDIT_BRANCH_LOG.md:303-315`): the seam is
"rl/envs/encoder_spec.py's frozen EncoderSpec with every per-gen table plus the derived
*_off/*_dim_v1 layout properties and n_actions via SinglesEnv.get_action_space_size; GEN1
carrying today's tables in today's order; **spec_for_format keyed on
GenData.from_format(fmt).gen with a NotImplementedError that names the missing pieces; the
gen-4 work list in the class docstring (incl. 'per-move physical/special is already
poke-env's move.category')**". A round-2 fix is also recorded as a gen-boundary correction:
"F-08: review fixes — **Reflect/Light Screen are gen-2 side conditions, terrain is gen 6**"
(`:308`).

**Open questions F-08 left for the maintainer** (`docs/archive/AUDIT_BRANCH_LOG.md:333-345`),
the ones that touch a gen4 encoder:

- "`gym.spaces.Discrete(10)` literals remain in analysis/eval scripts NOT listed in F-08
  (scripts/ch3_eval.py:577, scripts/ch3_fidelity_check.py:896, scripts/ch3_r1_spike.py:50,
  scripts/foulplay_vs_sh.py:159, scripts/d22_weight_norms.py:141, …)" — harmless at gen4
  (still 10) but a landmine at gen9.
- "`rl/networks/entity_deepsets.py`'s privileged-critic check has a literal `+ 10` … that 10
  is PRIV_ID_DIM (the id block), NOT the action count. I left it; flagging it so a future
  reader does not 'fix' it into N_ACTIONS."
- "`rl/networks/opp_action.py`'s L6 head over 4 move slots … is a per-move-slot head, not an
  action-space size … **It will need its own pass at gen 6+ where 4 move slots stop meaning
  4 move actions.**" — i.e. safe through gen4.
- "F-07 (encoder flags into Config) is adjacent and untouched … `spec_for_format`
  deliberately says nothing about the v2/ids flags (they are process-level, not per-gen)."
  `docs/proposals/F07_encoder_config_block.md` is the unruled proposal.

Consolidated open rulings (`:488-498`): F-21 (keep the borrowed set prior tracked?), F-04
(minibatch tail keep/fold/drop + routing), F-06/F-07 option choices, F-05 cadence (4
updates?), F-03 900 s liveness. **None gate the ladder** (`STATUS.md:43-45`).
**Cross-ref: encoder_requirements.md.**

## 5.7 The lifecycle rule that blocks archiving CHAPTER5

**tree-verified.** `docs/CLEANUP.md:26-30`: "**CHAPTER5.md migration** (its own lifecycle rule):
§3 (C1–C6 provenance), §6 (out-of-scope), §7 (five rulings incl. the 50M ceiling) must
survive into R2's pre-reg header; §1/§2/§4/§5/§8 are migrated/superseded already. Archive the
file WITH or AFTER R2's pre-reg — never before." R2 has since run and been credited
(`RESULTS.md:1022`), and CHAPTER5 §7's ruling 4 has been superseded by the 100M header — so
the migration obligation is partly discharged and partly stale. Not my call to resolve;
flagging it because a gen4 chapter brief is the natural place someone would try to fold
CHAPTER5 away.

## 5.8 §3b A2 (both-seat harvest) — licensed, still unbuilt

**tree-verified**, `CHAPTER5.md:249-256`, verbatim:

> "- **A2 — both-seat harvest.** We buffer agent1's transitions only; the opponent seat is a
> `PoolPlayer` whose trajectory is discarded. H&L consume both, and their per-battle batches
> are RETURN-BALANCED by construction (one winner + one loser), which removes batch-level
> outcome noise. **That is a variance property, not a data-volume one, so 50M-flat does not
> speak to it** — and gen 1 is unusually luck-heavy (freeze, para, crits, 1/256). Needs real
> collection wiring."

Status: licensed 2026-08-26 but SUBORDINATE (`CHAPTER5.md:239-241`, and ruling 5 at
`:531-536`); A4 (batch size) took R2's slot and credited; **A2 was never built.** It matters
for gen4 because Wang collected both seats too (§1.2) and because the "gen 1 is unusually
luck-heavy" premise weakens in gen4 (no 1/256 miss, different crit math) — i.e. the *argument
for* A2 is partly generation-specific. `A4`'s text also names A2 as "the first free 2x of
this same quantity at identical simulation cost … and A2 the obvious dose-matched placebo"
(`CHAPTER5.md:288-290`).

---

# 6. The 2-Opus house style for adjudications — three worked examples

**tree-verified** (MAIN, allowed path):
`/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/results/design_ch5_100m/synthesis_100m.md`.

The document's own shape is: **header naming the inputs** → **"Agreed without adjudication
(both memos, independently)"** → **"Runner adjudications (each records the losing
argument)"** → **"Carried to ratification (nothing silently assumed)"** → **"Refusal lists"**.
Verbatim frame (`synthesis_100m.md:3-5`): "Inputs: BRIEF_100M.md; mem_A.md (evidential
validity); mem_B.md (build/ops/cost). Neither memo escalated a SETTLED item. The draft
transcribes the agreed core and the adjudications below; reviews follow on the frozen draft."

Three adjudications to imitate:

**ADJ-1 — the "both were valid, here is why one won, and nothing is lost" form**
(`synthesis_100m.md:36-40`), verbatim:

> "ADJ-1 SEEDS: **104/112/120 (A), spares 128/136/144 ordered, replacement never addition.**
> B's 101/109/117 was equally valid on every criterion both memos checked (fresh, disjoint
> 8-wide windows, safe on both branches); A's triple is adopted for its specified spare
> protocol and the explicit 'no window contains any seed with a run dir' check. Nothing of
> B's is lost."

**ADJ-2 — the "the loser's objection is actually an argument for the winner" form, with the
adopted item's own scope limits attached** (`synthesis_100m.md:42-50`), verbatim:

> "ADJ-2 A-COLL: **adopted (A).** B refused 'the claim that G9's null at 12M bounds a bias at
> 100M' — which is an argument FOR A-COLL, not against it: G9 is vs-SH at 12M with a band
> exactly the size of the credit floor, so on a P1 credit the collector's effect on the
> PRIMARY axis is measured (6 arms x 3000 off-FP@20 at the 12M rungs, async acceptance fleet
> vs banked sync fleet, 7.75 h, agent-side, post-fleet, conditional on P1). Descriptive, can
> only weaken a credit, never a verdict input. Every credit sentence carries G9's signed
> delta; the header states G9 tests async AND timer jointly (A's third-wire-delta finding;
> discharges F6's owed RESULTS line)."

**ADJ-4 — the "right in spirit, wrong in mechanism; here is the corrected formula, and the
loser's form survives on the other branch" form** (`synthesis_100m.md:59-65`), verbatim:

> "ADJ-4 D-A FORM: **A's band form on the async branch.** B's closed form ('read against the
> checkpoint's own recorded steps_seen') is right in spirit but the optimizer's lr at a rung
> reflects the LAST UPDATE's anneal_basis, which lags the rung step by up to ~62k steps.
> Async D-A: lr within [f(step), f(step - 61,440)] per param group, f(s) = base_lr x max(0, 1
> - s/1e8) (x actor_lr_scale for groups 0/2). Sync fallback: B's closed form verbatim."

**The "carried to ratification" and "refusal lists" sections** (`synthesis_100m.md:75-85`),
verbatim, so a writer can copy the pattern of *not* silently deciding:

> "## Carried to ratification (nothing silently assumed)
> A's E1-E6 (FP-primary promotion for THIS round; 200-rung retention until
> S-SHAPE/S-ANNEAL/D-A recorded; A-COLL's conditional 7.75 h; N-TIMER disclosed-not-celled
> with the joint-coverage sentence; K6 rescale; R0-MEM fill-in) + B's two ops gaps: the
> control fleet has NO BACKUP COPY (a deletion would orphan the primary's comparator —
> ratify a copy or a retention clause) and the control's own 300 rungs need a retention line.
>
> ## Refusal lists
> Union of A §11 (11 items) and B §9 (9 items) — no conflicts between them; all are honored
> in the draft."

**The brief's own house style** is worth copying too — a numbered **"SETTLED — not open for
redesign. Believe one is wrong → write an ESCALATION section; do not silently design around
it"** block (`BRIEF_100M.md:29-60`), with each S-item carrying its reason, e.g. S5: "The case
for 100M is INDEPENDENT of the 2026-08-31 scale-shape read (one seed, cannot distinguish
plateau from noise); that read is not load-bearing in either direction and the header must
not lean on it", and S6, which forces the *losing* alternative into the header: "The header
must state why 100M x 3 beats the cheaper alternative it has to beat — 50M with more seeds …
The maintainer's choice is made (S1) — state the case and its honest weakness; do not
relitigate."

The downstream record of what the cycle bought (`SESSION_LOGS.md:9872-9886`): "brief -> two
Opus design memos (A evidential, B ops/cost) -> synthesis with six adjudications -> draft
fa450c2 … -> two Opus reviews (12 MUST-FIX, 27 SHOULD-FIX total) -> ALL applied and tagged
(722a31c) … Review 2 also caught the wave's rung-literal bug BEFORE any lane launched
(0410f10) — the cycle paid for itself twice."

The ladder-R4 cycle used the same shape at larger scale (`SESSION_LOGS.md:9974-9979`): "Full
2-Opus cycle: brief → mem_A (validity) / mem_B (ops) → synthesis (6 adjudications, losing
arguments recorded) → 578-line draft → review_1 (10 MF + 21 SF) + review_2 (6 MF + 13 SF) →
ALL 50 findings applied → maintainer ruled M1-M9".

---

# 7. gen1 encoder assumptions this breaks

These are the assumptions **in the project record** (not in the encoder source — that is
another agent's family) that stop holding at gen4.

1. **"Wang's encoder-relevant poke-env fixes are already upstreamed in 0.15.0."** The
   verified population was **two** fixes; the rest were dismissed as "structurally impossible
   in gen1" — Max PP tables, Sleep Talk, Curse ???-type, ability weather, Trace,
   `_orig_item`, choice lock (`SESSION_LOGS_PREDECESSOR.md:1091-1095`). **All live in gen4.**
   The bound that made the risk tolerable ("bounded by the clone (0.453 through this exact
   encoder)") is a gen1 bound.
2. **The BC-clone anchor leg is a frozen gen1 artifact at OBS_DIM 808** while live obs is 828
   (`configs/eval/ch5_100m_offfp.yaml:31`; `SESSION_LOGS.md:10105`). Gen4 needs a new clone
   built from a gen4-capable teacher, and the clone's build recipe is a *gen1* recipe.
3. **"FP is flat in search budget"** — the FP budget ladder's own explanation is "gen1's
   small trees (20 ms already searches deep enough)" (`SESSION_LOGS.md:5711-5713`). Gen4
   trees are larger; the FP@20 licence (MU-2, "5.1x cheaper") does not automatically carry.
4. **"SH is a stable denominator."** `JOURNEY.md:17`: "SimpleHeuristicsPlayer has hazard
   branches that are **inert in gen1 and live from gen4 on**, so an SH-denominated number
   partly measures SH getting stronger as we move up the arc." Every locked-protocol number
   we own is denominated in a *weaker* SH than gen4's.
5. **The SH boost bug's magnitude.** The record's comparability caveat
   (`SESSION_LOGS_PREDECESSOR.md:1023-1027`) assumes the bug is a constant offset; setup moves
   and boosts are far more central in gen4, so it is not.
6. **Action space 10 is fine, but the reason is generational.** F-08 derives it from the
   format — "10 through gen 5, 26 at gen 9" (`SESSION_LOGS.md:10027`). Gen4 keeps 10, so
   Wang's 494-way identity space stays the outlier, but `rl/networks/opp_action.py`'s 4-move-
   slot head is flagged as needing "its own pass at gen 6+"
   (`docs/archive/AUDIT_BRANCH_LOG.md:340-342`).
7. **Physical/special is type-determined.** `JOURNEY.md:38`: "gen4 is where physical/special
   becomes a per-move field rather than type-determined — that branch changes here and does
   not carry back." F-08's docstring already anticipates it: "per-move physical/special is
   already poke-env's move.category" (`docs/archive/AUDIT_BRANCH_LOG.md:311-312`).
8. **Side conditions and field state.** F-08's own round-2 correction:
   "Reflect/Light Screen are gen-2 side conditions, terrain is gen 6"
   (`docs/archive/AUDIT_BRANCH_LOG.md:308`) — the gen1 encoder's screen handling is a gen1
   special case (and gen1 Light Screen already breaks poke-env: "Light Screen →
   `Effect.UNKNOWN`", `SESSION_LOGS_PREDECESSOR.md:1096-1097`).
9. **"gen1 is luck-heavy" as a design premise.** A2's argument
   (`CHAPTER5.md:252-255`) rests on "freeze, para, crits, 1/256"; the 1/256 miss is gone in
   gen4 and crit math changes, so the variance argument for both-seat harvest weakens.
10. **Partial observability is the same problem.** `JOURNEY.md:119`: "**Gen 5+ introduces
    team preview**, which *removes* the hidden-team problem. Gens 1–4 keep it." Gen4 keeps
    it — so the set-prior machinery (`rl/envs/data/gen1_randbats_sets.json`, F-21, now
    tracked but with an owed ruling) has a gen4 analogue and the encoder work list should
    say who builds it.
11. **σ_seed ≈ 0.062 and the ~0.07 bar are gen1 constants.**
    `JOURNEY.md:116`: "gen1 measurements are currently uninterpretable at k=3 with σ_seed ≈
    0.062 against a 0.072 bar. Every sequencing decision above follows from that." (That 0.072
    is itself stale — r9 corrected it to 0.1007, `docs/IDEAS_POST_100M.md:22-24`.) Gen4's noise
    floor is **unmeasured**; no gen4 pre-reg may inherit these numbers.
12. **Episode length ~25–32 decisions.** `docs/IDEAS_POST_100M.md:298-299`: "self-play measures
    26–32 by era (R2: 32.047); 27.2 is decisions *vs SH*". `JOURNEY.md:75` already flags the
    consequence: "λ especially, since its effect scales as λ^(T−t), and that is a different
    regime at T≈25 than at T≈100."

---

# 8. Open questions for the maintainer (from the record; each with the record's own framing)

1. **Which Wang number are we matching — Table 4.1's 0.786 or Fig 4.1's ~0.85 — and what
   does "matched" mean numerically?** JOURNEY orders this pinned *before* starting
   (`JOURNEY.md:54-55`) and it is unruled. Note our own digitization of Fig 4.1 exists
   (`SESSION_LOGS_PREDECESSOR.md:977-982`) and is a third option: match the *curve*, not a
   point.
2. **Does the anchor battery survive into gen4 unchanged, and what are its legs?** vs-SH is
   a *different* SH in gen4 (§7.4 above); the BC clone must be rebuilt from something; the FP
   leg needs a gen4-capable Foul Play and a re-run budget ladder. Recommend the battery's
   *shape* is preserved and every leg is re-derived with disclosure.
3. **Is most-damage-typed built, and does it become a battery leg or stay descriptive?**
   Never ruled; only proposed (`JOURNEY.md:15-19`, `docs/IDEAS_POST_100M.md:102-104`). Note it
   costs a `tests/test_showdown_env.py:411` edit (the registry key list is asserted).
4. **Does "weights never transfer between generations" bind as a ruling, or is it intent?**
   It is a maintainer-authored JOURNEY standing note in a file CLAUDE.md calls "NOT a
   pre-reg" (§5.1). A gen4 pre-reg that assumes it should say which.
5. **Search's endpoint is missing.** No searched read of any 100M lane exists (§3.7). Does
   search_depreciation.md ship with an admitted hole, or does a searched 100M arm get
   pre-registered? (It is eval-only, ~2.6 h at R4S66's rate, and barred until the ladder run
   ends.)
6. **The IDEAS_POST_100M §1 re-rank is owed** under SS-CLIMB and has not been done
   (`STATUS.md:47-48`). Does gen4 sequencing wait on it?
7. **`JOURNEY.md:116`'s 0.072 bar is stale** (r9 corrected it to 0.1007) and the
   "altitude" question the 2026-08-29 entry parked (`SESSION_LOGS.md:9213-9216`) is still
   parked. Fix in place, or leave the maintainer's file verbatim?
8. **F-07 / F-21** (`docs/archive/AUDIT_BRANCH_LOG.md:488-498`) both touch the encoder and
   are unruled: whether encoder flags move into `Config`, and whether the borrowed set prior
   stays tracked. A gen4 encoder inherits both.
9. **Gen4 chapter exit condition.** `JOURNEY.md:68`: "**Give gen4 a written exit condition
   when the chapter is opened**, or it becomes where the project lives. It is a borrowed
   instrument, not a home." Unwritten.
10. **`docs/IDEAS_POST_100M.md:96` says "12M per-lane search deltas" and they are 50M off-FP
    deltas** (§3.1). Correct the file, or record the correction only in the gen4 notes?

---

# 9. Unread / unverified — what I did NOT check

- **I did not open a single PDF or external clone this session.** Every Wang, H&L, ps-ppo,
  VGC-Bench, Metamon and pokejax number here is quoted **as the project record reports it**.
  Where the record says a subagent verified something against the primary, I tagged it
  source-verified and named the entry; that is a chain of custody, not a re-verification.
- **Wang's Table A.1/A.2/A.3 digits** (`JOURNEY.md:42,45`) are literature-only at digit
  granularity. Someone should re-check γ 0.9999 / λ 0.754 / the LR formula
  10^-4.23/(8x+1)^1.5 against the thesis text dump before a gen4 config header quotes them.
- **`docs/prior_work/wang_fork_diffs.md` itself** (2,362 lines, untracked) — not read. My account
  of the fork contents is the 2026-08-03 log entry's account.
- **`rl/envs/encoder_spec.py`** — not read; only its landing record
  (`docs/archive/AUDIT_BRANCH_LOG.md:303-345`) and the audit-close log entry.
  `docs/proposals/F07_encoder_config_block.md` — not read.
- **`configs/eval/ladder_r4.yaml` and everything under `results/ladder`** — barred; the run
  is blind. Nothing in this note depends on R4's outcome.
- **`mem_A.md` / `mem_B.md` / `review_1.md` / `review_2.md`** of the 100M cycle (3,000+
  lines) — not read; only `synthesis_100m.md` and `BRIEF_100M.md` were in scope. The
  refusal lists are therefore known only by their *count* (A §11 = 11 items, B §9 = 9
  items), not by content.
- **`results/design_fp_gap/ch4_synthesis.md`** — read only the two MU-2 blocks (165–178,
  276–290); its other adjudications are unread and may contain further anchor rulings.
- **`RESULTS.md` §§1–12, 14, 15** and `README.md` outside 160–185 — not read. §15 is "the
  full vs-SH results table and the chapter narrative" and will contain per-arm numbers I have
  not cross-checked.
- **`SESSION_LOGS.md` entries not listed in my source table** — roughly 250 of ~300 entries
  are unread. I selected by title and date per the protocol; a claim I report as "not in the
  record" means "not in the entries I read plus the greps I ran", and the greps were narrow
  (`wang`, `MU-2`, `MU-8`, `most-damage`, `R4S66`, `0.148`, `anchor batter`, `JOURNEY`,
  `MaxBasePowerPlayer`) — I did not run broad keyword greps over SESSION_LOGS, per protocol.
- **Nothing here is needs-live-verification except where explicitly tagged** (§2.7 gen4 FP
  budget gradient; §3.7 the searched 100M endpoint). Both are barred until the ladder run and
  any later fleet complete.
