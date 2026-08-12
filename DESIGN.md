# DESIGN — the roadmap after the pivot

**Status: r7 RATIFIED 2026-08-07 (maintainer review, same day as drafted) — D10–D17 binding,
all per the inline recommendations: D10(a) M3 is the success claim, D11(a), D12(b), D13(a)
Stage-0 MUST_RECHARGE fix lands and the 0.3890 comparator re-baselines, D14(a), D15(b),
D16(a), D17(a).** r6's D1–D7 remain ratified and still bind wherever r7 does not supersede
them; §8 names exactly what carries. Lifecycle unchanged: each item's pre-registration moves into its config header
(the `configs/showdown_sp12m_v2.yaml` pattern) as it is built, STATUS.md tracks execution,
and this file is deleted once its content has fully migrated.

Self-contained on purpose — a reviewer should need no other file and no prior conversation.
Section numbers from earlier revisions are cited as "r6 §N" where they no longer exist here.

> **§7 is the decision list (D10–D17). Everything before it is the evidence those decisions
> rest on. §2 is the part to argue with first: it defines what "works" means.**

Revision history, condensed. r1–r3 (2026-08-04): the original training-side package —
BC-from-SH warm start (Arm A), faint shaping (Arm B), distributional value (Arm C) — plus the
verified 109k-replay human corpus. r4 (2026-08-04): renamed from `DESIGN_P7.md` on spin-out
into this repo. r5 (2026-08-05): P6 read and undercut the package's premise. r6 (2026-08-05,
RATIFIED, D1–D7): full rewrite against P6 hardened by three review passes — Arm A retired as a
run, Arm C parked, the human corpus promoted to candidate main line, the ceiling arithmetic
re-scoped, "past the clone" corrected to "level with the clone"; then extended 2026-08-05 by
§11 (search, PROPOSED, D8–D9), which the human corpus's failed sizing bars made live.
**r7 (this revision, 2026-08-07): MAINTAINER PIVOT — pure from-scratch self-play in
`gen1randombattle` becomes the main line, chosen for NOVELTY (never demonstrated in gen1; the
nearest existence proof is Huang & Lee 2019 in gen7 at 2–3×10⁸ decisions) rather than for raw
strength, with the Foul-Play/BC chapter banked as eval anchors and a fallback; the chase is
explicitly revocable and §7's D17 states the abandon criterion so that revocability is
honest.** Naming note: P4/P5/P5b/P6 name experiments inherited from the predecessor repo
(`deep-rl-from-scratch`), kept as provenance; artifacts live here.

## 1. Where the project is, and what changed

Task: Pokémon Showdown Gen 1 random battles, battle phase only, via poke-env against a local
Showdown server. Current agent class: PPO, `[512,512]` MLP over an 807-dim hand-written
observation (encoder v2), 10 discrete actions (6 switch slots + 4 move slots), terminal-only
±1 at `gamma = 1.0`. Benchmark opponent: poke-env's `SimpleHeuristicsPlayer` ("SH"), on our
poke-env 0.15.0 build whose setup branch is dead upstream (every number below is against that
build). Locked protocol for every headline number: final checkpoint, deterministic policy,
ties as non-wins, 3 seeds pooled, **3000 battles/seed** per r6's D2c amendment.

The board. Starred rows are NOT locked-protocol — single fit seed and/or n=1000, i.e. probe
reads that are not yet allowed to be headlines.

| result | vs SH | note |
|---|---|---|
| PPO 12M flat / **+LR anneal — best RL** | 0.4330 / **0.4607** | vs-SH-TRAINED |
| PPO 6M annealed (P5b), re-scored at 3000/seed | 0.4308 ± 0.0052 | the D2c re-eval |
| **Scratch self-play 12M, v1 + broken pool** | **0.3800 ± 0.0089** | 2026-08-01 |
| **Scratch self-play 12M, v2 + fixed pool** | **0.3890 ± 0.0089** | Δ +0.009, z +0.72 — NULL |
| BC clone of SH (P4, 813k rows) | 0.4657 | in-repo re-score |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** | 0.486 at n=40k |
| Foul Play + our patches — the teacher | 0.8307* | n=7,200 |
| BC-of-FP, v2 encoder, 180k rows | 0.558* / **0.569*** | final / val-peak epoch |

Two rows do the work in this document: **0.3890** is where pure self-play sits after its one
honest attempt, and **0.489** is what SH itself is worth. Everything the chase is about lives
between them and just past them.

**The ladder translation, which is the reason none of these numbers should be read as
"nearly solved"** (derivation in `prior_work/README.md`, from Metamon Table 2 + Fig 17): SH
scores 39.7% / 41.2% GXE on the gen7/gen9 randbats human ladders, so **0.489 parity ≈ 40%
GXE**, and the published pure-policy randbats field *starts* at 72% (Huang & Lee, Glicko-1
1677). Our best agent projects ~20 Elo BELOW SH. All of these are cross-format
extrapolations — nobody has measured `gen1randombattle` on a human ladder — and D7(a) (ladder
Elo/GXE is the project's success metric) still stands with its EXECUTION deferred until an
agent is clearly past SH.

**What changed on 2026-08-07 is the goal, not the board.** The maintainer's decision, recorded
verbatim in SESSION_LOGS: pure self-play in gen1 "is a more interesting project because it has
never been done; sitting atop already-done BC or supervised training is not as interesting; it
does not need to match or beat Foul Play." The project therefore stops optimizing for the
strongest agent and starts optimizing for a **demonstrated pure-self-play agent**, with the
Foul-Play chapter banked (§6) rather than abandoned.

## 2. What "works" means — the milestone ladder

Novelty needs a bar, or the claim is unfalsifiable. Proposed: four milestones, each read under
the locked protocol at **3 seeds × 3000 battles**, each stated as a pooled point estimate with
the arithmetic that makes it decisive rather than suggestive.

Measurement constants (MEASURED, from P6's variance decomposition and this repo's evals): at
3000 battles/seed the within-seed binomial sd is ~0.0091 and the between-seed component is
~0.006, giving a pooled arm se ≈ **0.006** and, against a comparator measured at matched n,
**se_diff ≈ 0.0089**. Battles, not seeds, are the binding constraint — a fourth seed costs a
training lane and buys the smaller variance component.

| bar | definition | margin over comparator | ties-renormalized Elo vs SH |
|---|---|---|---|
| **M1 — off the plateau** | pooled ≥ **0.4400** | +0.051 over 0.3890 ≈ **5.7·se_diff** | ≈ −20 |
| **M2 — SH-mirror parity** | pooled ≥ **0.489**, 2σ lower bound ≥ 0.4657 | +0.100 over the plateau | ≈ 0 |
| **M3 — past SH** | pooled ≥ **0.510** (> 0.5 with 2σ clear of parity) | +0.021 over parity ≈ 2.4·se_diff | ≈ **+12** |
| **M4 — stretch: reach the clone** | pooled ≥ **0.558** | matches a distilled search teacher | ≈ +46 |

Notes each bar needs:

- **M1's bar is the vs-SH-trained line, not an arbitrary number.** 0.4400 sits just past PPO
  12M flat (0.4330) and past P5b's re-scored 0.4308: an agent that has never seen SH matching
  what SH-trained PPO achieved before the anneal. It is also +0.051 over the 0.3890 plateau,
  where the largest lever this repo has ever credited was +0.051 at 6M (the anneal) and the
  encoder-v2 + pool bundle bought +0.009. **M1 is the go/no-go gate for the whole chase.**
- **M2 is the honest headline if M3 does not arrive.** "A from-scratch self-play agent in gen1
  randbats reaches parity with the standard scripted benchmark" is a true, checkable, novel
  sentence. Its comparator (0.489, n=20k; 0.486 at n=40k) is the best-measured number on the
  board.
- **M3 is the success claim.** vs-SH is ADMISSIBLE as a primary read here, and this is the
  first time that has been true in this repo: SH is **held out of training entirely** (§5), so
  the number measures generalization to an unseen opponent rather than exploitation of the
  training opponent. The argument is `configs/showdown_warmrl_v2.yaml` D-2's, adopted verbatim:
  "Holding SH out makes vs-SH a genuinely HELD-OUT opponent for the first time — which is what
  makes it admissible as the PRIMARY read." **Guard, mandatory at M2 and above:** the
  SH-exploitation falsifier (warmrl F1) — every milestone read above M1 carries a two-orientation
  head-to-head vs at least one non-SH anchor (500/pair/orientation; the +0.018 deterministic-vs-
  sampling seat bias is measured, so pool orientations). A vs-SH number that jumps while the
  anchor head-to-heads stay flat is SH-specific and does not claim the milestone.
- **M4's comparator is not yet protocol-grade.** 0.558/0.569 are single-fit-seed n=1000 probes
  and 0.569 carries a best-checkpoint selection caveat. If M4 is ever in play, the clone gets
  re-scored under the locked protocol first (~tens of minutes; no retraining).

**What the field's evidence says is reachable, at what scale** — stated plainly, because the
ladder is a ladder of *local* firsts and does not touch the published field:

- **M1: no direct evidence either way.** There is no published pure-self-play datapoint in
  gen1 randbats at any scale — that absence is the novelty. Wang's gen4 pure network hit ~0.575
  vs SH at ~6M steps, but it was **trained against SH**, so it bounds nothing here. INFERRED:
  M1 is plausible at 12M–50M *if* signal or structure is the binder; if neither is, it is a
  scale statement and Rung 3 owns it.
- **M2/M3: inside the only existence proof's trajectory, at 10⁸ scale.** Huang & Lee reached
  Glicko-1 1677 in gen7 randbats — roughly **+200 Elo over SH's ~1450–1500 band** — from pure
  mirror self-play at 2–3×10⁸ decisions. Parity and a bit past it are far inside that curve.
  What is NOT measured anywhere is *at what scale* parity arrives; nobody published the
  learning curve. MEASURED counter-datapoint: pokejax, scratch PPO in gen4, ~0.55 vs SH at
  ~378M steps on an n=20 eval — scale alone does not guarantee it, recipe matters.
- **M4: beyond every published gen1 datapoint** (there are none) but ~1/4 of the way to H&L's
  gen7 margin. Not out of reach at 10⁸-class scale; nothing in gen1 says so.
- **The field's floor (72% GXE) is not on this ladder.** Even M4 lands ~25 GXE points below it.
  Say so in any writeup: this chase is about demonstrating the mechanism in a generation where
  it has never been shown, not about entering the published field.

## 3. The evidence base, honestly stated

### 3.1 What we measured, including the null that starts this chapter

**The 12M preview is a clean NULL** (`configs/showdown_sp12m_v2.yaml`, seeds 10/11/12,
pre-registered, all R0 gates passed, R1 learning gate passed early at winrate_anchor 0.94–0.95
by 3.7M): encoder v2 + the fixed self-play pool scored 0.3890 (0.393 / 0.377 / 0.397) against
the 0.3800 record, **Δ +0.0090, se_diff 0.0126, z +0.72 — NOT CREDITED**. The in-training
matched-window read (0.382 vs 0.363 at 6–7.3M) agreed on "small positive, far below credit".
**Bundle caveat, recorded before launch and binding now:** that run changed encoder *and* pool
together, so the null is on the BUNDLE; neither component is individually exonerated.

**The instructive contrast is the point of the whole document.** The SAME encoder v2 bought
**+0.107 win rate** in BC (0.451 → 0.558 at 180k rows, z ≈ 4.8, MEASURED) and **+0.009 ± 0.013**
in scratch self-play at 12M. Representation pays when there is a strong signal to represent;
it does not rescue a sparse-signal bootstrap at 1/20th of field scale. That is a controlled
measurement, not an argument, and it says the binder at 12M is the **signal**, not the
representation — which is what sets the rung order in §4.

### 3.2 The existence proof, and the three deltas we have never run

**Huang & Lee 2019 (IEEE CoG), VERIFIED 2026-08-07** against the paper AND `yuzeh/metagrok`
(MIT, cloned as a sibling; the committed config reproduces the paper's 1,327,618 params exactly
and the released checkpoint loads). The recipe: **pure mirror self-play from random init** —
both seats the same object, no pool, no BC init, no curriculum — **3.84M battles ≈ 2–3×10⁸
decisions, 6 days, ~$91 on GCP**, gen7 randbats, laddering to Glicko-1 1677 / 71.94% GXE.
Caveats the index carries: n=300, one run, one fresh account, no error bar (±2.6pp binomial),
possibly sampled rather than greedy (then a lower bound); "1677 and 72% GXE" is one number
quoted twice; their bot-vs-bot table does not transfer (their opponents are a max-damage bot
and the 2019 pre-Rust ancestor of foul-play).

Three things they did that our null run did not, all **extracted from their code and absent
from the paper**:

1. **Signal.** `gamma = 0.95` plus a **5-term ZERO-SUM shaping**: faint 0.0125, fail 0.005,
   supereffective 0.0025, resisted 0.0025, immune 0.005 — all antisymmetric, hence unfarmable
   in mirror play. Also **no entropy bonus**, no grad clipping, constant lr 2e-4.
2. **Structure.** Not a flat MLP: 128-d entity embeddings, a shared per-Pokémon subnet, a
   DeepSets max-pool over the team, and a **shared per-action scoring head**
   (`[trunk ‖ move_emb ‖ switch_target_emb] → shared MLP → scalar`). Zero precomputed type
   chart — now 2 of 2 published ≥70%-GXE pure-policy agents.
3. **Scale.** 20–45× our 12M budget on the log's reading. **Flagged as unresolved (D-item in
   §4, Rung 3):** if their decision count includes both seats and ours counts only the
   learner's transitions, the real factor is ~10–12×, and a 2× error in Rung 3's target budget
   is ~2.5 days of box time. Resolve from `metagrok` before the budget is set.

Also worth carrying: their **negative** results. Randbats self-play never learned multi-turn
setup (Trick Room used 0.12–0.15 of the time), and 50 iterations of fine-tuning on fixed teams
collapsed randbats play to 15.4% vs its own parent — catastrophic forgetting is a live hazard
in this exact setting.

Second precedent, weaker but same shape: ps-ppo's RL phase is **pure mirror self-play vs the
current policy** after BC-from-a-patched-SH, at a claimed 250M states on one RTX 3090 with
800–2048 concurrent battles across 10 local servers. Its 2102-Elo screenshot corresponds to a
snapshot that does not instantiate, its published win-rate-vs-SH figure has no evaluation code
behind it in 49 commits, and several of its advertised features never fire — so it is an
infrastructure and design reference, never evidence.

### 3.3 Why Arm B's null does not contradict H&L's shaping

Arm B (screened out 2026-08-06, pooled Δ **−0.0004**) was: ONE faint term, ±0.1, symmetric,
**with terminal cancellation** — i.e. exactly potential-based shaping with
Φ = 0.1·(faints_opp − faints_self) — at `gamma = 1.0`, trained **against SH**. The repo's own
rule explains the null: potential-based shaping approximately linear in already-encoded
features is inert (Φ was ≈ 0.6·(obs[2] − obs[1])); the cancellation that made it provably safe
made it provably useless.

H&L's is a different object on four axes: **five** event terms, not one; **not cancelled**, so
policy invariance is deliberately given up; **antisymmetric zero-sum**, which is what keeps it
unfarmable when both seats are the same policy; and at **gamma 0.95**, where a terminal ±1 over
our measured ~25-step episodes is discounted to 0.95²⁵ ≈ **0.28** — comparable in magnitude to
the accumulated shaping mass, so the shaped terms are load-bearing by construction rather than
a perturbation. In mirror self-play a term either seat can farm is neutral in expectation; vs a
fixed scripted bot it is not. **None of that reasoning was available to Arm B, and none of
Arm B's null transfers to it.** (INFERRED, stated as such: the mechanism story is ours; H&L
published no shaping ablation.)

### 3.4 The throughput arithmetic, including a correction

MEASURED: ~500–555 steps/s/lane at 3-wide under encoder v2 (SP preview R0), 573 on the smoke
against a 583 v1 baseline, 733.8 single-lane during migration at 611 dims. Working figure:
**~540 steps/s/lane, ~1,600 aggregate at 3-wide**, loop 94.7–94.8% collect at MLP width.

| budget | per lane at 540 steps/s |
|---|---|
| 12M | 6.2 h (preview measured ~6.1) |
| 50M | 25.7 h |
| 100M | 51 h |
| **250M** | **5.4 days** |

**The correction worth making before anyone specs a rewrite:** H&L's own run averaged
~2.5×10⁸ decisions / 6 days ≈ **~450 decisions/s aggregate** (INFERRED — their decisions/battle
is our estimate). Our box at 3-wide is already several times that in aggregate. **The gap to
their scale is WALL CLOCK PER SEED, not raw speed.** Rung 0's purpose is therefore to turn a
5-day run into an overnight-to-two-day run so the chase fits evening blocks and so more than
one recipe can be tried — not to make an impossible run possible. That reframing is what keeps
Rung 0 from becoming a project of its own.

## 4. The chapter plan — four rungs, cheapest falsifiable first

Ordering principle: the 12M preview says representation was not the binder, so **signal**
(cheapest, most different from anything we have run) goes first, **structure** second, and
**scale** last, carrying whatever credited. **Rungs 1 and 2 run at TODAY'S loop speed** —
3×12M ≈ one overnight at 3-wide. Only Rung 3 needs Rung 0.

### Rung 0 — loop throughput engineering (the enabler; engineering, no compute)

The standalone spec EXISTS: `prior_work/THROUGHPUT_SPEC.md` (2026-08-07). Its headline
finding, from source: **`num_envs` buys zero concurrency — SyncVectorEnv serializes all 8
sub-envs' server round-trips on the main thread, and ~80% of the loop is idle websocket
wait**. The fix is a Stage-2 async collector on the plain-Player path (poke-env's `PokeEnv`
hardcodes `max_concurrent_battles=1`, so the Gym stack cannot be extended — which conveniently
leaves the locked eval path untouched by construction), K=32–64 concurrent battles, batched
inference through the `rl/collect.py` seam (~950 lines, 2–4 evenings), projecting 540 →
~1,400 steps/s/lane with pre-registered gates G1–G9 — including two CRITICAL silent-corruption
hazards it caught in advance (the `old_logp` recompute assumption and a `PoolPlayer` latch
race under concurrent battles). Decomposition experiments E1–E4 (each ≤10 min) come first.

**Do the measurement half first — it is one evening and it decides whether the rest is a day
or a week.** The arithmetic that motivates it: the history-features audit measured
`embed_battle` at **~1.7 ms/decision**; at 540 steps/s/lane that is ~0.9 core-seconds of
encoding per wall second per lane. If that holds end-to-end, **the bottleneck is our Python,
not the Showdown server**, and the cheap wins are batched inference across the 8 envs plus
encoder cost, not more server processes. If it does not hold, the ps-ppo/elitefurretai
concurrency model is the answer. Nobody has decomposed this loop at production width; every
plan built on assuming the server is the wall is currently unsupported.

- **Isolates:** nothing experimental. It is infrastructure and it credits on a stopwatch.
- **Cost:** measurement ~1 evening; cheap wins ~1–3 evenings; a concurrency re-architecture is
  a chapter of its own and is NOT approved by this document (D14).
- **Read:** end-to-end steps/s/lane at `[512,512]` under the production config, on a
  ≥150k-step run, median over the last 90% — never `showdown_throughput.py`'s server-side
  number. **Target: ≥5×**, which puts 250M×3 seeds at roughly one day of box time.
- **Branch on null:** if the loop is already near a hardware wall, Rung 3 is bought in cloud
  wall-clock instead (D15) or capped at 50–100M, and the milestone ladder is read against
  whatever scale is actually affordable — stated in the writeup, not quietly dropped.

### Rung 1 — SIGNAL at 12M (H&L reward design alone)

The single cheapest test of the pivot's premise. Arm = the 0.3890 config **verbatim** except
`gamma: 0.95` and the 5-term antisymmetric zero-sum shaping at H&L's constants. Entropy
coefficient stays at our 0.01 (H&L used none) — a deliberate deviation, recorded, so this rung
is a two-part bundle and not a three-part one; our SP preview's entropy fell 1.88 → ~0.4 and
never approached the 0.15 alarm, so removing the bonus is not obviously safe and is not free.

- **Isolates:** reward/discount design, at fixed representation, fixed opponent scheme, fixed
  budget. The comparator is a run we have already paid for.
- **Cost:** 3 lanes × 12M ≈ **6.2 h/lane at 3-wide** — one overnight — plus finals.
- **R0 correctness gate** (catches the ps-ppo off-by-one class in seconds, as Arm B's did): on
  a random-policy rollout, the two seats' shaping streams must sum to exactly zero
  event-by-event (antisymmetry); each of the five terms must fire at a nonzero, sane rate; and
  faint attribution must be checked against observed faint counts. Also log
  **|shaping mass| / |discounted terminal mass| per episode**: if shaping mass ≫ 0.28 the
  objective has been replaced rather than augmented, which is a finding, not a tuning problem.
- **PRIMARY:** pooled finals vs SH under the locked protocol at 3000/seed, against 0.3890
  **re-evaluated at matched n** (owed, ~tens of minutes, no retraining — the P5b re-eval
  precedent). Credit line unchanged: Δ ≥ +0.025 AND ≥ 2·se_diff, se_diff = larger of
  pooled-binomial and seed-clustered.
- **Falsifier (Arm B's lesson, generalized):** win-rate delta ≤ 0 while the shaped-event
  differentials (faints, resisted/immune hits avoided) improve materially ⇒ objective
  distortion. Kill the rung; do NOT tune the five coefficients — coefficient tuning against a
  distorted objective is how a bar-chaser is built.
- **Branch on null:** signal was not the binder at 12M. Proceed to Rung 2 (structure) rather
  than to scale, and record that H&L's shaping may be a 10⁸-scale effect — a claim Rung 3 can
  test later by carrying it forward regardless of the 12M read (pre-state that carry-forward
  now, so it is not a post-hoc rescue).

### Rung 2 — STRUCTURE at 12M (per-action scoring head + entity embeddings)

Arm = the winner of Rung 1 plus H&L's architecture family: tokenize inside the network (the
21-token reshape in `prior_work/ARCH_SCREEN_SPEC.md` — **no encoder change, no OBS_DIM change,
no re-embed**), shared per-mon subnet, DeepSets max-pool over the team, shared per-action
scoring head over [trunk ‖ action token]. **Explicitly NOT the attention trunk**: the spec
measured a 34.6× CPU train step and projects 205–220 steps/s/lane, which fails the throughput
gate below and doubles Rung 3's wall clock. DeepSets + a pointer head is the cheap two-thirds
of H&L's structure; attention is a later question, if ever.

- **Isolates:** the policy's action parameterization and entity handling, at fixed signal.
- **Cost:** engineering ~2–3 evenings (`rl/networks/`, a `trunk:` key on PPOAgent defaulting to
  "mlp" and bit-identical, the `_orthogonal_init` hazard the spec names), then 3 × 6.2 h — plus
  a **free pre-screen** on the banked tapes (fit the same BC objective per trunk, read
  held-out `val_kl` and agreement; ~18 min/fit at 180k rows). The pre-screen chooses the trunk
  before any RL budget is spent, which is the method ps-ppo itself used.
- **Pre-registered throughput gate (adopted from the arch spec, tightened):** ≥ 450
  steps/s/lane at 3-wide (≤ ~20% loss). A trunk that fails it does not enter Rung 3 regardless
  of its RL read, because Rung 3's budget is denominated in wall clock.
- **PRIMARY / credit line:** as Rung 1, against Rung 1's winner.
- **Purity note, which must be disclosed rather than finessed:** the BC pre-screen reads
  teacher-generated tapes. No teacher weights or data reach the RL agent — but the *choice of
  trunk* is informed by them. §5 defines that as a design-time channel; D11 ratifies it.
- **Branch on null:** structure was not the binder either; the remaining hypothesis is scale
  alone, which is the weakest position this chase can be in and the one D17's abandon criterion
  is written for.

### Rung 3 — SCALE (50M, then 250M-class), carrying whatever credited

- **Isolates:** nothing. It is the existence proof's own variable, and the only one the field's
  evidence positively supports.
- **Cost at today's loop:** 50M = 25.7 h/lane; 250M = 5.4 days/lane. With Rung 0 at 5×: ~5 h
  and ~26 h. **Step 1 is 50M**, which is affordable today and yields this repo's first
  self-play scaling slope (the vs-SH line's was flat 6M→12M = +0.0407, z ≈ 3.2).
- **Reads:** the milestone ladder (§2), plus in-training vs-SH rungs every 100k for curve shape
  only, plus the mandatory non-SH anchor head-to-heads at M2+. Pre-register the 12M→50M delta
  as the secondary that decides whether 250M is bought.
- **Budget precondition:** resolve the decisions-per-step accounting against `metagrok` (§3.2)
  before setting the 250M target; a 2× error is 2.5 days.
- **Branch on null:** see D17.

**Sequencing.** Rung 0's measurement half first (one evening, no tree conflict), then Rung 1
launches, then Rung 0's cheap wins and Rung 2's engineering land in the gaps between runs.
Standing constraint: launches must come from a clean committed tree, so tree edits never
overlap a launch window.

## 5. Purity — what the claim excludes, and why the encoder stays

The claim being chased is "a pure from-scratch self-play agent". That phrase has to be
enforceable or it will erode one convenience at a time.

**A run is PURE iff the trained weights are a function only of (a) random initialization,
(b) experience generated by the agent playing against its own current or past weights, and
(c) the environment (observation, action space, reward).** Concretely EXCLUDED from any run
claiming purity:

- **No BC initialization.** `init_from` pointing at any clone disqualifies the run.
- **No teacher or human data in training** — no Foul-Play tapes, no SH-clone data, no human
  replays, no distillation loss, and specifically **no KL-to-BC anchor** (the `bc_kl_coef`
  machinery stays at its 0.0 default and dormant).
- **No scripted opponent in the training distribution.** SH, Foul Play, MaxBasePower: none of
  them appear as training opponents. Opponents are the agent's own weights, current or pooled.
- **No reward channel derived from another agent's evaluation.**

Explicitly ALLOWED:

- **Scripted and distilled agents as EVAL anchors** — SH (the board), the FP clone, Foul Play
  itself, the SH clone. Evaluation is not training; this is what makes the milestone ladder
  measurable at all, and holding SH out of training is precisely what makes vs-SH admissible
  as a primary read (§2, M3).
- **The observation encoder, including v2 and future feature work.** This is the load-bearing
  argument, so state it fully: **the encoder is part of how the environment describes the
  state, not a prior over how to play it.** It is the same class of artifact as the action
  space and the reward function, both of which every published "pure self-play" system also
  hand-designs. H&L's own system hand-built species/move embedding tables, a DeepSets team
  pooling, and a 5-term shaping — nobody calls that impure, and nothing in the pure-self-play
  literature demands raw bytes. The line that must not be crossed is a feature that smuggles a
  *policy* into the observation: "what would SH do here", an FP-derived value or action
  distribution, a human-frequency prior over moves. Encoder v2's move-effect block and speed
  edge are game mechanics recomputed from poke-env data; they are on the right side of that
  line, and they are also the encoder the 0.3890 comparator was measured under, so keeping them
  costs nothing and changing them costs a re-baseline (D13).
- **Design-time knowledge from outside** — hyperparameters, architectures and reward designs
  read from published work, or screened by BC on banked tapes (Rung 2). These do not enter the
  weights. **Disclosure requirement:** any writeup states that the trunk was chosen by a BC
  screen against a search teacher's data. It is a weak information channel, and pretending it
  is zero would be the kind of quiet claim this project has repeatedly caught other people
  making.

**Fusion is outside the claim.** A self-play run that plateaus may later be compared to, or
fused with, the banked BC line — but a fused agent is a *different* agent, reported under a
different name, and cannot be described as pure self-play. §6 restates this because it is the
single most likely place for the claim to rot.

## 6. The banked chapter — FP/BC artifacts, ON ICE

Nothing is deleted. The Foul-Play/BC chapter produced this repo's strongest agent and its most
reusable infrastructure; it stops being the main line and becomes three things.

**What exists** (all MEASURED, all on disk): the patched Foul Play teacher at **0.8307**
(n=7,200), plus its non-SH head-to-heads (0.876 vs our best RL, 0.872 vs the SH clone, n=250
each) which settled the SH-exploitation question with data; **180,440 rows / 7,200 battles** of
tapes, ids unique, all six fidelity gates passing under BOTH encoders, re-embeddable at ~580
rows/s; the v2 clones at 0.558 final / 0.569 val-peak (probe grade); a donor clone fitted with
the teacher-value critic (held-out value R² 0.661); `configs/showdown_warmrl_v2.yaml` as a
complete DRAFT pre-registration with six maintainer decisions in its header; and the P4-scale
collection GO (~35k battles ≈ 900k rows ≈ **19.7 h at 3-wide**) — **not spent, and not spent
while the chase runs.**

Their three roles:

1. **Eval anchors — the non-SH opponents the self-play agent is scored against.** The FP clone
   (once protocol-graded) and Foul Play itself are the falsifier for SH-specific gains at every
   milestone from M2 up. This is now their primary job, and it is a real one: without them,
   "past SH" is one number against one bot.
2. **The fallback line.** If the chase is revoked (D17), warm-started KL-anchored RL resumes
   from a ratified draft with **zero rework** — the KL anchor code, the critic-warmup constants
   (5 updates at rollout 512, measured), `actor_lr_scale` 0.25, the entropy handoff finding
   (BC-warm starts sit at `loss/entropy` 0.063 and fail the old [0.2, 1.0] R0 band from update
   1) and the D-1 donor gates are all in place.
3. **Possible later fusion — quarantined.** Comparison is free and encouraged (head-to-heads
   between the self-play agent and the clone are the most informative single number this
   project could produce). Fusion is a separate, separately-named chapter (§5).

Also banked and useful regardless of line: the pool-eviction fix (span-preserving thinning),
the encoder fingerprint stamped into `meta.yaml`/`bc_metrics.json`, the arch-screen spec, the
distillation-objectives survey, and `prior_work/HISTORY_FEATURES_DESIGN.md` with its live
encoder bug (D13).

Seed hygiene: 0–13 are spent; **14–22 stay reserved for the warmrl draft** while it is on ice;
the self-play chase claims **23 upward**. Distinct seeds across lanes AND arms is a landmine,
not a preference.

## 7. DECISIONS FOR THIS REVIEW (D10–D17)

**RATIFIED 2026-08-07: all eight adopted per recommendation — D10(a), D11(a), D12(b),
D13(a), D14(a), D15(b), D16(a), D17(a).**

Numbering continues from r6/§11's D1–D9. Each with options and the author's recommendation.

**D10 — Ratify the milestone ladder, and name which bar is "works".** *(a)* As written in §2
(M1 0.4400 / M2 0.489 / M3 0.510 / M4 0.558, all at 3 seeds × 3000, with the non-SH anchor
guard from M2 up), with **M3 as the success claim**, M1 as the go/no-go gate, and M2 as the
reportable headline if M3 does not arrive. *(b)* Same ladder, **M2** as the success claim —
parity is a defensible novelty bar and it is 2× cheaper in scale terms. *(c)* Different bars.
**Recommendation: (a).** M2 as the *claim* invites the reading "matched a weak bot"; M2 as the
*headline-if-M3-misses* is honest either way, and the cost difference between them is Rung 3's
second half, which D17 governs anyway.

**D11 — Ratify the purity definition (§5), including the design-time disclosure.** *(a)* As
written. *(b)* Stricter — no BC pre-screen on teacher tapes at all, choose the trunk from
published work only. *(c)* Looser — allow a scripted opponent as a small fraction of training
("it's just exploration"). **Recommendation: (a).** (b) costs a free, informative screen and
buys purity theatre, since reading H&L's architecture off their code is the same channel with
worse resolution. (c) is the erosion this section exists to prevent: a mixed-opponent run is
not the thing that has never been done, and it also destroys the held-out-SH argument that
makes vs-SH admissible as the primary read.

**D12 — Rung ordering.** *(a)* Rung 0 in full first, then 1→2→3. *(b)* **Rung 0's measurement
half first (one evening), then Rung 1 immediately at today's loop speed, with Rung 0's cheap
wins and Rung 2's engineering landing between runs.** *(c)* Skip to scale — buy 50M on the
existing recipe and see. **Recommendation: (b).** Rungs 1–2 need no throughput work, and the
one-evening decomposition is what tells us whether Rung 0 is a day or a week — that number
should exist before it is scheduled. (c) spends 26 h/lane to re-measure a recipe whose 12M read
we already have, with no new hypothesis attached.

**D13 — Encoder: does v2 freeze, and does the Stage-0 fix ride along?** The encoder stays v2
under §5's argument; the live question is the **MUST_RECHARGE bug** — `Effect.MUST_RECHARGE` is
structurally always 0 in v1 AND v2 (0/2,427 measured, against 185/2,427 for the bool poke-env
actually sets), so recharge and partial-trap turns encode as all-zero move blocks with no
indicator of why. In gen1 randbats those are Hyper Beam, Wrap/Fire Spin, sleep and freeze —
exactly the states a self-play agent must learn around. The fix is 2 dims. **The cost is the
comparator:** any semantics change re-baselines 0.3890, i.e. 3 × 6.2 h to re-run Rung 1's
control. *(a)* Land Stage-0 now, re-run the 12M control (one extra night), run the whole chase
on one encoder. *(b)* Freeze at v2/807 for the chase; defer Stage-0 to the next semantics
change. *(c)* Land it and accept a cross-semantics comparator. **Recommendation: (a) if the
maintainer will spend the night, else (b). (c) is not acceptable** — it re-opens exactly the
confound the fingerprint stamp was built to catch. **The 22-dim history block does NOT ride
along either way**: it is a separate bundle with its own screen and would confound Rung 1.

**D14 — Throughput-engineering scope.** *(a)* Measurement only — decompose the loop at
production width, no loop changes. *(b)* Measurement plus the cheap wins it points at (batched
inference across envs, encoder hot paths, additional server processes). *(c)* Full
re-architecture on the ps-ppo/elitefurretai model — N servers, centralized batched inference,
hundreds of concurrent battles. **Recommendation: (a) now, (b) authorized on its numbers,
(c) only if Rung 3's 250M step is actually bought.** Target for (b): ≥5× end-to-end
steps/s/lane at `[512,512]`. Note (c) is a chapter, and this document does not approve
chapters by implication.

**D15 — Compute policy: local box or the ~$91-class cloud option.** H&L's entire run cost ~$91
for 6 days. *(a)* Local only; cap Rung 3 at whatever fits evening blocks. *(b)* **Rent a
many-core CPU box for Rung 3 only**, reproducible from config + seed, results copied back.
*(c)* GPU. **Recommendation: (b), gated on Rung 0's decomposition.** The loop is ~95% collect
at MLP width, so a GPU buys ~nothing unless Rung 2's trunk credits and the update becomes
50–60% of the loop; core count is the lever. Two notes that make this easier than the r6-era
version of the same question: the chase uses **no dataset**, so the unlicensed-data
governance constraint does not apply at all, and CPU-only is a repo convention because MPS is
flaky, not because rented CPUs are disallowed.

**D16 — Opponent distribution: keep the pool, or match H&L's pure mirror?** Neither published
pure-self-play success used an opponent pool (H&L: both seats one object; ps-ppo: mirror vs the
current policy), and Metamon's naive latest-checkpoint self-play arm underdelivered. Our pool
is now correct (eviction fixed) and the 0.3890 comparator was measured with it at
`pool_size 20 / latest_prob 0.8`. *(a)* Keep the pool as-is. *(b)* Match H&L — pure mirror,
`latest_prob 1.0`. *(c)* Treat it as a rung. **Recommendation: (a).** It is the comparator's
configuration, it costs nothing measurable (the fixed pool's 12M read was within noise of the
broken-pool run), and it hedges cycling — a risk neither existence proof had to survive at our
budget. Record that this is a deviation from both precedents. (c) is a third arm the ladder
does not have room for.

**D17 — The abandon criterion (the chase is revocable; this is what makes that honest).**
Propose: **the chase is called off when Rung 1 and Rung 2 have both read out AND Rung 3's first
scale step (50M) has completed, and the pooled locked-protocol final is still below M1
(0.4400).** That is three pre-registered hypotheses plus a 4× scale-up failing to move a
from-scratch self-play agent past the vs-SH-trained line. Two additional triggers, either
sufficient: cumulative chase compute > **20 lane-days**, or calendar > **8 weeks** of evening
blocks without M1. On abandon: the warmrl line resumes from its ratified draft with zero
rework, and the self-play result is written up as a **measured negative with a scale bound
attached** — "pure self-play in gen1 randbats does not reach the vs-SH-trained line at ≤50M
decisions under these three recipes" is a real, citable result, and the honest one. *(a)* Adopt
as written. *(b)* Adopt with different thresholds. *(c)* No pre-stated criterion — decide in
the moment. **Recommendation: (a).** (c) is how a chase becomes a sunk cost; the maintainer's
own framing ("we can call it quits later") is worth exactly as much as the criterion written
before the money is spent.

## 8. Standing constraints — by reference, not repeated

These bind unchanged; they are listed so the reviewer knows nothing was quietly dropped.

- **Locked eval protocol** (final checkpoint, deterministic, ties as non-wins, 3 seeds pooled,
  3000 battles/seed per r6 D2c) and the **credit line** (pooled Δ ≥ +0.025 AND ≥ 2·se_diff,
  se_diff = larger of pooled-binomial and seed-clustered). `eval/win_rate` comes from
  env-supplied `info["outcome"]`, never the sign of the return.
- **Pre-register every experiment in its config header before launching** — arms, R0 gates,
  PRIMARY with an explicit credit line, secondaries, falsifiers, and the branch on each
  outcome. Every rung in §4 gets one.
- **All of CLAUDE.md's landmines**, especially: distinct `--seed` per lane AND arm (username
  collisions kill lanes with a misleading timeout); launcher liveness checks battle PROGRESS,
  not run-dir existence; stagger lane starts (SIGSEGV in torch lazy init); commit docs BEFORE
  launching and launch from a clean tree; `simulator: 4` in the gitignored server config.
- **Any `OBS_DIM` or observation-semantics change invalidates every existing checkpoint** and
  re-baselines every comparator measured under the old semantics (D13). The encoder fingerprint
  in `meta.yaml`/`bc_metrics.json` is the guard — check it, do not assume the env var was set.
- **Showdown evals are UNPAIRED and not reproducible** — per-battle return correlation ≤ 0.04
  across all 21 run-pairs measured in P3; buy precision with battles, not with pairing
  machinery, and not primarily with seeds.
- **D7(a) stands:** ladder Elo/GXE remains the project's ratified success metric, with vs-SH as
  the internal board; ladder EXECUTION stays deferred until an agent is clearly past SH — i.e.
  until M2/M3, at which point it becomes the natural confirmation of the chase.
- **r6's retirements stay retired:** Arm A (BC-from-SH warm start) as a run, Arm B (screened out
  at −0.0004), Arm C (distributional value, parked — and doubly moot at gamma 0.95 only if the
  return distribution stays trivial, which Rung 1's shaping would change; if Rung 1 credits,
  re-read r6's unparking conditions before assuming it is dead).
- **§11's D8/D9 (search) are UNRATIFIED and now moot for the main line** — the FP teacher work
  they authorized already happened as the banked chapter (§6); the P4-scale GO stays unspent.

## 9. Risks, and what would falsify this line

1. **The plateau may be a pure scale wall** — the field's only existence proof lives at 10⁸,
   and if signal and structure both null out, the chase reduces to buying wall clock. D17 is
   the response; Rung 0 and D15 are the mitigations.
2. **Every rung is a bundle.** Rung 1 changes gamma and adds five terms; Rung 2 changes
   pooling, embeddings and the head. A positive result DEMONSTRATES, it does not ATTRIBUTE —
   the sp12m_v2 precedent applies: attribution ablations only get paid for on success.
3. **Rung 1 deliberately abandons policy invariance.** Non-cancelling shaping means the
   objective is no longer "win"; the zero-sum antisymmetry is the only thing keeping it
   unfarmable, and it is unfarmable only because both seats share weights. The falsifier is
   pre-stated and the response to it is to kill the rung, not to retune constants.
4. **Self-play pathologies with no external anchor**: cycling (the pool hedges it), and H&L's
   own measured failures — never learning multi-turn setup, catastrophic forgetting under
   distribution narrowing. The eval anchors (§6) are the detector; they are also the only
   reason a self-play number means anything.
5. **Wall clock vs evening blocks** is the practical risk, not FLOPs: a 5-day lane cannot be
   babysat in short sessions, and a lane that dies at hour 60 costs more than the experiment.
   Checkpoint cadence and per-lane progress verification matter more at Rung 3 than anywhere
   this project has been.
6. **The novelty claim is a claim about the literature, and our index is not a systematic
   search.** The defensible sentence is "no counterexample exists in our index", not "it has
   never been done" — and the index has been wrong twice this month (a guessed paper title for
   H&L; "Foul Play supports gen1randombattle", which was true from source and false in
   practice). Before any writeup, the gen1-pure-self-play claim gets one deliberate
   adversarial search against it.

## 12. Post-50M lever queue (PROPOSED 2026-08-09 — D18–D20, ratify at the 50M readout)

**Status: RATIFIED 2026-08-11 (maintainer, "ratify 12") — D18–D22 binding.** Adopted
with the recommended sequencing: **D22 plateau diagnostics FIRST** (also explains the
50M s35/s37 seed divergence), **then D18 privileged critic** (novelty verified
2026-08-10), then D19/D21 as singles per their notes; D20 stays post-chase. Drafted
2026-08-09–10 from three maintainer-supplied external advisories triaged against the
encoder source and the record (SESSION_LOGS entries, incl. corrections). Numbering
continues from D17; the section number continues past r6's retired §10–11 (§11 D8/D9
remains unratified and moot).

**D18 — PRIVILEGED (ASYMMETRIC) CRITIC rung — recommended first after the readout.**
CTDE (AlphaStar-style): during self-play training the critic's input is widened with the
opponent seat's TRUE own-side state; the actor's observation is unchanged.
- EVIDENCE (measured on the live 50M lanes at 15M): `loss/explained_variance` plateaus
  at 0.56–0.59 on all three seeds — ~40% of return variance unexplained, at gamma 1.0 /
  terminal-only ±1 / no team preview (5/6 opponent mons hidden at turn 1). Part is
  irreducible gen1 RNG; the hidden-team part is what this lever removes. The 50M lanes'
  EV trajectory is the free control curve.
- WHY CHEAP HERE: the critic is ALREADY a separate stack (repo contract, deliberate
  deviation from H&L); the privileged vector never enters the obs space, so no OBS_DIM
  change, no checkpoint invalidation, no comparator re-baseline; the locked eval
  protocol exercises the actor only, so the eval path is untouched by construction.
- PURITY: clean under §5 — the opponent seat's state in mirror/pool self-play is our
  own process's environment state; no teacher, no scripted opponent. One disclosure
  line in any writeup.
- DESIGN SKETCH: privileged input = actor obs 828 ‖ opponent seat's own-side blocks
  (reuse `_fill_mon`/`_fill_move`; no new features). Plumbing: per-battle registry
  passes seat B's own-side vector into seat A's `info` through the collection path
  (~2–3 evenings, Rung-2-scale). The SAME plumbing serves D19 — build once.
- RUNG SHAPE: one lever (critic input only; same actor/trunk/recipe as the 50M
  winner), read at 12M vs the matched-budget standing best under the standard credit
  line, own pre-registered config header. Secondary: EV delta vs the control curve.
- FALSIFIER, PRE-STATED: EV jumps but win rate flat/negative ⇒ the critic fits
  information the policy cannot exploit and the advantage signal degraded — kill the
  rung, do not tune around it.
- BIAS QUESTION RESOLVED (third advisory, 2026-08-10): Baisero & Amato, "Unbiased
  Asymmetric RL under Partial Observability" (AAMAS 2022, arXiv:2105.11674) — a
  privileged-ONLY critic V(s) is biased (Thm 4.2, and Monte-Carlo targets do not fix
  it), but a critic conditioned on the actor's observation PLUS privileged state,
  V(h,s), is unbiased incl. for bootstrapping (Thm 5.1). BINDING DESIGN CONSTRAINT:
  the critic input is actor-obs ‖ privileged block — the privileged block may never
  REPLACE the actor's view. (Our sketch already satisfies this.) Honest residue: the
  theorem's h is the full action-observation history; our obs is an approximate
  belief state standing in for h — near-Markov by construction, noted, not proven.
  NOVELTY CHECK DONE (2026-08-10, external deep-research pass, archived at
  prior_work/RESEARCH_2026-08-10_prior_art_and_levers.md — UNVERIFIED citations):
  adversarial search across arXiv/ICML/NeurIPS/ICLR/AAMAS/IEEE-CoG/RLC/GitHub/Smogon/
  the PokeAgent Challenge retrospective found NO privileged/asymmetric critic in any
  Pokemon RL system (Metamon: shared-trunk symmetric; VGC-Bench: symmetric twin nets;
  H&L, Wang: symmetric PPO) — claim NOT REFUTED. Phrasing rule, binding: "no
  documented instance found," never "proven first." Additional refs banked: Lyu et
  al. JAIR 2023 (history-state values unbiased), Informed AAC (arXiv 2509.26000 —
  partial privilege can match full state; start compact: species+sets), and a
  cautionary null (asymmetric SAC underperforming in memory settings — the effect is
  largest when hidden info dominates returns, which turn-1 gen1 satisfies; size NOT
  guaranteed, and never tested at γ=1.0 terminal-only).

**D19 — AUXILIARY OPPONENT-TEAM PREDICTION rung.** CE head over species for unrevealed
opponent slots, trained against ground truth (free in self-play); forces an explicit
belief state instead of hoping one emerges from win/loss. One head + one loss term on
D18's plumbing. Purity-clean, no obs change. Sequence AFTER D18's read (attribution).
CAVEATS from the 2026-08-10 research pass: the head's gradient flows into the ACTOR
trunk (actor-side change — unlike D18 it can shift actor behavior directly, so its
rung stands alone and never bundles); and it is partially redundant with D18 (critic
USES hidden info, head learns to INFER it) — if D18 credits, re-scope D19's question
before spending lanes. Supporting prior art: agent-modeling-as-auxiliary-task (arXiv
1907.09597), DouZero+ hidden-hand prediction.

**D20 — the v3 ENCODER BUNDLE (post-chase; one re-baseline pays for everything, D13
cost known and paid once already for v1→v2/808).** Contents: Light Screen — a POKE-ENV
PARSER problem, not a tuple edit (gen1 `|-start|...Light Screen` maps to
`Effect.UNKNOWN` in 0.15.0; known since 2026-07-30); real partial-trap fix
(`PARTIALLY_TRAPPED` is structurally dead — gen1 traps surface via `|cant|`, same bug
class as MUST_RECHARGE); toxic/confusion/disable counters + which-move-disabled;
Substitute remaining HP; summed-team-HP scalars both sides (matters more under DeepSets
max-pool, which cannot reconstruct sums); minor volatiles (Bide/Rage/Transform/Mimic/
Mist); and the parked 22-dim history block RIDES ALONG so one re-baseline covers all.
PRECONDITION: extend `obs_fidelity_check` to the crit/SE/miss/`|cant|` paths (its
coverage gaps are documented) and verify each field actually populates before encoding
it. DECLINED, recorded so they do not resurface: running obs normalization (breaks
frozen comparators; obs are hand-normalized by design), Wang's PP/HP binning
(information already present continuously), standalone sleep-counter one-hot (scalar
present; ruled inert under the Arm-B linearity rule).

**D21 — RECIPE/SELF-PLAY HYGIENE POOL (optional, sequenced after D18/D19; refreshed
from the third advisory 2026-08-10, λ note amended same day).** The demoted recipe
rung's candidate contents, updated: ROLLOUT SIZING restated in the right currency —
episodes/update (~30 today at 1024 steps; target 100–300; scale via batch-size-
invariance, Hilton et al.); GAE λ as a pre-registered SWEEP {0.95, 0.98, 1.0}, NOT an
assumed 0.75 — the 2026-08-10 research pass reverses the earlier low-λ advice for OUR
regime (terminal-only ±1 + short ~30-step episodes → MC return unbiased with bounded
variance; Alpha-Mini found λ=1.0 optimal for exactly this reason; the λ≈0.75 systems
are longer-horizon); LR annealing (Wang's gen4 thesis carries the only controlled
ablation in this literature: 0.55→0.80 val win rate — single thesis, but a real
ablation); plus three cheap additions with on-policy evidence — KL-based early
stopping on epochs, entropy COEFFICIENT SCHEDULING high→low (entropy does double duty:
exploration AND mixed-strategy exploitability control — consistent with our measured
seat asymmetry; decay too fast and exploitability rises), and PFSP-style win-rate-
prioritized pool sampling (favor near-50% opponents; D16's comparator note applies —
any sampling change is a lever, not a default). Each is a separate pre-registered
lever; bundling them re-creates the factorial hazard the ladder rule exists to
prevent.

**D22 — PLATEAU DIAGNOSTICS (Stage 0 of the post-50M program — run BEFORE choosing
among D18/D21 orderings; offline + one cheap probe, no new training lanes).** From the
2026-08-10 research pass, adopted because it redirects everything after it. On the
EXISTING 50M artifacts, measure: (1) value explained-variance trajectory (already
logged); (2) policy-entropy trajectory (logged); (3) WEIGHT-NORM trajectory across the
~100 checkpoints/lane (Juliani & Ash: plasticity loss under on-policy domain shift
correlates with growing parameter norms — self-play drift IS continual domain shift);
(4) dormant-neuron fraction + feature effective rank on tapes; (5) an EXPLOITABILITY
PROXY — train a fresh best-response vs the frozen final checkpoint (short lane, eval-
side artifact, purity-irrelevant) and read its win rate. DECISION RULE, pre-stated:
rising weight norms + flat win rate → plasticity ceiling → the REGENERATIVE
(L2-toward-init) regularizer rung jumps the queue (the ONE plasticity family validated
on-policy; ReDo/hard resets stay banned); flat EV + low effective rank →
representation/optimization ceiling → D18 first (as queued); best-response wins easily
+ entropy collapsed → equilibrium/exploitability ceiling → PFSP first, and an
R-NaD-style dynamics regularizer (DeepNash, Science 2022) becomes the named
larger-change candidate. Otherwise → D18 as queued. CONFIRMED-DECLINED by the same advisory's negative-
results list (independent corroboration, recorded): RND/curiosity, recurrence-first,
periodic resets/ReDo, exotic optimizers, PopArt/symlog at bounded ±1 returns,
reconstruction aux losses. Two-hot/categorical value head: stays PARKED (Arm C) — the
advisory grades PPO-specific evidence weak; the Farebrother non-stationarity argument
is noted for whenever Arm C is re-read. SimBa block (obs-norm+residual+LayerNorm):
rides only with a future trunk change, never alone mid-chapter.


## 13. The 250M budget memo (PROPOSED 2026-08-11 — decision inputs only, no launch)

**Status: DRAFTED 2026-08-11 (evening, D18 lanes running). Nothing here is a
decision: Rung 3's own pre-registration makes the 12M→50M delta the purchase
input and D18's readout reshapes the lever question. This section makes the
250M quote HONEST when the chapter asks for it. It supersedes Rung 3's stale
cost line ("250M = 5.4 days/lane" assumed ~540 steps/s; measured reality
below) and discharges its budget precondition (metagrok accounting).**

**Seat accounting, RESOLVED 2026-08-11 (prior_work/README.md, H&L entry).**
H&L's learner trained on BOTH seats of every battle (paper Algorithm 1 "2m
self-play matches"; code path verified). Their 3.84M battles ≈ ~2.3×10⁸
learner-consumed transitions ≈ ~1.15×10⁸ per-seat decisions. **A 250M-step
run of ours ≈ 1.1× their learner diet and ≈ 2.2× their per-seat experience**
— 250M is scale parity-to-excess with the only published ≥70%-GXE pure
self-play agent (budget parity, not result parity; theirs is gen7).

**Wall-clock at MEASURED rates** (350-390 steps/s 3-wide, ≥400 solo, ~300-315
at 5-wide, entity trunk, this box):
- 250M × 3 lanes, 3-wide @ ~350/s: ~8.3 days/lane ≈ **25 lane-days** — alone
  exceeds the ENTIRE 20 lane-day abandon trigger (D17), and ~2.5× the ~9-10
  lane-days remaining (chapter ~10-11 spent through D18).
- 250M × 1 lane, solo @ ~400/s: ~7.2 days ≈ 7 lane-days — fits the remainder
  but is single-seed, which the 50M seed-fragility adjudication makes weak
  evidence by this repo's own standards.
- Post-throughput IF THROUGHPUT_SPEC's ~2.6× Stage-2 projection transfers
  (E1-E4 measurement evening, D12b, still owed): 3-wide ~910/s → ~3.2
  days/lane ≈ **9.5 lane-days for 3 lanes — fits the remaining budget.**
  E1-E4 is therefore the GATING ITEM for any in-cap 3-lane 250M.

**Paths if 3 lanes are wanted and E1-E4 under-delivers** (maintainer calls,
listed not recommended): (a) renegotiate the 20 lane-day trigger (it is an
abandon trigger, not a budget line — but renegotiating a pre-stated criterion
after the money wants spending is exactly what D17 warns about; say so in the
log if done); (b) rent compute — in charter scope, H&L's whole run was ~$91
on 2019 GCP, a modern many-core box for ~10 days is roughly $200-500 (needs a
real quote); OPEN QUESTION for ratification: does rented compute count
against the lane-day trigger, whose purpose is opportunity cost of the chase?
(c) 2 lanes as a middle — still ~17 lane-days pre-throughput, over remainder.

**What 250M buys, honestly.** The 12M→50M credited delta was +0.029 over a
4.17× scale-up; 50M→250M is another 5×. But D22's closed diagnosis (EV
plateau 5M→50M, critic srank collapse) says the plateau is representational,
not experience-starved — naive scale-up is the wrong buy, which is WHY D18
ran. 250M is only worth pre-registering while carrying a credited lever:
- D18 CREDITS → the next scale step is a priv-critic 50M (~5 lane-days at
  measured rates, fits remainder); 250M sits behind ITS readout + E1-E4.
- D18 NULL/NEGATIVE → regenerative-L2 at 12M (~2 lane-days) is next; 250M
  recedes until some lever moves the 12M number again.
Either branch: no 250M pre-registration before (1) a credited lever at 50M,
(2) E1-E4 measured, (3) the lane-count/cap/rent question above answered.
