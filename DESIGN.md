# DESIGN — the roadmap after P6

**Status: RATIFIED 2026-08-05 — maintainer (human) review; §9's author recommendations D1–D7
adopted as written.** Lifecycle from here: each item's pre-registration moves into its config
header (the `configs/showdown_r512_lra.yaml` pattern) as it is built, STATUS.md tracks
execution, and this file is deleted once its content has fully migrated.

Self-contained on purpose — a reviewer should need no other file and no prior conversation.

> **§9 is the decision list (D1–D7), each now DECIDED per its stated recommendation.
> Everything else in this document is the evidence those decisions rest on.**

Revision history, condensed. r1–r3 (2026-08-04): the original training-side package —
BC-from-SH warm start (Arm A), faint shaping (Arm B), distributional value (Arm C) — plus an
external borrow-advisory (VGC-Bench's +25–30 is BC-from-**humans**, not BC-from-SH) and the
verified 109k-replay human corpus (§10). r4 (2026-08-04): renamed from `DESIGN_P7.md` on
spin-out into this repo. r5 (2026-08-05 02:30): P6 read and undercut the package's premise.
**r6 (this revision): full rewrite against P6, then hardened against three independent review
passes (experimental design, strategy, fact-check). Arm A retired as a run, Arm C parked, §10
promoted to candidate main line, the ceiling arithmetic re-scoped (§3), one P6-era claim
corrected against this repo's own re-measurement ("past the clone" → "level with the clone",
§2), and the open forks turned into an explicit decision list (§9).** Naming note:
P4/P5/P5b/P6 name experiments inherited from the predecessor repo (`deep-rl-from-scratch`),
kept as provenance; artifacts live here, including the P4 clone checkpoints
(`runs/bc_p4_512_40k_s{0,1,2}`) and the P6 finals (`runs/showdown_r512_12m_s{0,1,2}`,
`runs/showdown_r512_lra12m_s{3,4,5}`).

## 1. Where the project is

Capstone repo spun out of a from-scratch deep-RL project (DQN, PPO, SAC built without RL
libraries — a rule complete there and retired here; the goal here is the strongest agent, with
external code and data in scope on merit). Task: Pokémon Showdown Gen 1 random battles, battle
phase only, via poke-env against a local Showdown server. Agent: PPO, `[512,512]` MLP over a
611-dim hand-written observation, 10 discrete actions (6 switch slots + 4 move slots),
terminal-only ±1 reward at `gamma = 1.0`. Benchmark opponent: poke-env's
`SimpleHeuristicsPlayer` ("SH"). Locked protocol for every headline number: final checkpoint,
1000 battles/seed, 3 seeds pooled, ties as non-wins, deterministic policy. One standing
benchmark caveat: our poke-env 0.15.0 SH has a dead setup branch (upstream bug, report
unfiled), so every number below is against that build — and ps-ppo's SH numbers are against a
differently-patched SH, another reason its figures do not transfer.

The board, all measured under the locked protocol:

| result | value | note |
|---|---|---|
| PPO 6M, flat LR (P5) | 0.3923 ± 0.0089 | r512 recipe |
| PPO 6M, annealed (P5b) | 0.4433 ± 0.0091 | anneal credited, +0.051 |
| PPO 12M, flat (P6) | 0.4330 | per seed 0.425 / 0.424 / 0.450 |
| **PPO 12M, annealed (P6) — best RL** | **0.4607** | per seed 0.449 / 0.451 / 0.482 |
| BC clone of SH (P4) | 0.4530 pooled; **0.4657 re-scored in-repo** | two same-protocol measurements, ~1σ apart |
| SH-vs-SH mirror (P4 R0) | **0.489** (n=20k) / 0.486 (n=40k) | the SH-parity point |

The clone row needs its footnote read: 0.4530 is the original P4 measurement (predecessor
repo); 0.4657 is this repo's port-verification re-score of the same checkpoints
(`runs/bc_p4_512_40k_s*/migration_check8.json`, 1000 battles/seed). The RL best sits between
them.

Base recipe (credited): `configs/showdown_r512_lra12m.yaml` — `[512,512]`,
`rollout_steps: 512`, `num_envs: 8`, `epochs: 4`, `minibatches: 4`, `lr: 2.5e-4` linearly
annealed to 0 over the budget, `gamma: 1.0`, `opponent: heuristics`. Cost: ~2.9 h per 3-seed
arm at 6M at 3-wide; ~6.5 h at 12M (P6 measured 501–506 steps/s/lane at 6-wide → 6.6 h/lane;
its pre-registration budgeted 6.0–6.4 h). The loop is 94.8% collect.

## 2. What P6 established

P6 (flat vs annealed LR at 12M, 3 seeds/arm, pre-registered, 6/6 lanes green, R0 gates
passed):

- **The anneal is CREDITED at 12M** — pooled +0.0277, z = 2.16 under its pre-registered
  estimator — but it cleared the +0.025 line by 0.003 where the 6M read cleared by double.
  Direction replicates; magnitude does not. Recorded caveats: seed-level Welch p ≈ 0.12, both
  arms carried by one strong seed; arms seed-unpaired (flat s0/s1/s2, annealed s3/s4/s5), so
  per-seed cross-arm comparison is meaningless — the pooled test never assumed pairing.
- **Raw budget bought as much as the anneal**: flat 6M→12M = +0.0407 (z ≈ 3.2, the one
  genuinely solid secondary). The annealed 6M→12M marginal is +0.0174 ± 0.0129 — *not
  statistically distinguishable from zero*, and confounded by construction (a 12M anneal is a
  shallower schedule, not merely a longer run; the pre-registration forbids reading it as
  "budget caused it").
- **Mechanism**: second-half `approx_kl` means 0.00554 (flat) vs 0.00167 (annealed), 3.3×,
  with the annealed arm decaying monotonically by quarter (0.00468/0.00367/0.00233/0.00101)
  against a trendless flat arm — the schedule is demonstrably engaged. `clip_frac` 2.8× lower.
  Entropy separated (clean 3-vs-3 rank split, annealed lower) but only ~6%; the pre-registered
  entropy-collapse tell did not occur. The anneal acts mostly on step size, only mildly on the
  action distribution.
- **P4's training-side diagnosis is vindicated and CLOSED — with one correction to the P6-era
  claim.** P4 (2026-08-02) showed a supervised clone of SH through the exact capstone
  encoder+trunk reaches the mid-0.45s while RL sat at 0.39–0.44 — the plateau was
  training-side, not representational. Training-side work (anneal + budget) then closed the
  gap: **RL at 0.4607 is now level with the clone** (between its two measurements, 0.4530 and
  0.4657). The P6-era claim "past the clone for the first time" does not survive this repo's
  own re-score, and P6's pre-registered "past the teacher" amendment mark — pooled ≥ 0.47 —
  was not reached. Level, not past.

Consequence: the original package's premise — "a better policy is representable and PPO is not
reaching it; warm-start PPO from the clone to hand it that policy" — no longer describes the
world. Warm-starting from the clone to chase a policy already level with it buys at most the
cloning tax, inside a band the credit line can barely resolve.

## 3. Ceilings — which levers are capped, and at what

This is the arithmetic the review should check hardest; r5 and earlier drafts stated it
loosely.

- **0.489 is the SH-parity point, and it caps *imitators of SH* only.** It is the SH-vs-SH
  mirror win rate (below 0.5 because ties count as non-wins; 0.486 at n=40k, so read the gap
  to parity as 0.025–0.028). A perfect SH clone converges to it by construction; P4's clone
  paid a ~0.03 cloning tax against it (on the original measurement; the in-repo re-score
  nearly erases the tax). Any BC-from-SH lever — Arm A as originally designed, more SH data, a
  better SH clone — is bounded here. RL at 0.4607 sits ≈0.03 below parity.
- **Nothing caps RL at 0.489.** A policy genuinely better than SH beats it beyond parity
  without bound: Wang's gen4randombattle **pure network scored 0.786 vs SH** — ~0.575 at our
  6M budget, 0.786 at his full training budget (thesis Table 4.1; its own Fig 4.1 shows ~0.85,
  unreconciled — our index carries both). Our training opponent *is* SH, so past parity PPO
  becomes an SH-exploiter and that curve keeps going. Counter-datapoint: pokejax, ~0.55 at
  ~378M steps (scratch PPO, gen4, n=20 eval — weak measurement). Scaling exists but is
  recipe-dependent.
- **A high vs-SH number is not strength.** Metamon measured SH against the Gen1OU human ladder
  at 16W–59L ≈ 0.21 — the population beats SH four times in five. Driving vs-SH from 0.46
  toward 0.6+ by exploiting a fixed scripted bot optimizes a benchmark, not the agent; the
  project goal is the strongest agent, which the ladder defines, not SH.
- **Human demonstrations are the one lever aimed at ladder strength directly.** VGC-Bench —
  scratch transformer PPO 0.48 vs SH at 5M steps; BC-initialized variants 0.62–0.78, i.e.
  +25–30 points at matched budget, the best-evidenced initialization result anywhere — is
  BC-from-**humans**, verified against the PDF: *"We train a behavior cloning (BC) policy to
  match the distribution of human actions given a state from the dataset D collected by the
  human play data collector."* (Scope caveats: doubles/VGC, joint action space, team building
  in scope, doubles-modified SH — a mechanism precedent, not a transferable magnitude.) §10
  documents a verified 109,147-replay `gen1randombattle` human corpus and what it would cost
  to use. The §10 fallback (expert iteration from a search bot) is likewise not SH-anchored,
  but its ceiling is the bot's, not the ladder's.

External-evidence hygiene, carried over: ps-ppo (Gen 9 randbats, full source read locally) is
a design reference, not evidence — BC-from-SH init + transformer + faint shaping +
distributional value + 250M states, all at once, no ablations, and its ">85% vs SH" figure has
no evaluation code behind it in any of 49 commits (its ladder Elo is real). Wang's LR-anneal
ablation is the one external result this repo has replicated (P5b/P6).

## 4. Proposal — two tracks, one retirement

Track 1 is sequenced first because it is cheap and its result decides the shape of everything
after it. The tracks share one physical constraint: launches must leave a clean committed tree
(`git_dirty` stamping), so the working order inside an evening block is *launch Track 2 lanes
first from a clean tree, then edit the tree for Track 1 work* — not "parallel" in any looser
sense.

### Track 1 — price the human corpus (measure, do not build)

Split honestly by what each check needs (r6 change: the r3 "afternoon" bundled checks that
require a working parser with checks that don't):

**Parse-free half (the actual afternoon).** Sample the 109k `gen1randombattle` replays and
measure: (1) upload-date distribution and a recency cutoff — Gen-1 randbats set pools,
Showdown's protocol, and the sim have all changed across the corpus's 2005–2026 span, so the
*usable recent-era* subset is the real corpus size, not 109k; (2) `rating` nullity and any
recoverable skill signal (verified mostly-null; the question is whether "mostly" leaves a
usable slice); (3) log-length / decisions-per-battle distributions from raw logs; (4) winner
extractability; (5) coverage of the vendored set pool (`showdown/data/random-battles/gen1/teams.ts`)
against replay-observed sets, the tractability check for hidden-team inference; (6) Foul Play:
does it support `gen1randombattle`, and at what measured seconds-per-decision — the latency
number D5 and the §10 fallback both need.

**Parser-slice half (needs a minimal Metamon-fork slice first, ~days not hours).** (7)
clean-parse fraction on a recent-era sample; (8) usable decisions per battle after dropping
spectator-hidden (`action = -1`) rows, and the share of those rows; (9) the RecordingPlayer
golden-path test (§10) passing on self-generated battles — the action-remap correctness gate.

**Provisional go/no-go bars, for the review to adjust, not accept silently:** recent-era
usable subset ≥ 50k replays; clean-parse ≥ 0.8 on that subset; hidden-action share ≤ 0.35.
Above all three → the corpus chapter proceeds as the main line (D1). Below any → price the
Foul Play fallback with check (6)'s measured latency before deciding. The deliverable is a
**sizing and fallback trigger**, not a pure go/no-go — §3's arithmetic means some form of
non-SH-anchored data work happens regardless.

**Track 1 engineering (cheap, de-risks the chapter):** the Arm A warm-start smoke (below) and
the golden-path test double as chapter groundwork; neither needs pre-registration (smokes, not
experiments).

### Track 2 — Arm B, faint-based reward shaping

The one surviving compute arm. Unaffected by P6 — it does not depend on the clone gap, and a
shaping term carries into RL-after-human-BC unchanged. Rationale: terminal-only ±1 at
`gamma = 1.0` over ~25-step episodes (measured 24.2–24.6 mean on the P6 finals) is an
extremely sparse signal.

**Form, redesigned in r6 (deliberate deviation from ps-ppo):** ±0.1 per faint, symmetric
(their confirmed constants: `faint_self: -0.1`, `faint_opp: +0.1`), **plus terminal
cancellation** — on the terminal transition, emit the negation of the accumulated faint
potential (not on truncation). Reason: the symmetric faint term is exactly potential-based
shaping with Φ = 0.1·(faints_opp − faints_self), but at `gamma = 1.0` the sum telescopes to
Φ(s_T) unless Φ vanishes at the terminal — without cancellation the effective outcome signal
spans ±1.6 and a clean-sweeping 48%-win policy outscores a trading 50%-win one. The trade-down
failure mode ps-ppo risked is *in the objective as written*; cancellation removes it provably
(policy invariance, Ng et al.), keeps `rollout/episode_return` comparable to every prior run
(episode return = terminal ±1 again), and keeps value targets in ±1 (advantages are normalized
per minibatch, value targets are not — unshaped-terminal shaping would silently inflate value
loss ~2.5× against `value_coef: 0.5`). The shaped term stays clearly subordinate to the
terminal signal by construction. Known trap, from ps-ppo's log (commit `17e0955`): an
off-by-one in faint attribution.

Kept honest: Wang won with sparse ±1; ps-ppo shipped ±0.1 faint shaping at 250M states — two
strong systems, opposite choices — so this is a probe, not a default.

### Parked — Arm C, distributional value head

r5 carried this as a co-equal arm; r6 parks it, for a reason earlier drafts had backwards.
Under terminal-only ±1 at `gamma = 1.0` the return distribution has support {−1, 0, +1} —
three atoms — so a 51-bin categorical head (an imported Atari constant) has nothing to model;
its only live rationale is a cross-entropy-vs-MSE auxiliary effect, a weak prior. It becomes
interesting **iff Arm B credits** (shaped per-step signal makes intermediate returns
multi-valued during learning even though cancellation keeps episode returns at ±1 — note the
*within-episode* value targets are what the head models) or the corpus chapter introduces
dense signal. If unparked: spine-first on CartPole + two named MinAtar games, 5 seeds, an
equivalence test (TOST) against a pre-stated ±10%-of-baseline margin — not an unfalsifiable
"parity" — plus a correctness assertion that E[Z] reproduces the scalar critic's target; and
the distributional *target* (MC return vs λ-return projection) must be specified, since that
choice, not the bin count, is load-bearing. Comparator gap to price first: the predecessor's
CartPole/MinAtar run dirs were **not ported**, so the gate needs either a baseline re-run here
or citation of the old repo's numbers.

### Retired — Arm A, the BC-from-SH warm start

Not run as an experiment. Its motivation was the clone gap, which P6 closed from the other
side; its ceiling is parity (§3); and its best outcome duplicates what scratch RL already
achieved. What survives:

- **A one-hour warm-start smoke, filed under Track 1 engineering** (r6 addition, from review):
  single seed, ~100–200k steps, warm-started from the existing `runs/bc_p4_512_40k_s0` after
  the guard fix below. Reads (recorded, not gated): win rate at step 0 ≈ the clone's — the
  broken-handoff detector r5 pre-registered; no collapse in the first updates under
  critic-only warmup; value loss reaching a sane level before unfreeze. This de-risks the
  human-BC chapter's day-one path — the only *untested* init path is exactly BC-checkpoint
  (untrained critic) + anneal, since `configs/showdown_sp6m.yaml` proves `init_from` works for
  PPO checkpoints — without spending ~6.5 h on a 3-seed arm whose answer no longer matters.
- **The staged-unfreeze design** — critic-only warmup (the P4 clone has *no trained critic*;
  naive PPO from it computes advantages off a random value head and destroys the cloned policy
  in the first updates, which measures a broken handoff, not the lever), then PPO with a
  reduced backbone LR. Mechanism sound; ps-ppo's specific multipliers are dead code at their
  HEAD and were never ablated — constants are ours to choose. Inherited by §10's chapter
  design.
- **The `rl/train.py:134` guard fix** — the code refuses `init_from` + `lr_anneal_steps`
  because resuming restores the update counter and the anneal clamps LR to ~0 silently. The
  fix (a warm start is a *fresh* run: reset the update counter, or anneal over remaining
  steps) is a design decision to make once, at the smoke.

## 5. Pre-registered reads (Track 2)

**Credit line:** pooled delta ≥ +0.025 AND ≥ 2·se_diff, 3-seed finals, ties as non-wins,
against the same-budget annealed control. r6 names the estimator, which no prior document did:
**se_diff = the larger of the pooled-binomial and the seed-clustered estimate.** (At P6's n,
binomial gives 0.0128 and seed-clustered 0.0137; P6's credit stands under its pre-registered
binomial arithmetic, but the margin was 0.003 vs 0.0003 depending on estimator — that
ambiguity should not recur.) Family size for false-credit accounting: two primaries are
planned against the control (Arm B now, Arm C if unparked); no correction applied, recorded so
the count is honest.

**Proposed protocol amendment (D2): raise finals to 3000 battles/seed, both arms AND control,
by re-evaluating the stored control checkpoints.** Variance decomposition of P6's finals:
within-seed binomial sd at 1000 battles is 0.0157 against an implied between-seed component of
only ~0.006, so ~88% of an arm-mean's variance is battle noise, not seed noise — the binding
constraint is battles, which are eval-only and cheap (~tens of minutes per arm at measured
rates, vs ~6.5 h to train one). At 3000/3000, se_diff drops 0.0137 → 0.0088; leaving the
control at 1000 wastes most of the gain (0.0115). Honesty note: the fixed +0.025 floor still
caps power at ~50% for a true boundary-sized effect no matter the battle count — extra battles
buy specificity (false credits at a true null: 2.3% → 0.2%) and power on larger effects, and
would have made P6 itself seed-level significant. Re-evaluating P5b's checkpoints in-repo also
retires a quiet confound: the 6M control numbers were measured under predecessor-repo code.

- **R0 gates, every arm:** late entropy in [0.2, 1.0]; ties ≤ 4%; steps/s within ~25% of the
  lane baseline for the concurrency used. **Arm B adds a shaping-correctness R0** (catches the
  ps-ppo off-by-one class in seconds): on a random-policy rollout, per-episode shaped return
  must equal the terminal ±1 exactly (cancellation working), and the running faint potential
  must match observed faint counts.
- **Arm B PRIMARY:** pooled finals vs the same-budget annealed control. With terminal
  cancellation, `rollout/episode_return` stays comparable to prior runs; the shaped term must
  still never leak into the eval path (eval reads `info["outcome"]`, never returns).
- **Arm B MECHANISM (pre-registered, recorded not gated)** — without these a null is
  uninterpretable (did shaping fail, or fail to change the signal?): value explained-variance
  (**not currently logged — add before launch**), pre-normalization advantage std,
  `approx_kl`, `clip_frac`, grad norm.
- **Arm B SECONDARIES with a falsifier:** episode length; faint differential *conditional on
  losses* and the fraction of losses where the agent led on faints (the unconditional
  differential is mechanically determined by outcome). Falsifier: win-rate delta ≤ 0 while
  loss-conditioned faint differential improves by > 0.5 mons ⇒ objective distortion — do not
  raise the coefficient, kill the arm.
- **Budget/control per D2's recommendation:** 6M screen against the re-evaluated P5b control
  with a **futility gate, not the credit line** — advance to 12M iff pooled delta ≥ +0.009
  (the point where the one-sided 90% upper bound still reaches +0.025; screening at the credit
  line itself is a ~50%-sensitivity coin flip that kills real levers). Full credit line
  applies only at 12M vs the P6 annealed control. P6's own transfer shape (+0.051 at 6M →
  +0.028 at 12M) says a lever worth +0.025 at 12M should show ~+0.045 at 6M, which the
  liberal screen catches with >99% probability.

## 6. Blockers and risks

1. **Power is thin at these deltas, and the cheap fix is battles, not seeds.** See §5's
   amendment; the r5-era instinct "more seeds" was the expensive lever (a fourth seed means
   training a fourth lane) aimed at the smaller variance component.
2. **The stop rule constrains Track 2's interpretation.** Ratified 2026-08-02: the 0.5-vs-SH
   bar is not chased under this recipe class; training probes need their own pre-registration.
   Arm B is a mechanism probe under that rule. Its pre-stated **amendment condition carries
   forward unchanged: the README gains a measured sentence only if a PRIMARY credits** (or a
   pooled final clears the 0.47 mark). A long-horizon run (D4) needs re-ratification, not a
   config edit.
3. **The corpus chapter's risks are §10's** — parser fork, action-remap silent-mislabel
   hazard, spectator-hidden actions (and their non-random bias), era drift, scale/dataloading,
   no skill filter, no stated license. None are priced until Track 1 runs.
4. **Encoder freeze vs the corpus.** Any `OBS_DIM` change invalidates every checkpoint (§8),
   and a corpus materialized as *embedded vectors* freezes the encoder the same way. r6
   constraint: **store reconstructed trajectories in raw (replayable) form; embed at load or
   into an encoder-version-keyed materialized cache.** This is *deferred* cost, not zero cost
   — see §10's scale risk for the honest arithmetic.
5. **6M→12M transfer is not automatic.** P6 showed the same lever at +0.051 (6M) and +0.028
   (12M); any 6M-credited lever needs its 12M confirmation before entering the headline
   recipe. D2's two-stage design bakes this in.

## 7. Explicitly NOT proposed

- **Encoder enrichment now.** P4's bucket analysis priced the known feature residue at 2.1% of
  clone disagreements and attributed the weak buckets (forced-switch agreement 0.866,
  voluntary-switch 0.556, vs all-status 1.000 and val free-agreement 0.9017/0.8987/0.9047) to
  boundary sharpness, not missing information — and P6 drew level with the clone without
  touching the encoder. Two questions survive, parked, both `OBS_DIM`-changing: an explicit
  **STAB flag** (~4 dims; we precompute the harder cross-entity multiplier but omit STAB;
  ps-ppo encodes it), and **boosts as 7×13 one-hots** replacing the `boosts/6` scalar (a
  representation change aimed exactly at the boundary-sharpness finding). Caveat for the next
  chapter: P4 exonerated the encoder *for representing SH's policy*; that verdict does not
  automatically extend to representing human play — revisit if human-BC underfits. §6.4's
  raw-storage constraint keeps revisiting cheap.
- **Transformer / entity-tokenized trunk.** Capacity is not the measured constraint; on CPU it
  costs throughput inside a loop that is 94.8% collect, and inference sits inside collect. The
  inference-cost measurement is a hard precondition, not a step. Gen 1 also shrinks the prize
  (no items, abilities, weather, Tera — much of what their attention relates does not exist).
- **Wholesale hyperparameter adoption from ps-ppo** (`gamma` 0.999, `clip` 0.1, `epochs` 2, …)
  — each is a separate variable; none are evidenced by ablation.
- **JEPA, KV-cache history, move-ID embeddings** — undisclosed and unablated in the only
  source using them; the author's public description contradicts his own code.
- **MCTS follow-on.** Downgraded, and D6 makes it formal: PokéAgent 2025's Gen1OU podium was
  pure-policy RL at #1 and #2 with the engine-search agent (Foul Play) #8 despite winning
  Gen9OU — the pure-policy handicap is smallest in early gens. Search stays out of scope for
  this phase. **REOPENED 2026-08-05 by §11** (proposed, not yet ratified): Track 1's bars
  failed and §10's own fallback is a search bot, so the question is no longer hypothetical.
  §11 does not overturn the reasoning above — it narrows what "search" is being proposed.

## 8. Operational notes

- **Any `OBS_DIM` change invalidates every existing checkpoint.** Evaluate all outstanding
  finals before such a change lands.
- **Concurrent lanes need distinct `--seed` across arms** — global `random` is seeded from
  `cfg.seed`, poke-env derives Showdown usernames from it; same-seed lanes collide and the
  loser dies at first `reset` with `TimeoutError: Agent is not challenging` (killed an arm
  once already). Harness improvement worth one line of code when convenient: salt the username
  RNG per lane, decoupling it from `cfg.seed` — this would also permit seed-*paired* arms,
  permanently retiring the "both arms carried by one strong seed" caveat class.
- **Eval battles are not common-random-number paired across arms** — `rl/common/evaluation.py`'s
  docstring advertises paired comparisons, but Showdown episodes are server-rolled and the env
  never seeds them. The predecessor repo already measured what pairing would buy: per-battle
  return correlation ≤ 0.04 across all 21 run-pairs, and the observable team draw explains only
  ~3.7–4% of outcome variance (P3; recovered 2026-08-05). Pairing buys nothing on Showdown —
  fix the docstring, do not build the machinery.
- **Launchers assert battle progress, not run-dir existence** — run dirs are written before
  the first `reset`. Stagger lane starts (SIGSEGV in torch lazy init has killed an unstaggered
  lane before any log line).
- Annealed checkpoints cannot be warm-extended (§4's guard); a 12M anneal arm runs from
  scratch with `lr_anneal_steps: 12000000`.

## 9. DECISIONS FOR THIS REVIEW

Each with options and the author's recommendation. A decision, once made, moves into the
relevant config header or STATUS.md; this section is the review's agenda.

**D1 — Phase placement of the human corpus (§10).** *(a)* Corpus first, park everything else;
*(b)* corpus after Track 2; *(c)* run Track 1's measurement now, decide placement on its
numbers against the pre-stated bars (§4); *(d)* its own phase, structured as a
data-engineering chapter, not a probe arm. **Recommendation: (c) immediately, with (d) as the
presumptive shape if the bars clear.** The corpus is the only lever aimed at the actual goal
(§3): SH-imitation levers are parity-capped, and RL-vs-SH levers past parity optimize a bot
the human ladder beats four times in five. (a) without measurement commits a chapter on an
unpriced option; (b) sequences a cheap afternoon behind 2.9–13 h of compute (D2-dependent) for
no reason.

**D2 — Track 2 budget, control, and the eval amendment.** *(a)* 6M arm vs the P5b control
(~2.9 h); *(b)* 12M arm vs the P6 control (~6.5 h); *(c)* 6M screen with the +0.009 futility
gate, credited levers confirmed at 12M (§5). Bundled protocol amendment either way: finals at
3000 battles/seed for arm and control (re-evaluate stored control checkpoints; ~tens of
minutes), se estimator named as §5 specifies. **Recommendation: (c) with the amendment.** It
is (a) plus the confirmation (a) would need anyway (§6.5), both controls already exist, and
the two independent reads combine to better evidence (effective se ≈ 0.0097) than a single
12M read. Known blind spot, accepted: a lever whose effect exists *only* at 12M dies at the
screen; P6's transfer shape says that inversion is unlikely.

**D3 — Arm A's disposition.** *(a)* Run it anyway at 12M; *(b)* retire the run, keep the
smoke + staged-unfreeze design + guard fix as §4 specifies; *(c)* delete it entirely.
**Recommendation: (b).** (a) spends ~6.5 h on a parity-capped question whose best outcome
duplicates the scratch result; (c) throws away the handoff machinery the human-BC chapter
needs on day one — the untrained-critic hazard is identical there, and the smoke prices it at
~1 h.

**D4 — A long-horizon scaling run (24M+, ~13 h).** The case for: flat 6M→12M = +0.0407
(z ≈ 3.2) is real, contradicting the archive prior that steps buy nothing, and Wang's curve
shows a pure network reaching 0.786 vs SH at large budget. The case against: the annealed
marginal (+0.0174 ± 0.0129) is inside noise and confounded by schedule shape, so there is no
statistical basis for extrapolating the *best* recipe's curve from two points; the run
measures SH-exploitation (§3); and the stop rule exists precisely here. *(a)* Run now; *(b)*
defer until the corpus decision; *(c)* reject under the stop rule for this recipe class.
**Recommendation: (c), revisit inside the next chapter if its recipe changes the premise.**

**D5 — A benchmark beyond SH.** vs-SH stays the locked comparison metric (board continuity),
but past parity it measures exploitation. *(a)* Stand up a ladder eval now — re-priced by
review: a working reference exists (ps-ppo's deleted `eval.py`, recoverable via
`git show 7fb522c^:eval.py`, ladders via `ShowdownServerConfiguration` + `player.ladder(n)`),
so the cost is an account, rate limits, and human time, not new infrastructure; *(b)* add
Foul Play as a second scripted anchor **iff** Track 1 check (6) confirms format support AND
its measured seconds-per-decision makes evaluation affordable — at search-bot latencies
(~10 s/move class), the locked protocol's ~81k decisions is hundreds of hours, so (b) almost
certainly implies a reduced pre-registered protocol (e.g. 150 battles), decided when the
anchor is adopted, not after; *(c)* nothing until the corpus chapter. **Recommendation: (c),
with check (6) gathered anyway inside Track 1** — the same latency number prices the §10
fallback, and a ladder eval is the natural success metric *of* the corpus chapter (D7).

**D6 — Formally close two standing questions** so they stop being revisited. *(i)* The MCTS
follow-on: downgrade per §7. *(ii)* The training-opponent question past parity (self-play
pool vs SH-anchored mix): defer to the corpus-chapter design, where the answer depends on
whether a human-BC anchor exists — **amended by review: before deferring, recover the
predecessor repo's `showdown_sp6m` self-play arm numbers into SESSION_LOGS.md here.**
*Recovery DONE 2026-08-05 (see that session-log entry): self-play NOT CREDITED at matched
init + budget (Δ = −0.023 vs the matched control, inside the ±0.025 floor; SP-final vs its
own parent 0.5050 ± 0.0065 after 6M steps), with the recorded caveat that the 3-seed paired
design resolves only MDE ≈ 0.14 at the recipe level. One recovered bug rides along: ported
`rl/selfplay/pool.py` evicts index 1 on overflow, breaking pre-seeded pools — fix before any
future self-play rung.* **Recommendation: adopt both closures; the deferral now starts from
the recovered record instead of a lost one.**

**D7 — Success metric and end state (new in r6; the review should not skip it).** The stop
rule bounds one recipe class but nothing defines "done" for the project. *(a)* Ratify: the
project's success metric is **ladder performance** (Elo/GXE on the public
`gen1randombattle` ladder), with vs-SH retained as the internal comparison board; define the
capstone's end state as "a ladder-evaluated agent + a written comparison against the prior-work
anchors," with the ladder eval built in the corpus chapter. *(b)* Keep vs-SH as the only
metric and define an end state in those terms. *(c)* Leave it undefined. Two sub-decisions
ride along regardless: **GPU rental** for the BC arm is charter-permitted but gated on a
measured embed/parse throughput split (if the dataloader is the bottleneck, a GPU buys
nothing — §10); and **the unlicensed corpus does not leave the local box** (a rented cloud box
is not "local, gitignored") unless the review decides otherwise. **Recommendation: (a), with
both sub-decisions as stated.**

## 10. The human replay corpus — verified 2026-08-04; the candidate main line

### What exists

`HolidayOugi/pokemon-showdown-replays` on HuggingFace — public Showdown replays via the
Showdown API. 33,154,470 rows / 69.8 GB parquet, upload dates 2005–2026, counts current to
2026-06-20. Schema: `id`, `format`, `players`, `log`, `uploadtime`, `views`, `formatid`,
`rating`. **`gen1randombattle`: 109,147 replays** — verified against the dataset's own
per-format table, more than Gen1OU's 102,574. At Gen 1 game lengths, counting both
perspectives, plausibly 10–20M state-action pairs — 11–22× P4's 903,090 SH decisions, an
order of magnitude. Filter to the format; never pull the full 69.8 GB. **Pin the dataset
revision and checksum the filtered subset** — the dataset is live and grows; unpinned
re-downloads silently change the training set.

### Why it is the candidate main line

Human demonstrations are not anchored to SH at any point (§3): the ceiling is the uploader
population's strength, which Metamon's Gen1OU measurement (SH ≈ 0.21 vs ladder) suggests is
far above everything on our board. Temper it twice: `rating` is mostly null (verified), so
absent a recoverable skill signal a clone learns the *mean uploader*, not the strong players
inside that 0.21 — and replays are **voluntarily uploaded**, over-representing games someone
thought worth saving (milder in randbats than tournament OU, but real). Expect well above SH;
do not expect the naive +0.3.

### What it costs — the shortcut does NOT exist (all verified 2026-08-04)

- **Metamon's parser is not reusable as-is.** It does not support random battles (Gens 1–4 OU
  + Gen 9 OU only); it replaced poke-env's message parsing with its own, so its output cannot
  feed our `embed_battle(battle, type_chart)`; and its action space (13 discrete, or a
  9-choice `MinimalActionSpace` for Gens 1–4) orders moves and switches **alphabetically**
  where ours is poke-env insertion order with 6 switch slots including the always-illegal
  self-switch — a re-sort plus a hole, not a permutation. **An off-by-one here silently
  mislabels every row and is invisible in training curves** — the exact failure class in
  pokejax's diagnosed obs-bridge bug list. Its Gen-1 *mechanics* parsing is still the right
  thing to fork (gen1randombattle and gen1OU differ only in team source).
- **Mitigation, required before any training run (Track 1 check 9): a golden-path round-trip
  test.** `rl/collect.py`'s `RecordingPlayer` already produces ground-truth (obs, mask,
  action) rows from self-generated battles; feed those battles' logs through the replay-parse
  path and assert recovered action indices match exactly. ~An hour of work; eliminates the
  silent-mislabel mode.
- **Spectator replays hide each player's private view.** Metamon's own docs concede heuristic
  reconstruction ("no way to be perfect"); unrevealed choices become `action = -1` rows
  needing an explicit policy (masked out of the loss, most likely). **Bias warning (r6):
  hidden actions are not missing at random** — they correlate with switch decisions, exactly
  the skill P4 measured as weakest (voluntary-switch agreement 0.556) and the behavior the
  corpus is being bought to teach. Masking silently biases the clone against it; the chapter
  design must at least measure the skew (what fraction of `-1` rows are switches, inferable
  from the next revealed state).
- **Era drift.** The corpus spans 2005–2026; set pools, protocol format, and sim mechanics all
  moved. The vendored `teams.ts` is *today's* pool. Old logs may fail to parse, and logs that
  parse may be off-distribution for the env we train and evaluate in. Track 1 check (1) sets a
  recency cutoff; the usable corpus is the post-cutoff subset, not 109k.
- **Scale and the honest cost of §6.4's raw-storage constraint.** P4's 903k rows embed to a
  2.23 GB array that the current BC path loads *fully into RAM* (`scripts/train_bc.py`);
  10–20M pairs is 25–50 GB embedded — 12–22× anything this pipeline has handled. "Embed at
  load time" is deferred cost paid every epoch, and `embed_battle` takes a live poke-env
  `Battle` object, so it means replaying protocol into poke-env state per pass. Requirements
  before any GPU spend (D7): a measured rows/s for the replay→embed path, and a sharded
  memmap or encoder-version-keyed materialized cache design. P4's own data-scaling read
  carries over as the reason to want the scale at all: the SH clone was still data-limited at
  40k battles (+0.021 val-agreement per doubling, ratio 0.78) — the identical question
  re-arises here with 100× the data.
- **The clone's evaluation plan (r6; §5's credit line does not transfer).** A human-BC clone
  gets: held-out human action-agreement (the cheap supervised milestone, available long before
  any RL and resumable in evening blocks); vs-SH under the locked protocol (board continuity
  only — §3 says it stops meaning strength past parity); head-to-head vs the best RL policy;
  and, if D7(a), the ladder. Pre-register these in the chapter's own design doc.

### Components inherited from the retired Arm A (§4)

The warm-start handoff is this chapter's day-one machinery: the `rl/train.py:134` guard fix,
critic-only warmup then reduced-backbone-LR unfreeze (the human clone will have an untrained
critic exactly as the SH clone does), and the step-0-win-rate broken-handoff detector — all
smoke-tested cheaply on the existing SH clone before the chapter bets on them.

### One structural advantage

**Hidden-state reconstruction is better posed in randbats than in OU.** OU teams are
player-chosen from an enormous space (why Metamon needs usage-statistics heuristics);
`gen1randombattle` sets come from a fixed, public, enumerable pool — and this repo already
vendors it (`showdown/data/random-battles/gen1/teams.ts`). The standing worry that choosing
randbats locked us out of the human-data lever was exactly backwards.

### Fallback: expert iteration from a search bot

Generate demonstrations from Foul Play (open source; #8 Gen1OU at PokéAgent 2025 — its
strength relative to SH is inferred from competition placement, no direct Foul-Play-vs-SH
measurement exists in our index) instead of parsing humans: perfect formatting, correct
perspective, our exact action space, zero parsing. Cost: search bots run orders of magnitude
slower per decision than the 2,769 decisions/s P4 measured generating SH data (old-repo logs;
Wang's MCTS ran ~10 s/move) — P4-scale data is days, not minutes — and `gen1randombattle`
support is unverified (Track 1 check 6, which also measures the latency). Lower ceiling than
human experts; far lower engineering risk. Priced as the fallback if Track 1's bars fail.

### Governance

No charter carve-out needed (the no-RL-libraries rule is retired here). Binding: provenance —
anything forked from Metamon is named in the README and in code with an exact pin; adopting
the parser is a stated decision recorded here or in STATUS.md, not an incidental convenience.
We take Metamon's parser design, not its offline-RL algorithms or agents. The corpus has **no
stated license**: local, gitignored, never committed (it is 69.8 GB in full anyway), and it
does not leave the local box without a D7 decision. (The may-go-public strictness that
originally motivated extra caution was relaxed 2026-08-05; not committing and not
redistributing unlicensed data still stands.)

## 11. Search — proposed amendment to §7 and D6(i)

**Status: PROPOSED 2026-08-05, NOT ratified.** Written at maintainer request, on the stated
view that "eventually we will need some type of search." If ratified, this supersedes §7's
MCTS bullet and D6(i)'s closure. Everything below separates MEASURED from INFERRED, because
most of what is confidently repeated about search in Pokémon is neither.

### Why this reopens now, when D6 had just closed it

D6(i) closed the MCTS question so it would stop being re-litigated every session. Two things
measured on 2026-08-05 changed the inputs, which is the legitimate trigger for reopening:

1. **Track 1's bars failed.** The ≥50k recent-era subset does not exist at today's set
   distribution (≥2023 = 49,693 replays but only 28% level-table match; ≥2024-04, the level
   table's step change, = 44,391 at 91%), and the corpus sizes at ~6.06M decisions total
   (~6.97M calibrated) — **~3.4× P4, not §10's projected 11–22×**. §10 names the fallback for
   exactly this outcome: *expert iteration from a search bot.*
2. **That search bot was priced.** Foul Play supports `gen1randombattle` (MEASURED from source
   at commit `25c976f0`: generic format parsing, a registered GEN1 mechanics entry, gen1
   protocol handling, and a live gen1 set file at pkmn.github.io). Its per-decision cost is a
   **dial, not a property**: `--search-time-ms` defaults to 100 and feeds
   `monte_carlo_tree_search(state, search_time_ms, threads)`, with random-battle mode searching
   `parallelism × 2` sampled battles (×4 shallow early), so stock wall clock is **~0.2
   s/decision (INFERRED, not measured)**.

So the fallback §10 already sanctioned is both triggered and priced. That is a narrower claim
than "search is now a good idea," and §11 is deliberately not making the wider one.

### What the prior against search actually says, and how far it reaches

§7's evidence stands and is the strongest datapoint we have: Foul Play won Gen9OU and placed
**#8 in Gen1OU**, where #1 and #2 were pure-policy RL. Same bot, same search, opposite outcome
by generation. A plausible mechanism: Gen 1 removes most of what makes deep tactical trees pay
(no items, abilities, weather, Tera) while adding brutal variance (speed-derived crit rates,
permanent freeze, sleep), and averaging over a high-variance tree shrinks the EV gap between
candidate moves relative to the noise. **Honest caveat, per prior_work/README.md's standing
warning:** that is a competition *placement*, not a measurement — no direct Foul-Play-vs-SH
number exists in our index — and placement conflates tuning, search budget, and luck.

The prior therefore bears hard on *inference-time search as the agent* and much more weakly on
*search as an offline teacher*, where a slow bot's strength is amortized rather than paid per
move. §11 proposes the latter.

### Three structural facts any search design here must respect

1. **Simultaneous moves.** Both players commit at once; there is no "my move then yours" tree
   and no max node. The correct treatment at each node is a matrix game wanting a MIXED
   (equilibrium) strategy — a search that maximizes against a fixed opponent model is
   exploitable by construction. This is not a detail that can be patched later; it decides the
   algorithm.
2. **Imperfect information.** You cannot instantiate a tree over a hidden opponent team, so
   candidate teams are sampled and each searched (determinization), which carries documented
   pathologies — chiefly strategy fusion, where the search assumes it will know the hidden
   state at future nodes when it will not. **Mitigating, and it is the same structural
   advantage §10 identifies:** randbats sets come from a fixed, public, enumerable pool we
   already vendor, so the sampling distribution is far tighter than OU's player-chosen teams.
   Determinization is better posed here than anywhere else in this game.
3. **The cost fork, which matters more than either.** Collection runs ~600 steps/s/lane.
   Search *in the training loop* (true AlphaZero, where search generates the targets) is a
   100–1000× hit on data generation; AlphaZero worked because its simulator was nearly free
   and it had TPU farms. On one CPU box at our budgets that is not viable, and §11 recommends
   against it explicitly rather than leaving it implied. Search *offline* or *at inference
   only* costs what it costs, once.

### The trap, stated before any option is chosen

Search would exploit `SimpleHeuristicsPlayer` hard and vs-SH would jump. §3 and D7 already say
that past parity vs-SH measures SH-EXPLOITATION, not strength — so search's most
impressive-looking number is precisely the one this project has agreed not to trust. **Any
search work is read on the ladder (D7's ratified success metric), with vs-SH as board
continuity only.** A search arm scored on vs-SH would be a bar-chaser under the stop rule.

### Options, with costs

- **(A) Feasibility note only — the gate.** ~an afternoon, no arm. Does poke-engine's gen1
  build reproduce *Showdown's* gen1 mechanics closely enough to search in, and what is its node
  throughput? Any divergence is a silent modelling error that makes the search optimize the
  wrong game, and Gen 1 is exactly where sims disagree (1/256 miss, speed-derived crits, wrap
  semantics, hyper-beam recharge, the stat-modification glitches Foul Play's source names).
  Deliverables: a mechanics-agreement rate against our own env on replayed trajectories, a
  measured s/decision (retiring the INFERRED 0.2 above), and a measured Foul-Play-vs-SH win
  rate under a reduced protocol — the number our index has never had. First cost, already
  measured: poke-engine compiles **per generation** (`make poke_engine GEN=gen1`,
  `--no-default-features`) and the stock wheel is gen9/terastallization, so (A) starts with a
  from-source gen1 build, not a `pip install`.
- **(B) Inference-time search wrapper.** Wrap search around the existing policy at eval/ladder
  time; no training change, reuses a checkpoint we already have. Cost at the locked protocol:
  3 seeds × 3000 battles × ~27 decisions/side ≈ 243k decisions ≈ **13.5 h at 0.2 s/decision**,
  which is why (B) implies a reduced pre-registered protocol (D5 already anticipated this).
  Directly tests §7's inherited claim on our own board.
- **(C) Expert iteration — search as a teacher. RECOMMENDED.** Generate demonstrations offline
  with Foul Play, distill into the policy by BC, then RL from there using the warm-start
  machinery already built and smoke-tested (critic-only warmup, `actor_lr_scale`,
  `begin_warm_start`). Arithmetic: P4's dataset was 903,090 SH decisions; at 0.2 s/decision
  that is ~50 h single-threaded or **~6 h at 8-way parallelism**, and the search budget is a
  knob that can be turned down for bulk generation. This buys a P4-scale dataset from a far
  stronger teacher than SimpleHeuristics, with perfect formatting, correct perspective, our
  exact action space, and **zero parsing risk** — against a human corpus that just came in
  smaller and dirtier than projected. It also sidesteps all three structural facts above: cost
  is paid once offline, and the shipped agent needs no search at inference.
- **(D) Search in the training loop.** NOT recommended; see fact 3.

### What (C) inherits and what it does not

Inherits: the whole warm-start path, now measured — handoff verified non-breaking (frozen-window
0.4875 vs the clone's 0.4657), critic warmup ~5 updates sufficient, and the **entropy finding
that is a hard prerequisite: a BC-warm-started run sits at `loss/entropy` 0.063 and does not
move, failing the [0.2, 1.0] R0 band from update 1.** A distilled search teacher will be at
least as peaked as an SH clone, so its `entropy_coef` must be chosen before the first run, not
waived after it.

Does NOT inherit §10's evaluation plan: there is no held-out human agreement metric here. The
reads are held-out agreement against the TEACHER (a supervised milestone available long before
any RL), vs-SH for board continuity only, head-to-head vs the best RL policy, and the ladder.

A free by-product of (C), worth taking: the teacher dataset is also an **architecture screen**.
Fitting the same BC objective on our encoder with each candidate trunk (current MLP-[512,512]
vs a transformer) and comparing held-out teacher agreement answers the architecture question
with **zero RL budget** — it is the method ps-ppo itself used, and the dataset it needs is one
(C) produces anyway. This is a read inside the chapter, not a separate arm.

Ceiling, stated honestly: (C) is bounded by Foul Play's own strength, which **nobody in our
index has measured**. That is the single number option (A) exists to get, and it should be got
before (C) is committed to — a teacher weaker than it looks would cap the chapter exactly the
way SH capped P4.

### Decisions for the maintainer

**D8 — Does search re-enter scope, and in which form?** *(a)* No; D6(i) stands. *(b)* (A) only
— buy the measurement, decide later. *(c)* (A) then (C), with (C) gated on the feasibility
note's numbers. *(d)* (A) then (B). *(e)* (C) immediately, skipping the gate.
**Recommendation: (c).** It is the cheapest path that converts §7's inherited judgement into a
measured one, and it puts the gate before the chapter-sized commitment. (e) commits to a
teacher of unmeasured strength; (a) is now hard to defend given Track 1's result.

**D9 — Does the corpus chapter yield to it, or run beside it?** *(a)* Corpus chapter proceeds
as the main line anyway on the ≥2024-04 subset (44,391 replays, ~3.06M decisions). *(b)* Expert
iteration replaces it as the main line. *(c)* Expert iteration first — it is faster, cleaner and
parser-free — with the corpus chapter re-priced afterwards against what the distilled agent
actually achieves. **Recommendation: (c), with (a) explicitly still live.** The two are not
exclusive and the corpus does not spoil; but the human corpus's headline advantage was scale,
and that advantage is what Track 1 just removed.
