# F-04 minibatch tail policy — DRAFT PRE-REGISTRATION (PROPOSAL, NOT RATIFIED; the default stays `keep` until the maintainer rules)

**STATUS: PROPOSAL.** This is a draft pre-registration paragraph for a
NON-LEVER WIRE CHANGE, written 2026-09-02 on the audit branch (finding F-04,
`docs/AUDIT_ACTION_PLAN.md` §3/§4). Nothing here is in force. The opt-in
wire shipped in commit `650a8e6` (`PPOAgent(minibatch_tail=...)`, values
`keep | drop | fold`) with the default `keep` = today's behaviour bit-for-bit.
THE PIN (rewritten after review round 1, which found the original compared the
new loop to ITSELF): `tests/test_ppo_episodes.py::test_minibatch_tail_keep_is_
bit_identical_to_the_pre_f04_agent` loads `rl/agents/ppo.py` AS OF
`5d3c6b7c841c008b0e70e916e3d8242ef3166bb5` (the commit before the wire) into a
throwaway module and RUNS that agent beside today's — same seed, same kwargs,
same batch, every async tail — asserting equal weights, equal Adam state, an
equal metrics dict INCLUDING its keys, and an equal torch RNG state afterwards.
Four mutations of the `keep` path (floor 2 -> 3, an extra RNG draw, a moved
slice boundary, the diagnostics leaking under `keep`) were each verified to
FAIL it. Review round 2 asked that the pin be unable to stop pinning quietly,
so its baseline is VENDORED at `tests/fixtures/ppo_pre_f04.py.txt` (72,626
bytes, sha256 `307ad4a1…` pinned in the test) and the object store is only a
cross-check: a missing or edited baseline FAILS, a baseline that disagrees with
`<sha>:rl/agents/ppo.py` FAILS, and an unreachable commit — the post-squash-
merge future — drops the cross-check while the pin keeps running. Nothing in
the loader skips. Its companion `test_minibatch_tail_default_is_keep_and_bit_
identical` reimplements the pre-F-04 loop in-file as a row-and-RNG oracle, and
`test_pre_f04_baseline_is_present_and_pinned` asserts the baseline separately
so losing it is a red run.
The production-shape arithmetic below is pinned by
`test_minibatch_slices_plan_at_the_100m_recipe` (B = 30,720 + eps,
minibatches 120, eps in 1/2/60/119/120/250) and the R0-3 read by
`test_minibatch_tail_metrics_at_the_100m_shape`. No fleet runs, no config
flips and no default moves on this text. It has NOT been through the 2-Opus
design cycle; that cycle is owed if and when this becomes the ratified header
of a run.

**journey_step: NOT ASSIGNED — off-arc until ruled** (CLAUDE.md's off-arc
clause: "off-arc work needs a maintainer ruling"). It is learner-wire
hygiene, so its candidate homes are the steps that next touch the gen1
recipe, quoted so the ruling can pick one: JOURNEY step 8 — "Recipe findings
are generation-agnostic: rollout size, minibatch structure, λ and γ, LR
schedule [...] Port them home." / "Pre-register the gen1 re-test as part of
the gen4 chapter, before running it."; JOURNEY step 10 — "The big one, with
a recipe validated somewhere the instrument works." The exit condition of
whichever step is named is to be restated here verbatim on ratification;
until then this file licenses nothing.

---

**THE CHANGE (a wire, not a lever).** On the async path an update's batch is
30,720 + eps rows of whole episodes (`configs/showdown_sp_100m.yaml:88` DOSE
paragraph discloses "a trailing partial slice"). THE SHAPE IS THE SAME IN
BOTH ARMS' FILE AND THE 100M FILE, which is why one test shape covers both:
`num_envs: 8` x `rollout_steps: 3840` = the 30,720-step update budget,
`epochs: 4`, `minibatches: 120`
(`configs/showdown_sp_batch50m_async.yaml:128, :167-169` ==
`configs/showdown_sp_100m.yaml:537, :576-578`). `minibatch_size = B //
120` and `range(0, B, mbs)` leave a final slice of B mod mbs rows; because
B = 120·mbs + r with r < 120, that tail IS r — uniform on 0..119 and never a
function of the 256-row width. Today (`keep`) a 1-row tail is skipped
(commit 15719d9, smoke3) and every 2..119-row tail is z-scored over ITSELF
and takes a full Adam step at the same lr as a 256-row minibatch: Adam's
normalisation keeps the step's MAGNITUDE that of a real minibatch while its
DIRECTION is a 2..119-sample estimate. `fold` appends a tail under
`mbs // 2` to the slice before it; `drop` skips it. At this recipe the floor
`mbs // 2 >= 128` exceeds the largest possible tail (119), so EITHER policy
acts on EVERY 2..119-row tail; the `mbs // 2` boundary is reached only at
small `minibatches` (where the tests exercise it), never in production.

**FOOTPRINT, stated up front.** Per update: 4 epochs x (120 full + 1 tail)
slices; P(tail >= 2) = 118/120, so ~3.93 of ~484 gradient steps (0.81%) are
the F-04 step, tail width uniform on 2..119 (mean 60.5 rows). Over 100M
steps (~3,255 updates) that is ~12,800 of ~1.575M gradient steps. Under
`fold` the last executed slice is 258..~378 rows (< 1.47 x mbs); under `drop`
a mean of ~59.5 of ~30,780 rows (0.19%) sit out per epoch, different rows
each epoch because `perm` is fresh. PRIOR EXPECTATION: a null. The proposal
exists because the numerics MOVE and the repo's rule is that anything moving
the learner's numerics is pre-registered before it touches a headline run —
not because a credit is expected.

**DOSE (decided now, not at read time).** Data dose MATCHED: same
`total_steps` AND same `lr_anneal_steps` — BOTH 50M in BOTH arms, the
comparator's own schedule (`configs/showdown_sp_batch50m_async.yaml:125,
:164`), every lane KILLED by the wave runner at its 12M crossing rung, so
the two arms see the same lr at every step they train; same collector, same
batches, same `perm` draws. A 12M-annealed T config is FORBIDDEN by the
comparator's own header (it would compare learning-rate schedules, not tail
policies) and is a STOP at R0-2. Optimizer dose differs by construction and
is stated: gradient steps per epoch
`keep` 121 (whenever tail >= 2) vs `fold`/`drop` 120 (-0.8%); rows trained
per epoch `keep` = all, `fold` = all, `drop` = all minus the tail (-0.19%).
HOW WE WOULD KNOW: the two diagnostics that exist ONLY under a non-default
policy — `loss/minibatch_rows_min` (must read >= 256 at every update under
either policy; a smaller value means the floor logic is not the one
described here) and `loss/minibatch_rows_dropped` (exactly 0 under `fold`;
in 0..119 under `drop` — it is the tail width, so 0 only when the batch
divides exactly) — are RECORDED at grade time, never asserted. GAP,
named: no `loss/grad_steps` key exists; the realized per-update step count
is derived from batch sizes, not logged. Adding it under the same
non-default gating is ruling item 4 below.

**ARMS.**
- T: 3 lanes of the Stage-2 acceptance config
  (`configs/showdown_sp_batch50m_async.yaml`) with `agent: minibatch_tail:
  fold` as the ONLY delta — the config diff against the comparator's file is
  recorded in the ratified header (R0-2). STOP MECHANISM, pinned:
  `total_steps: 50000000` and `lr_anneal_steps: 50000000` STAY (the
  comparator's own schedule, `configs/showdown_sp_batch50m_async.yaml:125`
  and `:164`); each lane is KILLED once its 12M crossing rung lands, by the
  same runner and the same glob the comparator's lanes were —
  `scripts/ch5_g9_wave.sh:37` `rung_of() { ls "$1"/ckpt_0120*.pt ... }`,
  polled at `:83`/`:98`. "12M" names where a lane is STOPPED and READ, never
  a config horizon; the comparator's own header states the reason verbatim
  ("running a 12M-annealed config instead would compare learning-rate
  schedules, not collection loops", `:30-34`). `fold` is proposed over `drop`
  because it keeps every row in every epoch; `drop` is the alternative NOT
  RUN and is named as not run.
- C: the banked G9 acceptance fleet — the SAME FILE with the default `keep`,
  async, seeds 66/75/83, `runs/showdown_sp_batch50m_async_s{66,75,83}`, each
  lane killed by that runner at its 12M crossing rung (realized
  `ckpt_0120000{13,09,41}.pt`, i.e. 9-41 steps of overshoot) — per-seed
  vs-SH finals 0.65933 / 0.68367 / 0.67333, pooled 0.67211, seed sd 0.0122
  (SESSION_LOGS 2026-09-01; restated as the 100M header's N-COLL disclosure,
  `configs/showdown_sp_100m.yaml:96-103`). NO CONTROL COMPUTE IS SPENT.
- SEEDS: matched 66/75/83 is the clean paired read, and those seeds have
  TWO legal owners today (`tests/test_ch5_r2_prereg.py::test_seeds_are_
  window_disjoint_and_unused`: R2's fleet and the acceptance fleet). A third
  owner is a maintainer ruling plus a one-line amendment to that guard
  (ruling item 3). FALLBACK if refused: fresh seeds 152/160/168 (window-
  disjoint from every seed in play: 66/75/83, 104/112/120, spares 128/136/
  144), with the loss of pairing DISCLOSED — the clustered se then carries
  two fleets' seed variance instead of a paired difference.
- COST, honest: 12M at the realized 574 steps/s is ~5.8 h/lane, 3 lanes
  concurrent — over the 5 h line, so the launch is the maintainer's
  (CLAUDE.md rule 4). Eval: vs-SH 3 x 3000 ~6 min. Off-FP@20 descriptive
  3 x 3000 serial ~3.9 h, agent-side, detached, resume-safe.

**PRIMARY READ — pooled vs-SH, locked protocol, RUNG vs RUNG.** Each T
lane's 12M CROSSING-RUNG checkpoint (`ckpt_0120*.pt`; the async loop names
rungs at the crossing step, so the glob and not the vector path's exact
literal — bounded overshoot ~15k steps, 9-41 realized in the comparator,
realized step RECORDED per lane) — the SAME object the comparator's per-seed
finals were read from, never a "final" of a 12M config, and the T config's
own `total_steps` is 50M — 3000 battles/seed, 3 seeds,
deterministic policy, ties as non-wins, vs `SimpleHeuristicsPlayer`. ACROSS-LANE
AGGREGATOR, named once and binding everywhere: the EQUAL-WEIGHT MEAN of
per-seed finals, computed WITHIN each arm over its own lanes. Pooled-over-
battles, per-lane median, best/worst lane and per-lane deltas are RECORDED
and NEVER govern. delta = pooled_T - 0.67211. WHY THIS AXIS: it is the axis
the comparator was measured on, at zero control cost; the 100M run's
off-FP@20 primary axis is not available for the comparator until A-COLL
fires (iff the 100M lands in P1), and this proposal does not wait on it.

**CREDIT LINE, VERBATIM (CLAUDE.md "Conventions"; restated here exactly
once):** "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff,
where se_diff is the LARGER of the pooled-binomial se_diff and the
seed-clustered se_diff, the latter computed from the per-seed finals at
read time." Clustered formula: sqrt(s_T^2/k_T + s_C^2/k_C). BAR =
max(0.025, 2*se_gov). PLANNING SE at p = 0.67, n = 3000/lane, k = 3:
binomial per lane 0.00859, per arm 0.00496, difference 0.00701; clustered
at s_T = s_C = 0.0122: 0.00996. 2*se_gov = 0.0199 < 0.025, so THE FLOOR
GOVERNS for any realized s_T <= ~0.0179. This is a NON-LEVER: the credit
line is restated because every band below is defined by it, not because a
credit is sought.

**CELLS (half-open, exhaustive; each names the side it reads).** The read
is G9's: a null band with the SIGNED delta carried in every quote.
- W-NULL  |delta| < 0.025          WIRE ACCEPTED as a non-lever. `fold` may
                                   become the default BY RULING; every
                                   future header that runs `fold` carries
                                   this signed delta beside N-COLL's.
- W-POS-L +0.025 <= delta < +BAR   POSITIVE side, letter-met, seed-fragile.
                                   NOT adopted on this read, NOT credited.
                                   EMPTY BY CONSTRUCTION when BAR = floor.
- W-POS-C delta >= +BAR            POSITIVE side, NAMED CELL. A variance fix
                                   removing 0.8% of steps is NOT expected to
                                   clear the credit floor; this reads as a
                                   confound (pairing, a second config delta,
                                   the 12M horizon's own noise) before it
                                   reads as a credit. Maintainer question
                                   WITH the numbers; adoption deferred; no
                                   README row.
- W-NEG-L -BAR < delta <= -0.025   NEGATIVE side, letter-met. `keep` stays;
                                   finding closed as "measured, not
                                   adopted".
- W-NEG-C delta <= -BAR            NEGATIVE side, credited in reverse: the
                                   policy HURT. `keep` stays; the mechanism
                                   question is recorded as an open item, not
                                   chased.
- K       k_T <= 2                 DESCRIPTIVE ONLY, no cell fires (1-df
                                   seed sd; CI multipliers 0.45x-31.9x).
Boundaries: delta = +0.025 -> W-POS-L when BAR > 0.025 else W-POS-C;
= +BAR -> W-POS-C; = -0.025 -> W-NEG-L when BAR > 0.025 else W-NEG-C;
= -BAR -> W-NEG-C. NO CELL MOVES THE ARC: the table changes which default
a FUTURE header may use, never where the project goes next.

**SECONDARY, descriptive, never verdict inputs.** (i) Off-FP@20 greedy
3 x 3000 serial on T, reported ONLY if the comparator's own off-FP@20
finals exist by then (they land iff A-COLL fires); every quote names the
budget and carries the two standing disclosures (weakly powered
equivalence; flattering point estimate). (ii) `loss/grad_norm`,
`loss/clip_frac`, `loss/approx_kl` curves overlaid on the acceptance fleet's
— DISCLOSED as not bit-comparable: the per-update mean's denominator moves
484 -> 480 and the removed step was the noisiest one, so a small downward
shift in the noise metrics is the EXPECTED signature, not evidence.
(iii) `loss/minibatch_rows_min` and `loss/minibatch_rows_dropped` per the
DOSE paragraph.

**R0 SANITY GATES (zero-lane, at launch; any failure is STOP before the
first step).**
- R0-1 `tests/test_ppo_episodes.py` green at the launch commit, in the launch
  env, AND `-rs` shows ZERO skips in it — the bit-identity pin has no skip
  branch left (its baseline is the vendored `tests/fixtures/ppo_pre_f04.py.txt`,
  not the object store), so a skip anywhere in this file means the pin was
  edited and is a STOP, not a pass. The six tests R0-1 covers:
  `..._keep_is_bit_identical_to_the_pre_f04_agent`,
  `test_pre_f04_baseline_is_present_and_pinned`,
  `..._default_is_keep_and_bit_identical`,
  `..._policies_on_async_shaped_batches`,
  `test_minibatch_slices_plan_at_the_100m_recipe` and
  `..._metrics_at_the_100m_shape`.
- R0-2 `diff` of the T config against `showdown_sp_batch50m_async.yaml` is
  exactly the `minibatch_tail: fold` line (plus seeds/run-names if the
  fallback seeds are ruled); in particular `total_steps: 50000000` and
  `lr_anneal_steps: 50000000` are UNCHANGED — a T file reading 12M on
  either is the learning-rate-schedule confound the comparator's header
  forbids, and is STOP.
- R0-3 the FIRST logged update of every lane reads
  `loss/minibatch_rows_dropped` == 0 and `loss/minibatch_rows_min` >= 256;
  a lane whose first update reads otherwise is running the wrong wire.
- R0-4 the standing launch gates: clean tree, distinct `--seed`s across
  lanes, fresh server, `simulator: 4`, every seat sending `/timer on`.

**PEEKING / STOPPING.** The standing bars: no outcome-based stop, extension
or lane replacement; no checkpoint evaluation of any lane between launch and
the last lane's end; in-loop `eval/win_rate` is visible and NOT actionable.
FREEZE RULE, verbatim in effect: no cell, bar, bar formula, n, aggregator,
sidedness, comparator or barred-sentence list moves after the FIRST
treatment datum on the primary axis lands.

**HONEST WEAKNESSES.** (a) 12M is not 100M: a null at 12M is ASSUMED to
remain one at 100M — the same assumption G9 made for N-COLL, named here as
an assumption. (b) One vs-SH rung at n = 3000 is worth ±0.02 (landmine
2026-08-31); the band is ~2.5 se_gov wide, so a true +0.025 effect is
detected only ~half the time and a true 0 lands outside the band ~1% of the
time. The fleet buys "no evidence the wire moves the outcome" — which is
the claim a wire change needs, not a credit. (c) ~17.4 lane-hours for a
0.8%-of-steps hygiene change is a poor standalone buy; see the routing
below.

**ROUTING — three ways to dispose of F-04, for the ruling (cheapest first).**
1. DISCLOSE-AND-ADOPT: rule `fold` the default with no fleet, and list it
   as N-TAIL in the next headline run's non-lever list beside N-COLL /
   N-TIMER, with the footprint arithmetic above as its disclosure. This is
   how N-TIMER was handled. Cost: zero; weakness: never measured.
2. RIDE-ALONG: the next fleet that is already being run for another reason
   at the acceptance shape (a pre-step-8 recipe check, a future collector
   acceptance) carries `minibatch_tail: fold` and this paragraph becomes a
   named non-lever cell in THAT header. Cost: zero marginal compute;
   weakness: confounded with that fleet's own lever unless that header cells
   it.
3. STANDALONE FLEET: the arms above, as written. Cost: ~17.4 lane-hours +
   6 min eval; the only route that produces a clean paired number.
The audit recommends 1 or 2; 3 is written out so it is a real option, not a
gesture.

**RULINGS NEEDED (each a maintainer decision; none assumed).**
1. `fold`, `drop`, or neither (keep `keep`).
2. Routing 1, 2 or 3 above.
3. If 3 (or 2 at the acceptance shape): seeds 66/75/83 as a third legal
   owner (amend the guard test) or fresh 152/160/168 (pairing lost,
   disclosed).
4. Whether to add `loss/grad_steps` under the same non-default gating so
   the DOSE paragraph's "how we would know" is logged rather than derived.

Until ruled: `minibatch_tail` defaults to `keep`, no config in `configs/`
sets it, and every number in this file is planning arithmetic, not a result.
