# Monster pre-reg — drafting notes

**Serves:** JOURNEY step 10, the 100M gen-1 fleet whose finals are the step-11
ladder candidates. **Drafted 2026-09-10.** Nothing here is ratified; the
authority is `configs/showdown_monster100m.yaml` (prose) and
`configs/showdown_monster100m.prereg.yaml` (machine-readable). This file records
**what had to be decided to write those**, **what is being left to the
maintainer**, and **what in the drafting brief turned out to be wrong against
the code**. It is not a second copy of the pre-reg.

## Four things changed under this draft on 2026-09-10

Two measured facts and two open decisions. The pre-reg is drafted **to the
facts**; the decisions are written out with **both branches** and are not picked
here.

**FACT 1 — arm B is bitwise arm A.** `runs/engine_pe_s66` vs `runs/engine_a1b_s66`
at `ckpt_010500013`: **21 identical rungs** including the step counter, **223
shared tensors / 3,428,015 elements, ZERO differing**, digest
`104a9339eb6a2260`. The head takes a separate `autograd.grad` over its own
params after the clip is read and its construction rewinds the global RNG, so
actor, critic, aux head and every minibatch permutation match.

- **A greedy A-vs-B comparison is not "null by design" — it is literally the same
  number.** It is no longer registered as a contrast. The cell is **P-ID**, an
  identity *assertion*: a single differing element is an **R0-class event**, not
  a result.
- **This falsifies a claim an earlier draft of this file made.** That draft argued
  collector/learner interleaving would make the lanes drift and proposed
  `|B − A|` as the collector's run-to-run reproducibility floor. **The collector
  is deterministic** at a fixed lane seed and policy — the battle stream is
  `splitmix64(lane_seed * PHI ^ battle_counter)`, the pool stream is a private
  `np.random.default_rng(seed)`, neither reads a clock. There is no interleaving
  floor and the reasoning that predicted one was wrong. It is recorded in the
  header rather than deleted.
- **Three of the nine planned lanes were buying duplicate checkpoints.**

**FACT 2 — arm B's target was wrong and is fixed (commit `b147f48`).** The head
regressed the GAE(λ) target. At γ=1 with a terminal-only reward that is exactly
`lam^(N-1-t)*z + (1-lam)*sum_k lam^(k-1) V(s_t+k)`, so at λ=0.95 over ~34
decisions **~53% of the head's target mass was the ordinary critic's own output —
~82% at the first decision**, which is where the privileged block carries the most
information. It now regresses the Monte-Carlo return.

- The verdict metric is **`priv_eval/ev_mc_advantage`** (head EV − critic EV, both
  against the outcome, same batch, same pass — `rl/agents/ppo.py:1638-1653`).
- **`priv_eval/explained_variance` is a DIAGNOSTIC and is barred as a verdict
  input**, and the header says why: scoring the head against a target half-written
  by its opponent flatters it by construction.
- **R0-B5 now gates on the post-fix keys being present from update 1** — their
  absence means the lane is running the pre-fix head, which is the one thing that
  distinguishes a correct arm-B lane from the smoke that was running while this
  was drafted.

**DECISION 1 (RWM-11) — does B ride A's lanes?** Recommended **D1-RIDE**:
`priv_eval_coef` on in arm A's own three lanes, the bitwise smoke as the control,
**three lanes freed**. `D1-SEPARATE` is written out in full and leaves a complete
pre-reg. The freed lanes are a **named branch (RWM-12)** with two concrete
allocations — `ALLOC-AB5C4` (A/B on five seeds, C on four) and `ALLOC-AB9` (all
nine on A/B, if arm C is dropped). More seeds is the leading candidate because
**the governing band is seed-clustered** and because the ladder object is an
**ensemble** candidate (S3's P-E read the LOO-ensemble at ~+0.012 on a 3-member
pool).

**DECISION 2 (RWM-13) — arm C.** Both reviews contest it, and all three objections
are in the header: it is D18's exact lever at **λ=0.95** while the vacatur named
the **λ=1.0 pure-baseline** variant; the variance-reduction channel has **~30×
less headroom** at a 30,720-step update than at D18's 1,024; and **its falsifier as
first drafted could not fire** — it conditioned on an "uncollapsed critic", and the
**maximum critic ctx srank99 ever recorded in this project is 25 of 384**.

- **The word "kill" is barred for this arm** per the 2026-09-06 ruling. Only
  **NULL** and **CREDITED NEGATIVE** are available. The earlier `C-FLAT-KILL` cell
  is **removed, not renamed**.
- The partition is now an exhaustive **(primary delta) × (mechanism moved)** cross
  — 3 × 2 with the FLAT/NOT-MOVED cell sub-labelled by which leg failed, **eight
  named cells, all reachable**. srank and EV are **reported axes**, not gates, so
  an arm C that moves EV and not srank still lands in a named cell
  (`C-FLAT-EVONLY`) and is reported as a **replication** of D18 at 8.3× the dose.
- Every arm-C sentence names `gae_lambda 0.95, update 30,720, k=<n>`, or a null
  here will be read as answering IDEAS 4.7 when it answers D18.

**Also now carried in the header:**

- **No search seam exists.** `grep -rn priv_eval rl/search/` returns zero lines.
  **P-BS is DEFERRED and is not a cell of this run**; the six sites it waits on are
  named, and arm B's registered primary is the training-time **P-BEV**, available
  today. The artifact survives the deferral because the head is in every
  checkpoint — recoverable at eval cost only, and **not** recoverable if the head
  is not trained now.
- **Power, printed verbatim.** At k=3 × n=3000, **P(credit | a true +0.025) =
  0.45** — a coin flip at its own bar. On the vs-SH axis at p=0.789, **≈0.07**,
  where credit needs **≥ 0.81367**. The saturation argument was already
  pre-registered at `configs/showdown_sp_100m.yaml:141-145` and `:205-213`; this
  file re-prints it. Both figures ride every null the run produces.

## The deliverables

| file | what |
|---|---|
| `configs/showdown_monster100m.yaml` | arm A **and the whole prose pre-registration** |
| `configs/showdown_monster100m_b.yaml` | arm B; 4 keys differ, quotes the parent by path |
| `configs/showdown_monster100m_c.yaml` | arm C; 3 keys differ, quotes the parent by path |
| `configs/showdown_monster100m.prereg.yaml` | the sidecar; `rulings_wanted` last, `ratified_decisions: {}`, `verdict_authorized: false` |

The two extra config files are not a stylistic choice: `rl/train.py` has
`--config`, `--seed`, `--run-name` and no key-override flag
(`rl/train.py:1460-1465`), so three arms is three files or it is not launchable.

**Verified, not assumed** (2026-09-10, `pkmn-engine-port` env, both encoder env
vars set):

- All three configs pass `load_config` → `selfplay_env_kwargs` (both keys) →
  `_async_collector_mode` → `_engine_collector_checks`. That is every launch-time
  guard `rl/train.py` applies before it touches a GPU-free tensor.
- Key-by-key diff on the parsed YAML: A↔B differ in exactly 4 keys, A↔C in
  exactly 3, A↔`showdown_sp_100m.yaml` in exactly 8. **Zero undeclared
  differences.**
- `PPOAgent` builds for all three at seed 104, param counts and shapes as the R0
  gates claim — see the table below.
- No duplicate YAML keys at any depth in any of the four files (the R1 defect
  `tests/test_ch5_r2_prereg.py::test_no_duplicate_keys_at_any_depth` exists for).
- The credit-line phrase appears **exactly once** in the header (the repo's own
  `test_header_carries_the_load_bearing_verbatims` rule).
- `tests/test_100m_prereg.py` and `tests/test_ch5_r2_prereg.py` — 42 passed. They
  stay green until a lane writes its config; see "the amendment" below.

### The agent builds, measured at seed 104

| arm | actor params | **actor param sum** | critic params | critic ctx_in | priv_eval head | block_dim |
|---|---|---|---|---|---|---|
| A | 626,059 | **442.300** | 494,849 | 640 | — | 0 |
| B | 626,059 | **442.300** | 494,849 | 640 | 642,305 (ctx_in 1024) | 408 |
| C | 626,059 | **375.635** | 642,305 | 1024 | — | 408 |

This is the init-pairing claim, checkable in one line at launch: **B's actor and
critic are bit-identical to A's; C's actor is not.**

---

## What I had to decide

### 1. Seeds: one triple across all three arms, under distinct `seat_tag`s

CLAUDE.md rule 2 says distinct `--seed`s **including across arms**. I read the
*mechanism* rather than the headline, because on this collector the mechanism has
moved:

- `rl/train.py:508-525` — on `collector.mode: engine` **no training env is
  constructed at all**. The agent is built against `fake_spaces()`; the collector
  is in-process with "no sockets, no threads, no child processes".
- The only poke-env object per lane is the in-loop **eval** env
  (`rl/train.py:533`, `make_eval_env`, `seat_role="e"`) — two usernames.
- `rl/envs/make.py:41-49`: with `seat_tag` set, explicit `AccountConfiguration`s
  are injected from `seat_names(seed, tag, role)` =
  `f"as2s{seed}{role}{sha256(tag)[:4]}"` + `{a,b}`. **poke-env's global-`random`
  derivation is never reached**, so rule 2's failure mechanism is not present.

Verified live rather than derived: the design-B smoke at seed 66 under
`seat_tag: pe` is on the server right now as `as2s66ecdf6a` / `as2s66ecdf6b`
(`runs/engine_pe_s66.nohup.log`) — exactly `seat_names(66, "pe", "e")`.

So the answer is **all three arms may share one seed triple, provided every arm
carries a distinct `seat_tag`**. The 18 usernames are computed and pinned in the
header; all distinct, 13 characters against the 18-character cap.

I chose **104 / 112 / 120** — the banked Node 100M fleet's own seeds — because
that makes arm A init-paired lane-for-lane with
`runs/showdown_sp_100m_s{104,112,120}`: same recipe, same dose, same anneal,
**only the collector differs**. That buys the 100M reading of the collector delta
A-1 explicitly could not produce, for a 6-minute fresh re-read, and it cannot be
recovered later.

**The 8-wide "seed window" is a vector-path reservation and does not bind an
engine lane.** `make_vec_env` seeds sub-env *i* at `seed + i`; the engine path
builds no vector env. Recorded so the window is not later treated as a live
constraint.

### 2. The amendment the ratification commit must make — and it is not the one the brief named

- **`tests/test_100m_prereg.py::test_seed_windows_disjoint_and_unused` goes RED
  the moment lane 1 writes its config.** It enumerates `[104..111]`,
  `[112..119]`, `[120..127]` and allows only `showdown_sp_100m_s{104,112,120}` to
  stamp a seed inside them. The amendment adds the nine monster dirs as the
  **second legal owner**, in the comment form the 2026-09-01 and 2026-09-09
  amendments used, **in the ratification commit**.
- **`tests/test_ch5_r2_prereg.py::test_seeds_are_window_disjoint_and_unused`** —
  the test the brief named — guards 66/75/83 only and is **unaffected**.

### 3. `priv_eval_coef: 0.5`

The head shares no parameters with the actor or the critic, has its own Adam
group and its own gradient clip, and feeds nothing — so the coefficient **cannot
reach the policy or the critic by construction**, and the only channels it
touches at all are the clip threshold and Adam's epsilon. Its value is therefore
an optimisation choice for the head alone. 0.5 is `value_coef`: it trains the
evaluator head under the **critic's own recipe**, which is what makes
`priv_eval/explained_variance` an apples-to-apples read against
`loss/explained_variance` on the same batch (read P-EV). **Chosen for
comparability, not tuned**, and no tuning of it is licensed.

### 4. Width and waves: 6-wide in two arm-balanced waves, ~45.3 h

Planning rate: the **A-1b lanes' own whole-lane** rate (1,386.79 steps/s at width
3, evals on, fixed build) scaled by the **measured** maxout width ratio
(1,282.3 / 1,620.5 = 0.7913) → **1,097.4 steps/s per lane at width 6**. One
extrapolation, labelled: the width ratio is measured with evals *off*, so it is
an upper bound on rate.

- Wave 1: seeds 104 + 112, **all three arms**, 6 lanes, width 6 → 25.3 h
- Wave 2: seed 120, **all three arms**, 3 lanes, width 3 → 20.0 h
- **~45.3 h**, against the banked Node fleet's 49.4–49.8 h for *three* lanes.

**Waves are cut by seed, never by arm.** A wave is a shared box condition; a wave
holding unequal numbers of each arm confounds arm with box. Cut by seed, every
wave holds one lane of each arm per seed and the wave effect cancels in every
between-arm contrast.

**Nine-wide is refused on memory, and the refusal is measured.** Per-lane RSS at
width 6 is 1.825 GB (`maxout.json`'s `peak_rss_gb` is the **fleet sum**, not
per-lane — `scripts/engine_maxout.py:58-72`), so nine lanes is 16.4 GB of the
non-growing figure against 11–13 GB of comparable idle headroom on a 24 GB box.
Growth over a 25 h lane is unmeasured on this path; on the Node path a lane grew
1.39× over 49 h. The named, measured unlock is the **mmap'd team bank** (3
processes: 1.37 GB `read()` vs 0.00 GB mmap'd), which is staged in STATUS as a
free win and not implemented.

Because 6 is the top of the measured grid, the pre-reg adds a **12-minute W-0
measurement at launch** with a pre-stated rule (9-wide iff aggregate ≥ 1.10× the
6-wide aggregate **and** fleet peak RSS ≤ 14.0 GB).

### 5. Arm B's win-rate read is deferred, and its primary is the one that exists

Arm B's only credit-seeking read is the **searched** one, and **nothing under
`rl/search/` knows about the privileged block today**: the `evaluator` dial
accepts `{"noise", "loo", "oppact_uniform"}` and `critic_fn` maps
`(N, 828) → (N,)`. `docs/proposals/privileged_critic_engine_route.md` §4.4
specifies the seam (four functions plus a seat-mirrored `shadow_battle`) and §4.2
establishes it is *possible*; two guards in `scripts/ch3_eval.py` will fire and
need rulings, not quiet edits.

So **P-BS is deferred and is not a cell of this run**. Arm B's registered primary
is **P-BEV** on `priv_eval/ev_mc_advantage`, which needs no build, is paired
*within* a lane (head and critic on the same rows, same update, same target), and
whose power therefore scales with the number of **lanes** carrying the head rather
than the number of **arms** — which is why `ALLOC-AB9` does not weaken it. No
magnitude band is pre-registered on it, because the metric has never been measured
on a real lane at any dose; what is pre-stated is an exhaustive **sign test**
(POS / NEG / MIXED, a lane at exactly 0.0 reading MIXED).

The artifact survives the deferral: the head is in every checkpoint, so P-BS is
recoverable at any later date **at eval cost only** — and it is *not* recoverable
if the head is not trained now. That is the whole reason the head rides this run.

### 6. P-BA is gone; P-ID replaces it

An earlier draft registered a greedy B-vs-A contrast and argued it measured the
collector's reproducibility floor. **FACT 1 measured that comparison at exactly
zero**, and there is no floor to measure — the collector is deterministic. A
contrast whose value is known in advance to be the integer zero is not a contrast,
and registering one would manufacture a null out of an equality. It is replaced by
**P-ID**, an assertion: a single differing element between a head-on lane's
actor/critic and a same-seed control's is an **R0-class event that stops the
fleet**, not a result. No win-rate comparison between A and B is reported on the
greedy axis, in either direction, on any branch.

### 7. Arm C's mechanism axis — the kill drafting withdrawn

The falsifier and D18's numbers are restated verbatim from
`configs/showdown_sp_priv12m.yaml:148-151` and `results/d18/grade.txt`. An earlier
draft of this file proposed that EV-up + win-rate-flat + an *uncollapsed critic*
be a **kill with a mechanism**. **That drafting is withdrawn**, on two grounds:

- the **2026-09-06 ruling bars "kill"** for a single fleet — a small-run null
  closes nothing and only a measured ceiling kills — so only **NULL** and
  **CREDITED NEGATIVE** are available to this arm;
- the uncollapsed-critic condition **could not fire**: the maximum critic ctx
  srank99 ever recorded here is **25 of 384** (D18 s41), no lane at any dose has
  exceeded it, and the matched-12M controls read 8/14/11.

What is registered instead is a **reported axis**, not a gate: MECHANISM MOVED iff
EV is higher in C than in the paired A lane on every seed **and** srank is strictly
greater on every seed, crossed with the three-way primary delta. The asymmetry is
deliberate and disclosed — "moved" is a strong conjunction and "not moved" is
everything else, which biases the partition *against* the mechanism claim, the
direction an arm re-opening a vacated null should be biased in. The srank leg stays
in because without it EV-up-and-flat is equally explained by representational
collapse; with it as an axis rather than a gate, an arm C that moves EV and not
srank lands in `C-FLAT-EVONLY` and is reported as a **replication of D18 at 8.3×
the dose**, which is worth having and is not a closure.

### 8. Every comparator is read in the same session

The repo has a **measured era bias** on this instrument: the same three 100M
checkpoints, same `seed_start`, deterministic, one week apart, give 0.79589 vs
0.78867. The sharper precedent is −0.0148 at ~2.6× its binomial se, one day
apart, and `configs/eval/ch3_r4_ensemble_critic.yaml:592` says it is "a bias
worth 59% of the floor that no se term captures." So the three arms are read in
one contiguous interleaved session, and **D-COLL100 re-reads the banked Node
checkpoints fresh** (~6 min) rather than differencing against the banked number.

---

## What I am leaving to the maintainer

Fourteen entries, `RWM-1` … `RWM-13` (with `RWM-1b`), in the sidecar's
`rulings_wanted`. The four that most change the run:

- **RWM-11 — does arm B ride arm A's lanes?** FACT 1 says three of nine lanes were
  buying duplicate bytes at ~25 h each. Recommendation: **D1-RIDE**.
- **RWM-13 — does arm C run, and in what form?** Recommendation: **D2-RUN, with
  the configuration named in every sentence it produces** (λ 0.95, update 30,720,
  k=n) — because it does *not* test what IDEAS 4.7 names, and without that clause
  a null here will be read as answering 4.7 when it answers D18. `D2-DROP` and
  `D2-REFORM` are both written out.
- **RWM-8 — the verdict axis.** vs-SH at p ≈ 0.79 is the weakest axis available;
  the 100M pre-reg's own arithmetic gives P(credit) 0.488 off-FP@20 against 0.067
  vs-SH at a matched logit gain, and its item E1 promoted FP@20 "for that round
  only". Recommendation: **keep vs-SH and disclose** — but the decision must be
  made before launch, because the freeze rule makes it unmakeable afterwards.
- **RWM-10 — no independent review has run on this file.** A-1 ran two; the second
  found four *code* defects, one of which would have killed a perfect arm at its
  second update. This file has more moving parts than A-1 and commits ~45
  fleet-hours. **Fund two reviews before answering any of the above.**

Also owed: **RWM-1/1b** (shared seeds, and this triple), **RWM-2** (the test
amendment), **RWM-3** (width, and re-ask if mmap lands), **RWM-4** (the bank at
this dose), **RWM-5** (fund the search seam, don't gate the fleet on it, give it
its own pre-reg), **RWM-6** (arm C's pre-fleet smoke as a hard precondition),
**RWM-7** (confirm the withdrawal of the kill drafting), **RWM-9** (what the fleet
shape should be now that three lanes are free), **RWM-12** (what those lanes buy).

**`M-UNRATIFIED` is a fleet-level cell**: if any of the pending decisions is
unanswered at launch time, **the fleet does not launch**. The arm list and the
lane allocation are not defaults this file may pick.

---

## What the brief got wrong against the code or the record

Highest-value first.

1. **`configs/engine_a1.yaml:734-736` and its sidecar are STALE about a refusal
   that no longer exists.** They claim `rl/train.py:803-816` "refuses
   `collector.mode engine` when [`privileged_dim`] IS set". That refusal was
   **lifted with the design-B seam (commit 7d8650e, 2026-09-10)**; the current
   code at `rl/train.py:826-856` is a **width equality check only**. A-1's arm is
   still clean (the key is absent, `ENGINE_KEYS` is strict), so no A-1 number
   moves — but the header's stated mechanism is wrong and should be corrected.
   **Arm C is launchable precisely because of this.**
2. **The brief named the wrong seed guard.**
   `tests/test_ch5_r2_prereg.py::test_seeds_are_window_disjoint_and_unused`
   guards 66/75/83. At seeds 104/112/120 the test that goes red is
   `tests/test_100m_prereg.py::test_seed_windows_disjoint_and_unused`.
3. **`collect/battles_in_flight == 8` cannot be an R0 gate on this collector.**
   It is read straight from the Rust stats and *is* the constant `k`
   (`engine_collector.py:308`), as are `rooms_tracked` and (literal 0)
   `episodes_discarded`. A-1 dropped all three as gates for this reason. They are
   **stamps** in this pre-reg, recorded and unable to fire.
4. **"324/408 non-constant columns" appears nowhere in this repo.** The recorded
   observation is **329/408 on 1,530 real rows**
   (`configs/engine_a1_priveval_smoke.yaml`, from
   `tests/test_engine_privileged_seam.py`), and the *pinned rule* is
   `nonconst > PRIV_DIM // 4 = 102`, not either number. The gate is written as
   the rule.
5. **D22's srank collapse is 7–13 over 37.5–50M, not 9–13** (50M alone: s35 10 /
   s36 7 / s37 9). The repo's canonical "7–11 of 384" reproduces no single-step
   row and should carry an "as recorded" hedge. **And D18's srank secondary
   compared its 12M critics against 50M controls** — a cross-budget comparison;
   the matched-12M rows (8/14/11) are in the same CSV and are what this pre-reg
   quotes.
6. **D18's control EV band "0.549–0.561" is superseded.** The 2026-08-16 audit
   re-derived it from `history.csv` as 0.5751 / 0.5572 / 0.5657 (s26–28) and says
   in terms that the recorded band reads low. D18's own per-lane figures
   (0.5972 / 0.6150 / 0.6206 / 0.5972 / 0.6040) are the audited ones too.
7. **"334.851 → 410.510" is seed-specific.** It is
   `tests/test_entity_trunk_gen4.py:194-199` at *its* seed. At seed 104 the
   measured pair is **442.300 → 375.635** — same residue, opposite direction,
   which is what "the RNG stream moved" means and what "a bigger init" would not.
8. **0.3960 is not the 100M fleet's FP@20 number.** It is the depth-1 search@M
   arm on lane s112 at n=1000 (`S3_READOUT.md:101-106`). The fleet's own FP@20
   greedy read is 0.48633 / 0.50167 / 0.50733 → **pooled 0.49844** at n=3000/lane;
   0.50167 is s112 alone.
9. **0.78867 is not "the" banked 100M vs-SH pooled.** The banked read is
   **0.79589**; 0.78867 is the *fresh* re-read of the same three checkpoints on
   2026-09-10. Both are real, they differ by −0.00723, and which one you use is
   the era-bias decision above.
10. **STATUS's "~40 h; +11–15 h over two arms" presumes nine-wide.** Two arms is
    6 lanes = one width-6 wave = 25.3 h, so "+11–15 h" only works if the third
    arm's lanes join the same wave. The measured 6+3 structure is +20.0 h.
11. **`results/engine_a1/speedup.json`'s engine fields are all `null`** and it
    cannot supply an engine rate or split. The usable files are
    `results/t1/leg_c.json`, `leg_d.json`, `results/engine_a1/update_share.json`
    and the lanes' own `history.csv`.
12. Two smaller ones, recorded because they will bite someone: **the gen-1
    BC-clone is an 808-d model** served to an 828-d fleet through the
    cross-encoder shim, and **its tapes predate the FP@20 budget** (clone built
    2026-08-09; FP@20 adopted 2026-08-23). CLAUDE.md's *gen-4* clause says "a
    gen-4 clone of FP@20 tapes"; the gen-1 clause says only "BC-clone h2h (500)",
    and the standing gen-1 leg is this clone as used on the 100M fleet.
13. **A one-byte repo inconsistency in the credit line.** The prose form
    (`configs/showdown_sp_100m.yaml:59-62`) ends with a period, 214 chars; the
    YAML scalar (`configs/eval/search_s3_100m.yaml:184`) does not, 213 chars. The
    monster header carries the prose form, the sidecar carries the scalar form
    byte-identical to search_s3's, and the divergence is recorded rather than
    silently picked.

---

## Handed over: the launch commands

> **CLAUDE.md rule 4.** ~25 h per lane, ~45 h per fleet. **The maintainer
> launches.** Nothing below runs until every `RWM-n` is answered,
> `verdict_authorized` and `launch_authorization` are set in the sidecar, and the
> preconditions `PRE-1` … `PRE-11` are met. **A launcher script is owed**
> (`scripts/engine_gates.sh` is the model) and does not exist; these are the raw
> payloads, one per block, and a script that enforces the preconditions is better
> than a human checking by eye.
>
> **THE LANE LIST BELOW IS THE `ALLOC-3x3` / `D1-SEPARATE` FORM** — nine lanes,
> three arms, three seeds. It is written out because it is the only allocation
> whose configs exist on disk today. **Under the recommended `D1-RIDE` it is
> wrong**: the three `monster100m_b_*` blocks disappear, the two `priv_eval` keys
> move into `configs/showdown_monster100m.yaml`, and the freed lanes become the
> extra seeds `RWM-12` names (which need their own config copies at seeds 128 /
> 136, or 144 … 168 under `ALLOC-AB9`). **Do not run these blocks until the
> allocation is ruled** — `M-UNRATIFIED` says the fleet does not launch with a
> pending decision, and this is the block it is protecting.

**Preflight — run one at a time, read the output.**

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && git status --porcelain && df -h . | tail -1 && vm_stat | head -6 && sysctl -n hw.memsize
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown && nohup node pokemon-showdown start --no-security >> /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/logs/showdown_server.log 2>&1 < /dev/null &
```
</command>

**Wave 1 — six lanes, width 6, seeds 104 and 112, all three arms. Run each block
in order, ~90 s apart; verify each lane individually before the next (a lane can
SIGSEGV at startup before any log line).**

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m.yaml --seed 104 --run-name monster100m_a_s104 > runs/monster100m_a_s104.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m_b.yaml --seed 104 --run-name monster100m_b_s104 > runs/monster100m_b_s104.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m_c.yaml --seed 104 --run-name monster100m_c_s104 > runs/monster100m_c_s104.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m.yaml --seed 112 --run-name monster100m_a_s112 > runs/monster100m_a_s112.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m_b.yaml --seed 112 --run-name monster100m_b_s112 > runs/monster100m_b_s112.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m_c.yaml --seed 112 --run-name monster100m_c_s112 > runs/monster100m_c_s112.nohup.log 2>&1 < /dev/null &
```
</command>

**Liveness — run this twice, 15 s apart, and compare. A lane can stall ALIVE at
ZERO CPU and every `pgrep` passes forever; the CPU-time delta is the instrument.**

<command>
```
ps -Ao pid,time,rss,command | grep 'bin/python -m rl.train' | grep monster100m | grep -v grep
```
</command>

**Wave 2 — three lanes, width 3, seed 120, all three arms. Only after wave 1 is
complete.**

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m.yaml --seed 120 --run-name monster100m_a_s120 > runs/monster100m_a_s120.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m_b.yaml --seed 120 --run-name monster100m_b_s120 > runs/monster100m_b_s120.nohup.log 2>&1 < /dev/null &
```
</command>

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --config configs/showdown_monster100m_c.yaml --seed 120 --run-name monster100m_c_s120 > runs/monster100m_c_s120.nohup.log 2>&1 < /dev/null &
```
</command>

**Resume, after a crash or a stall. One lane per block. A resume is not a warm
start; it restores the step, the anneal basis, the RNG streams and the engine's
battle counter. It also splits the wandb history — use
`scripts/merge_history.py`, not `extract_history.py`.**

<command>
```
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl && POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nohup /opt/anaconda3/envs/pkmn-engine-port/bin/python -m rl.train --resume runs/monster100m_a_s104 > runs/monster100m_a_s104.nohup.log 2>&1 < /dev/null &
```
</command>
