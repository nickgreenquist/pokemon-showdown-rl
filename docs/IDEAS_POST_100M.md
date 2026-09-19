# IDEAS_POST_100M — audited candidate levers (2026-09-01; last amended 2026-09-18)

Source: `~/Downloads/pokemon_rl_ideas.md` (a 2026-09-01 env-less code audit),
re-audited this session against the code, the committed record, and
`docs/prior_work/README.md`; verified claims are cited in place and the source
doc's errors are corrected in §7. **Not a pre-registration.** Every fleet
item here needs its own pre-reg header (credit line restated verbatim,
`journey_step` named) before anything launches.

**Status tally — 2026-09-06, amended 2026-09-08. STALE as of 2026-09-18:** four
rows were added post-ladder (**2.10, 2.11, 2.12, 4.9, §8.5** — 26 actionable rows
plus §8, which is deliberately outside this count), **2.2 is BUILT** (Round 3),
**4.3 has RUN** on every lane of the 200M fleet, and **§3's width/capacity entry
is ANSWERED**. Read Round 4 below before quoting any count here. Of the
22 actionable rows (2.9 and the §5 shared-trunk row added 2026-09-08 from the
SB3 audit; the §5 cross-features row banked the same evening; the SB3
MIGRATION itself is closed in §3): DONE 3 (2.5 ruled + CLOSED; 2.6 BUILT; 4.1 BUILT as the
gen-4 baseline's mechanism, unrun as a gen-1 lever); ABSORBED by the gen-4
design 2 (temporal context in §5; C6's defect via the variable-damage bit —
neither credited, both no longer open at gen 4); BUILT-UNRUN 1 (4.3); NOT
STARTED 16 (2.1–2.4, 2.8, 2.9, 4.2 as an arm, 4.4–4.7, the attention
re-benchmark, the §5 shared trunk, the §5 cross features, §6
except the branch-protection click). **Q45 CLOSED 2026-09-06: §4 is ranked
4.1 → 4.5 → 4.3 → 4.7 → 4.2 → 4.4, all downstream of JOURNEY 7.5** — **amended
2026-09-18: 4.9 (expert iteration) sits AHEAD of all six, and the whole section
is gated on 2.11 reading first.** Nothing
here precedes the first gen-4 run (ruled: Wang's recipe, levers held back);
2.2's pairing comes free SEQUENTIALLY by seed reuse — the tag matters only
for concurrent same-seed arms. 2.1 and the §6 ops items are the two cheap
agent-side slots once no babysitter session is mid-schedule.

**Two rulings, 2026-09-06 evening.** (i) The privileged critic's D18 kill is
VACATED AS FINAL — a 12M A/B on the pre-batch recipe does not close an axis;
the evidence stays in §3 and the live item is **4.7** (a 100M+ arm, mechanism
co-primary). (ii) A pool-vs-latest-only ablation is **NOT WANTED**: league
play stays on in gen 1, and `pool_size: 1` is Wang-fidelity only (§3). The
agent's pull-forward suggestion of the same evening is withdrawn.
**Kill-record audit, same evening (on the maintainer's question "what else was
killed too early").** §3 now classifies every entry as mechanism-bounded,
dose-limited, contingent or mixed-legs, and carries a STATUS CHANGES index of
what moved and where the live item lives — pointers, never second homes.
New row: **2.8** (GPU/MPS for the update, the kill whose premise expires with
the collector port). Repriced rather than resurrected: **4.3** (its +0.0451
sits above the k=8 shared-control bar) and the **attention** rung (§5 — killed
on a throughput microbenchmark, never measured on win rate). §4's ORDER is
untouched: the re-rank is the maintainer's and is still owed.

**Round 2 — 2026-09-04.** The sequencing floor below is DISCHARGED: fleet
done, frozen schedule run, graded **P3**, recorded (RESULTS §18; S-SHAPE
**SS-CLIMB**). Step 2 is in progress (ladder R4 on the 100M final s112,
`configs/eval/ladder_r4.yaml`). This round adds 2.7, two §3 firewall
entries, 4.5–4.6 (appended, UNRANKED — the re-rank is the maintainer's,
STATUS next-action 3), a §5 amendment and §7 round 2. Still not a pre-reg.
**Citations note (2026-09-04):** `CHAPTER5.md` was archived to
`docs/archive/CHAPTER5.md` under a 13-line banner, so a `CHAPTER5:N` line
cite below resolves at N+13 there; its §3 (the C1–C6 provenance table,
C6 at `:624`), §6 and §7 live verbatim in
`configs/showdown_sp_batch50m.yaml` (lines ~542–793) — the live location
for the C-items; §7 ruling 4 (the 50M ceiling) is superseded by name in
the 100M header.

**Round 3 — 2026-09-12 (overnight review session; three Opus reports under
`docs/research_reports/*_2026-09-12.md` and a plasticity probe).** Status
changes, each pointing at its evidence: **2.2 is BUILT** (`env_kwargs.seat_tag`,
`rl/envs/make.py:36-47`; the tally above is stale) and deliberately NOT used to
pair arms in the monster — pairing trades away the committee diversity the
ladder object monetises. **4.3 (regenerative L2) rides EVERY lane of the
2026-09-12 fleet** ([RWL-1] in `configs/showdown_monster200m.yaml`): the
probe's PLASTICITY-LOST branch fired for the critic (refit R = 1.89× a fresh
init, complete by 12M). **4.7 (privileged critic)** is not in that fleet (its
falsifier cannot fire; both reviews) and stays live here. **4.5 (more steps)**
is the fleet's horizon (200M) but is no longer read as a lever: the 50M and
100M committees read within 0.0013 vs SH and +0.030 ± 0.02 off FP@20 — steps
and members are additive and the horizon is the weaker one. **§5 LayerNorm in
the context stack is BUILT** (`trunk_kwargs.ctx_layernorm`, gated, tested) and
held for the next fleet (it removes `ctx_net` from the L2 per-block metrics).
**§5 width is being MEASURED for the first time** — the W trio widens the
critic to 1024 (the axis three on-policy sources name), with srank99 as a
fraction of width as the mechanism read; the entry in §3 stays contingent
until that reads. **§8.1 is answered up to ~300 ms** (the budget ladder to
dose XL, the tree at ~230 ms, poke_engine MCTS at 200 ms: flat; FP@500 for the
committee pending) and **§8.3 at depth-1** (n_det 1→64 flat). **NEW ROW 4.8
below: the committee.** The IDEAS-stale claim "our measured KL would never
fire" is gen-4; gen 1 reaches approx_kl 0.04–0.11.

**Round 4 — 2026-09-18 (post-ladder: LADDER R5 landed on the top-500 list, then a
week of search and mechanism reads; RESULTS §§20–24).** Status changes and new
rows, each pointing at its evidence:

* **§3's width/capacity entry is ANSWERED and no longer contingent** — RESULTS
  §21 fired branch 1 (critic first-layer srank99 **632/1024**, 0.617 of width,
  against **5/384** on the 100M baseline) and INVERTED branch 3 (explained
  variance **did not move**: 0.5881 vs 0.5919). Both halves are recorded in §3
  below. A bigger critic is no longer bounded by IDLENESS; it is bounded by the
  **EV ceiling**, and **the next fleet must not be sized on EV**.
* **§8.1 is answered at a real budget, and the answer is a null against the
  right bar.** The bar is **greedy 0.5765 (n=4500)**, not the depth-1 search,
  and every search configuration measured on the R5 committee is level with or
  below it (RESULTS §24). Separately, the R5 committee **beats FP@500**
  (0.5600, n=500, +2.70 se above even; RESULTS §25) and 25× budget buys Foul
  Play nothing (+0.010 at 0.32 se over FP@20, for 24.4× the wall clock) — so "FP beats us using 500 ms", the premise
  §8.1 was written on, no longer holds for this object.
* **§8.2's premise SURVIVES but its diagnosis is REVERSED.** Our critic is the
  ROBUST evaluator, not the fragile one: opening the gate costs our critic 0.006
  (0.38 se) and Foul Play's hand-tuned heuristic 0.088 (5.59 se), and the
  evaluator difference is −0.102 at 5.62 se at an open gate (RESULTS §24). The
  bottleneck §8.2 names is real, but "our critic is off-distribution garbage"
  is measured false and may not be quoted.
* **NEW Tier-0 rows: 2.10** (fix `_look_further`'s optimism — an IDENTIFIED
  DEFECT, hours of work, currently worth ~5 points at an open gate), **2.11**
  (measure the LUCK CEILING — BUILT AND UNRUN, and it BOUNDS every row above
  it), **2.12** (weight-averaging the last rungs — free, never tried).
* **NEW Tier-1 row 4.9 — EXPERT ITERATION**, and the maintainer ranks it the
  **TOP item of §4** (2026-09-18). It is the one lever that attacks both
  measured defects at once and it is IN CHARTER: the expert is our own search.
* **NEW §8.5 — disagreement-gated search**, the unspent-budget question §8.1
  asked, in the form the committee makes free.
* **Maintainer's stack rank for the search work, 2026-09-18:** (1) 4.9 expert
  iteration, (2) 2.10 the depth-2 optimism fix, (3) §8.5 disagreement-gated
  search, (4) 2.11 the luck ceiling **first, as a gate on all of it**, (5) 2.12
  weight averaging, (6) 4.8's members 4–6 on the W recipe.
* **Process, now in CLAUDE.md:** pre-reg is for LADDER RUNS and headline claims.
  A row here that only explores an idea needs no pre-reg and no ratification —
  what does NOT relax is counters-to-disk, matched comparisons, and a
  same-session anchor on every cross-session number.

**Sequencing floor (binding):** nothing below runs before FLEET DONE → the
frozen eval schedule → grade → record (HANDOFF §§1–3; the peeking bar covers
*any* checkpoint eval until the last lane ends). After the record lands,
**JOURNEY step 2 (ladder #3) is next on every branch** (HANDOFF §4.4);
fleet-scale retrains below are **step 8** work unless the maintainer pulls
one forward the way the 100M was.

---

## 1. The constraint that orders everything

σ_seed ≈ 0.0617 at k=3 (SESSION_LOGS 2026-08-28: R1-A bar 0.0717 =
2·σ_seed/√3; s_50(off-FP) 0.0617 ≈ vs-SH 0.0630). Realized unpaired bars run
0.065 (D23) – 0.0718 (R2) – 0.1007 (r9-corrected two-fleet form). D23's
finding generalizes: **an advisory-scale effect (+0.02..0.05) lands in the
recording band at k=3 unpaired** — only R2-sized effects (+0.137) credit.
Hence the tier order: instrument first, free reads second, fleets last and
only for levers that could plausibly clear ~0.07 — or that pre-commit a
mechanism-primary design (the D23/carry lesson, SESSION_LOGS 2026-08-13).

The 100M grade re-ranks §4: if S-SHAPE is still rising at 100M (quote it
with the mandatory anneal sentence), "more steps" competes with every lever
and the 2026-08-23 big-runs ruling's second re-trigger — "a live run whose
training logs are still clearly climbing" — is met by measurement (it still
needs a maintainer decision and a pre-reg; RESULTS §18); if it is bending,
the per-step levers below rise. Write the §4 pre-reg *after* the grade.
[2026-09-04: it read SS-CLIMB, +0.02925 at 4.6× the threshold — see 4.5.
The phrase "standing fewer-bigger-runs order" that stood here named no
ruling on the record; §7 #20.]

**The instrument itself is on the table — pointer added 2026-09-06.**
`docs/PKMN_ENGINE_RUST_PLAN.md` (DESIGN ONLY; implementing it needs a
maintainer ruling) is the one item that attacks this section's constraint at
the root instead of paying it: an in-process gen-1 collector on pkmn/engine,
projecting ~4.2x FULL-LOOP per lane (collection-only >= 25k steps/s at K=256,
after which the learner owns ~90% of wall — the 50x numbers are
collection-only), and the part that matters most here: **8 seeds a fleet-day
instead of 3**. That is the bar itself: bars scale as 1/sqrt(k), so k=3 -> k=8
takes the two-fleet form 0.1007 to ~0.062 and the shared-control form 0.0717
to ~0.044 — at which point D23's +0.0451 regenerative-L2 read would clear the
bar it missed instead of reading "letter-met, seed-fragile" (whether the effect
replicates at 8 seeds is what the run would test). Per-battle seeds also make 2.2's
arm-paired TRAINING seeds exact (same battle sequence for treatment and
control), which is the part of sigma_seed that pairing can actually remove.
**Do not quote the plan's CRN framing as the instrument win:** paired
EVALUATION with common random numbers is already answered in this section's
own list — feasible, small prize, and it "cannot touch sigma_seed", because
eval noise at n=3000 is +/-0.008 binomial while sigma_seed is across-TRAINING-
seed variance. The port also expires one kill's premise: MPS/GPU for the
UPDATE was measured 2026-09-01 at a ~2.5% whole-loop prize while collection
dominated; with the learner at ~90% of wall the same acceleration is worth
multiples of that, and CLAUDE.md's CPU-only rule wants a maintainer ruling
once 7.5 lands. Its §8.4 names 4.1, the D18 privileged block
(seat 2's own-side block is a slice of an obs the collector already builds —
so 4.7 lands there cheaply), CRN pairing and the depth-2 question as things
the path makes cheap. **Nothing in §4's ranking is priced against it yet — do
not re-rank this list without reading it.** It does NOTHING for gen 4 or gen 9
(RBY complete, GSC WIP, no DPP at the pin), so it is gen-1-lane
infrastructure: JOURNEY steps 8 / 10 / 11 / 11.5.

## 2. Tier 0 — instrument work and free reads (no fleet; after the frozen schedule completes)

**2.1 Re-measure eval overdispersion — RUN IT (~20 min agent-side).**
The ±0.02 landmine (docs/landmines.md:55) compares a **range** of 3 draws
(0.76467/0.78467/0.78333, spread 0.0200) to a binomial **se** (0.0077).
Expected range of 3 normal draws is 1.69σ = 0.0130 (sd 0.0068), so the
observed spread is ~1σ high — ordinary. On the matching statistic: sample sd
0.0112 = 1.45× binomial, 2 df, p ≈ 0.12 — unresolved. Run 5 more n=3000
passes of the same `runs/showdown_sp_batch50m_s83/ckpt_050000000.pt` (8
total, 7 df); `scripts/ch5_scale_shape_report.py:78-83` already prints the
spread check. If eval is binomial-clean, the rule over-buys battles when
read as a 1σ width; if 1.45× holds, the landmine is measured and stays.
Either way "pool 3 seeds, read shape" survives. Output: a numbers-backed
proposal to the maintainer to re-word the landmine — not an edit.

**2.2 Seed-sharing run tag — BUILD IT (few lines + a test).**
Every training A/B to date is unpaired for a mechanical reason, not a
statistical one: usernames derive from the seed
(`rl/envs/showdown_async.py:214,219` — `as2s{seed}a/b`; the sync path
derives at construction, `showdown.py:641`), so same-seed arms collide
(landmine rule 2; the R2 seed-guard "legal owner" bookkeeping exists because
of this). Add a run tag to the username and arms can share seeds: shared
init (when shapes match) + shared early episode stream. Honest expectations:
CH3 R4's paired-clustered se of 0.0080 (RESULTS.md:693) shows what *full*
pairing buys, but that was same-checkpoint eval pairing — training-seed
pairing cancels only what stays correlated through chaotic decorrelation, ρ
unknown. It is weakly dominant (ρ≈0 ⇒ no worse than unpaired), costs almost
nothing, and it is the only cheap attack on §1. Build before any §4 fleet;
measure and report ρ on first use. Extend the seed-guard test to tags.

**2.3 Critic own-move routing — offline read ONLY (hours, no fleet).**
Verified in code: `rl/networks/entity_deepsets.py:345-349` computes
`own_moves`; `ctx_parts` (:353-359) is field + both team pools + both
actives; the critic head reads ctx alone — no PP, no disabled, no own-move
detail (it also pays the `move_net` FLOPs and discards them). D18's closeout
named exactly these lines as "the first thing to fix if critic-side work is
ever revisited" (SESSION_LOGS 2026-08-16, :4580). Two honesty notes: the
opp-move-token exclusion is a *ratified* design (docstring :27-31, threat
info routes via mon matchup features), and D18's +0.045-EV cap is about
*hidden* info — own-move routing is a different quantity, mostly bounded by
species-stereotyped movesets instead. Spec: collect ~50k mirror decisions
with the 100M final (collection-only), regress critic-A (ctx as-is) vs
critic-B (ctx + own-move pool, 5→6 · entity_dim, critic-only change) on the
same (obs → ±1) targets; read held-out EV + Brier resolution (CH3 R0's Z1
decomposition: reliability 0.0117 = calibrated, resolution 0.0594 vs
uncertainty 0.2050 = the deficit is resolution). Fleet arm only if the
offline read shows a real resolution gain — then it is §4/step-8 work.

**2.4 P3 draw-frequency covariate — OPTIONAL (~20 min).**
P3 is predecessor-era (2026-08-03, heur_512 data): CV R² 0.0375 (p<0.005,
n=3000/146 species); coefficients read as strength, not rarity (Electabuzz
+0.098, Mewtwo +0.072, Abra/Alakazam +0.07; Tangela/Parasect/Grimer ≈
−0.07), and at ~120 appearances/species the per-species se (~0.045) can
manufacture the pattern. Re-run on fresh eval JSONs with draw frequency as a
covariate (count draws from the vendored
`showdown/data/random-battles/gen1/teams.ts` pool). No lever exists either
way — teams are server-rolled — this is bookkeeping hygiene.
`scripts/p3_team_luck.py` is do-not-relitigate-protected: extend, don't edit.

**2.5 Search-depreciation write-up — DO IT (mostly free; JOURNEY's own
pre-step-3 item).** The points exist: **50M** per-lane search deltas
+0.051/+0.104/+0.148 (the CH5 R1-B lanes s80/s81/s82, off Foul Play@20 at
n=1000 — not 12M; corrected 2026-09-05 per docs/design_gen4/open_questions.md
Q41) (monotone in lane weakness), 50M batch-lane R4S66
search@20 **0.38067 vs greedy 0.4740 (~10 se — search hurts)**, and the
100M primary adds the endpoint. Formalize the curve, feed the step-2
ladder-object ruling (greedy leads on today's evidence, HANDOFF §4.4) and
pre-frame JOURNEY 11.5. No training.
**Name the budget confound when quoting this (added 2026-09-06).** Every point
on the curve is depth-1 EXPECTATION search through poke-engine at **20 ms**
against a critic D22 calls the weak component. What the curve licenses is
"depth-1 at a 20 ms budget stops paying as the policy improves" — not "search
does not pay in Pokémon". The external field says the opposite at real budgets:
Wang's own headline (rank 8, Elo 1693, GXE 79.5) is his MCTS-at-inference
agent against the 0.786 network-alone we are matching in step 5, and PokéChamp
is search-based. JOURNEY 11.5 is the test; the honest framing there is
budget-limited, not mechanism-bounded. **How budget-limited, quantified (2026-09-09): 20 ms is
0.013% of the ladder's ~150 s per turn — see §8.1, which re-runs this curve at real
budgets.**

**2.6 most-damage-typed anchor — BUILT 2026-09-05 (`rl/envs/most_damage_typed.py`;
JOURNEY's own item).** The only anchor whose strength doesn't drift across
generations; H&L report 0.829 against it in gen7. Sibling of
MaxBasePowerPlayer with type awareness.

**2.7 Zero-init encoder expansion ("model surgery") — a TOOL, not a
lever; build only when an OBS_DIM change is actually scheduled (C6 as a new
bit, or temporal context). ~a day, zero training. Added 2026-09-04.**
The claim, verified against the paper (neither OpenAI Five nor AlphaStar is
in `docs/prior_work/README.md`, so this is the verification of record): Berner
et al. 2019, *Dota 2 with Large Scale Deep RL* (arXiv:1912.06680), §3.3
"Continual Transfer via Surgery" + Appendix B "Changing the Observation
Space" — new input weights are initialized as Ŵ = [W 0], "the output is
unchanged (ŷ = y)", the zero weights leave zero only where the new
observations carry gradient, and it is "a special case of Net2Net-style
function preserving transformations". So a checkpoint survives an encoder
widening with its policy bit-identical at step 0 (PPO ratio exactly 1;
optimizer moments zero-padded for the new rows). Where it lands here:
every observation feature enters through the first `nn.Linear` of a
per-entity subnet (`_subnet` → `mon_net` / `move_net` / `field_net`,
`rl/networks/entity_deepsets.py:151-156,196-199`) after the tokenizer
slices the flat vector by block stride; the id embeddings are untouched. A
new slot in a block = one zero row in the affected first-layer matrix, in
the actor AND the critic (separate nets, `ppo.py:418-419`); a loader path
that expands instead of refusing (`train.py:103-113` refuses a width
mismatch by design; the `init_from` path at `:515` dies on the same size
mismatch); the
old→new slot map — post-F-08 a function of two `EncoderSpec`s' `*_off`
properties instead of hand-kept offsets; and the gen-1 tape hash gate
(`tests/test_encoder_spec.py`, 612/808/828) extended to the new width,
never bypassed. **What it buys: deployment continuity only** — a ladder
object can carry an encoder fix without a from-scratch fleet. **What it
does not buy: credit.** The continued run is a chain off a finished
checkpoint (§3: re-heated lr IS the N-ANNEAL confound; dormancy), the
un-surgeried parent stays incomparable under the new encoder, and both
encoders must stay loadable side by side (the cross-encoder eval shim
precedent). **The limit the external summary omitted, from the same paper
(§4.2, "Rerun"):** OpenAI's from-scratch re-train in the final environment
— 2 months, 150 PFlops/s·days — reached over 98% win rate against the
final surgery-trained model; "the model ultimately plateaued at a weaker
skill level than the from-scratch model was able to achieve." Surgery paid
for a 10-month run they could not restart. Our fleets are 2–5 days,
weights never transfer between generations (JOURNEY standing note), and a
mid-run encoder change inside a long run is a bundle the one-diff rule
refuses — so the honest use here is narrow: a fix-carrying deployment
object, or a very long run that must not restart. The same summary's other
claim, that OpenAI Five used an asymmetric critic, is not in the paper
(§7 #17).

**2.8 GPU/MPS for the UPDATE — the kill whose premise expires with the
collector port. Added 2026-09-06; needs a maintainer ruling (CLAUDE.md says
CPU only for the RL loop).** What was measured 2026-09-01: MPS crashed on a
one-site CPU-generator defect (`pool.py`, fixed 2026-09-05) and the prize
behind it was **~2.5%** — but that was a WHOLE-LOOP prize while collection
owned most of the wall. The engine plan's §0 changes the denominator: the PPO
update already costs ~12.0 s per 30,720-step rollout, and once collection is
~1 s the learner owns **~90% of wall**, so accelerating the update is worth
multiples of 2.5% instead of a rounding error. **Read (free, no fleet):**
re-run `scripts/ch5_mps_update_bench.py` on the current recipe with the
`pool.py` fix in, at the 100M `trunk_kwargs`, and quote update-only s/rollout
CPU vs MPS with the width named — then the whole-loop share follows from the
engine's measured collection time (T-1c). **Sequencing:** the read is legal
now (it is a bench, not a training run); ADOPTING it is a CLAUDE.md change and
waits for the maintainer, and it should not precede 7.5 — a 4× on 10% of wall
is worth ~2.5%, which is exactly the number that killed it the first time.

**2026-09-08 addendum (the SB3 audit, `docs/research_reports/PPO_VS_SB3_UPDATE_AUDIT.md`).**
That audit's MAC model implies the update already runs at **~226 GFLOP/s on ONE
thread** (an UPPER bound: it excludes LayerNorm/ReLU/gather/autograd work), and
`libtorch_cpu.dylib` links Accelerate with every hot shape a clean sgemm — i.e.
the update may already be BLAS-bound, with no dispatch fat for a backend swap to
reclaim. If that figure is 2–3× high the opposite holds and even CPU fused Adam
pays. ONE run settles both, plus the actor/critic/backward/optimizer split and
the per-minibatch `approx_kl` max: `scripts/ch5_mps_update_bench.py --arms cpu1`
under `torch.profiler`. Needs the idle box, so it queues behind the gen-4
post-fleet schedule.

**2.9 Update-path micro-wins, BIT-IDENTICAL — DO (an afternoon, no fleet).
Added 2026-09-08 from the SB3 audit
(`docs/research_reports/PPO_VS_SB3_UPDATE_AUDIT.md`).** Four sites in OUR update
cost **4.3–6.0% of `update_sec`** (1.2–1.7 s of gen 4's 27.7 s) and change no
number, ranked by saving: store `old_logp` at act time instead of recomputing a
full actor forward over 19,968 rows (`rl/agents/ppo.py:1054`; the machinery
already exists at `:810` and `rl/selfplay/harvest.py:25-27`) **1.59%**; gate the
critic's dead `move_net` call on `is_policy`
(`rl/networks/entity_deepsets.py:517-521`, cf. the early-out at `:535-538`)
**1.46%**; stop duplicating `flat_critic_obs` (`ppo.py:1099-1100`) and gathering
the same rows twice per minibatch (`:1329`, `:1335`) — 1.62 GB of redundant
gather traffic per update, **0.5–1.7%** (this band rests on an assumed
bandwidth, not arithmetic); replace the second critic pass with a shift of
`values` (`:1052-1053`) **0.75%**. **Scope, stated because the audit's revision
2 withdrew a gen-1 claim over exactly this:** all four apply to the SYNC path
(gen 4, and the gen-1 50M runs). The gen-1 **100M** runs are
`collector.mode: async` → `update_episodes`, which ALREADY stores `old_logp` and
ALREADY uses one critic pass, so two of the four do not apply there. Say which
path you mean when quoting a gen-1 number. Separately and **NOT bit-identical**:
Adam runs the single-tensor Python loop on CPU (torch 2.13 omits "cpu" from
`_get_foreach_kernels_supported_devices()` and passes `use_fused=False`);
`fused=True` is a legal explicit override on cpu and is UNSIZED until the 2.8
measurement. **Sequencing:** the four bit-identical fixes are worth most AFTER
7.5 makes the update dominant, and they touch the update on a live recipe —
never mid-fleet.


**2.10 Fix `_look_further`'s OPTIMISM — an IDENTIFIED DEFECT, not a lever
(added 2026-09-18; **BUILT the same day**, unrun as an arm).** `rl/search/matrix.py::_look_further`
takes a **max over OUR replies with no min over the OPPONENT's**, and its
docstring justifies that by asserting the optimism "biases every row the same
way". **It does not**, and the failure mode is systematic: rows differ in how
many replies they have and how good the best one is, so the bias inflates
exactly the rows with the most escape hatches — which are the rows search then
overrides into. **What it costs, measured (RESULTS §24):** depth 1 and depth 2
are indistinguishable at a tight gate (−0.0007) and **−0.047 apart at 2.57 se
once the gate is open**; opening the gate costs depth-2 **0.052** against
depth-1's 0.006. **BUILT 2026-09-18** (`rl/search/matrix.py`,
`tests/test_look_further_backup.py`, 11 tests): a `depth2.opp_k` dial, default
**1 = the old pinned-opponent max, bit-identical**, so nothing banked moves;
at `opp_k>1` the opponent answers each of our replies with up to k moves (its
column action first) and the back-up is max-over-paths of min-over-that-path —
exactly minimax at `plies=1`, which is what every arm has ever run. Counters
before arms: `depth2/opp_replies_mean` proves the opponent really got answers
and `depth2/minimax_drop` proves the min moved the value.
**A SECOND DEFECT fell out of writing the tests and is also fixed:** a leaf the
lookahead could not expand at all was re-embedded at `turn + 1 + plies` and
re-scored, so merely TURNING DEPTH ON moved its value by whatever the encoder
does with a shifted turn count — noise attributed to depth. It now keeps the
value it has (`depth2/leaves_unexpanded` counts them), and **every depth-2 arm
before 2026-09-18 carries that artifact**. A third, smaller hole closes with
it: a SWITCH column produced zero grandchildren, because repeating "switch N"
at ply 2 is illegal and the raise landed in a `continue`.
**RUN 2026-09-19, AND IT DID NOT RESCUE DEPTH-2.** At a matched override rate
(0.1862 vs the depth-1 control's 0.1703, gap 0.016) the minimax backup reads
**0.5070 against depth-1's 0.5510 — −0.0440 at 1.97 se.** The dial FIRED:
`opp_replies_mean` 2.0 and **`minimax_drop` 0.057**, large against a δ of 0.08,
so the backup materially changed what the search believed. It changed it for the
worse.
**WHAT THIS DOES AND DOES NOT SETTLE.** The hypothesis this row was built on —
*the optimism is WHY depth-2 hurts* — is **not supported**: the optimism was
real and large, it was removed, and the arm got worse rather than better. It
does **NOT** say the optimism was harmless (it moved leaf values by 0.057), and
it does **NOT** close depth, the tree (a different vehicle, §26, still
unresolved), or MCTS. One budget, one vehicle, one session, at 1.97 se.
**THE NEXT HYPOTHESIS, and it is specific: PESSIMISM APPLIED TWICE.** The matrix
already weights rows by the opponent's own column distribution (`col_w = q`), so
the opponent's choice is ALREADY modelled probabilistically at the root. A MIN
over its replies at ply 2 then assumes worst-case play *on top of* an
expectation-weighted opponent — and a doubly-pessimistic evaluator inside an
argmax systematically undervalues high-variance lines, which are the aggressive
ones. **The test is the third option this row named originally and never ran: an
EXPECTATION over the opponent's reply instead of a min.** **BUILT the same
night** as `depth2.backup ∈ {"min", "mean"}`, default `min` so B2R's −0.0440
stays reproducible from the config that produced it, with the choice reaching
disk as a NUMBER (`depth2/backup_is_mean`) because the collectors average the
stats dict and a string would be dropped silently.
**The weight is UNIFORM, and that is stated rather than assumed away:** the
opponent model `q` lives at the ROOT and over CLASSES, and nothing evaluates the
opponent's policy at a leaf, so a per-reply weight does not exist to use.
Uniform sits strictly between max and min, which is the whole hypothesis. **If
`mean` beats `min` the double-pessimism reading is supported; if it lands between
min and the depth-1 control, the vehicle is simply not helped by depth at this
budget and 2.10 is done.**
**The declared B2R − B2O comparison is UNINTERPRETABLE** (rates 0.054 apart, a
design error disclosed in the config): §24 measured that acting more is worse
for depth-2, B2R acts more, so a loss there could be the rate alone. **Why it is
Tier 0 and not Tier 1:** it does not need a fleet, it does not need a pre-reg
(hacking), and until it lands **no depth-2 number on the matrix vehicle measures
depth** — it measures this bug. **It also gates a ruling:** the maintainer was
asked whether a null on the matrix vehicle may close MCTS; §22 declined to
close it, and closing it on a vehicle with a known-optimistic backup would be
the D18 mistake in a new costume.

**2.11 MEASURE THE LUCK CEILING — RUN 2026-09-18. THE GATE OPENS: the critic is
NOT at the format's ceiling (RESULTS §27, `readouts/OUTCOME_VARIANCE_READOUT.md`).**
**707 positions, 22,358 rollouts. Ceiling 0.3630, our critic 0.2176, headroom
+0.1454** — ~64% of a mid-battle outcome is irreducible and we hold 60% of the
rest. **By turn the story is sharper: the critic holds 73% of what is knowable at
turn 23 and 25% in the opening**, so the proportional gap is largest exactly where
a battle is still open — the regime search visits. The kill branch ("EV_ceiling ≈
our EV, so the critic is done") **DOES NOT FIRE**, and 4.9, 8.2 and every
evaluator row stay live on this evidence. **NEVER set the training EV of 0.59
against this ceiling** — different state distribution, and the matched pair is
0.2176 vs 0.3630. The original entry follows. RESULTS §21 measured `explained_variance` pinned at **~0.59** while
2.67× critic width and 126× first-layer rank bought **zero** of it; §22/§23/§24
then measured that search buys nothing at depth 2 with **either** evaluator.
**Both results have the same untested explanation: 0.59 may simply BE the
ceiling.** Gen-1 randbats carries enormous outcome noise — crits, freeze, full
paralysis, sleep turns, damage rolls, speed ties — and none of it is knowable
from a position. **What the script measures:** each position is held at **our
observation** (the right conditioning set, because that is the function whose EV
we are explaining), then `k` determinizations consistent with it × `m` rollouts
each under the same deterministic policy on both seats, giving
`EV_ceiling = 1 − Var_within/Var_total` **on the same positions** as the critic's
own EV — apples to apples rather than across two samples. Both irreducible
sources vary: engine chance AND hidden information.
**Why it is a GATE.** If the ceiling comes back near 0.6, then the critic is
DONE, no leaf evaluator can be much better, **search cannot be rescued by a
better value function**, and every remaining lever belongs on the POLICY — which
would re-rank this entire file, and in particular would make **4.9** a bad place
to spend a fleet. If it comes back near 0.9, the critic is the bottleneck, 4.9
and §8.2 are the right targets, and the depth nulls are an evaluator problem
after all. **Run it before committing a fleet to 4.9.** It is not a win rate and
not a claim about the ladder: it is a property of the FORMAT, measured through
our own encoder and policy.

**2.12 WEIGHT-SPACE AVERAGING of each lane's last rungs — free, post-hoc, never
tried (added 2026-09-18; promoted out of 4.8's "open, cheap, post-fleet" list
because it needs no fleet and no new members).** Average the parameters of the
final N checkpoints of a single lane and evaluate the average as a member (or as
the object). Zero training cost, zero inference cost — unlike 4.8, which pays
one forward per member. It is the standard post-hoc antidote to end-of-anneal
noise, and [RWL-4] named it and never ran it. **Read:** same locked protocol, on
one lane first; if a lane's average beats that lane's final, re-form the
committee out of averages and re-measure off FP@20 with a same-session anchor.
**Caveat that decides the design:** averaging across INDEPENDENTLY trained lanes
is not licensed (no shared basin, and permutation symmetry makes the average
meaningless) — this is **within-lane, across-rungs** only, and it composes with
4.8 rather than competing with it.

**BUILT AND SCOPED 2026-09-19 (`scripts/weight_average.py`).** Three averaged
checkpoints exist (`avg_last5.pt` on each W lane, sha-stamped, loading verified).
Two things were measured before spending an eval, and they pull in OPPOSITE
directions — which is why this row is **NOT closed**.

**(1) WHERE THE AVERAGE LANDS.** `‖avg_N − final‖ / ‖first_N − final‖ = 0.35` at
EVERY window size from 5 to 80 checkpoints, in BOTH lanes measured:

| window | span | ‖avg−final‖ | ‖first−final‖ | ratio |
|---|---|---|---|---|
| 5 | 198–200M | 0.0022 | 0.0062 | 0.36 |
| 20 | 190.5–200M | 0.0178 | 0.0514 | 0.35 |
| 80 | 160.5–200M | 0.1046 | 0.2846 | 0.37 |

**Averaging moves you about a third of the way back along the path.** And §29
measured that the last quarter of training is where **3–6 points of win rate are
made**, so moving backward along the tail has a real, measured cost.

**(2) IS THERE NOISE TO CANCEL?** `cos(d_i, d_{i+1})` of consecutive
displacements is **−0.046 to −0.073, stable at every stage of training** (last
10 checkpoints, 40-back, 100-back, 300-back) and reproduced across lanes. With
~1M parameters pure noise sits within ±0.001, so this is systematic. It is **NOT
a drift** (that would be positive) and not a strong oscillation either: the
trajectory is a near-orthogonal random walk with a slight restoring tendency.
**So there IS noise for an average to cancel** — the usual precondition for SWA
holds.

**THE TWO READINGS DISAGREE, AND THAT IS THE ANSWER: RUN THE EVAL.** Noise to
cancel argues for it; a third of the way back down a measurably productive tail
argues against. Neither dominates on paper, and the eval is one hour — a
committee of the three averages against the committee of the three finals, off
FP@20 with a same-session anchor. **Do not close this row on the geometry
alone.**

**One artifact hazard, recorded in the file itself:** `PPOAgent.load_state_dict`
indexes `state["optimizer"]["state"]` unconditionally, so the optimizer cannot be
dropped or the checkpoint will not load — the first draft did drop it and only a
load test caught it. It is therefore carried **verbatim from the last
checkpoint** and does NOT correspond to the averaged weights. The file is marked
`weight_averaged.eval_only` at the top level: **evaluate from it, never resume
from it.**

**2.13 RECALIBRATE THE LEAF VALUE — FREE, MEASURED AT +0.0195 EV, and it is not
inert (added 2026-09-18 from RESULTS §27.1).** An out-of-sample **isotonic**
recalibration of the critic's output moves EV from **0.2176 to 0.2371** on the
§27 positions. That is the whole calibration prize — a monotone map is the best
any rescaling can do — and it costs one fitted curve and no training.
**WHY IT IS NOT INERT INSIDE THE SEARCH,** which is the objection to expect: a
monotone map cannot reorder leaves at one node, but `matrix.py`'s `row_ev`
**averages** leaf values across the opponent's column distribution, and averages
of a non-linearly transformed quantity reorder; and the D5 margin gate is a
THRESHOLD on that same scale, so recalibrating changes the override rate and the
delta must be re-swept with it (the standing rule — match on the realized rate,
never on the knob).
**The fit itself:** `oracle ≈ −0.0348 + 0.8334 × critic` affinely (affine buys
+0.0107; the rest of the +0.0195 is the S-shape in the deciles). **Carry the
fit with the checkpoint** — it is a property of THAT critic, not of the format,
and a recalibration fitted on one checkpoint applied to another is a new
untested object.
**WIRED 2026-09-19** (`SearchAgent(calibration=...)`, default None and
bit-identical when unset; `calib/leaves` and `calib/mean_shift` reach the arm's
JSON, so a calibration that silently failed to load is distinguishable from one
that was never asked for).

**THE TENSION THIS ROW HAS TO ANSWER BEFORE IT GETS AN ARM, and it is not
rhetorical.** The +0.0195 is an **EXPLAINED-VARIANCE** gain, and this project
has now measured THREE TIMES that EV does not track strength: §21 (2.67× critic
width and 126× rank bought ZERO EV while the win rate moved), §27.1 (88% of the
critic's gap to the ceiling is ranking, which no rescaling touches), and §29 (EV
moves in the OPPOSITE direction to the win rate in 9 lanes of 9). **A lever
justified by EV is a lever justified by the one quantity measured not to
matter.**

**Why it may still pay, and the channel is different.** Those three are about
TRAINING — a better value fit does not make a better policy. 2.13 is about
SEARCH: `row_ev` takes an EXPECTATION over leaf values, so a monotone map
reorders rows (3.5% of pairs) and the D5 gate is a threshold on the same scale.
The claim is "the search picks a different action", not "the critic fits
better". **That is a real distinction and it is also an untested one.**

**So the arm must read the ACTION, not the fit.** Cheapest form: run the
calibrated and raw selectors on the SAME decisions offline and report how often
the chosen action differs and in which direction — a per-decision quantity with
thousands of samples, exactly the trick that made the 8.6 screen cheap. **If the
action almost never changes, this row is inert in practice whatever its EV, and
it should be closed without a fleet-grade arm.**

**What it does NOT do:** close the gap. It is 12% of it; the other 88% is
ranking (§27.1), which is 4.9's and 4.1's territory.

**2.14 BREAK THE DETERMINISTIC-POLICY LOOP — a MEASURED BUG with a BUILT fix,
waiting on one ruling (added 2026-09-18; RESULTS §28).** **103 of the 104 capped battles in the repo
were enumerated** (the claim first rested on six; see §28's correction box).
**100 of the 103 are a switch loop** — ~900–990 switches, ~100% strictly
alternating between two slots — and in **94 (91.3%)** the opponent is immobilised
on ≥80% of turns, usually one Pokémon **frozen solid**, while a deterministic
argmax oscillates instead of attacking it, until the 1000-turn cap makes it a tie
that the locked protocol counts as a NON-WIN. **It is a thrown-away win against a helpless opponent.**
**BUILT:** `rl/common/loop_breaker.py` (13 tests) takes the next-best legal
action on the fourth identical (observation, action) pair in a battle, escalating
a rank per escape so a cycle of any period unwinds. It stays **deterministic** —
a function of the episode's history, so a replay plays the same moves — and a
test pins that it **cannot change a single non-looping battle**.
**WIRED NOWHERE, AND THE RULING IS WHY:** it changes the POLICY FORM and the
locked protocol names the policy. **Worth:** up to +0.011 on the worst banked arm
and ~+0.0014 typically — small, free, and it removes a behaviour that is simply
wrong. **It is also a LADDER RISK:** R5 never hit it (max 121 turns, 0 ties)
because humans do not freeze-lock and then sit, but a 1000-turn rated game would
be ugly and R6 is unruled.

## 3. Ruled out / answered — do not re-propose

**How to read this section (maintainer ruling, 2026-09-06).** Two verdicts
live here and they are NOT interchangeable. A **mechanism-bounded** kill
measured the effect's ceiling — shaping's algebraic inertness, the
hidden-team EV bound, the best-responder's exploitability read — and is
final. A **dose-limited null** is an A/B at a dose whose se cannot exclude
an advisory-scale effect (§1: at k=3–5 unpaired, bars run 0.065–0.10, so
+0.02..0.05 lands in the recording band); it closes nothing at 100M+ on a
changed recipe. The asymmetry is visible in our own ledger: the LR anneal
credited at 12M ONLY because it was +0.0998 on the headline (0.6185 →
0.7183, RESULTS §9, aux+anneal stack disclaimer), while anything in the
advisory band at that dose reads as a null whatever the truth is. So every
entry here names the dose that produced it, and where a kill rests on both
legs it says which leg is load-bearing. Vacating a dose-limited null needs
no ruling; vacating a mechanism-bounded kill does.

**STATUS CHANGES, 2026-09-06 — an index, not a second home.** Each item below
lives in exactly ONE place; §3 keeps the evidence and points forward. Nothing
here is "unkilled" wholesale.

| §3 entry | what changed | live item |
|---|---|---|
| privileged critic | 12M A/B is dose-limited; information leg still binds | **4.7** |
| width / capacity | **ANSWERED 2026-09-17 (RESULTS §21)** — width is USED (srank99 632/1024), and it buys ZERO explained variance | stays here, both halves |
| PFSP / exploiters | 6M leg thin, transitivity leg carries it; league ruling moots it | stays here |
| paired eval via server seed | unchanged, and it is the CRN reconciliation point (§1) | stays here |
| D19 aux team head | final for GEN 1 only — format fact, not measured effect | open at gen 4 |
| shaping / chaining / survivor bonus | nothing changed | stay here |

Two kills with no §3 entry also moved: the **attention trunk** (killed on a
throughput microbenchmark — §5) and **MPS/GPU for the update** (killed at a
~2.5% whole-loop prize measured while collection dominated — **2.8**). And one
never-killed item is repriced by the collector plan: **4.3** (see its own note).

- **KO / status / HP-differential potential shaping.** [MECHANISM-BOUNDED —
  final: an algebraic identity, and potential-based shaping is
  policy-invariant by construction.] Inert by algebra:
  Φ = 0.6·(obs[2]−obs[1]) exactly (SESSION_LOGS :803), linear in emitted
  features. Measured null: Δ −0.0004, se 0.0074 (z −0.06) over 9,000
  battles; the 639,409-episode figure is the *invariance gate* (returns
  stayed {−1,0,+1}), not the null read. Standing rule binds: state your
  potential and show it is not already obs-representable.
- **Chaining runs off finished checkpoints.** [MECHANISM-BOUNDED — final:
  a fact about the schedule, not a measured effect.] lr_anneal ends at ≈0 (the
  pre-reg cycle barred own-run 50M rungs at "507.8× lr"); re-heating *is*
  the N-ANNEAL confound the 100M header names as the leading alternative;
  dormancy makes a collapsed representation a bad restart point.
- **Survivor bonus on a win.** [DOMAIN ARGUMENT, never measured — the ±1.6
  uncancelled span is arithmetic, the "sacrifice a mon to absorb sleep"
  reading is gen-1 domain knowledge. Not a dose-limited null; not a
  measurement either.] The docstring argument at
  `rl/envs/showdown.py:740-745` is the ruling: uncancelled shaping spans
  ±1.6 and a sweeping 48%-win policy outscores a trading 50%-win one; in
  gen1, sacrificing a mon to absorb sleep is correct play. (Citation note:
  this lives in code, not in a named record entry.)
- **Paired eval via server battle seed — ANSWERED 2026-09-01, feasible,
  small prize, don't build now.** [MECHANISM-BOUNDED — final, and it is the
  reconciliation point for the engine plan's CRN framing (§1): the engine
  makes CRN *exact* but cannot make the shared-variance share larger.] `RoomBattleOptions.seed` exists
  (`showdown/server/room-battle.ts:490`, passed at :575); only the wire path
  from the challenge command is missing (patch precedent: the timer knob;
  ps-ppo's rlspawn.ts). But CRN shares only the team draw + pre-divergence
  rolls, and the team-luck share of outcome variance is small (P3 R² 0.0375
  lower-bound). It cannot touch σ_seed. Revisit only if 2.1 finds real
  overdispersion traceable to team draws. Patch would live in
  `scripts/patches/` (server is gitignored).
- **Width/capacity scaling — ANSWERED 2026-09-17, and the answer has TWO HALVES
  that point opposite ways. Record both or neither.** [NO LONGER CONTINGENT. The
  contingency below was discharged by the monster fleet's mechanism co-primary,
  RESULTS §21 / `readouts/MECH200M_READOUT.md`.]
  **Half one — the IDLENESS kill is VACATED.** A 1024-wide critic carries
  **srank99 632, 0.617 of its width**, through its first layer, against **5 of
  384** on the 100M baseline and 26.7/384 on L2LAM — 126× the rank, and the
  delta is eight times the across-lane spread. Capacity at 1024 is *used*, not
  idle, and **L2-toward-init does not prevent the 384-wide collapse: width
  does.** "A wider critic would just sit idle" is measured false and may not be
  re-quoted.
  **Half two — the NEW bound is EXPLAINED VARIANCE, and it is flat.** EV did
  not move: **0.5881 (W, 1024-wide, 200M) against 0.5919** on the 100M lanes
  (across-lane sd 0.0006 / 0.0014), like-for-like at gae_lambda < 1. **2.67×
  width and 126× first-layer rank buy ZERO explained variance at the horizon.**
  The win rate did move, so the recipe is credited (+0.033 vs SH at 5.59 se,
  +0.046 off FP@20 at 4.79 se) — **but for the RECIPE AS SHIPPED, never for
  width as a separable lever**, because no contrast isolates it.
  **What this licenses and what it does not.** Licensed: a further width step is
  a legitimate proposal on changed evidence, and it must be pre-registered with a
  mechanism co-primary that is NOT explained variance. Barred: **sizing the next
  fleet on EV** (RESULTS §21 bars this by name); "the wide critic is worth
  +0.033"; "a wider critic fits the value function better" (measured false). And
  note what bounds the prize — at the COMMITTEE level the 200M recipe misses the
  floor over the 100M committee (+0.015 at 2.01 se): **the recipe gain and 4.8's
  committee gain substantially SUBSTITUTE rather than add.**
  *The original entry, kept because the ledger argument it rests on is still
  live:* the ledger argues directly against: the
  biggest credited win came at *reduced* params (626,059 actor under the
  681,994 K2 ceiling, +0.1513); H&L reached 72% GXE at 1.33M; measured
  idleness (D22: dormant 27→84–88% on s35/s36, critic ctx srank99 7–11/384;
  search-era lanes ~47/384). CNN is a category error (`rl/networks/conv.py`
  is MinAtar's DQN net).
- **PFSP / league exploiters** (AlphaStar's league — main agents on
  prioritized fictitious self-play, main exploiters, league exploiters;
  Vinyals et al. 2019, verified against the paper text 2026-09-04, not in
  `docs/prior_work/README.md`). **ANSWERED BY MEASUREMENT — not banned, not
  motivated.** A league fixes exploitability and cycling; three reads say
  neither is what limits us. [Mixed legs: (i) is a 6M best-responder, which is
  dose-limited on its own; (ii)'s transitivity fit (14 arms, ~30,000 battles)
  is the load-bearing leg and is not dose-limited. Also moot for gen 1 by the
  2026-09-06 ruling that league play stays on and is not ablated.] (i) D22
  read 5 (2026-08-11): a fresh 6M-step
  best-responder trained against the frozen struct50m final pooled
  **0.4765 ± 0.0112** (two orientations, 1000 each) against the 0.55 line,
  plateaued by ~1M and never reached parity; entropy 0.21–0.32. The routing
  sentence stands verbatim — "the plateau is a REPRESENTATION/CRITIC
  ceiling ... not an exploitability ceiling" — and RESULTS §4 records it as
  "why opponent-sampling work was never run". (ii) The board is
  transitive: memo B of the 2026-08-25/26 design cycle fit Bradley–Terry
  through the SH hub to every banked h2h — transitive to ±0.03 except the
  clone — and CH4 R1 (fresh same-session hub, 14 arms, ~30,000 battles)
  dissolved the clone exception into a policy-form mismatch (rho +0.005 ±
  0.013; "the board is transitive when like is compared with like"). No
  cycles for a league to cover. (iii) The pool: the predecessor's sp6m pool
  (2026-08-01, recovered record) measured strength-homogeneous
  (winrate_latest 0.4986–0.5013), "killing latest_prob/PFSP retuning at
  this rung by measurement"; every credited result since rode the
  production pool (20 snapshots, latest_prob 0.8 — OpenAI Five's 80/20).
  `pfsp_power` and `fixed_mix` were stripped 2026-08-29 (commit 4e5f5cf,
  docs/CLEANUP.md's strip list) as UNREACHABLE killed levers — `select()`
  byte-identical on the seeded stream; no run config on this disk (178
  runs) ever carried either key; `fixed_mix 0.05` ran only in the
  predecessor's Phase 4 (coverage by construction, zero strength gain,
  worse forgetting proxies). Purity is not the bar: an RL exploiter is
  in-family (MU-5, 2026-08-26) and the X-PROBE was declined as unneeded,
  not as impure. **Re-open only on** (a) a best-response probe against the
  CURRENT best object reaching parity — ~3.6 h end to end, the probe
  `docs/research_reports/CONSOLIDATED.md` §5 names as the step-8 gate —
  or (b) the cross-play forgetting read (CONSOLIDATED §4.1.ii) firing.
  Without one of those, "add PFSP / exploiters" re-proposes a measured null.
- **Auxiliary opponent-TEAM prediction (D19) — KILLED AT ZERO LANES.**
  [MECHANISM-BOUNDED — final FOR GEN 1, and the bound is a format fact, not a
  measured effect: 88–90% of gen-1 randbats team structure is a deterministic
  cap MASK (closed form over what is already revealed) and the belief residual
  is 0.024–0.034 nats of 4.955. It shares its bound with the privileged critic
  (§4.7).] **Does NOT transfer:** the cap-mask argument is a property of the
  gen-1 randbats generator. Gen 4's generator has not been re-derived, and gens
  5+ have team preview, which removes the hidden-team problem outright — so
  "belief over the opponent's team" is an open question at gen 4 and would need
  its own read before anyone cites D19 there. Record: RESULTS §4.
- **Pool-vs-latest-only ablation — NOT WANTED (maintainer, 2026-09-06).**
  League play STAYS ON in gen 1 — `pool_size: 20`, `latest_prob: 0.8`,
  `push_every_updates: 5`, in all 30 gen-1 configs — because the published
  field supports it; the maintainer declines to spend a fleet re-deriving
  that. `pool_size: 1` exists in exactly two files (`configs/gen4_wang50m.
  yaml` and its smoke) and ONLY as fidelity to Wang's naive latest-vs-latest
  arm: it is not an ablation arm, and no pool-on counterfactual is owed at
  gen 4 or anywhere else. Distinct from the PFSP entry above (that one is
  about prioritized sampling + exploiters, which we do not run).
- **Asymmetric / privileged critic. RUN AND KILLED AT 12M — D18 (2026-08-12);
  the KILL'S FINALITY IS VACATED (maintainer, 2026-09-06) and the live item
  is 4.7. The A/B leg below is dose-limited; the INFORMATION leg is the
  mechanism-bounded one and still binds. Evidence, unchanged:
  12M × 5 seeds, pooled 0.5364 vs 0.5509 (Δ −0.0145, clustered se 0.0221,
  z −0.65); its own falsifier fired (EV rose on every lane, win rate did
  not); the 2026-08-16 post-hoc implementation audit found zero defects —
  "do not re-run a 'corrected' D18: there is no correction to make."** It
  was the SOUND form — V(actor-obs ‖ privileged), Baisero & Amato 2022's
  unbiased construction, not the privileged-only V(s) the theory warns
  against — so "wrong form" is pre-empted; Lyu et al.'s centralized-critic
  variance critique is the recorded residual, and a λ=1 pure-baseline
  variant was judged not worth a lane. The magnitude, measured: handed the
  ENTIRE hidden team the critic gained **~+0.045 EV** of return variance
  against the hoped-for ~0.40; the rest is aleatoric (crits, rolls, 1/256
  miss, sampled opponent actions), which no privileged state explains.
  Corroborated by D19's closeout: 88–90% of the hidden team is a
  deterministic cap mask, belief residual 0.024–0.034 nats of 4.955. The
  only critic-side item still open is 2.3 (own-move routing), which is not
  privileged information. Provenance for outside advisories: the
  privileged value function in the literature is AlphaStar's ("during
  training only, the value function is estimated using information from
  both the player's and the opponent's perspectives"; Methods: "we also
  use the opponent's observations as input to the value functions") —
  OpenAI Five's is not (its value head is a projection of the same LSTM
  state as the policy, Berner et al. 2019 §3.1; §7 #17).

- **Migrating the learner to a library (Stable-Baselines3) — ANSWERED
  2026-09-08, verdict NEITHER; do not re-propose.** [MECHANISM-BOUNDED for the
  MIGRATION question only — the portable wins are live as **2.9** and the §5
  shared-trunk row, and are NOT closed.] Full audit:
  `docs/research_reports/PPO_VS_SB3_UPDATE_AUDIT.md`. SB3's PPO has exactly ONE
  update-path optimization we lack — `target_kl` early epoch termination
  (`stable_baselines3/ppo/ppo.py:261-270`, the break placed before
  backward/step) — it is `Optional[float] = None`, OFF BY DEFAULT in SB3 too,
  and our measured KL says it would never fire: `loss/approx_kl` over 1,761
  updates of `gen4_wang50m_s200` is **p50 0.00086, max 0.00228** against a
  trigger of 1.5·target_kl at a sane 0.01–0.03 — it would need 4× the all-time
  max (the logged value is the mean over 273 minibatches while SB3 tests
  per-minibatch, so the last epoch runs higher; nothing logs the per-minibatch
  max today). We already do three of the four ANTICIPATED wins BETTER than SB3:
  one-shot buffer→tensor conversion (`ppo.py:1012-1017`) vs a fresh `th.tensor`
  copy per minibatch (`common/buffers.py:480-493` + `:124-136`);
  allocation-free `explained_variance` (the residual IS `flat_advantages`,
  `ppo.py:1231-1240`) vs `np.var(y_true - y_pred)`; vectorized episode GAE (the
  F-10 `(Lmax, E)` layout, `rl/buffers/episode.py:139-194`). The fourth,
  `zero_grad(set_to_none=True)`, is torch 2.13's default for both. **The local
  clone is a dead end as a source:** Wang's fork at `version.txt` 2.0.0, and
  `git diff v2.0.0 HEAD` is 40 insertions / 12 deletions of TIMERS AND LOGGING
  across 5 files with `common/buffers.py` UNTOUCHED — algorithmically stock,
  ~9 minor versions behind the tags present locally, and `sb3-contrib`
  (MaskablePPO) is not cloned anywhere. **What a migration would cost:** SB3's
  PPO has NO action masking (our harness contract — `-1e8` sentinel, no
  `mask is None` branches, masking at eval too); `RolloutBuffer`'s fixed
  `(buffer_size, n_envs)` shape with its `assert self.full` cannot hold the
  both-seat harvest (seat-2 rows carry the pool member's OWN log-prob); plus
  per-episode GAE, the league pool, the resume/`meta.yaml`/history toolchain,
  and ZERO overlap with our locked metric names — a rename shim on day one,
  forever. **What SB3's design does suggest** is not code we would inherit:
  `share_features_extractor` (`common/policies.py:693`), i.e. the shared trunk,
  which is the §5 row.


## 4. Tier 1 — training levers (each its own pre-reg; step 8 unless pulled forward; 50M async recipe, ~1 day/fleet at 574 steps/s/lane)

Ranked. Build 2.2 first — at k=3 unpaired, only an R2-sized effect credits
(§1), so every arm below should either pair seeds or pre-commit a
mechanism co-primary (D23 lesson).

**AMENDED 2026-09-18 — the maintainer put 4.9 (expert iteration) at the TOP of
§4**, ahead of everything below, and gated the whole section on 2.11 (the luck
ceiling) reading first. The 2026-09-06 order stands for items 1–6 underneath it.
The maintainer's own stack rank across §2/§4/§8 that evening: **4.9 → 2.10 →
§8.5 → 2.11 (as a gate on all of it) → 2.12 → 4.8's members 4–6.**

**RANKED ORDER — 2026-09-06. Q45 CLOSED** (the maintainer delegated the
re-rank: "just do what you recommend"). Principle: cost-adjusted expected
credit under the **k=8** bar (§1), with built / zero-build items first, then
the one measured monotone effect, then hypotheses ordered by whether their
mechanism instruments already exist. **Everything here is downstream of
JOURNEY 7.5** — run these before the collector switch and they face the same
≈0.10 bar that already swallowed two of them.

1. **4.1 both-seat harvest.** Built, tested, live in gen 4, zero build cost;
   a ~2× sample-efficiency change — a dose multiplier, not a hypothesis. One
   arm to validate it (seat-2 rows are version-lagged ≤ 2 and do change the
   data distribution), then it stays on for good.
2. **4.5 more steps.** The only measured monotone curve we own (SS-CLIMB), and
   7.5 takes 250M from ≈124 h to ≈30 h a lane. Composes with 4.1's doubling.
   N-ANNEAL stays NAMED; fresh full-horizon only, never a warm start.
3. **4.3 regenerative L2.** Built (14 tests), +0.0451 already measured above
   the k=8 shared-control bar, mechanism co-primary that reads independent of
   the bar, and it decides whether §3's width kill stays factual.
4. **4.7 privileged critic at scale.** Maintainer-directed and cheap on the
   engine path (plan §8.4), but its information leg is bounded, so the live
   channel is variance reduction — real, second-order. After 4.3: it wants the
   same srank / dormancy instruments.
5. **4.2 gae_lambda 0.75.** One key, but the gen-4 run will already have said
   something about λ at T≈100 and R2's large updates bought much of the same
   averaging. Rides as the second arm of a paired fleet; it does not own one.
6. **4.4 H&L 5-term shaping.** Unchanged: LAST, gated on 4.1 / 4.3 / 4.5
   reading null.

Deliberately NOT in the order: **4.6** (C6) is a SCHEDULING item — it
invalidates comparability, so it lands last before step 10 or inside the
step-8 back-port, per its own entry. **2.8** (GPU for the update) is
infrastructure measured after 7.5, not a lever. The **attention win-rate arm**
(§5) enters at rank 3½ if and only if the free re-benchmark returns a
tolerable ratio.

**FIRST DIRECT EVIDENCE, 2026-09-18 (RESULTS §27.1): the critic is OPTIMISTIC
ABOUT ITS OWN SEAT by +0.0416, z = 2.74** — measured in self-play with one policy
on both seats, where the truth is EXACTLY zero (realized mean outcome −0.0006
over 22,358 rollouts), so there is no sampling argument to hide behind. The
collector runs `learner_seat: p1`, so the critic has only ever been fit from one
side of a symmetric game. The bias is **2.6× larger in the opening** (+0.0672 at
turns 2–8 against +0.0257 at 23+), i.e. worst exactly where the game is still
open. **This row has until now rested on a sample-efficiency argument — a dose
multiplier, not a hypothesis. It now also has a measured DEFECT to fix**, and a
falsifier that costs nothing: re-run `scripts/critic_calibration.py` on a
both-seat checkpoint and the bias should fall toward zero.

**4.1 Both-seat harvest — the repo's licensed A2 (CHAPTER5 §3, licensed
2026-08-26; do not confuse with docs/CLEANUP.md's audit item "A2"). STRONGEST.**
**BUILT 2026-09-05 (commit 66746dc, `selfplay.harvest_both_seats`,
`rl/selfplay/harvest.py`) for the gen-4 Wang-recipe baseline — and built
DIFFERENTLY from the sketch below: EVERY seat-2 row is harvested (no
"latest-only" filter) with the acting MEMBER's own log-prob recorded and the
member's push id carried as `version`, so staleness is a logged metric
(`harvest/version_lag_max`) rather than a filter; at the gen-4 recipe
(pool_size 1 / latest_prob 1.0 / push_every 1) the member IS the learner and
the lag is 0–1. On the SYNC path only (the async collector refuses it). As a
GEN-1 LEVER it remains UNRUN and un-credited: a gen-1 pre-reg would pair it
with the pool (latest_prob 0.8 / push_every 5) exactly as sketched, and the
filter question below becomes that pre-reg's first design decision.**
Seat 2's trajectory WAS discarded (`discard_seat2_obs=True` in `ShowdownEnv`;
`discard_seat2_obs=True`); in the async collector the opponent is a
listening Player that already encodes its own obs to move. Harvest = ~2×
episodes/update (~959 → ~1,700 at the 80% rule below) at zero extra
simulation and — unlike R2 — **without** reducing update count. Precedent is
as strong as this lane has: H&L, the only verified pure-self-play randbats
success, consumes both seats (Algorithm 1's "2m matches"; verified to the
line in docs/prior_work/README.md), with exactly return-balanced batches — one
winner + one loser per battle — which matters at γ=1 terminal-only. The
recorded blocker (2026-08-08 advisory: "seat 2 is ALWAYS a frozen snapshot
... needs behavioral-logp storage") has a clean answer: harvest only rows
where the drawn opponent is the *latest* snapshot (latest_prob 0.8,
push_every_updates 5 — `pool.py:185-192`), store that snapshot's own logp as
behaviour logp; ≤5-update staleness is the same order as seat 1's own
within-collection staleness, which PPO's ratio already absorbs. Drop the 20%
historical rows. Honesty: returns are exactly anticorrelated within a battle
and gradients cluster by battle → effective n < 2×; H&L is existence proof,
never a target (their m=7680 is self-described as "completely arbitrary").
Cost: logp capture in `pool.py:83-88` `move()`, a seat-2 episode builder,
reward mirroring, D-C-style gates (illegal/collision exactly 0 on seat-2
rows), a discard-rate metric, tests — then a fleet.

**READ 4.10 FIRST (added 2026-09-18).** The effective horizon at λ=0.75 is
**4 turns** in a battle averaging 29.5, and §27.1 measures the critic as blind
exactly where a short horizon makes it blinder. This row may still be right for
variance reasons, but it moves the dial the way the opening-blindness evidence
argues AGAINST, and it should not run without that stated.

**4.2 gae_lambda 0.75 — RUN IT, with corrected evidence.** λ=0.95 is
universal (39 configs) and was explicitly HELD at R2's GO/NO-GO
(`showdown_sp_batch50m.yaml:208`, "Q4"); the 2026-08-08 advisory verified
ps-ppo's ladder-era checkout `7fb522c` (the 2102-Elo system) at λ 0.75 FLAT
+ steps_per_update 32,768; the λ arm was slotted at branch (d), mooted when
structure credited, re-homed into D21, and swept 2026-08-16 — never run.
Pro-mechanism: D18 says the outcome residual is largely aleatoric (entire
hidden team worth +0.045 EV) and the value head is calibrated (Z1
reliability 0.0117) — λ<1 filters luck the actor can't condition on.
**Corrections the source doc needs:** (i) the external field is split, not
convergent — ps-ppo 0.75 and Wang 0.754 sit against **VGC-Bench at γ1.0/λ0.95
(our exact values)** and H&L at λ0.9/γ0.95; (ii) every λ<0.95 system pairs
it with dense-ish reward (ps-ppo faint ±0.1; H&L 5-term) — at our pure
terminal ±1, γ=1, ep len ~32, λ=0.75 gives actions >8 steps from the end
almost no direct outcome signal (0.75¹⁰ ≈ 0.06): the terminal reaches them
only through the value chain, and the value target itself becomes more
bootstrapped (`ppo.py:944`, targets = advantages + values) — two-sided,
given the critic is the diagnosed weak component (D22); (iii) R2's 30,720-
step updates already bought a large slice of the same aleatoric-noise
averaging — the advisory priced λ when updates were ~34 episodes, so the
marginal prize is smaller now (the source doc applies exactly this discount
to shaping but not to λ). Design: one arm, λ=0.75 verbatim, batch50m_async
recipe, 3 seeds (paired via 2.2 if landed; else the async acceptance fleet
66/75/83 is the free control), early kill-watch on value EV / entropy,
manipulation check on loss/adv_std (λ moves it mechanically — the
recipe12m header shows the gate pattern). A null closes the axis cheaply; a
negative with a slow-value signature names λ+faint-shaping (ps-ppo's actual
pair) as the follow-up pre-reg — never a bundle (recipe12m header, factorial
hazard).

**4.3 Regenerative-L2 at 50M — NEW (the source doc missed it).**
D23 (12M): "LETTER-MET, SEED-FRAGILE, NOT CREDITED" — Δ +0.0451 ≥ the
0.025 letter with bar 0.065; mechanism strong (norm BOUND held, critic
srank99 31/53/36 vs control 11/17/16, final→peak gap shrink realized);
falsifier did not fire — "the regenerative family is neither killed nor
closed." The lever is BUILT (`l2_init_decay`, θ₀ capture, metrics, 14
tests; −3.2% throughput). The 50M carry was designed and came back **NO-GO
AS SCOPED** (2026-08-13) — but what changed since: chapter budget reset,
1.53× async speedup, and the carry's own design guidance stands
(mechanism-primary: norms + srank primary, win rate secondary). Conditions
to revisit: 100M S-SHAPE bending (plateau pressure) or dormancy/srank
reading collapsed on the 100M finals (probe is cheap, D22 instruments
exist — with the D24 float64-svdvals fix; srank99=1 is a NaN sentinel).
PokéAgent finalists' plasticity levers (Kron, AID) are the same family;
this repo's own lever has local evidence and zero build cost.
**Repriced 2026-09-06 (not re-ranked — §4's order is the maintainer's):** the
NO-GO-as-scoped was priced against a 3-seed fleet. Its measured **+0.0451**
sits above the k=8 shared-control bar (~0.044) and just under the k=8
two-fleet bar (~0.062), so on the collector path (§1, JOURNEY 7.5) this is the
one banked effect whose SIZE the instrument can newly resolve — and its
mechanism co-primary (norms + srank) reads independent of the bar either way.
It is also the read that decides whether the width kill in §3 stays factual:
if the regularizer restores srank at scale, "capacity is idle" stops being
true.

**4.4 H&L 5-term shaping on the entity trunk — LAST, gated.** Factual base
verified: `hl_shaping` non-zero in exactly three runs on disk (signal12m
s23/24/25), all `trunk: mlp`, and the +0.0135 n.s. read was a γ0.95+5-term
*bundle* (the repo's own header calls it "never tested on the entity
trunk"). But: R2 bought the variance half, 4 of 5 terms reward play we
already dominate the replay field on (domin% 0.6 vs humans' 2.7 — ladder-R1
replay audit, not a clone number), the aleatoric ceiling caps the
credit-assignment half, and the "~1 in 4" price is an agent-authored
licensed estimate, not a maintainer ruling. Run only if 4.1–4.3 null or
S-SHAPE says more-steps is dead. Shaping ALONE at γ=1 (no bundle, no anneal
variant — on an inert term annealing anneals nothing, per the source doc
itself). Zero code; one overnight at 12M is NOT readable (D23's comparator
finding) — this too is a 50M-recipe question now.

**4.5–4.6 appended 2026-09-04, UNRANKED.** The ordering of §4 is the
maintainer's (STATUS next-action 3); these rows sit at the end because they
were missing, not because they rank last.

**4.5 More steps — a longer full-horizon run (the row §1 promised; the
100M's own successor). Confound named in the row: N-ANNEAL.**
Trigger, met: S-SHAPE read **SS-CLIMB** — W_hi (pooled rungs 85/90/95/100M)
0.77764 vs W_lo (65/70/75/80M) 0.74839, **+0.02925 ≥ se_W 0.00633**, 4.6×
the threshold; pooled curve 0.652 (5M) → 0.724 (50M) → 0.758 (75M) → 0.792
(100M) vs-SH at n=9000/rung. MANDATORY SENTENCE: the treatment's sub-100M
rungs are on the 100M anneal and are NOT comparable to a finished run at
the same step (507.8× in lr at 50M). It moves no cell and licenses no
extension (RESULTS §18); the 2026-08-23 big-runs ruling's second re-trigger
("training logs still clearly climbing") is now met by measurement, and
that ruling still requires a maintainer decision plus a pre-reg. **What it
is:** a FRESH fleet from scratch at a new `total_steps` with
`lr_anneal_steps == total_steps` (the recipe's full-horizon-anneal
convention, R0-b; `train.py:407-413` refuses any anneal shorter than the
run — the anneal trap), one-diff against `configs/showdown_sp_100m.yaml` in
exactly {total_steps, lr_anneal_steps, seed, run_name} (its own R0-a
pattern), control = the 100M finals (frozen comparator; the E2 exemption
holds until the R4 readout lands). **What it is not:** a resume or a warm
start. §3's chaining bullet binds — the 100M lanes finished at lr 1.1e-7 /
7.8e-8 / 1.3e-7 (D-A, "ran to ~0 as constituted"); `--resume` rebuilds from
the run's own config and cannot move the horizon; `init_from` re-arms the
anneal (`begin_warm_start`) and is legal in code, but it is the N-ANNEAL
confound in its purest form and is barred for credit. **The confound:** a
2×-horizon run trains hotter at every matched step and integrates 2× the lr
(the 100M header's own words); on any positive read it is the leading
alternative mechanism, and it stays NAMED, NOT CELLED at any horizon,
because the separating arm (2H under an H anneal) is exactly what the
anneal-trap guard refuses — running it means a deliberate, pre-registered
schedule-prefix arm, not a config edit. S-ANNEAL at 100M already showed the
shape: the finished 50M control sat above the treatment at every matched
mid-run step (50M: 0.783 vs 0.724) and the treatment passed it only as its
own anneal completed. **Honest prior for the read:** the 100M itself landed
P3 at +0.02389 vs BAR 0.025 (se_gov 0.00774; P(credit | true +0.025) ≈ 0.47
at s_T 0.01086), and the finished-to-finished vs-SH gain from the last
doubling was +0.00944 (SN-N). Unless the next doubling's effect is LARGER
than the last, k=3 unpaired lands in P3 again — the pre-reg must pair seeds
(2.2) or pre-commit a descriptive read; §1 is the constraint, not the
anneal. Dose: horizon is dose-unmatched by construction (that IS the
lever); optimizer passes per datum matched in configuration, as the 100M
header states. **Cost at 200M** (≈ H&L's ~230M-in-our-currency diet,
CHAPTER5 §7.4's calibration): ~100 h fleet wall at the 100M's realized
557.5–562.8 steps/s/lane 3-wide, plus the 100M's post-fleet eval schedule
(~7.5–15 h) with S-SHAPE doubled (40 rungs × 3 lanes × n=3000, +2 h),
≈ 5 days end to end; rung retention ≈ 2 × 8.3 GB (E2). Over the 5 h line:
maintainer launches, agent babysits. JOURNEY: ≈ step 10 pulled forward, as
the 100M was (RESULTS §18) — off-arc without the same explicit order. Reads
to carry: S-SHAPE with disjoint windows, S-ANNEAL against the 100M curve,
D-A liveness, sigma_seed descriptive, the anchor battery.

**4.6 C6 — fixed-damage encoder fix (MAINTAINER C-item; CHAPTER5 §3,
whose verbatim home since 2026-08-31 is
`configs/showdown_sp_batch50m.yaml:554,624`; first-class, unrun, unruled —
it may not be dropped, deferred or merged away without a recorded
maintainer ruling). Sequenced LAST, and F-08 did not change that.**
The defect, re-verified live in the env 2026-09-04: poke-env's gen-1 data
gives `base_power == 1` for seismictoss, superfang, nightshade, dragonrage,
sonicboom, counter and psywave (the vendored gen1 mod sets `basePower: 1`
on all seven; base data has 0), and `_fill_move` writes
`move.base_power / 100.0` = 0.01 (`showdown.py:251`) beside Thunderbolt's
0.95; the v2 effect block has no fixed-damage field. In the gen-1 randbats
pool (`data.json`, 146 species) only four occur: Seismic Toss (26 species),
Counter (24), Night Shade (3), Super Fang (2) — Dragon Rage, Sonic Boom and
Psywave never do. The type multiplier is right for the immunity (Ghost
blocks Seismic Toss) and spurious for 2×/0.5×. **Measured behavioural
cost** (2026-08-26 replay sweep, ~175 ladder-R1 replays, guaranteed
holders only): Seismic Toss 22/156 = 0.141 for us vs 67/232 = 0.289 for
humans (z −3.39); Super Fang 0/59 vs 17/47 = 0.362 (z −5.04). ~1% of
decisions (156 + 59 opportunities over ~20k). Route-around correction, same
day: `move_emb` is a learned `nn.Embedding(166, 64)` in every move token,
so the block is misleading, not unrepresentable — the fork's expected
effect is smaller than the sweep implied. The sweep's second defect
(force-switch corpse blocks) measured INERT (0/42) and is not part of C6.
**Two shapes, both invalidate:** (a) constant-OBS_DIM semantic fix — an
effective power in the bp slot (level-scaled for Seismic Toss / Night
Shade; Super Fang and Counter are state-dependent and need a flag or a
live estimate) — same width, changed semantics: the ENCODER_V2-flag
precedent (`train.py:178`: a checkpoint is interpretable only with its
fingerprint), so it must be flagged and fingerprinted, and old checkpoints
see off-distribution values (the sweep's own warning about "fixing" defect
2); (b) a "variable-damage" bit — the gen4 design's choice
(`docs/design_gen4/encoder_requirements.md` §3.6: nine BP-0 damaging moves
get the bit) — an OBS_DIM change, which 2.7 can carry forward for a
deployment object. Either way the gen-1 tape hash gate changes by design
and is re-pinned at the new fingerprint. **Read:** not a credit candidate
at k=3 (~1% of decisions, partial route-around) — mechanism-primary (the
sweep's own statistic: Seismic Toss / Super Fang usage on guaranteed
holders, replay-measured), win rate secondary. **Sequencing:** LAST
(CHAPTER5 C6: "runs after R2 and before nothing") because it destroys the
baselines everything else is graded against; the seam did not change the
cost (§5). The gen4 chapter pays the invalidation anyway (CONSOLIDATED
§5), so the two honest homes are the step-3 rewrite's gen1 back-port (step
8) or the last gen1 training change before step 10. Cost: fork ~half a day
+ a full fleet.

**4.7 Privileged critic AT SCALE — RE-OPENED 2026-09-06 (maintainer). The
D18 kill's FINALITY is vacated; §3 keeps every number.** The ruling: an axis
is not closed by trivial old runs. D18 was 12M × 5 seeds on the pre-batch
recipe and its A/B leg (Δ −0.0145, clustered se 0.0221, z −0.65) cannot
exclude +0.02 — a dose-limited null, not a ceiling. **What the vacatur does
NOT touch:** the information leg. The ENTIRE hidden team was worth ~+0.045
EV of return variance against a hoped-for ~0.40, and D19 found 88–90% of it
recoverable as a deterministic cap mask (belief residual 0.024–0.034 nats of
4.955). So this is NOT "D18 with more steps" — that framing was audited
2026-08-16 (zero defects, "there is no correction to make") and the form was
already the sound one (V(actor-obs ‖ privileged), Baisero & Amato 2022).
**The live hypothesis is the channel D18 never measured:** a both-seat
critic as a VARIANCE REDUCER at large batch and long horizon. Lyu et al.'s
centralized-critic variance critique is the recorded residual, and the λ=1
pure-baseline variant was "judged not worth a lane" at 12M — at 100M+ with
the batch config it is worth a lane. **Design sketch (needs its own
pre-reg):** a fresh full-horizon 100M+ fleet, one diff against the current
recipe, seeds paired (2.2); MECHANISM CO-PRIMARY — value-loss and EV
trajectory plus critic srank against the control, win rate secondary
(§1: a win-rate primary at this bar is how D18 became unreadable);
D18's falsifier restated verbatim (EV rose on every lane, win rate did not)
and pre-committed as a NULL branch this time, never a kill. **Cost:** the
4.5-class expense (~100 h fleet wall + eval schedule), so it competes with
4.5 for the same slot and the two are inseparable if bundled — one or the
other, pre-registered. **JOURNEY:** step 10 territory, or step 8's
back-port; NOT gen 4. Step 4's held-back-lever list names the privileged
critic, which predates this ruling and reads as a gen-4 candidate — the
maintainer's scope here is a large gen-1-scale run with the batch changes,
so JOURNEY wants an amendment at the next maintainer pass.

**4.8 THE COMMITTEE — members as the lever (added 2026-09-12; the only free
lever this repo has CREDITED, and it had no row).** A masked log-prob ensemble
over the finals of separately trained lanes: **+0.0349 vs SH at 5.9 se**
(ENS3 of the 100M finals vs a same-session greedy re-draw, 2026-09-11) and
**+0.067 off FP@20 at 4.7 se** (ENS3F 0.557 and its fresh-pair replicate
0.577 vs a same-session greedy re-draw at 0.500, 2026-09-12), at greedy
speed, with every composition on top of it (depth-1 gate, ensemble-as-prior
search) a null on both axes. Members 4–6 measured with the 50M finals as
extra members (`configs/eval/ens_width*.yaml`): +0.010 at 1.8 se vs SH,
−0.014 ± 0.019 off FP@20 — unresolved with WEAKER members, and not saturation.
**Mechanism:** variance reduction over independently trained policies plus
disagreement where each member is off-distribution (the committee overrides
its first member 10.8% of decisions vs SH and 27.8% off FP). **Sequencing:**
every fleet's lanes are members; the ladder object is the best committee off
FP@20 (ENS3 of a trio / ENS6 / ENS9 with the 100M finals), floor = the 100M
ENS3. **Open, cheap, post-fleet:** equal-strength members 4–6 (the 200M
lanes answer it), weight-space averaging of each lane's last rungs as a
member, and the clustered se the credit still lacks (two 3-committees).
Never "ensembling helps" in general — the credit licenses THESE checkpoints.

**4.9 EXPERT ITERATION — train on the SEARCH's visit distribution (added
2026-09-18; the maintainer's TOP §4 item, and the highest-ceiling row this file
has). IN CHARTER: the expert is OUR OWN SEARCH, not external data.
DESIGN: `docs/proposals/EXPERT_ITERATION.md`.** AlphaZero's
actual loop, not "MCTS bolted on at inference": the search at state `s` returns
an improved distribution `π′ = N/ΣN` over root visits and a root value; the
network is then trained toward BOTH (cross-entropy to `π′`, value toward the
search-backed target) and the improved network makes the next search better.
Expert iteration in the Anthony/Tian sense; nothing about it requires a teacher.

**Why THIS lever, on OUR evidence.** The post-ladder week measured two defects
and this is the only proposal that attacks both at once:
0. **THE GAP IS A RANKING GAP, AND THAT IS WHY IT IS A TRAINING LEVER (RESULTS
   §27.1).** The critic sits at EV 0.2176 against a ceiling of 0.3630, and an
   out-of-sample isotonic recalibration — the best any rescaling can do — closes
   only **12%** of that. **The other 88% is the critic not knowing WHICH position
   is better**, which no post-hoc fix touches and which is exactly what a
   changed training signal addresses. And the failure is concentrated where this
   lever operates: r² **0.287** against the oracle at turns 2–8 versus **0.727**
   at 23+.
1. **Our critic is never trained on search-visited states.** PPO's value loss
   fits a baseline on the state distribution our OWN POLICY reaches; search
   deliberately visits the lines the policy does not play. §8.2 has said this
   since 2026-09-09 and nothing has ever trained for the second objective.
   RESULTS §24 sharpens it: our critic is the ROBUST evaluator (opening the gate
   costs it 0.006 against a hand-tuned heuristic's 0.088), so the material is
   good — it has simply never been ASKED the search's question.
2. **Our policy is never trained toward the search's improved distribution.**
   Measured 2026-09-11 and recorded in `configs/eval/tree_r5.yaml:36`: at a
   small budget **90.9% of root visits land on one action**, because the prior
   is sharp and nothing ever moves it. **Confirmed live 2026-09-18 (RESULTS §26):** the TV
   arm (a real tree, decide=visits, iters 100) changed the played action on
   **3.65% of decisions — 1.1 decisions per battle**, and read +0.014 at 0.64 se
   against an in-session greedy anchor. A tree whose visit distribution is
   nearly its own prior IS nearly the greedy policy, which is what every "search
   is a null" result has been measuring. A tree whose visit distribution is
   nearly its own prior cannot express an improvement, which is exactly why
   every visits-decided arm reads like greedy. Training on `π′` is the only
   mechanism that turns search compute into a POLICY change instead of an
   inference-time override.

**Why it is not the depth question again.** §22/§23/§24 measured *inference-time*
search on a FROZEN network — a one-shot override at 6–19% of decisions. Expert
iteration changes what the network IS. Search there is a training signal whose
value compounds over a fleet, and its failure mode (a bad expert teaching a bad
target) is different in kind from "the override didn't pay".

**What it needs, cheapest first.** (i) The search already computes per-action
statistics; `rl/search/tree.py` returns visits, and nothing persists them — log
`π′` and the root value on every searched decision. (ii) A policy loss term
toward `π′` on those states, and a value target from the search's root rather
than the raw return. (iii) The dose question that decides the price: searching
every decision is ~100× a greedy step, so the realistic shape is **search a
SAMPLED FRACTION of decisions** (or only the ones §8.5 flags) and train on
those, not all of them. **This is a FLEET item and needs its own pre-reg** with a
mechanism co-primary that is NOT explained variance (RESULTS §21 bars that).

**THE FREE FALSIFIER, and it comes with step (i).** If `π′` is ~the prior, the
cross-entropy term is a no-op with extra compute. **Measure KL(`π′` ‖ prior) and
the fraction of decisions where argmax `π′` ≠ argmax prior on BANKED arms before
any fleet.** If that KL is ~0 at an affordable budget, this lever is dead without
spending a day, and the right follow-up is the tree's BUDGET rather than the
loss. That makes step (i) worth doing even if the rest is never ratified.

**The gate, stated plainly: run 2.11 FIRST — DONE 2026-09-18, AND IT OPENS.**
RESULTS §27 puts the ceiling at 0.3630 against our critic's 0.2176 on the same
positions: **+0.145 of explainable variance is unclaimed, about 40% of what is
knowable**, so the kill branch does not fire. **And it points at exactly this
lever:** the critic holds 73% of the ceiling at turn 23 and **25% in the
opening**, i.e. it is short of signal about positions whose outcome is still
open — which is the regime search visits and what training on search-visited
states addresses. What remains gating this row is the FREE FALSIFIER above
(KL(`π′` ‖ prior) on banked arms), not the luck ceiling.

**Composes with:** 2.10 (a tree with an optimistic backup would teach the bug),
§8.5 (which decides WHERE to spend the search), 4.8 (members stay members), and
4.7 (a privileged critic is a better expert on exactly the hidden-information
lines search visits). **Never quote 8.4 beside it** — distillation from Foul
Play is a charter change and this is not.

**4.10 THE CREDIT-ASSIGNMENT HORIZON — why the critic is BLIND in the opening,
and why BOTH ENDS of the λ dial have already failed (added 2026-09-18 from
RESULTS §27.1 + §27).** This is a mechanism, not a hypothesis, and it explains a
measurement rather than predicting one.

**THE ARITHMETIC.** Gen-1's reward is **terminal only**, and the recipe runs
γ=1.0, λ=0.95. GAE weights the real outcome k steps ahead by (γλ)^k, so in a
battle averaging **29.5 turns**:

| k turns from the end | 5 | 10 | 20 | 24 | 29 |
|---|---|---|---|---|---|
| weight on the ACTUAL outcome | 0.77 | 0.60 | 0.36 | **0.29** | 0.23 |

**At turn 5 the value target takes 29% of its signal from what actually
happened and 71% from the critic's own downstream estimates** — and §27.1
measures those early estimates as the WORST the critic has (r² 0.287 against the
oracle at turns 2–8, against 0.727 at 23+). **The target is self-referential
exactly where the critic is weakest.** Effective horizon 1/(1−λ) = **20 turns**
against a 29.5-turn mean battle: the outcome signal does not reach the opening.

**AND BOTH ENDS OF THE DIAL ARE ALREADY TESTED, BOTH FAIL, FOR OPPOSITE REASONS
THE LUCK CEILING NOW EXPLAINS.**
* **λ = 1.0** (Monte-Carlo targets) is L2LAM, and it lost heavily — 0.4481 off
  FP@20 against W's 0.5417. §27 says why: **~64% of a mid-battle outcome is
  IRREDUCIBLE**, so an MC target is mostly noise, and the variance swamps the
  horizon it buys. **CAVEAT, and it matters: L2LAM bundled MC targets with a
  384-wide critic, so λ=1.0 is not cleanly isolated** — the fleet's own readout
  attributes the loss to the value TARGET, but the contrast is not clean.
* **λ = 0.95** is the incumbent and cannot reach turn 5, per the table above.
* **4.2 proposes λ = 0.75**, which moves the effective horizon to **4 turns** —
  the WRONG WAY on this evidence. That row should be read against this one before
  it ever runs.

**WHAT IS UNTESTED, cheapest first.**
1. **λ between 0.97 and 0.99** — horizons of 33 and 100 turns, cheap, never
   tried, and the only part of the dial neither end has ruled out. A screen can
   read the by-turn r² profile (`scripts/critic_calibration.py`) rather than a
   win rate, which is far better determined.
2. **A value target from the SEARCH ROOT** (IDEAS 4.9 item iii) — it sidesteps
   the tension entirely: the root value is lower-variance than an MC return and
   is not the critic's own early estimate, so it is neither noisy nor
   self-referential. **This is an independent argument for 4.9 that does not go
   through the policy at all.**
3. **A horizon-aware target** — e.g. MC for the last N turns where variance is
   low and the outcome is near, bootstrapped before that. Untried, and it is the
   shape the by-turn profile actually argues for.

**HOW WE WOULD KNOW, and it is free:** the read is the BY-TURN r² profile against
the rollout oracle, not a win rate. `scripts/critic_calibration.py` produces it
from any `outcome_variance` run, and a lever that works must lift the turn-2–8
bucket specifically. **Do not read this row as a win-rate lever until that
profile moves.**

## 5. Tier 2 — architecture (step 8 at the earliest; most of it folds into step 3)

- **Attention re-benchmark — DEFERRED POST-LADDER (maintainer, 2026-09-11); the
  live home is JOURNEY 11.6.** Still DO-able in minutes-to-an-hour with no training,
  and explicitly NOT run on 2026-09-11 so it could not tempt a third arm into the
  monster. Two updates to the pricing since the kill: the engine port took the
  update from 25% to 65% of wall, so a slow trunk costs MORE now; and the 34.6x was
  measured against the flat MLP, so the ratio against today's trunk is unknown.
  ARCHITECTURE EXPIRES AT A RUN'S LAUNCH — taking this rung means another training
  run, which is why it sits behind the ladder.
  [THROUGHPUT-PROXY kill — the weakest class on the list: no attention arm has
  ever been measured on WIN RATE here, at any dose. Industry-standard
  architecture killed on a speed microbenchmark against a different trunk.]
  The 34.6× kill was a CPU train-step microbenchmark vs the flat [512,512] MLP
  (2026-08-07, pre-entity-production); "attention-vs-entity_deepsets has
  NEVER been measured" (CHAPTER5:207). Re-run ARCH_SCREEN_SPEC's step
  against the current trunk; an honest ratio either re-opens or re-closes
  the rung with a live number. **The live item, 2026-09-06:** the re-benchmark
  is Tier-0 free work and settles only THROUGHPUT; if it clears, the actual
  question — attention vs entity-deepsets on WIN RATE, never measured here at
  any dose — is a §4-class fleet arm and needs its own pre-reg, mechanism
  co-primary, on the collector path where k=8 makes it readable.
- **DCN / two-tower explicit crossing — PARK for step 8.** The unbuilt
  middle rung (CROSS_FEATURES ladder). Only with a mechanism-read design;
  12M win-rate primaries are dead (§1).
- **Temporal context — FOLD INTO STEP 3, harder than the source doc says.**
  Both *validated* comparables are single-snapshot: the 2102-Elo ps-ppo is
  the `7fb522c`-era system (KV-cache/temporal is HEAD-only, no logs or
  checkpoints anywhere in its history), and H&L is single-snapshot +
  lastmove. It changes OBS_DIM — invalidating every checkpoint as a
  comparable object, the 100M finals included (they are the step-2 object:
  ladder R4 pins s112 at obs_dim 828, frozen until that readout lands). The
  gen4 encoder rewrite (JOURNEY step 3, Wang's one-hot duration counters,
  docs/prior_work/HISTORY_FEATURES_DESIGN.md) is where Markovianity gets
  redesigned for free — and it now has a landing zone:
  `docs/design_gen4/encoder_requirements.md` (2026-09-04) is designed
  against the landed F-08 seam. **F-08 did not change the cost above**
  (checked 2026-09-04): `rl/envs/encoder_spec.py` owns the per-gen tables
  and the intra-block offsets, its own docstring restates the landmine (a
  new field is an OBS_DIM change; every checkpoint invalidated), and
  OBS_DIM and the block strides are still derived at import in
  `showdown.py`, with `train.py` refusing a width mismatch. What the seam
  changed: the old→new slot map for 2.7 is now a function of two specs
  instead of hand-kept offsets. 2.7 can carry a checkpoint across the
  change as a DEPLOYMENT object; it cannot make the change free for credit
  (§3, chaining).
- **Width — SKIP** (§3, width/capacity bullet).

- **Shared actor/critic trunk — a PRE-REG item, ~20% of the epoch loop (added
  2026-09-08 from the SB3 audit).** Actor and critic are two INDEPENDENT
  DeepSets encoders (`rl/agents/ppo.py:513-515`), and the duplicated stage is
  **790,016 of the critic's 1,183,616 MAC/row = 66.7% of its forward**, i.e.
  **19.5% of the epoch loop** — the single largest number in the audit, and 4×
  every bit-identical win in **2.9** combined. `entity_deepsets.py:44-47`
  records the separate stacks as a DELIBERATE deviation from Huang & Lee, who
  share; SB3's own default is `share_features_extractor`
  (`common/policies.py:693`). So this is an ARCHITECTURE decision with a
  win-rate risk (a shared trunk couples value and policy gradients, which is
  why the deviation was taken), never a refactor: it needs its own pre-reg, and
  it is not bit-identical. Worth most after 7.5, when the epoch loop owns the
  wall.


- **Explicit cross features / DCN-style crossing — RUNG 2 of an existing spec,
  NEVER RUN (banked 2026-09-08 on the maintainer's ask).** Not a new idea:
  `docs/prior_work/CROSS_FEATURES_AND_ARCHITECTURE.md` already ladders it —
  rung 0 hand-composed crosses, rung 1 pointer/shared-slot head, **rung 2
  explicit crossing (two-tower dot product / DCN)**, rung 3 entity attention.
  We built rung 3's cousin (`entity_deepsets`) and **skipped rung 2 entirely**.
  That doc's own caveat travels with every formula: it was written in a session
  with NO repo access, so verify against `baselines.py` and the gen-1 damage
  formula before implementing, and `docs/prior_work/`'s audit of it supersedes
  it on conflicts. **The maintainer's framing (2026-09-08, from RecSys
  wide-and-deep):** the "wide" half is a SPARSE MEMORIZATION branch over cross
  features, which is the half we have never had — our ID embeddings are inputs
  to the dense trunk, not a crossing branch.
  **Size the cross deliberately — the arithmetic decides the form.** Full 3-way
  (attacker species × defender species × move) is 301·301·183 ≈ **16.6M cells**
  in gen 4 (151·151·165 ≈ 3.8M in gen 1) against ≈48M decisions per 50M-step
  lane ≈ **3 samples/cell**, i.e. unlearnable. 2-way is the tractable form:
  species×species ≈ 90k cells ≈ 530 samples/cell, move×defender-species ≈ 55k.
  START 2-WAY; hash or factorize before any 3-way.
  **Why this is NOT the §3 width kill re-proposed.** That kill rests on measured
  IDLENESS of DENSE capacity (dormancy 27→84–88%, critic ctx srank99 9–13/384 at
  37.5–50M). An embedding row is updated only when its cell is seen, so it
  cannot go dormant the way a dense layer does — the idleness mechanism does not
  transfer, and this is a different question rather than a re-proposal.
  **Capacity datapoint, RECORDED not acted on:** `ps-ppo` is **14,490,657
  params** (transformer 6.31M + subnets 4.32M + JEPA 1.58M + readout 2.10M;
  **embeddings only 141k**, verified by instantiating the model 2026-08-04) and
  claims ladder 1900+ at gen 9 — 21× our actor's 674,763. It is simultaneously
  the strongest external argument for DENSE capacity and evidence that such
  scale is NOT embedding-shaped. Re-opening §3's width kill on it needs a
  MAINTAINER RULING (§3's rule: vacating a mechanism-bounded entry does).
  **Cheap pre-test, fully offline, no server:** screen the branch SUPERVISED on
  the gen-4 BC-clone dataset (`runs/bc_gen4_fp20_soft_s0`, val agreement 0.433
  is the incumbent) before any RL run touches it; a width sweep on the same
  fixed dataset also separates "the architecture cannot represent the target"
  from "RL training does not use what it has". **PURITY NOTE:** only the
  ARCHITECTURE CHOICE may transfer — no weights trained on FP tapes enter the
  learner, or the pure-self-play lane is contaminated (the clone is an anchor,
  never training data). Needs its own pre-reg; not bit-identical; worth most
  after 7.5.


## 6. Ops hygiene (from the 2026-09-01 auto-mode review; sequenced)

Safe now (server-side, touches nothing on this box): **GitHub branch
protection on `main`** — block force-push and deletion; maintainer's click.

After FLEET DONE + frozen schedule + grade are recorded:
- gitleaks (or equivalent) pre-commit hook — live secrets are the ladder
  bot credentials and the W&B key. Not while the babysitter session is
  mid-schedule (a failing hook derails its commits).
- Permission config: soft-block `git clean` / `git reset --hard` (in this
  repo `git clean -fdx` deletes the *gitignored* `showdown/` server AND all
  of `runs/` in one shot — worse than any `rm`), plus ladder-launch and
  `git push` soft blocks; allow-list read-only inspection (`git status/
  diff/log`, `pytest`, `ps`, `extract_history`) so the prompts that matter
  still get read.
- `runs/`-outside-tree symlink migration: decide only after E2's rung
  retention window closes (~600 rungs must stay until S-SHAPE, S-ANNEAL,
  D-A are committed) and after checking resume metadata for embedded paths.
- `npm ci --ignore-scripts` as the habit for any `showdown/` reinstall
  (then re-set `simulator: 4` — standing landmine).
- docs/CLEANUP.md shelf unshelves at the readout per its own terms (audit items
  A2–A5); B3 (decide()-helper refactor) became legal when R2 landed but
  waits until the frozen eval paths are done being load-bearing.

## 8. Post-JOURNEY — the strength chapter (JOURNEY 14; NOT in the tally above)

These rows are **outside** the §2–§6 tally on purpose: they belong to a chapter that
starts after JOURNEY step 12 wraps the story, they are not part of the novelty claim,
and no number from them may be quoted beside a pure-lane number. Added 2026-09-09 on the
maintainer's ask ("recheck how much search over our own self-play value function gives
us... hoping it can give a big boost without needing to distill or imitate FP").

**8.1 The unspent inference budget — the cheapest real read on this list.** The ladder
allows **~150 s per turn** (the tight path; a challenge gets 300) and we play GREEDY.
Every point on the search-depreciation curve in **2.5** is depth-1 EXPECTATION search at
**20 ms** = **0.013% of the available budget**, while Foul Play beats us using 500 ms =
0.33% of it. So "search stops paying" is currently a statement about one thousandth of
the budget. **Read:** re-run the depreciation curve at 0.5 s, 5 s and 50 s per decision
on the engine (7.5 makes state-copy ordinary) against the same checkpoints, and report
decisions/sec beside every point. No training. This is the measurement that decides
whether the strength chapter is worth opening at all, and it can run on an idle box.

**ANSWERED 2026-09-18 — and the answer is a NULL against the RIGHT BAR, plus one
premise of this row retracted.** (i) **The bar is GREEDY**, not the depth-1
search: three independent greedy draws on the R5 committee read 0.5747 / 0.5720 /
0.5827, pooling to **0.5765 (n=4500)**, and **every** search configuration
measured on that object is level with or below it — best searched arm 0.5627
(RESULTS §24). Budget was not the binding constraint: the gate was (RESULTS §24),
and opening it does not get search above greedy. (ii) **"Foul Play beats us using
500 ms" is RETRACTED for this object.** Measured head-to-head 2026-09-18: the R5
committee beats **FP@500 at 0.5600 (n=500, 0 ties, +2.70 se above even)**, and
25× budget buys Foul Play nothing (FP@500 vs FP@20 is +0.010 at 0.32 se). The
100M committee lost that same matchup at 0.472, so this is a real change in the
object, not in the instrument. FP@500 is an INSTRUMENT, not a rung, and both FP
disclosures travel with every number here. (iii) **What is still unspent** is
therefore not "more milliseconds on the same construction" — it is **where** the
budget goes (§8.5) and **what the network learned from it** (4.9).

**8.2 A critic trained AS AN EVALUATOR (the actual bottleneck).** Search amplifies its
leaf evaluator, and D22 measures ours as the weakest component we have (critic context
srank99 **9–13 of 384** at 37.5–50M; dormancy 27 → 84–88%). PPO's value loss builds a
baseline for advantage estimation ON THE POLICY'S OWN STATE DISTRIBUTION; search needs
accurate values on HYPOTHETICAL states it has never played. Nothing here has ever trained
for the second objective. Candidates, cheapest first: a value head trained on
self-play returns from RESAMPLED states rather than visited ones; bootstrapped n-step
targets from the search itself (its root value is a better target than the raw return);
and the plasticity levers in **4.3** / **4.7**, which are the same fight seen from the
other side — a rank-9 representation cannot evaluate positions it has not seen. Pairs
with **8.1**: if a real budget still does not pay, this is why, and 8.1 alone cannot
distinguish "search does not help here" from "our evaluator is not good enough to search
with".

**AMENDED 2026-09-18 — the PREMISE SURVIVES, the DIAGNOSIS IS REVERSED, and the
D22 numbers quoted above are superseded for the WIDE critic.** (i) **Our critic
is the ROBUST evaluator, not the fragile one.** The assumption written above —
that a critic fit only to our own policy's states would break on search-visited
lines — is measured FALSE in the opposite direction: tripling how often search
acts on it costs **0.006 (0.38 se)**, while doing the same to Foul Play's static
hand-tuned heuristic costs **0.088 (5.59 se)**; the evaluator difference is
−0.020 (1.56 se) at a tight gate and **−0.102 (5.62 se)** at an open one
(RESULTS §24). "Our critic is off-distribution garbage" may not be quoted.
(ii) **The srank/dormancy half is fixed by WIDTH, not by a plasticity lever:**
the 1024-wide critic carries srank99 **632/1024** where the 384-wide lanes carry
5–27 (RESULTS §21) — so "a rank-9 representation cannot evaluate positions it has
not seen" no longer describes the current object. (iii) **But the bottleneck this
row names is still real, and now has a sharper name:** explained variance did NOT
move with that width (0.5881 vs 0.5919). Either 0.59 is the format's ceiling
(**2.11 measures exactly this, and must run first**) or the critic needs a
DIFFERENT OBJECTIVE rather than more capacity — which is **4.9**. This row's
candidate list is superseded by 4.9 for the second and third items; the first
(value targets from RESAMPLED states) survives as the cheap version of it.

**8.3 Belief-sampled search (the imperfect-information leg 11.5 does not ask).** Randbats
hides sets, EVs and unrevealed moves; JOURNEY 11.5's depth question is perfect-info. FP
approximates the real thing by searching a sampled world, and our gen-4 encoder already
carries an exact set prior. Sample opponent sets from the prior, search each, aggregate at
the root. The h2h gap against FP is more plausibly THIS than depth. Cost scales with the
sample count, so it is a dial, not a cliff.

**AMENDED 2026-09-12 / 2026-09-18:** n_det 1→64 at depth 1 is FLAT, so belief
breadth is not what depth-1 search is short of. The row stays open because it has
never been measured where it could matter — inside a tree deep enough for the
sampled world to change the line, and at a gate open enough for the aggregate to
be acted on. Both of those are 2.10 + §8.5 work, not new machinery.

**8.5 SEARCH ONLY WHERE THE COMMITTEE DISAGREES — the unspent-budget question in
the form the committee makes FREE (added 2026-09-18; the maintainer ranks it
third of the search items; **BUILT the same day**, unrun as an arm).** §8.1's budget is not short; it is spent UNIFORMLY,
on the ~97% of decisions where the answer was never in doubt. **We already
compute the signal that says which decisions those are, on every decision, at
zero extra cost:** 4.8's masked log-prob committee holds each member's
distribution, and its disagreement is a free per-decision estimate of how
contested the position is. **Measured on THIS object, off FP (the FP500 block,
RESULTS §25): the committee overrides its first member on 9.7–10.0% of
decisions.** (4.8 quotes 10.8% vs SH and 27.8% off FP@20; **the 27.8% is the
100M committee, a different object** — and "pooled argmax ≠ member-0 argmax" is
a different, smaller quantity than "any member dissents", so **the gate's
realized rate is MEASURED by a screen cell rather than predicted from either**.) **Read:** spend the budget only where disagreement is
high — no search at all below a threshold, and a LARGE budget (500 ms–5 s, the
ladder allows ~150 s/turn) above it. **Why it is not the dose question again:**
every dose measured so far raised the budget on EVERY decision, which is why
depth-2's 3.27× cost bought −0.0007; concentrating the same total compute on the
decisions that are actually close is a different experiment, and it has never
been run. **Two properties make it cheap:** the gate is free (already computed),
and the total budget can be held CONSTANT against a uniform-dose arm — which
makes the comparison matched on the thing that is not being tested, the rule the
2026-09-17 override-rate confound was paid for. **Caveats:** disagreement is a
proxy for closeness and could be anti-correlated with where search helps (that is
the finding if it reads null); and the arm must be matched on override rate to a
uniform control, or it measures the gate again. **BUILT 2026-09-18** (`rl/search/agent.py`'s `disagree=` dial,
`tests/test_disagreement_gate.py`, 14 tests). Two metrics: **`votes`** — the
fraction of members whose own argmax is not the pooled argmax, the exact
quantity 4.8's credit rests on, and free because `_EnsembleActor` now keeps the
per-member log-probs it already computed — and **`margin`** — `1 - (p1 - p2)` on
the pooled prior, which works for a single agent. Both ends are pinned:
threshold 0.0 searches everything, a threshold above every score plays exactly
the greedy argmax (not a third policy), and `None` is every banked arm. A
one-legal-action decision scores 0 under both. Gate skips are folded into the
`skips` denominator, or a healthy gated arm reads VOID on `depth2/fired_rate`.
**RUN 2026-09-19. THE SELECTION CLAIM IS A NULL; the CONCENTRATION claim is
still open (DUM pending).** At a search rate matched to three decimals (0.431
both), gating on committee disagreement reads **0.5870** against a COIN's
**0.5840** — **+0.0030 at 0.14 se.** The coin does just as well.

**WHAT IS AND IS NOT TESTED, because this is one cut of one metric.** The arm
ran `votes` at threshold 0.30, which on a THREE-member committee means "ANY
member dissents" — the coarsest cut the metric has, and a weak notion of
contested. **Untested: `votes` at 0.5 (two of three dissent, a rarer and
sharper signal), the continuous `margin` metric, and any committee larger than
three.** A null at the coarsest cut does not close the idea that disagreement
carries usable signal; it closes "any dissent, three members, this threshold".

**And the two arms are NOT identical in what they did.** DGV overrode 21.0% of
the decisions it searched against DRV's 14.7% — selection works, in the sense
that contested positions do produce more overrides — so DGV changed **9.1%** of
all decisions and DRV **6.3%**. Given §24's measurement that changing more is
worse, DGV doing equally well while changing half again as many decisions is, if
anything, mildly favourable to selection. At 0.14 se none of that is a result.
**Feeds 4.9 directly** — it is
the natural answer to 4.9's dose question (search the flagged fraction, train on
those states).

**8.6 THE TREE'S BUDGET, on the gumbel rule — the direct follow-up to RESULTS §26
(added 2026-09-18).** §26 ran a real decoupled-UCT tree at `iters: 100` against an
in-session greedy anchor and got **TG (gumbel) 0.6040 vs greedy 0.5830 = +0.0210
at 0.96 se** — the first search arm this project has measured that is not below
greedy, and **unresolved rather than null** (se_diff 0.0220 at n=1000).
**Two things follow, and the order matters.**
**(i) LADDER THE BUDGET BEFORE ADDING n.** Resolving +0.0210 at 2 se takes
n≈4,375 per arm — an overnight block — and it would spend that on the WEAKEST
version of the arm. `iters: 100` is precisely the regime the 90.9%
visit-concentration measurement describes: the prior dominates and the tree can
barely express an improvement (TV changed **1.1 decisions per battle**). If more
iterations move `π′` off the prior, the effect to resolve is a bigger one.
Ladder `iters` 100 / 300 / 900 on the gumbel rule with an in-session greedy
anchor, and **report KL(`π′` ‖ prior) and the override rate at every rung** —
those are the mechanism, and they are also exactly what **4.9**'s free falsifier
needs.
**(ii) RETIRE `q + margin` AS THE TREE'S DECIDE RULE.** It is the worst of the
three at 2.00 se (TG − TQ = +0.0440), and it is *the shape of the selector every
banked matrix number uses*. The ordering is not explained by action rate — TQ
acts BETWEEN TV and TG — so this is a statement about the rule itself.
**Cost:** iters 300 ≈ 2.8 h at n=1000; iters 900 ≈ 5 h at n=600. One block with
an anchor is a night. **This does not close or open MCTS** — one budget, one
object, one session, and CLAUDE.md rule 6 still applies.

**8.4 FP distillation — the LAST rung, and a CHARTER CHANGE.** Tapes, soft targets,
DAgger-style relabelling of our own states. **Excluded from the pure lane by CLAUDE.md
("expert-data bootstrapping into the learner is excluded") and it needs its own maintainer
ruling before one row of it enters a learner.** Do not reach for it until 8.1 + 8.2 have
been measured and found insufficient. Three things already known if it ever runs: (i) FP
decisions cost ~250x a self-play decision — FP@500 emits ~0.8 decisions/s against a lane's
~200 steps/s appetite, so a live FP opponent can feed **0.4% of one lane** and any
"league at X% vs FP" prices out at ~12 concurrent FP processes for 5%; the only viable
shape is pay-once-per-decision, reuse-many-times, i.e. TAPES, never opponents. (ii) Q38
(2026-09-09) found FP@20 and FP@500 **not distinguishable as opponents** (0.2933 vs
0.2640, |Δ| 0.029 against 2·se_diff 0.046) at **24x** the wall clock, so FP@20 is where
volume lives and FP@500 must justify itself on VALUE targets or not at all. (iii) Our
existing clone reproduces almost none of its teacher — **0.464 vs SH against a teacher at
0.904**, val agreement 0.433 — so a "league of FP clones" proxies nothing until the
distillation itself improves. Two free door-openers meanwhile: **record the search's
per-action statistics, not the chosen move**, in any FP tape collected from here on (the
search already computes them, and soft targets are the one distillation objective that
survived our own testing), and keep a state-copy/rollout surface in the collector.

## 7. Corrections to the source doc (so nobody re-imports them)

1. R2: 1,024→30,720 steps/update, ~34→**~959** episodes/update (not
   ~1,100); biggest credit *of CH5* (project-wide biggest is +0.1513,
   entity structure).
2. R2 was not the advisory's continuation — its batch size was
   independently recalibrated against H&L (CHAPTER5:264-269). The λ half:
   advisory → branch (d) mooted → D21 → swept 2026-08-16.
3. "Reliability 0.0117" is CH3 R0's Murphy decomposition of the *search*
   value head vs SH (Brier 0.1567 = 0.0117 + resolution 0.0594 /
   uncertainty 0.2050) — not a fleet-R0 read.
4. Omitted: VGC-Bench runs γ1.0/λ0.95 (docs/prior_work:407-411) — the
   "convergent 0.75" prior has a third system on the other side; and
   steps_per_update 32,768 / λ0.75-flat belong to commit `7fb522c` (HEAD:
   36,864, plus an undocumented dynamic-λ 0.55–0.95).
5. "Unpaired se terms 0.024–0.049" — not found as recorded; the honest
   unpaired comparators are the seed-clustered bars 0.065 / 0.0718 / 0.1007.
6. The 639,409 episodes were the shaping-invariance *gate*; the null was a
   separate 9,000-battle read (Δ −0.0004, z −0.06).
7. "~27-decision domain": self-play measures 26–32 by era (R2: 32.047);
   27.2 is decisions *vs SH* (CH3 R0).
8. P3 is predecessor-era (2026-08-03, heur_512 data), not 100M-cycle;
   coefficients also include Abra/Alakazam +0.07.
9. srank99 "7–11 of 384" is the D22 s35–37 probe; search-era headline lanes
   read ~47/384; any future rank quote needs the D24 float64 fix.
10. The ±1.6 / 48-vs-50 trade-down argument lives in the
    `showdown.py:728-757` docstring (Arm-B rationale), not a named record
    ruling — conclusion unchanged.
11. "~1 in 4" for shaping is an agent-authored licensed estimate
    (CHAPTER5 §3b), not maintainer-priced.
12. Missing entirely: the built, letter-met, uncredited regenerative-L2
    family (§4.3) — arguably better-evidenced than the shaping retry it
    ranks above.

**Round 2 — 2026-09-04, the remote re-read's four gap claims, verified here
against the record before anything above was added:**

13. "C6 is the only measured encoder defect" — the 2026-08-26 sweep
    confirmed TWO (fixed-damage: measured behavioural cost; force-switch
    corpse blocks: measured INERT, 0/42) plus minor finds (Counter
    critRatio 3.0, Ditto id). C6 is the only one with a measured cost.
14. C6's move list: poke-env gen-1 `base_power == 1` covers seven moves
    (seismictoss, superfang, nightshade, dragonrage, sonicboom, counter,
    psywave); only four are in the gen-1 pool (Seismic Toss, Counter,
    Night Shade, Super Fang). CHAPTER5's list names two moves that never
    occur (Dragon Rage, Sonic Boom) and omits Counter.
15. "CH4 R1 fit Bradley–Terry ... to every h2h on disk, transitive to
    ±0.03" — that fit was memo B's, on BANKED data, in the 2026-08-25/26
    design cycle; CH4 R1 fit a fresh same-session hub (rho +0.005 ±
    0.013; FP excess > 2.6 points excluded) and dissolved the clone
    exception. Same conclusion, wrong attribution.
16. "pfsp_power and fixed_mix removed 2026-08-29 as inert (CLEANUP A4)" —
    removed as UNREACHABLE killed levers (commit 4e5f5cf; docs/CLEANUP.md
    "Stripped as ruled"; `select()` byte-identical on the seeded stream).
    "A4" in docs/CLEANUP.md is also the label of a shelved audit item
    (`update()`'s variadic tuple) — cite the strip list, not "A4" (the
    trap 4.1 already flags for "A2"). Neither key appears in any of the
    178 run configs on disk.
17. "OpenAI Five used an asymmetric critic" (the external summary) — not
    in Berner et al. 2019: "The LSTM state is projected to obtain the
    policy outputs (actions and value function)" (§3.1, Fig. 1); no
    privileged input anywhere in the text. The privileged value function
    is AlphaStar's (main text and Methods, quoted in §3). The remote
    session's doubt was correct.
18. "Zero-init surgery leaves the policy unchanged" — verified (App. B,
    Ŵ = [W 0], ŷ = y; Net2Net cited), but the summary omitted the same
    paper's Rerun (§4.2): from scratch, 2 months, 150 PFlops/s·days,
    > 98% vs the final surgery-trained model — "plateaued at a weaker
    skill level than the from-scratch model". Continuity at a strength
    cost (2.7).
19. "F-08 makes §5's OBS_DIM cost reasoning stale" — false. The seam
    restates the landmine in its own docstring; OBS_DIM and the strides
    are still import-time globals in `showdown.py`; the loader still
    refuses a width mismatch. F-08 changed table ownership and made the
    intra-block layout derivable (a slot map for 2.7), not the cost. §5
    amended for accuracy, not cost.
20. This doc's own §1 (2026-09-01) cited "the standing fewer-bigger-runs
    order" — no such order is on the record. The governing texts are the
    2026-08-23 big-runs ruling (huge runs only for a ladder-ready model, or
    logs still clearly climbing; CHAPTER5 §7.3 kept it in force) and the
    explicit 2026-08-31 100M off-arc order (RESULTS §18). Fixed in place.
