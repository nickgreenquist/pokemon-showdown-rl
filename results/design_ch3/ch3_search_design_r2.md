# CHAPTER 3 — INFERENCE-TIME SEARCH. Design r2 (post-review, ratifiable)

**Status: RATIFIED 2026-08-21 (maintainer, in-session). §10 rulings 1–4
APPROVED verbatim ("yes, approve all the above"); ruling 5 (D7(a) ladder)
stays deferred as designed. Maintainer emphasis recorded with the approval:
the purity of the pure-self-play lane is the binding concern, and ONE-TURN
LOOKAHEAD is what is ruled valid — R4+ (depth ≥ 2, SM-MCTS, mirror
refinement, Nash) remains UNAUTHORIZED and returns to the maintainer as its
own pre-reg. R0 is authorized to build and run.**

Provenance: r1 synthesized 2026-08-21 from two independent Opus designs
(`design_input_A.md`, `design_input_B.md`) against `evidence_brief.md`;
reviewed by two independent Opus reviewers (`draft_review_1.md`: 17 MF / 14 SF;
`draft_review_2.md`: 10 MF / 13 SF; both SOUND-WITH-MUST-FIXES); **all 27
must-fixes folded into this r2** (fold log in §11), plus the load-bearing
should-fixes. The input docs and r1 remain on disk as frozen, NON-NORMATIVE
background; **this document is self-contained and is the only normative one.**
Measurements cited as (M-x) were taken 2026-08-21 on this box; methods are in
the input docs and reviews.

---

## 1. The chapter in one paragraph

Chapter 2 measured training compute as saturated (D29r2 R-B FLAT). Chapter 3
asks whether INFERENCE compute moves the same agent: at each decision, build
the turn's joint-action payoff matrix M[a][b] over our legal actions a (from
`info["action_mask"]`, ≤9) and the opponent's six L6 action classes b;
estimate each cell by pushing determinized states through a validated gen-1
forward model whose chance handling is **branch-exact over accuracy, crit,
secondary-effect, status and sleep-wake structure, with damage collapsed to
the average roll (`DamageRolls::Average` — a NAMED approximation, measured and
gated in §5), retaining the top-6 branches by probability with the retained
mass RENORMALIZED**; score leaves with our own critic; play the best response
to the opponent-action distribution from our own credited oppact head:
a* = argmax_a Σ_b q(b|s)·M[a][b]. One ply, deterministic, node-budgeted. Every
network inside the search is a D26 checkpoint head; nothing trains; the whole
chapter runs on checkpoints that already exist (verified: `checkpoint.pt`
carries actor, critic AND aux_head, all inference-runnable; the critic is
obs-only). **Point prediction, before any number exists: +0.02 to +0.05 vs SH
over 0.71825 — CREDIT-vs-FLAT is a coin flip at the +0.025 bar.** FP's 0.8307
is an upper bound on (search + a GOOD hand-crafted eval), not on this design;
our leaf evaluator is a self-play critic with EV 0.56–0.59 and ctx srank99
7–11/384 (D22), and §7's instruments exist because the value head, not depth,
is the likely binding constraint. One honesty line (review 2, PASSED-12): FP's
0.83 ran through poke-engine's own MCTS+eval, never through
`generate_instructions` — the existence proof does NOT transfer to the exact
primitive this chapter uses; the FG battery is the price of that gap.

## 2. Forward model and its honest fidelity statement

**Pick: poke-engine 0.0.48, gen1 build, as a PURE TRANSITION FUNCTION** —
only `State`, `generate_instructions`, `apply_instructions`,
`reverse_instructions`, `calculate_damage`. Never `mcts` /
`monte_carlo_tree_search` / `iterative_deepening_expectiminimax` (they carry a
hand-crafted eval; do-NOT #2). The vendored Showdown, unmodified, is the
offline FIDELITY ORACLE (§5). Fallback, pre-specified: if the maintainer
refuses the engine (§10.1) or FG-2 fails its 3-evening repair budget, the
chapter re-routes to Designer A's in-process Showdown-sidecar architecture
(`design_input_A.md` §5, starting from its R0-a spike) — a switch, not a
redesign.

**Known, named approximations of the engine path** (each measured, each with
its gate or its disclosure):
1. **Average damage roll** — the engine emits one damage per branch
   (mean-of-39-rolls × 0.925 floor); KO/no-KO at the roll boundary is
   deterministic where the game flips a coin. Gate: `fidelity/ko_disagreement`
   (§5 FG-2k) measured on the R1 harvest; **pre-registered repair if it reads
   > 0.05: a 2-point roll expansion (0.85/1.00, weighted by true roll mass
   either side of the KO threshold) at ~2× leaf cost, re-priced by the R1-0
   spike before any verdict battle.** The B1 licensed sentence carries the
   measured number either way.
2. **Top-6 branch retention, renormalized** — branches sorted by probability
   (ties broken by the engine's instruction order), kept mass renormalized so
   no cell is shrunk by its own tree width. Measured branch counts (14,400
   real gen-1 (a,b) pairs): mean 2.79, median 2, p95 8, only 6.4% > 6 — so
   retained mass is ~1.0 for most cells. Gates: `fidelity/retained_mass`
   recorded per dose, flag < 0.95; offline truncation probe Z2' (500 harvest
   states, |top-6 − all-branch| cell delta, zero battles) reported at R1.
3. **Engine does NOT enforce partial-trap or must-recharge** (sleep/freeze it
   does). The bridge detects both and substitutes `"none"`, counted
   (`bridge/forced_none`). Our own such turns are already placeholder-skipped
   (§4 R2); the OPPONENT's are only partly observable — the unmodellable
   residue is counted and disclosed, never silently simulated as an attack.
4. **Reflect/Light Screen are gen-1 VOLATILES in the engine** (measured:
   side-condition mapping is a silent no-op). The bridge maps them into
   `volatile_statuses`. **Light Screen is unobservable from battle1** (poke-env
   0.15 has no `Effect.LIGHT_SCREEN`; our encoder already records this) — a
   NAMED unmodellable, removed from FG-2's field set, its harvest frequency
   measured and carried in the honesty notes.
5. **Unknown volatile strings are silently ignored by the engine** — so
   `bridge.py` carries a single explicit `Effect → PokemonVolatileStatus`
   table, asserted exhaustive at import (one-time probe per name confirming it
   is not silently dropped).

**Install mechanics (deviation from the pyproject-only rule — maintainer
ruling §10.2):** PEP 621 cannot carry per-requirement build flags, and
poke-engine's DEFAULT build is **gen 4** (`default = ["poke-engine/gen4"]`),
so a naive pin silently installs the wrong generation. The engine therefore
lives in `requirements-search.txt` (referenced by comment from
`pyproject.toml`) with the exact command documented in the README:
`pip install --no-cache-dir --force-reinstall --no-binary poke-engine
poke-engine==0.0.48 --config-settings="build-args=--features
poke-engine/gen1 --no-default-features"` — `--no-cache-dir` is mandatory
(pip's wheel cache ignores config-settings; a gen1 cp313 wheel already in this
box's cache proves both the hazard and that **the 3.13 source build works** —
verified by running `generate_instructions` in the 3.13 env; no worker
fallback needed). FG-5's attestation (module-path discriminator `src/gen1/`≥1,
`src/genx/`==0, `"used for spc"`≥1, plus .so sha256) runs at EVERY rung and
its expectation table carries all three failure rows: gen9 (0/20+/0), **gen4
(0/genx>0/0)**, gen1 (7/0/1).

**Leaf path:** no second encoder, ever. `ShadowBattle` duck-types exactly the
attribute surface `embed_battle` reads (verified complete against the real
function: battle-level `active_pokemon, opponent_active_pokemon, team,
opponent_team, turn, force_switch, trapped, available_moves`; per-mon
`current_hp_fraction, fainted, status, level, base_stats, types, type_1,
type_2, boosts, effects, must_recharge, status_counter, preparing, moves,
species`; per-move `base_power, accuracy, current_pp, max_pp, type, category,
priority, id, entry` — `available_moves` and the id-suffix inputs are
SYNTHESIZED by ShadowBattle, per review 2 SF-9). `embed_battle` reads no event
history (verified), so a leaf state suffices. Unrevealed opponent slots at
leaves get the same `randbats_prior` fill the live encoder applies — the leaf
observation is distributionally what the policy trained on, free.

**Measured cost model (review-2 corrected; the r1 92.6 µs omitted the
readback/ShadowBattle direction):** State construct 27.2 µs · generate 15.1 µs
· apply 17.7 µs · readback 12.9 µs · embed (real objects) 72.5 µs · critic
5.4 µs/state at B=128 (22× cheaper than B=1 — **batching is load-bearing**;
all leaves of a decision are independent and score in one ~B≈500 call; the
leaf evaluator is the CRITIC — r1's 10.8 µs figure was the actor). Realistic
leaf ≈ 140–170 µs. Dose M realized ≈ 216 pairs × (15 µs + 2.79 × ~155 µs) ≈
**~100–110 ms/decision ≈ 2.6–2.9 h/seed** — but every number in this
paragraph is an ESTIMATE that the R1-0 end-to-end spike replaces: 200 real
harvested decisions through the complete Dose-M search fix `ms_per_decision`
and `leaves_per_decision`, and the dose table, the F3 baseline, and the
watchdog threshold are all frozen against THOSE measurements, by the formulas
given here, before any verdict battle.

## 3. Determinization, opponent model, determinism

**Determinization — RSD (rejection-sampled set determinization) over the
vendored pool.** Our side exact; opponent revealed mons exact where revealed
(species → exact level/stats via `randbats_prior.species_level`); unrevealed
move slots sampled from `conditional_move_probs(species, revealed)` (exists,
byte-verified against vendored data.json); **unrevealed bench species: a NEW
sampler over the 146-species pool with rejection on the generator's
type/weakness cap-of-2** (review 2 SF-2: this team-level piece does NOT yet
exist — it is the one new sampler this chapter writes; D19's closeout bounds
what it must capture: 88–90% cap mask, 0.024–0.034 nats residual, recorded
approximation). **Constraint (MF-5b): the sample for the opponent's ACTIVE is
rejection-constrained to CONTAIN the four encoder move slots**, so L6 classes
0–3 always map to a real determinized `Move.id`. NOT belief-state learning:
D19 dead, D18 NULL, "NEVER belief state" — RSD samples a public enumerable
generator and learns nothing. PIMC justification, stated here because this
document must carry it: depth-1 is structurally immune to strategy fusion and
non-locality (no future information set exists one ply deep), and on Long,
Sturtevant, Buro & Furtak (2010)'s three predictors — leaf correlation HIGH,
bias LOW, disambiguation HIGH (gen1 randbats reveals a move or mon nearly
every turn) — this board sits where PIMC is known to work. Those objections
DO bite at depth ≥ 2 and are carried as R4-prereq caveats. **FG-7 gates
support** (true team in sampler support ≥ 0.99, seat-2 offline).

**Shared determinizations (MF-13):** the same N_det determinizations, drawn
once per decision from the key-derived stream, are used for EVERY (a,b) cell;
rows are therefore paired across determinizations ("shared determinizations",
deliberately not "common random numbers"). Asserted by R2-4.

**L6 → engine action mapping (MF-5), the full law:**
| L6 class | engine action string |
|---|---|
| slot j ∈ {0,1,2,3} | the determinized active's `Move.id` for encoder slot j (bare id, e.g. `"bodyslam"` — the `"switch X"` display form is a trap; measured) |
| OTHER_MOVE | **renormalize q over the other five classes; `oppact/other_move_mass` recorded per decision** (a determinized mon has exactly 4 moves; no fifth exists to simulate) |
| SWITCH | one bench target sampled PER DETERMINIZATION, **uniform over legal (unfainted, non-active) bench** — declared; bias direction named in §9: uniform averages over bad switch-ins, so the search is systematically OPTIMISTIC about our staying in |
A switch action of ours = the target's bare species id (measured: `"chansey"`
parses, `"switch chansey"` raises). Assertion, gated at R2-4: every string
handed to `generate_instructions` is derived from the determinized state,
never formatted from a class name.

**Opponent model:** q = the oppact head's L6 posterior at the ROOT (runs from
battle1 alone — verified: `forward(ctx, opp_moves, opp_bench)` takes exactly
the actor's `return_features=True` tuple; `canonicalise` is obs-derived),
uniform-within-class refinement. The head is promoted from train-time-only to
inference — a role change named as a confound: trained to predict a frozen
self-play snapshot, deployed against SH. `oppact/sh_accuracy` + `sh_nll` are
measured at R1 (harvest ground truth, zero battles) BEFORE R2 depends on the
head. **Fallback (MF-4 — the r1 fallback was an SH model in disguise and is
DELETED): if q is degenerate, the replacement prior is the L6 marginal
measured on SELF-PLAY rollouts of the same checkpoints (zero SH data), and the
switch criterion is SH-free: median H(q) > 0.95·ln 6 measured on SELF-PLAY
states, threshold named now.** §10.3's ruling text covers priors DERIVED FROM
SH-vs-us battles, not just explicit SH features. A's mirror-policy
within-class refinement is an **R4-only option — not built, not measured in
this chapter** (MF-15 resolution; r1 §2 row 8 is amended accordingly).

**Determinism for a search agent, the four clauses (binding at every rung):**
D1 node-count budget only, hard cap, never wall-clock (a time budget makes the
policy a function of machine load). D2 all sampling from one
`numpy.random.Generator` keyed by `hash((checkpoint_seed, battle_index, turn,
decision_index))` — never global `random` (poke-env derives usernames from it;
eval-side usernames are OS-entropy, verified — no cross-arm collision exists,
and the driver prints every realized username anyway). D3 ties broken by
matrix score → policy prior → lowest action index; no dict-order resolution.
D4 argmax over the renormalized matrix score. Single-threaded search;
parallelism across battles/lanes only. Gate R2-3 proves all four (50 decision
points × 2 fresh processes × {1,4} threads → 50/50 identical orders).

**Placeholder turns (our side):** when Showdown's gen-1-only path replaces our
move list with the `Fight` placeholder (sleep/freeze/partial-trap; measured
4.0–10.3% of decisions), **the search is SKIPPED and the policy argmax is
returned**, counted as `search/placeholder_skips`. The realized skip rate
TRAVELS WITH EVERY RUNG-2 SENTENCE ON EVERY BRANCH (MF-12); above 0.25 it
additionally becomes a headline caveat (K0-3 is an escalation, not the switch
that turns disclosure on).

## 4. The rung ladder

| rung | what | verdict? | ledger (est) | evenings |
|---|---|---|---|---|
| **R0** | free compute + headroom (no forward model) | R0.B only | ~0.02 | 1 |
| **R1** | bridge + FG battery + R1-0 spike. NO verdict battles | no | ~0.02 | 3–4 |
| **R2** | CREDIT TEST: depth-1 @ Dose M vs fresh policy arm, 4×3000 paired | **PRIMARY** | ~0.5 | 1 |
| **R3** | mechanism grid: dose segments + evaluator axis. NON-CREDITING throughout | no (mechanism) | ~2.6–3.0 | 2 + 1 overnight |
| R4+ | conditional: depth ≥2 / SM-MCTS regret matching; mirror refinement; Nash/robustness; any NEW credit test at another dose | — | — | **NOT AUTHORIZED HERE** — own pre-reg, own ratification |

Through R3: **~3.1–3.5 ld, ~8–10 evenings** (review-1 SF-1 accounting: R3's 10
instrument cells add ~0.4–0.8 ld to B's bare 2.13). Chapter 2 realised ~11 ld.
The scarce resource is EVENING BLOCKS. Worst-case single loss: one 300-battle
chunk — ~20 min at Dose M, **~60–70 min at Dose L** (MF-2 fix; the 24-h bar
holds everywhere). Doses (caps, frozen by formula against the R1-0 spike):
**S** = N_det 1 × top-6, cap 324 · **M** = N_det 4 × top-6, cap 1296, node cap
1500 · **L** = N_det 16 × top-6, cap 5184 (the r1 "all ~18 branches" reading
is DELETED — top-6 retains ~full mass at measured branch counts, and the
15,552-leaf reading was 3× the priced cost). Realized-vs-cap is measured, not
assumed (§5 F3).

### R0 — one evening, no forward model, and it can kill the chapter
**R0.A — instrumented audit (descriptive, 1000 battles ≈ 40 s of play +
offline):** per decision: turn, n_legal, masked π, p_max, top-2 gap, V(s),
oppact L6 posterior + entropy, placeholder flag. Outputs: `contested_frac`
(p_max < 0.90, tabulated at {0.99,0.95,0.90,0.75}); `placeholder_frac`;
decisions/battle vs SH (re-anchors the cost model — M2's 29 was self-play);
**Z1 value-quality decomposition** (calibration curve of (V+1)/2 vs realized
outcome in 10 bins; Brier with reliability/resolution/uncertainty; AUC by turn
decile; the aleatoric floor of explained variance — the number D22 never
produced); the successor-ranking read (V's ordering of true next states at
contested decisions — recorded at R1 when the harvest exists, and named here
because K0-1's kill can be REVISITED on this matched statistic).
**R0.B — ensemble-4 arm (falsifiable, dies same evening):** A0 = the four D26
checkpoints greedily, 3000 each (12,000). A1 = masked log-prob equal-weight
mean of the four, argmax, 3000 × 3 eval batches. A2 = the four LOO-3
ensembles × 3000, recorded-never-governing (correlation-inflated, sentence
attached). PRIMARY: delta = p(A1 pooled 9,000) − equal-weight mean of per-lane
A0. Aggregator: EQUAL-WEIGHT MEAN, named once, binding; median/worst-lane
recorded never governing. Clustering: eval batch (n=3) for A1, checkpoint-lane
(n=4) for A0 — A1 has NO training-seed replication, so the clustered term ~
binomial and **the +0.025 FLOOR governs; a credit licenses "ensembling THESE
four checkpoints", never "ensembling helps"** (pre-shrunk). Bands B1/B2/B3
(two-sided)/B4/B5 as §6's, same cut points. NOT dose-matched to search (4×
forward pass vs ~124 ms) and never reported as its placebo; how-we'd-know:
`ensemble/flip_rate` + delta = the chapter's only (flip value, win delta)
anchor, quoted at R2/R3.
**R0 gates:** R0-a `eval/win_rate == wins_from_returns` exact, every JSON
(HARD). R0-b `mask_desyncs` recorded, nonzero = disclosure not void. R0-c
single-member ensemble reproduces that member's argmax 1000/1000 replayed
decisions. R0-d sha256 of the four checkpoint.pt recorded (they are D26's
objects). R0-e pre-reg committed, tree clean.
**Kills:** **K0-1** — leaf-evaluator gate: **AUC pooled over all decisions in
turn deciles 2–8** (aggregator NAMED, MF-10; per-decile curve recorded, never
governing) **< 0.60 → no V-leaf search**; re-route to MC-leaf (FG-8); both
failing → chapter STOPS, written up as measured two ways. 0.60's provenance,
disclosed honestly: a design constant set in advance — the lowest
discrimination at which argmax-over-~9-successors can plausibly beat its own
prior — not derived from a measurement; the kill is revisitable at R1 on the
matched successor-ranking statistic. **K0-2** — ensemble delta ≤ 0 AND
contested_frac(0.90) < 0.15 → cost-benefit STOP (not logical: a peaked policy
can still be wrong — FP overrides confident policies constantly); overridable
by the maintainer IN WRITING only (§10.4). **K0-3** — placeholder_frac > 0.25
→ headline-caveat escalation per §3 (the skip-rate disclosure itself is
unconditional).

### R1 — the bridge and the referee gate (no verdict battles)
Build order (strict): install+attest engine → bridge.py → ShadowBattle →
**R1-0 end-to-end spike** (200 harvested decisions through the complete Dose-M
search: freezes ms/decision, leaves/decision, watchdog constants, F3 baseline)
→ FG battery. **Harvest:** 500 battles under the R0.A recorder (~20 s of
play), both seats logged; seat-2 data NEVER reaches the search (FG-4 is the
machine check). **KILL: any blocking FG unfixable within 3 evening blocks →
the §2 fallback route, or the chapter stops with gate/value/threshold named.**

| gate | asserts | bar | blocking |
|---|---|---|---|
| FG-1 | State round-trip to_string→from_string→to_string byte-identical | 100% | yes |
| FG-2 | one-step agreement vs the REAL server: some retained branch matches observed next state on the field set: actives' species/status/sleep-rest counters/5 boosts/substitute-HP/volatile set ∩ {reflect, mist, focusenergy, leechseed, confusion, partiallytrapped, bide, recharging, flinch}/faint masks/active indices. **HP: banded to the branch's implied roll interval — accept observed_damage ∈ [0.85,1.00]×(branch_damage/0.925), engine rounding** (MF-2; exact HP match is impossible under average-damage). PP EXCLUDED (poke-env never decrements it — would measure poke-env). **lightscreen EXCLUDED — unobservable, named unmodellable** (§2.4). Signed damage residuals + `mass_on_observed` ≥ 0.05 reported as calibration | covered ≥ 0.98 | **yes — load-bearing** |
| FG-2p | same, placeholder stratum (sleep/freeze/partial-trap actives), separately sized and graded | ≥ 0.95, else stratum declared out-of-scope and the §3 skip covers it | yes |
| FG-2k | **`ko_disagreement`: fraction of harvest transitions where average-roll faint/no-faint ≠ server's** (MF-1) | recorded; > 0.05 → the 2-point roll expansion is built and re-priced before R2 | yes (the branch, not a stop) |
| FG-3 | 5-step drift of (HP fracs, faint counts) vs empirical continuations | recorded, flag > 0.10 | no |
| FG-4 | leak gate, BOTH mechanisms: raise-on-access sentinels on `battle2`/`info["privileged"]` over a 100-battle run, AND the poisoned-battle test (hidden team replaced by impossible sets → bit-identical decisions); static: `rl/search/` imports nothing from `fp.*`, calls none of the engine's search entry points; every generated mon carries an RSD provenance tag asserted at construction. **The sentinel assertion also runs at chunk 0 of EVERY VERDICT ARM** (SF-13) | 100%; failure = PURITY INCIDENT (retraction, not caveat) | yes |
| FG-5 | engine attestation: 7/0/1 discriminator + .so sha256; gen1/gen4/gen9 expectation rows | exact, every rung | yes |
| FG-6 | encoder parity `embed_battle(battle1)` vs `embed_battle(ShadowBattle(bridge(battle1)))`, elementwise, root states (determinization exact there). Budget = **named FIELD FAMILIES with per-family tolerances, set from the measured R1 baseline** (MF-8: opponent-HP quantisation ±0.01; PP excluded, named; sleep-vs-Rest counter excluded pending split, named; volatile map per §2.5; preparing; aliasing/turn dims) — the r1 "≤4 dims" assertion is DELETED; the budget is frozen AFTER one measured pass, BEFORE any verdict battle | all non-exempt dims exact to 1e-6 | yes |
| FG-7 | RSD support: true opponent team (seat-2, offline) in sampler support; top-1 species recall on unrevealed slots recorded (support ≠ calibration — SF-3 noted) | ≥ 0.99 | yes |
| FG-8 | MC-leaf pilot (only if K0-1 fired): 200 states, 16 policy rollouts/leaf through the engine, outcome AUC | ≥ 0.65 | conditional |
Also at R1, zero battle cost: `oppact/sh_accuracy` + `sh_nll`; Z2' truncation
probe; the successor-ranking read; `lightscreen`/opponent-trap-recharge
unmodellable frequencies.

### R2 — the credit test (one evening)
**Arms:** A0 POLICY fresh (4 lanes × 3000, ~8 min total) and A1 SEARCH@M
(4 × 3000, ~3 h at 4-wide), same session, same sha, same server process,
chunked 10 × 300 (seed_start advanced per chunk; pooling 10×300 ≡ 1×3000,
measured 2026-08-05).

> **CREDIT LINE (VERBATIM, INCLUDING THE LARGER-OF CLAUSE): a lever is
> credited iff pooled delta ≥ +0.025 AND ≥ 2·se_diff, where se_diff is the
> LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the
> latter computed from the per-seed finals at read time.**
> Disclosed conservative addition: se_diff here = the larger of THREE terms —
> pooled-binomial (two-sample), paired-clustered sd(d_i)/√4, unpaired
> two-sample clustered (`d25_grade.py::se_terms`, verified line 121). The
> third term can only raise the bar.
> **df DISCLOSURE (MF-9), stated before data: n=4 lanes, df=3. 2·se at df=3
> is ≈86% coverage (t₃,.975 = 3.18), and P(sd(d_i) underestimates σ_d by 2×)
> ≈ 0.14 — the seed-fragility clause is close to inert at this n, and the
> +0.025 FLOOR is the substantive protection. The ratified credit line is NOT
> changed; this is what it buys at n=4.**

Aggregator: EQUAL-WEIGHT MEAN of per-lane deltas d_i = p(A1,ℓ) − p(A0,ℓ),
named once, binding; median/worst-lane recorded, never governing. Clustering
unit: checkpoint-lane, PAIRED — cluster-level pairing, which DESIGN §8's
per-battle "UNPAIRED" measurement (r ≤ 0.04) does not forbid. **Arithmetic
before data (MF-8 corrected): 2·se_binom = 0.0115 two-sample (the r1 0.008 was
the frozen-comparator/single-arm form), so the binomial still never governs;
the floor is the expected operative bar unless sd(d_i) > 0.025. Power
(disclosed provenance: computed under A's FROZEN comparator; this design's
fresh comparator makes it optimistic by ~3 points and the size understated by
~0.006): ≈0.71 at true +0.030, ≈0.97 at +0.040, size ≤ ~0.023.** The 4-lane
sign-flip permutation has min p = 1/16 — reported as color, NEVER
letter-bearing.

Protocol: final checkpoint; deterministic per §3's four clauses; ties as
non-wins; vs SH; 3000/seed (DESIGN §8 governs over CLAUDE.md's stale 1000);
4 seeds pooled ≥ locked 3 (disclosed conservative deviation); both encoder env
vars; `eval/win_rate` from `info["outcome"]` with `wins_from_returns` exact
cross-check.

**Pre-launch gates:** R2-0 engine attestation (FG-5). R2-1 FG-1/2/2k/6/7
re-run green at launch sha, transcript to SESSION_LOGS. R2-2 FG-4 green
(+chunk-0 sentinel in both arms). R2-3 determinism gate. R2-4 no-op +
mapping gate: dose-1 collapsed matrix returns the policy argmax 50/50;
shared-determinization assertion; every engine string derived from state.
R2-5 win-rate cross-check exact (HARD). R2-6 offline suite green at launch
sha. R2-7 checkpoint sha256 == R0-d. R2-8 budget gate: ms/decision and
leaves/decision within ±25% of the R1-0 spike values, else THE DOSE IS
RECOMPUTED BY THE SAME FORMULA to hold the sweep ≤ 3.5 h at 4-wide, logged,
before any lane is judged. R2-9 pre-reg committed + clean tree (grader
enforces). R2-10 A0-STABILITY: |fresh A0 pooled − 0.71825| ≤ 0.02 (≈3.4
binomial se — fires on era change, not noise), else STOP and investigate
before any A1 battle; the frozen D26 finals are the tripwire, never the
comparator. **During-sweep:** D2-A watchdog/fallback counters checked at every
chunk boundary (see F3). D2-B chunk wall ≤ 2× projection (recorded, not a
stop). D2-C `mask_desyncs` per arm, differences disclosed.

**Containment (MF-10 — r1's silent-fallback watchdog is DELETED):** the node
cap bounds the worst case by construction; the in-process watchdog fires at
`max(10 × p50, 3 × p100)` of the R1-0 spike's per-decision timing and
**RAISES** — killing that 300-battle chunk (~20 min, re-run after diagnosis) —
it never silently returns the policy answer, so a silent policy arm cannot
exist and F3's zero-tolerance is free.

**F-GATES — EVALUATED BEFORE ANY BRANCH IS READ; any firing F VOIDS THE
PRIMARY and no band is adjudicated; F-gates may co-occur and all firing
F-gates are reported (MF-11).**
- F1 FIDELITY BREAK: any blocking FG fails at R2-1 → VOID, ledger recorded.
- F2 LEAK: FG-4 fails → VOID + purity incident; every number from that build
  RETRACTED, not caveated.
- F3 SEARCH DID NOT SEARCH (MF-3 redefinition): `search/timeouts > 0` after
  diagnosis shows a code defect (not a re-run chunk), OR
  `|leaves_mean − leaves_expected| / leaves_expected > 0.25` on any lane,
  where `leaves_expected` is the R1-0 spike's measured realized-leaves
  baseline on harvest decisions — never the nominal cap (realized ≈ 0.36–0.46
  × cap at measured branch counts; gating on 0.8 × cap would void a healthy
  arm with certainty). `placeholder_skips` are excluded from the mean and
  reported separately.
- F4 ERA BREAK: NOT APPLICABLE (fresh comparator, same session) — named.

**BRANCHES over delta, hi = max(0.025, 2·se_gov), mutually exclusive,
covering the real line; each carries its R3-launch action (MF-16); the KILL
below is a SUFFICIENT condition for not launching, the per-branch clauses
govern otherwise:**
- **B1 delta ≥ hi — CREDIT** (upper side). Licensed sentence, all qualifiers
  mandatory (MF-12): *"one-ply expectation search over a validated gen-1
  forward model (transition agreement FG-2 = X%, ko_disagreement = Y%,
  average-damage approximation named; search inactive on Z% of decisions —
  the gen-1 placeholder stratum), using only our own self-play
  policy/value/opponent-action heads, scores W vs SH — +delta over the
  identical checkpoints played greedily, same session, at an operative bar of
  BAR."* README headline row and STATUS change. Fires: (i) SH-exploitation
  falsifier (two-orientation h2h vs the BC clone, D26 H4 machinery, ~20 min);
  (ii) h2h vs FOUL PLAY itself (the purity-legal anchor, strongest opponent on
  this board); (iii) **R3 LAUNCHES**. Milestone consequence named, not acted
  on: D7(a)-vs-CLAUDE.md ladder contradiction goes to the maintainer.
- **B2 +0.025 ≤ delta < hi — LETTER-MET, SEED-FRAGILE, NOT CREDITED** (upper
  side; EMPTY whenever 2·se_gov ≤ 0.025 — named, expected). D26 stays
  headline; phrase travels verbatim. **R3 LAUNCHES.**
- **B3 |delta| < 0.025 — FLAT (the only two-sided cell).** D26 stays headline.
  Sentence carries both points, the CI, and the explicit non-exclusion clause
  (at se_gov ≈ 0.006, +0.005 gives CI [−0.007,+0.017] — excludes neither 0
  nor the predicted +0.02; QUOTE IT). **R3 launches ONLY IF the R0
  flip-anchor is positive** (`ensemble/flip_rate`-vs-delta slope > 0) or
  `search/flip_rate` ≥ 0.05 with Instrument-3 diagnostics indicating
  noise-limited rather than converged-and-wrong; otherwise the chapter STOPS
  (a FLAT search that rarely disagrees with its policy has no mechanism to
  dissect).
- **B4 −hi < delta ≤ −0.025 — LETTER-MET NEGATIVE** (lower side; empty on the
  same condition as B2). D26 stays headline. **R3 does NOT launch**; the
  oracle-leaf/value diagnostics (§7) may run at 1-lane scale as a post-mortem,
  results to the maintainer, no new credit read.
- **B5 delta ≤ −hi — NEGATIVE.** D26 stays headline, unqualified. Licensed
  sentence names depth-1, BR, Dose M, the evaluator — never "search". **R3
  does NOT launch**; B5 routes to the §7 value-quality diagnosis (a search
  much worse than its policy means Q̂ anti-correlates with truth), maintainer
  decides any follow-up.
KILL (sufficient): delta ≤ 0 AND d_i ≤ 0 in ≥ 3 of 4 lanes → R3 does not
launch regardless of branch.
README/STATUS obligation: B1 changes the headline row; B2–B5 add a row
carrying the verdict phrase verbatim, headline unchanged; F1–F3 record the
void in STATUS only. No branch leaves README untouched; no branch silently
rewrites it.

**Dose matching, decided up front:** NO dose-matched placebo will run — a
zero-information same-compute arm degenerates to a known-weaker policy and
fails for reasons unrelated to the hypothesis. The compute confound is
addressed by R3's E2 noise dial at screen grade, and **honestly sized
(MF-17): at 2 lanes × 1000, E2 resolves only ≥ ~0.028 — larger than the
+0.025 bar it stands in for. THE PRE-WRITTEN SENTENCE, before data: "a
generic-compute confound smaller than 0.028 survives this chapter UNTESTED."
Upgrade, pre-priced and maintainer-buyable at readout: E2(σ=0.2) at 4 × 3000
= 0.5 ld makes the ±0.02 band a ~2.4σ read.**

### R3 — the mechanism grid (why, not whether). NON-CREDITING THROUGHOUT.
**(MF-7: the r1 "best single dose" letter-bearing read is DELETED. No R3 cell
can produce a credit; any new credit claim — e.g. Dose L looks strong —
requires a FRESH pre-registered credit test on new battles (an R4-family
item, own yaml, own ratification). Dose M's R2 read STANDS and is never
re-read against R3's comparator.)**
**Dose axis:** A0 fresh (8 min), SEARCH@S, SEARCH@M (reused from R2 only if
the sha is unchanged, else re-run and priced), SEARCH@L; 4 lanes × 3000 each.
**PRIMARY (MF-5: the equal-log2-spacing made the r1 OLS slope a two-point
contrast with Dose M weightless, blind to saturation): the TWO SEGMENT
CONTRASTS, each read per lane and aggregated as the equal-weight mean:**
`seg1 = Δ_M − Δ_S`, `seg2 = Δ_L − Δ_M`, band = **+0.0125 per segment** (the
minimum meaningful response: +0.025 across the full ladder), clustered se over
4 per-lane values each. Cells, sides named:
- **T1 DEPTH/DOSE-LIMITED** (upper): seg2 ≥ max(0.0125, 2·se_seg2) — still
  buying at the top. Action: an R4-family pre-reg MAY be proposed; nothing
  launches from this document.
- **T2a RESOLVED-NULL** (MF-6): both segment CIs EXCLUDE +0.0125 →
  licensed bound sentence: *"one-ply search over our own heads does not gain
  ≥ +0.025 more anywhere on S→L (realized ≤ ~2100 leaves/decision at cap
  5184)".* Reachability, stated now: needs clustered se_seg ≤ ~0.006, i.e.
  sd(seg_i) ≤ 0.0125 — possible, not guaranteed; if unreached, T2b is the
  landing cell and NO bound is published.
- **T2b INDETERMINATE**: a CI contains both 0 and +0.0125 → sentence: "the
  dose ladder did not resolve a slope at this power", CI quoted. No bound.
- **T3 VALUE-LIMITED / SEARCH-PATHOLOGY** (lower): either seg ≤
  −max(0.0125, 2·se_seg) — more search made it worse; the classic
  correlated-evaluator amplification signature (Beal/Nau; the named
  DEPTH-HARMFUL analogue). Chapter closes on the diagnosis with §7's
  instruments as evidence — the most informative negative available.
**Evaluator/instrument cells (screen grade, 2 lanes × 1000 each, ±2·binomial
≈ ±0.028 — descriptive, bands read as directional color, never verdicts):**
E2 = V + N(0,σ), σ ∈ {0.1,0.2,0.4} (the compute-confound instrument, §above);
E3 = LOO 3-lane critic ensemble (pure, zero training); MC-leaf at matched
realized-leaf budget (the unbiased corner of the bracket: MC ≫ V → value
ceiling; MC ≈ V → depth/noise); λ-blend, λ ∈ {0.25, 0.5}; oppact ablation
(uniform over legal classes — the first inference-time measurement of the
credited head's contribution); the CONTAINED oracle-team diagnostic (true team
substituted; separate binary, FG-4 disarmed with a loud banner, BARRED from
README/STATUS/headlines — D18-privileged discipline). **The composition
control is DROPPED (MF-9: at measured branch counts, top-24 ≡ top-6 for 93.6%
of pairs, so the N_det=1 arm runs ~4× fewer leaves and the control varies
exactly what it holds); the honesty note stands: "more leaves" vs "leaves
spent on determinizations" is NOT separated in this chapter.** Reading table:
MC≫V → value ceiling (fix evaluator: E3/λ-blend, new pre-reg); V≫MC → noise;
both ≈ policy → depth or stop; both < policy → F-gate territory, not a
finding.

## 5. Pre-registration mechanics (eval-only) — executable, machine-checked
`configs/eval/ch3_rung<N>.yaml`: comment header in the recipe12m style; the
BODY is read by the driver and the grader — it cannot drift from what ran.
Required fields (grader refuses to grade if any is missing): 1 rung/title/
status line; 2 arms (kind, checkpoint paths + sha256, battles, chunks; search
arms: the full dose block — cap, node cap, n_det, branch policy incl.
renormalization, decision rule, tie-break, watchdog constants, placeholder
policy, shared-determinization flag); 3 comparator: fresh (banked requires an
era_attestation block + drift F-gate — unused here); 4 pairing + clustering
unit in words; 5 aggregator + recorded_only list; 6 credit_line verbatim,
asserted byte-equal to a module constant; 7 se_terms
[pooled_binomial_two_sample, paired_clustered, unpaired_clustered], rule:
larger_of; 8 primary/secondary (each letter_bearing: true|false)/falsifiers/
branches with lo/hi/side/action — **the grader machine-checks that branches
PARTITION the real line, no gap, no overlap**; 9 r0_gates (id, script,
threshold, blocking); 10 kill + action each side; 11 dose_matched +
how_we_would_know (§4 R2's clause verbatim); 12 readme_status_obligation per
branch, none absent; 13 ledger + wall projections + lane width; 14
burns_training_seeds: false (asserted — chapter 3 trains nothing).
`scripts/ch3_grade.py`: refuses dirty tree or uncommitted pre-reg; stamps
pre-reg sha256 + git sha into the readout JSON; prints operative bar,
governing se term BY NAME, every branch cut in win-rate units, the landing
branch; reuses `d25_grade.py::se_terms`; ships synthetic known-p tests, one
per branch cell, including the F3 baseline-comparison path.

## 6. New code (all search code under `rl/search/` — the leak grep is one directory)
`rl/search/bridge.py` — battle1 + RSD → `poke_engine.State`; **written from
the poke_engine .pyi/API and OUR encoder semantics only. The foul-play clone
is GPL-3.0 (SF-7): its helpers are consulted as LANDMINE DOCUMENTATION only
and never as an implementation reference; no code is derived from it.** The
Effect→volatile table (§2.5) lives here. `rl/search/determinize.py` — RSD
incl. the NEW bench-species sampler (§3). `rl/search/shadow_battle.py`.
`rl/search/matrix.py` — cell fill, renormalization, L6 mapping law, BR solve,
tie-breaks. `rl/search/agent.py` — `SearchAgent`, `act()` contract, raising
watchdog, `search/*` + `bridge/*` counters. `scripts/ch3_eval.py` — chunked
resumable driver; prints realized usernames; asserts `simulator: 4`; staggers
process starts 20 s; verifies chunk 0 before the next lane starts.
`scripts/ch3_fidelity_check.py` — the FG battery (obs_fidelity_check mould).
`scripts/ch3_grade.py`. One additive `--search` branch on `eval_checkpoint.py`
is the entire allowed diff to the existing eval path; `rl/common/
evaluation.py` and the encoder are untouched (FG-6 proves the latter).

## 7. Value ceiling vs depth ceiling — the instruments in one table
| instrument | where | separates |
|---|---|---|
| Z1 calibration + aleatoric floor | R0, offline | is EV 0.56–0.59 bias or irreducible noise |
| successor-ranking read | R1 harvest, offline | K0-1's proxy vs the capability search needs |
| MC-leaf vs V-leaf bracket | R3 | evaluator BIAS vs estimator/depth |
| E2 noise dial | R3 | information vs compute (the placebo substitute, sized honestly) |
| E3 LOO ensemble, λ-blend | R3 | is the evaluator on the steep part |
| dose segments seg1/seg2 | R3 PRIMARY | dose-limited vs saturated vs pathological |
| oracle-team diagnostic | R3, contained | determinization error vs everything else |
| oppact ablation | R3 | what the credited head buys at inference |

## 8. DO NOT BUILD
1 No patching the vendored Showdown server. 2 No poke-engine search/eval
entry points. 3 No FP-derived code (GPL + purity; landmine reading only).
4 **No model of SimpleHeuristics anywhere inside the agent — no SH features,
no SH rollouts, no priors DERIVED FROM SH-vs-us battles (MF-4 closed that
door), no tuning on the scorer; diagnostics may measure against SH offline,
the agent may never.** 5 No belief-state learning / team prediction. 6 No
wall-clock budgets. 7 No second encoder (fallback only, re-gated). 8 No
training; seeds 66/67, 75/76, 83/84, 93/94 stay held; anything
AlphaZero-shaped is a later chapter. 9 No subprocess-per-rollout sim. 10 No
tree reuse / transpositions / progressive widening in this chapter. 11 No
tuning any search constant on verdict battles. 12 No cross-era ensembling at
R0. 13 No ladder execution without the D7(a) ruling. 14 No re-scoring of
D26's finals. 15 No server battle timer. 16 No silent fallback-to-policy
anywhere in the search path (the watchdog raises).

## 9. Honesty notes (travel with the chapter)
- The forward model averages damage rolls; KO-boundary coins are scored
  deterministically. `ko_disagreement` is measured before any verdict battle
  and travels with every headline sentence; the 2-point expansion is the
  named repair.
- FP's 0.8307 does not transfer to `generate_instructions` (FP never calls
  it) and bundles an eval we may not use. The existence proof funds the
  attempt, not the expectation.
- The SWITCH-target law (uniform over legal bench) biases the search toward
  staying in; named, directional, unquantified until R1.
- OTHER_MOVE mass is renormalized away (no fifth move exists in a
  determinized set); `oppact/other_move_mass` records how much.
- Light Screen and the opponent's trap/recharge lock are unmodellable from
  battle1; frequencies measured at R1 and disclosed.
- "More leaves" vs "leaves on determinizations" is not separated (the
  composition control died in review); a generic-compute confound < 0.028
  survives untested unless the E2 upgrade is bought.
- At n=4, 2·se_clustered is an ~86%-coverage criterion and the floor is the
  real protection — said here, before data.
- R0's ensemble credit, if any, licenses "THESE four checkpoints" only.
- The oppact head is deployed against an opponent it was not trained to
  predict; its SH calibration is measured at R1 before R2 leans on it, and
  its inference-time value is measured (ablation), not assumed.
- Every cost number predating the R1-0 spike is an estimate; the spike's two
  measurements freeze the dose, the F3 baseline and the watchdog by formula.

## 10. Maintainer rulings this design needs (it takes none)
1. **Forward-model admissibility**: poke-engine gen1 as a pure transition
   function inside the pure lane. RECOMMENDATION: ALLOW (a rules engine, same
   category as the vendored sim; the transition API is eval-free and
   separable — a fact about the published API). Fallback if refused: the
   A-sidecar route, pre-specified.
2. **Install mechanics deviation**: `requirements-search.txt` + documented
   `--no-cache-dir --force-reinstall` build line instead of a pyproject pin
   (PEP 621 cannot express the gen1 build flags; the default build is GEN 4;
   the wheel cache ignores config-settings). This deviates from CLAUDE.md's
   pin rule and needs an explicit OK.
3. **Determinization source**: the vendored randbats generator (via
   `randbats_prior` + the new bench sampler) sampling consistent opponents at
   inference — ALLOWED-AND-DISCLOSED recommended. Boundary text: priors
   derived from SH-vs-us battles are FORBIDDEN inside the agent (MF-4);
   self-play-derived priors are in-lane.
4. **K0-2 override ownership** (the only cost-benefit kill; maintainer-only,
   in writing).
5. **D7(a) ladder contradiction** — unresolved on purpose; a B1 forces it.

## 11. Fold log — all 27 MFs, disposition one line each
R1-MF-1/R2-MF-1 exactness claim → restated everywhere incl. B1 sentence;
renormalization pre-registered; retained-mass gate; FG-2k + Z2' added; 2-point
expansion named repair. R1-MF-2 Dose L → top-6 composition fixed, table+chunk
loss re-derived. R1-MF-3/R2-MF-3 F3 → measured-baseline gate, skips excluded.
R1-MF-4 SH-marginal fallback → deleted; self-play marginal + SH-free switch
criterion; ruling text widened. R1-MF-5 slope → two segment contrasts, bands
in effect units. R1-MF-6 T2 → split T2a/T2b; reachability precomputed;
bound only from T2a. R1-MF-7 best-dose credit → deleted; R3 non-crediting;
new credit = new pre-reg. R1-MF-8/R2-SF-1 → 0.0115 two-sample; power table
provenance disclosed. R1-MF-9 → df=3 disclosure block. R1-MF-10 → K0-1
aggregator named (pooled AUC), 0.60 provenance disclosed, successor-ranking
revisit path. R1-MF-11 → F-precedence sentence. R1-MF-12 → B1 qualifiers
mandatory; K0-3 escalation. R1-MF-13 → shared determinizations, stated +
gated. R1-MF-14 → self-contained; inputs demoted to non-normative. R1-MF-15 →
mirror refinement = R4-only, row amended. R1-MF-16 → per-branch R3 actions +
KILL precedence. R1-MF-17 → E2 honestly sized; untested-confound sentence
pre-written; upgrade priced. R2-MF-2 → HP banded to roll interval. R2-MF-4 →
requirements-search.txt + exact command + gen4 attestation row + ruling §10.2.
R2-MF-5 → mapping law table; slot-containment rejection; OTHER_MOVE
renormalize; SWITCH law declared. R2-MF-6 → volatile map asserted exhaustive;
"none" substitution counted; Light Screen named unmodellable, out of FG-2.
R2-MF-7 → cost model corrected; R1-0 end-to-end spike freezes dose/F3/
watchdog; critic-vs-actor citation fixed; batching named load-bearing.
R2-MF-8 → FG-6 field families, measured budget. R2-MF-9 → composition control
dropped, honesty note. R2-MF-10 → watchdog raises; chunk dies; threshold from
spike p50/p100. SFs folded: R1-SF-1 (R3 ledger), R1-SF-2 (2.4 h/seed +
derate), R2-SF-2 (bench sampler is NEW code), R2-SF-4 (top-6 defined),
R2-SF-5 (Dose-L description), R2-SF-7 (GPL — no FP-derived code), R2-SF-9
(ShadowBattle synthesizes available_moves + id inputs), R2-SF-13 (sentinel on
verdict binary). Remaining SFs are review-recorded; none is load-bearing for
ratification.
