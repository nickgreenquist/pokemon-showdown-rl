# P6 — the last experiment run in the old repo, and what it changes

> **CORRECTION (2026-08-05):** the old repo's final SESSION_LOGS entry, written at close-out from
> the run artifacts, supersedes this file's "Mechanism" section on two points: `approx_kl` was
> reduced **3.3×** on the annealed arm (0.00554 → 0.00167 second-half means), not "halved"; and
> entropy **DID separate** (clean 3-vs-3 rank split, annealed below flat) — only the predicted
> entropy-collapse tell failed to occur. Corrected record: this repo's SESSION_LOGS.md,
> 2026-08-05 P6 entry. Numbers elsewhere in this file stand.

Completed 2026-08-05 ~02:30 in `/Users/nickgreenquist/Documents/Projects/deep-rl-from-scratch`.
Read `start.md` first for bootstrap; this file is the current state of the science.

**Bottom line: PPO now beats the behavioral clone, and the remaining headroom against this
benchmark opponent is 0.028.** That closes the gap the whole `DESIGN_P7.md` package was built to
exploit — read §"What this breaks" below before implementing anything from it.

---

## The result

12M steps on the credited r512 recipe, flat learning rate vs linear anneal to zero. Both arms from
scratch, 3 seeds each, 6-wide, pre-registered before launch. **6/6 lanes completed** — a clean
sweep, notable because a seed collision killed a whole arm earlier that day and a prior 6-wide
probe lost a lane to SIGSEGV.

| arm | pooled (n=3000) | per seed |
|---|---|---|
| flat 12M | **0.4330** (1299/3000) | 0.425 / 0.424 / 0.450 |
| annealed 12M | **0.4607** (1382/3000) | 0.449 / 0.451 / 0.482 |

delta **+0.0277**, se_diff 0.0128, **z = +2.16**, 2·se_diff = 0.0257.

**PRIMARY verdict: the anneal is CREDITED at 12M** (line was delta ≥ +0.025 AND ≥ 2·se_diff).
**But it clears by 0.003 where the 6M read cleared by double** (+0.051 at 6M vs +0.028 at 12M).
The direction replicates; the magnitude does not — the shape you'd expect if annealing mostly buys
a cleaner endpoint rather than a better trajectory.

**R0 gates PASSED on all six lanes**: entropy 0.244–0.289 (band [0.2, 1.0]), ties 1.0–2.4%
(≤ 4%), steps/s 501–506 (within 25% of 556).

### Secondaries

- **flat 6M → 12M: +0.0407** (0.3923 → 0.4330). Doubling the budget bought about as much as the
  anneal did. This cuts against the archive prior — VGC-Bench 0.48 at 5M, pokejax ~0.55 at ~378M —
  that step count buys almost nothing. At *this* scale it bought a fair amount.
- **annealed 6M → 12M: +0.0174** (0.4433 → 0.4607). Confounded exactly as pre-registered: a 12M
  anneal is a *shallower* schedule, not merely a longer one. Budget and slope move together.

### Mechanism (recorded in-flight, not gated)

- **`approx_kl` halved on the annealed arm** across the run (0.0044 at 2–4M → 0.0027 at 6–8M) while
  the flat arm held flat (0.0058 → 0.0057). The schedule is demonstrably engaged.
- **Entropy did NOT separate** — 0.284 flat vs 0.275 annealed at 6–8M. This is *contrary to the 6M
  pre-registration*, which expected a frozen-entropy signature as the tell. **The anneal shrinks
  step size, not the action distribution.** Worth remembering before designing another schedule
  probe around entropy.
- **Loop split held at 94.8% collect / 5.2% update** on all six lanes for the full 12M, confirming
  the earlier measurement at a much longer horizon.

---

## The board now

| result | value |
|---|---|
| PPO 6M, flat lr | 0.3923 ± 0.0089 |
| PPO 6M, annealed | 0.4433 ± 0.0091 |
| PPO 12M, flat lr | 0.4330 |
| **PPO 12M, annealed** | **0.4607** ← best |
| BC clone of SimpleHeuristics | 0.453–0.465 |
| **SH-vs-SH mirror ceiling** | **0.489** |

All vs poke-env's `SimpleHeuristicsPlayer` under the locked protocol: final checkpoint, 1000
battles/seed, 3 seeds pooled, ties as non-wins, deterministic policy.

---

## What this breaks — read before touching `DESIGN_P7.md`

P4 (the supervised cloning diagnostic) had established that the plateau was **training-side**: a
clone of SH reached 0.453 while RL sat at 0.408–0.443, so a better policy was representable but
PPO wasn't reaching it. `DESIGN_P7.md` was built on that gap.

**The gap is closed.** RL is at 0.4607 — above the clone, and 0.028 below the mirror ceiling. P4's
prediction was right and training-side work closed it, which is a satisfying outcome but leaves
the design proposal standing on a premise that no longer holds.

Recorded in `DESIGN_P7.md` as **revision 4**, at the top. Specifically:

- **P7a (BC warm start from SH) loses most of its motivation.** Warm-starting from a 0.453 clone
  to reach a policy already at 0.4607 starts *behind*. Its staged-unfreeze design is still correct
  if BC is ever used — but the teacher should be human replays, not SH.
- **§3's 0.489 bound is now the operative ceiling on everything SH-derived**, with 0.028 of room.
  Any SH-based arm is fighting for scraps.
- **§10 (the 109,147-replay `gen1randombattle` human corpus) is MORE important, not less** — it is
  the only proposal in the document whose ceiling is not 0.489.
- **P7b (faint shaping) and P7c (distributional value) are unaffected.** Neither depends on the
  clone gap; both stand as written.

**Do not implement §4 as specified.** It needs a revision pass against these numbers before the
team review means anything.

---

## Everything changed in the old repo (all committed at `57a93e5`)

The old repo is being archived; these are its final states. Copy or consult, don't edit.

| file | what changed |
|---|---|
| `SESSION_LOGS.md` | the 2026-08-04 entry's `RESULT PENDING` marker replaced with the full P6 read — numbers, gates, secondaries, mechanism, artifacts. Last entry in the file. |
| `STATUS.md` | P6 recorded; a new **"THIS REPO IS BEING ARCHIVED"** section pointing here |
| `README.md` | amended per the pre-stated condition. Its closing passage had claimed the clone "sits above every RL policy on this board" — **that is now false** and was rewritten with the 12M result, the narrow margin, the mechanism read, and a pointer to the capstone's new home. |
| `DESIGN_P7.md` | **revision 4** banner at the top (see above). This file is on the copy manifest — make sure you take the corrected version. |
| `configs/showdown_r512_12m.yaml` | the P6 pre-registration, written before launch. Worth reading as the template for how experiments are specified here. |
| `configs/showdown_r512_lra12m.yaml` | the annealed arm; one changed line vs the control |

**Run artifacts** (in the old repo, ~425–431k history rows each — copy if wanted, they are the
evidence behind every number above):
`runs/showdown_r512_12m_s{0,1,2}` and `runs/showdown_r512_lra12m_s{3,4,5}`.

Note the seeds: the annealed arm is **s3/s4/s5**, not s0/s1/s2. Concurrent lanes cannot share seed
values — poke-env derives Showdown usernames from the global RNG that `cfg.seed` seeds, so
same-seed lanes collide and the loser dies at first `reset` with a misleading
`TimeoutError: Agent is not challenging`. This killed the annealed arm's first launch. The arms
are therefore **unpaired in seed value**; the pooled proportion test never assumed pairing, so the
PRIMARY stands, but per-seed cross-arm comparison is meaningless.

---

## Suggested next questions

Not decisions — the team review still has to happen, now against these numbers.

1. **Is 0.489 actually the ceiling worth targeting?** Everything on the board is measured against
   one scripted bot that Metamon found loses to the human ladder about 4 times in 5 in Gen1OU. A
   result of 0.46 vs SH may say less than a ladder Elo would.
2. **Does the human corpus (`DESIGN_P7.md` §10) become the main line now?** It is the only lever
   left whose ceiling isn't 0.489. Its cost is a parser fork and an action-mapping correctness
   problem, both documented there.
3. **Was the +0.0407 from doubling the budget a real scaling signal or a one-off?** It contradicts
   the prior from two external sources. If real, it changes what a long run is worth.
4. **P7b/P7c are still clean, cheap and unaffected** — worth running on their own rather than as
   part of a package whose premise moved.
