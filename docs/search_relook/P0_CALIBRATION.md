# PHASE 0 — CALIBRATION AND DE-RISKING

**Status:** MEASUREMENT, not a pre-reg. Nothing here credits anything. It is the
gate `ENGINE_SEARCH_DESIGN.md` §7 Phase 0 asks for, and its one binding output
is the **stop rule on Form B** (depth-2 with sampled chance), §2.

**Run:** 2026-09-10, fully offline — no server, no websocket, no battle — on a
**CONTENDED** box: five `ch3_eval` jobs, the `engine_pe_s66` `rl.train` lane, two
detached ladder queue scripts and the Showdown server were live throughout, load
average 8-9 on 14 cores. Every wall-clock number below is therefore
**descriptive only, never a budget number** (`S1_S2_SCREENS.md:152-159`). The one
place a timing *ratio* is quoted (§7) is defensible only because both sides of it
were measured on the same loaded box within the same hour.

**Code:** `scripts/search_p0_calibration.py` (driver: `stage-a`, `stage-b`,
`combine`) and `scripts/search_p0_write_spike.py` (the throwaway write side).
No file under `rl/search/`, `rl/envs/`, `rl/agents/` or `configs/eval/` was
touched — Phase 0 is "no new production code".
**Data:** `results/search_p0/p0.json` (gitignored, like all of `results/`).

**Journey position.** JOURNEY 11.5 / 14, via `ENGINE_SEARCH_DESIGN.md`. Phase 0
only; Phase 1 is not started.

---

## 1. Method

### 1.1 Two stages, because no single env has both simulators

`CLEANUP E1` / `STATUS.md` watch items: `poke_engine` lives in
`pokemon-showdown-rl`, `pkmn_gen1` in `pkmn-engine-port`, and nothing has both.
So:

| stage | env | what it does |
|---|---|---|
| `stage-a` | `pokemon-showdown-rl` | runs the **existing** `rl.search.matrix.solve_decision` at dose **M** on the selected harvest roots; dumps `row_ev`, `ev_matrix`, the realised L6 columns and their weights, the determinizations, and the root `ObservableState` |
| `stage-b` | `pkmn-engine-port` | rebuilds each root as 384 engine bytes, samples chance, values every child with the same lane's critic, reports `sd(margin)` |
| `combine` | either | merges to `p0.json` |

Both stages read `results/ch3_r1/harvest_s6{2,3,4,5}.pkl` only — never
`harvest_priv_*` (FG-4). Checkpoints are the four sha256-pinned 12M lanes in
`configs/eval/ch3_rung0.yaml`, i.e. the same object `S1_S2_SCREENS.md` measured
its median margin on. Encoder flags `POKEMON_RL_ENCODER_V2=1
POKEMON_RL_ENCODER_IDS=1` on both stages; torch threads 1 (a) / 2 (b);
everything under `taskpolicy -b`.

### 1.2 The corpus and the restriction

Design §7's own hedge: the σ-margin read must "run on a stubbed subset:
no-status, no-boost, no-transform roots, where the write side is provably exact
and W-ACTIVESTATS cannot contaminate the read."

`restricted_ok()` implements that, and **widens** it, because three more fields
carry hidden counters the write side would otherwise have to sample and thereby
contaminate the very thing being measured. A root is inside the subset iff it is
non-aliased **and**:

- neither active has a **status**, any non-zero **boost**, or the **TRANSFORM**,
  **CONFUSION**, **SUBSTITUTE**, **REFLECT**, **LEECH_SEED**, **FOCUS_ENERGY**
  or **PARTIALLY_TRAPPED** effect;
- neither active is **preparing** or **must_recharge**;
- **no mon anywhere on either side is asleep** (W-SLEEP's hidden turns-left would
  enter the instant a bench mon switches in);
- the root is neither **force_switch** nor **trapped** (a different matrix shape
  — `matrix.py:24-28` gives those a single `none` column).

Counts are in §3.1. Two draws are taken, and they are different objects:

- **plain** — 50 per lane evenly strided over the non-aliased pool with
  `np.linspace`, exactly as `scripts/ch3_r1_spike.py` and
  `search_s1_s2_screens.py` draw theirs. This is the design's "~200 harvest
  roots" read literally, and how many of *those* survive the restriction is the
  headline the brief asks for.
- **restricted** — 50 per lane strided over the restricted pool, so the σ read
  gets its full n instead of only the survivors. **The σ measurement runs on this
  draw**; the top-k measurement is reported on both.

### 1.3 The write-side spike: what the exposed surface allows

**The question "can the exposed Python surface build a mid-battle state at all?"
is answered YES**, and that is a Phase-0 finding in its own right. What made it
possible, all already exported by `engine/pkmn_gen1/src/python.rs`:

- `pkmn_gen1.pokemon_record(species, level, moves, ivs, evs)` → the 24-byte
  `Pokemon` record, built by `team.rs::PokemonSet::to_bytes` (`python.rs:159-175`);
- `pkmn_gen1.Battle.from_bytes(b)` — wraps 384 arbitrary bytes with **no
  validation** (`python.rs:290-297`), which is exactly the hole a spike needs;
- `Battle.bytes()`, `Battle.choices(p, req)`, `Battle.update(req1, c1, req2, c2)`;
- `pkmn_gen1.Tables.encode(state)` (`pyencode.rs:170-180`) — the **same Rust
  encoder the collector uses**, driven from a hand-built `ObservableState` dict
  (`observe.rs`), with tables from `rl.envs.engine_tables.build_tables()`;
- `species_names()` / `move_names()` / `max_pp()` for the id maps.

So the spike assembles the 384 bytes **in Python**, transcribing `layout.rs`'s
offsets into `search_p0_write_spike.py`. The module docstring lists every field
it **sets** and every field it **defaults**; repeated here because it is the
whole basis on which the σ number can be trusted:

**SET** — `B_TURN`, `B_RNG`; per side `S_ORDER` (identity with `order[0]` swapped
to the active, as `switchIn` does, `mechanics.zig:234-236`); per stored
`Pokemon`: `P_STATS` (**ours**: the request's exact `stats`; **theirs**:
`PokemonSet{ivs:[30;5], evs:[255;5]}`, which design §2.3 shows is the
determinizer's max-DV model bit-for-bit), `P_MOVES` ids **and** pp (a revealed
foe move at `max_pp − observed uses`, the A-1a rule), `P_HP`, `P_STATUS`,
`P_SPECIES`, `P_TYPES`, `P_LEVEL`; per `ActivePokemon`: `A_STATS` (equal to the
stored stats, which is **exact on this subset** — no boost and no status on
either active means `switchIn`'s output *is* the stored stats and
W-ACTIVESTATS cannot bite), `A_SPECIES`, `A_TYPES`, `A_BOOSTS` = 0,
`A_VOLATILES` = 0, `A_MOVES` = the stored slots.

**DEFAULTED, and therefore declared** — `B_LAST_DAMAGE` = 0 (family
**W-LASTDMG**; a Counter in a child reads zero damage), `B_LAST_MOVES` = 0 (same
family), `S_LAST_SELECTED_MOVE` = 0 and `S_LAST_USED_MOVE` = 0 (family
**W-LASTMOVE**; a Mirror Move in a child sees nothing), and every hidden volatile
counter = 0 (which is not a stub on this subset: the restriction removes every
root that has one).

One correction the spike had to make and Phase 1 will too: **poke-env resets a
fainted mon's `max_hp` to 100** while the request's `stats.hp` stays
authoritative. 1,785 of 80,376 own-side mon-slots in the harvest (2.2%) show
`stats.hp != max_hp`, and **every one of them is fainted**. The spike takes
`stats.hp` as max HP and writes `hp = 0` for a fainted mon; anything else raises.

### 1.4 Reading an engine state back, and the L-BOUNDARY rule

A child's observation is built by **copying the root's `ObservableState` and
overwriting only what one ply can change**, which is what design §1.3's
L-BOUNDARY demands:

- **our side** is read exactly from the engine — every slot's HP fraction
  (`hp/max_hp`), fainted, status; the active slot; the active's boosts,
  volatiles and charging flag; and the active's live move slots with their
  engine PP;
- **their side** keeps the root's information boundary. The active's HP comes
  back through **Showdown's own percentage grain**, `ceil(100·hp/maxhp)/100`
  (`track.rs:28-38`), not the exact determinized integer. An unrevealed bench mon
  stays absent from the opponent block until the transition switches it in — at
  which point it is appended as newly revealed, with its determinized species,
  level and types, exactly as the protocol would reveal it;
- **opponent move slots** carry only the *revealed* moves, in reveal order, with
  PP decremented by what the engine actually spent. The prior conditioning and
  slot fill are left to `encoder.rs::opponent_move_slots` in Rust — the same
  contract `scripts/engine_p1.py` uses, and for the same reason (importing the
  rule into the harness would make it unfalsifiable);
- `aliased` is derived from the engine's own hard-lock set
  (`Volatiles::forced()`, `layout.rs:200-203`), which is precisely poke-env's
  single-offered-move alias; `force_switch` from the request the update returned.

Two things follow, and both are stated rather than relied on. (a) Everything held
at the root's value is **chance-invariant within a cell** — the column fixes
which opponent move was used — so holding it cannot inflate or deflate σ.
(b) The child projection has **no oracle**: §1.5's gates validate the *root*
projection bitwise, and the child path reuses that same code, but nothing
independently checks a child. That is Phase 1's R1-E, not Phase 0's.

### 1.5 Three self-checks the spike earned

These are not R1-E. They are what a Python spike can check for free, and they
are the reason the σ number is worth reading at all.

- **S-0** — run the **Rust** encoder on the root `ObservableState` built by
  `engine_p1.state_from_battle` from the rehydrated harvest battle, and compare
  bitwise to the harvest row's own `obs`, which the **Python** `embed_battle`
  produced live at collection time. This re-checks gate P-1 on a new corpus.
- **S-1** — the real write-side gate: build the 384 bytes, hand them to the
  engine, read them straight back through the child projection, encode, and
  compare bitwise to the same harvest `obs`. Any write-side or reader bug shows
  up here.
- **mask parity** — the engine's own `choices("p1", "move")`, mapped back
  through `order`, against the harvest's action mask. This is R1-E leg C in
  miniature, and leg C is a **hard stop** below 99.5% in the design.

### 1.6 The σ-margin protocol

For each restricted root, at dose **M** (`n_det = 4`, the same four RSD
determinizations `solve_decision` drew, replayed from the same
`decision_rng(checkpoint_seed, battle_index, turn, decision_index)` key), with
the **same rows** (the harvest mask), the **same L6 columns and weights**
(`col_classes` / `col_w` re-derived and asserted equal to the solve's own
`search/col_classes`):

```
child(a, c, d, s, f) = update(state(d), a, c ; seed(f, c, d, s))
cell(a, c, d)        = (1/S) Σ_s v(child(a, c, d, s))
row_ev(a)            = Σ_c q̃(c) · (1/D) Σ_d cell(a, c, d)      # matrix.py:269-270
margin(f)            = top1(row_ev) − top2(row_ev)
```

`S` is samples per `(row, col, det)`, exactly as design §5.1 writes it, over
`S ∈ {1, 2, 4, 8, 16, 32}` **nested as prefixes** of one S=32 draw (so every `S`
level still gets `R` independent families, and the levels are correlated with
each other by construction — stated, and irrelevant to the gate, which reads one
`S` at a time). `R = 20` independent chance-seed families, the design's floor.
`v` is the lane's own critic on the Rust-encoded child; a terminal child is
±1 / 0 without asking the critic, as `matrix.py:117-130` does.

**CRN-1**, verbatim from design §1.2: *"the chance seed is a pure function of
`(decision key, col, det, sample index)` and **never** of the row."* The `crn`
arm implements exactly that. The `nocrn` arm is the same code with the row index
mixed into the seed — a matched pair differing in exactly one term, drawn
independently rather than resampled, so the comparison is a real measurement and
not a bootstrap.

### 1.7 One reference the design forced, and stage a did not produce

Stage a runs the **as-is** leaf encoding — the R2-credited object, and the right
baseline for the *margin scale* the stop rule divides by. But design §1.1 defines
Form A as like-for-like against **`det_blind`**, and the engine spike's child
projection is det_blind by construction (§1.4). Comparing argmaxes against the
as-is solve would therefore mix the simulator swap with the encoding swap, and
`DET_BLIND.md:234-255` measured the encoding swap **alone** at an 11.4% flip
rate. So the agreement leg gets its own reference:
`search_p0_calibration.py detblind-ref` re-solves the same roots with
`leaf_view=public_view(battle)` and changes nothing else. §3.4 reports against
that; `p0.json` carries both, labelled `_ASIS` and `_DETBLIND`.

### 1.8 One optimisation, and it is a memo rather than an approximation

A child's
value is a function of its observation alone, and the observation reads only
bytes `0..370` — the party records, the active blocks, the order and the turn.
`B_LAST_DAMAGE` (370), `B_LAST_MOVES` (372) and the advanced PSRNG seed (376) are
hidden and never encoded. So two chance samples that landed on the same public
state share a value **exactly**, and are computed once. Gen 1 has 39 damage
rolls, so a cell's 640 draws collapse hard; measured 6.8× end-to-end. Same key,
same 828 floats, same critic.

---

## 2. THE STOP RULE — verdict

> **Design §7 Phase 0, verbatim:** *"If σ-margin at `S = 32` with CRN-1 still
> exceeds `0.5 × median(margin)`, sampled chance cannot resolve a decision at any
> affordable dose and **Form B does not get built**."*

| | value |
|---|---:|
| `median(margin)`, dose-M poke_engine solve, restricted subset (n = 287) | **0.03280** |
| stop-rule threshold, `0.5 ×` that | **0.01640** |
| **`sd(margin ǀ S = 32, CRN-1)`, mean over roots** | **0.00835** |
| ratio to threshold | **0.509** |
| same, median over roots | 0.00624 (ratio **0.381**) |

> ## **THE STOP RULE PASSES. σ-margin at S = 32 with CRN-1 is 0.00835, which is
> ## 0.51 × the threshold of 0.01640. Form B is NOT killed.**

It passes on the mean-over-roots statistic and on the median-over-roots
statistic, so the branch does not depend on that choice. **σ-margin first crosses
`0.5 × median(margin)` at `S = 16`** (mean; `S = 8` on the median) — and that
`S` is what sets the real depth-1 speedup, §7.

Two things the verdict does **not** say, and both belong next to it:

- The design's **own dose-choice rule** in §1.2 is tighter than its stop rule:
  *"Choose the smallest `S` with `sd(margin) ≤ 0.2 × median(margin)`."* That
  target is **0.00656**, and `S = 32` does **not** reach it (0.00835). σ scales
  as `1/√S` to within 1% over the top of the measured grid (the S=16→32 step is
  ×0.704 against `1/√2 = 0.707`), so the extrapolation is safe:
  **`S ≈ 52` per (row, col, det) for the design's own rule.**
- The verdict is measured on the **restricted subset only** (§1.2), which is
  45.3% of the non-aliased corpus. The excluded half is systematically *messier*
  — status, boosts, force-switch, recharge — and there is no reason to assume the
  margin scale or the chance variance are the same there. **This gate licenses
  Form B; it does not license skipping R1-E.**

---

## 3. Measurement (1) — σ-margin calibration

### 3.1 The corpus, and how much of it survives the restriction

Measured over all 13,702 harvest rows (`results/ch3_r1/harvest_s6{2,3,4,5}.pkl`):
**13,396 non-aliased**, of which **6,065 (45.3%) are inside the restricted
subset**. Reasons for exclusion, as a % of the 13,396 (a root can trip several):

| reason | count | % |
|---|---:|---:|
| opponent active has a status | 4,445 | 33.18 |
| own active has a status | 2,807 | 20.95 |
| `force_switch` | 2,018 | 15.06 |
| own active has a non-zero boost | 1,118 | 8.35 |
| a mon **anywhere** on the opponent's side is asleep | 1,023 | 7.64 |
| opponent active must recharge | 761 | 5.68 |
| opponent active has a non-zero boost | 532 | 3.97 |
| own active must recharge | 126 | 0.94 |
| opponent active confused | 102 | 0.76 |
| opponent active preparing | 43 | 0.32 |
| own active preparing | 4 | 0.03 |
| `trapped` | 3 | 0.02 |
| own active has Reflect | 1 | 0.01 |
| own side asleep anywhere | **0** | 0.00 |

**The brief's question, answered literally: of a 200-root stride of the
non-aliased pool, exactly 100 survive the restriction — one half.** Saying it
loudly, as asked: **the σ-margin gate below is measured on a corpus that excludes
54.7% of real decisions, and it excludes them non-randomly.** Every field that
makes a root hard — status, boosts, the status×boost intersection W-ACTIVESTATS
is wrong on, the hidden sleep and confusion counters, the force-switch request
shape — is exactly what got cut. That is the design's own instruction (§7: "run
it on a stubbed subset… where the write side is provably exact"), and it is the
right call for a *calibration*, but the number is a **lower bound on the noise a
real depth-2 search would face**, not an estimate of it.

(Own-side sleep at 0 is not a bug: a sleeping own mon is a locked turn, which the
harvest marks `aliased`, and non-aliased rows are the whole corpus here. §2.5's
"own active asleep 48" counts aliased rows too.)

The σ measurement ran on **288 roots** — the 200-root restricted stride plus the
88 non-overlapping survivors of the plain stride — 51,537,920 engine updates in
860 s. One root has a single legal action and has no margin; it is dropped, as
`S1_S2_SCREENS.md:146-149` drops its 19.

### 3.2 The write side worked, and it is bitwise-checkable

| gate | result |
|---|---|
| **S-0** — Rust encoder on the root `ObservableState` vs the harvest's own Python-encoder `obs` | **288/288 bitwise identical**, max abs difference exactly 0 |
| **S-1** — build 384 engine bytes, read them back, re-encode, vs the same `obs` | **236/288 bitwise (81.9%)**; **own half 288/288 bitwise**; mean **0.188 dims differ** per root, max 2; **max abs difference 0.0100** |
| **mask parity** — the engine's own `choices("p1","move")` vs the harvest mask | **288/288 (100%)** |

S-1's entire residual is one thing and it is the predicted thing: **W-HP**, the
opponent's HP percentage grain. `max |Δ| = 0.0100` is exactly one percentage
point, and it only ever appears on opponent HP dims. `DET_BLIND.md:280` priced
W-HP at 0.558 dims/root on the full corpus; here it is 0.188 dims/root, smaller
because the restricted subset has a different revealed-mon mix. **Our own side
round-trips bit-for-bit on every root**, which is the claim the stat model (§2.3)
had to support.

Mask parity at 100% is worth stating against the design's own bar: R1-E leg C is
a **hard stop below 99.5%**. On the restricted subset the spike is at 100%.

Two child-side counters, both declared rather than swept: over 51.5M children,
**2,309 (0.0045%)** had Transform fire, and the spike's child projection does not
model Transform's stat/type copy (it keeps the root's base stats). 133,468
children switched the opponent to a previously-unrevealed mon, which the
projection **does** model (it appends the mon as newly revealed).

### 3.3 σ-margin vs S, with and without CRN-1

`R = 20` independent chance-seed families per root; each cell is the mean of `S`
samples per (row, col, det) at `n_det = 4`; `sd` is across families, then
averaged over the 288 roots.

| `S` | **sd(margin) CRN-1** | median | p90 | sd(margin) no CRN | **variance saved by CRN-1** | argmax agreement vs `det_blind` |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.04026 | 0.02851 | 0.08495 | 0.04800 | ×1.42 | 0.7472 |
| 2 | 0.02996 | 0.02220 | 0.06111 | 0.03713 | ×1.54 | 0.7990 |
| 4 | 0.02248 | 0.01666 | 0.04625 | 0.02868 | ×1.63 | 0.8375 |
| 8 | 0.01657 | 0.01180 | 0.03453 | 0.02190 | ×1.75 | 0.8576 |
| 16 | **0.01186** | 0.00869 | 0.02467 | 0.01595 | ×1.81 | 0.8764 |
| 32 | **0.00835** | 0.00624 | 0.01695 | 0.01177 | **×1.99** | **0.8967** |

*(the "variance saved" column is `(sd_nocrn / sd_crn)²`; the threshold line
`0.5 × median(margin) = 0.01640` sits between S = 8 and S = 16.)*

**CRN-1 is worth a factor of two in variance, and it is now measured rather than
assumed.** Design §1.2 flagged it explicitly as *"a heuristic, not an identity —
the engine consumes rolls in an order that depends on both actions, so identical
seeds do not guarantee identical shared events — and it must be measured, not
assumed."* At `S = 32` sharing the chance seed across rows halves the variance of
the margin, i.e. **CRN-1 is worth 2× the samples, free.** The benefit *grows*
with `S` (×1.42 → ×1.99), which is the signature of a genuine common-component
cancellation rather than a small-sample artefact.

### 3.4 The sampled solve agrees with the enumerated one at 89.7%

This leg needed its own reference and got one (§1.7). Design §1.1 defines Form A
as like-for-like against **`det_blind`** on poke_engine, and the engine spike's
child projection *is* det_blind by construction — so the agreement number had to
be taken against a `det_blind` solve, not against the as-is solve stage a ran.
`scripts/search_p0_calibration.py detblind-ref` re-solves the same 288 roots with
`leaf_view=public_view(battle)` and nothing else changed.

Two checks that the reference is the right one:

- **det_blind vs as-is flips the argmax on 10.76%** of these roots, against
  `DET_BLIND.md:234-255`'s **11.4%** on the full 13,396. Independent corpus,
  same answer.
- **det_blind's median margin is 0.03432 vs as-is 0.03280** — a 4.6% difference,
  so the stop rule's threshold is not sensitive to which encoding sets it. So is
  the *engine* arm's own median sampled margin: **0.03327 at S = 32**, and flat
  across the whole S grid (0.03704 → 0.03327), which also says the noise is not
  inflating the median margin at these doses.

With that reference:

> **At `S = 32` with CRN-1 the sampled engine solve picks the same action as the
> exact-enumeration `det_blind` solve on 89.7% of decisions** (86.3% without
> CRN-1; 74.7% at `S = 1`).

That lands **right on Phase 2's proposed ≥ 90% argmax-agreement target and well
clear of its 85% hard floor** — measured before Phase 2 starts, on a corpus
Phase 2 will reuse. It is the strongest single piece of evidence that the write
side and the simulator swap are sound, because the two paths share *nothing* but
the determinizations, the columns and the critic.

---

## 4. Measurement (2) — top-k retained mass

**What §5.3 literally asks for cannot be measured at Phase 0.** Its item 3 is
"the fraction of decisions where the **depth-2 winner** was outside the depth-1
top-`root_k`", and depth-2 does not exist. So three measurable prunings are
reported instead, each named for the design knob it prices. All on the 200-root
plain draw (the representative corpus), restricted-subset figures alongside.

Shape first, and it matches the design's own constants exactly: **6.670 legal
rows** per decision (design §2.5 quotes 6.601 on the full corpus and 6.67 on the
100M lanes) and **4.185 realised columns** (design §4.2's 4.19).

### 4.1 Branch mass — the truncation `top_branches = 6` actually costs

| `top_branches` | retained branch mass (mean) | p10 | min | argmax change vs 6 |
|---:|---:|---:|---:|---:|
| 3 | 0.9657 | — | — | **8.0%** |
| **6 (the credited dose)** | **0.9943** | 0.9821 | 0.9531 | — |
| 12 | 0.9995 | — | — | **1.0%** |

**`top_branches = 6` is within 1.0% of the 12-branch answer and retains 99.43% of
chance mass.** This is the number design §1.2's estimator comparison needed and
did not have: poke_engine's truncation bias is **small**. Set against §3.4, at
`S = 32` the sampled estimator differs from enumeration on **10.3%** of
decisions while doubling `top_branches` differs on **1.0%** — so the design's
recommendation survives its own test: *"For depth 1, at a matched leaf count,
poke_engine's estimator is strictly better."* **The engine wins depth-1 on wall
clock alone, not on estimator quality.**

### 4.2 Row pruning by the policy prior — this is the `child_k` question

§5.3: *"`child_k` prunes the child's rows the same way, **by the child's own
policy prior** (a second pre-pass at every child is not affordable)."* Measured
one ply up, on the root: keep the top-`k` rows by the masked policy prior, then
take the depth-1 argmax among them.

| `k` | argmax change vs all rows | mean row_ev lost | row_ev lost when it changed |
|---:|---:|---:|---:|
| 3 | **15.0%** | 0.00736 | 0.04906 |
| 4 | **11.5%** | 0.00637 | 0.05537 |
| 6 | **4.0%** | 0.00019 | 0.00478 |
| all | 1.0% (the **tie floor**) | 0 | 0 |

The `all` row is not zero because `row_ev` ties get broken in prior order rather
than index order; 1.0% is therefore a floor on every cell above, so read the
cuts as **14.0% / 10.5% / 3.0%**. On the restricted subset: 17.4 / 10.8 / 3.8%
against a 0.7% floor.

**`child_k = 3` throws away the depth-1-best row on one decision in seven, and
when it does the cost is 0.049 of row_ev — six times the S=32 sampling noise.**
That is a real price on a knob the design currently proposes without one. At
`child_k = 6` it is 3% and nearly free, but 6 ≈ the mean legal row count, so it
prunes almost nothing.

### 4.3 Row pruning by the depth-1 pre-pass — the `root_k` question

Keeping the top-`root_k` rows by depth-1 `row_ev` cannot change the *depth-1*
argmax (it is rank 1 by construction), so the measurable quantity is the
**row_ev gap between the last kept row and the best excluded one** — the size of
the depth-2 correction that would have to occur for the cut to have cost the
decision.

| `root_k` | decisions needing no cut at all | gap p10 | **gap p50** | gap p90 |
|---:|---:|---:|---:|---:|
| 3 | 8.0% | 0.00002 | **0.01829** | 0.08603 |
| 4 | 16.0% | 0.00000 | **0.01273** | 0.09358 |
| 6 | 41.0% | 0.00000 | **0.00297** | 0.05026 |

**Put this next to §3.3 and it is a warning.** `sd(margin | S=32, CRN-1)` is
**0.00835**. At `root_k = 4` the median gap is **0.01273** — only 1.5× the noise
of the very estimator doing the pruning — and the **p10 gap is 0.00000**, i.e. on
at least a tenth of decisions the pre-pass ranks the boundary rows within
floating-point noise of each other. **Root pruning at `root_k ∈ {3,4}` is not
safe against its own estimator's noise at any `S` Phase 0 measured.** Phase 3
should either raise `S` at the pre-pass specifically, or expand ties, or set
`root_k` ≥ 6 and accept that it prunes little.

### 4.4 Column pruning by `q̃` — nearly free

| `k` columns kept | retained opponent-action mass (mean) | p10 | argmax change vs all |
|---:|---:|---:|---:|
| 3 | 0.9869 | 0.9568 | **0.0%** (restricted subset 1.74%) |
| 4 | 0.9975 | 0.9934 | **0.0%** (restricted subset 1.39%) |
| 6 | 1.0000 | 1.0000 | 0.0% |

There are at most 5 realised columns (4 move classes + SWITCH), so `k = 3` is the
only real cut, and it keeps **98.7% of the opponent-action probability mass** and
changes **no** argmax on the plain draw. **Column pruning is the cheap axis; row
pruning is not.**

---

## 5. Measurement (3) — W-ACTIVESTATS incidence

**Not re-measured.** `ENGINE_SEARCH_DESIGN.md` §2.5 already has it, measured on
the same 13,702-row harvest:

| | count | % of 13,702 |
|---|---:|---:|
| **opponent** active (PAR\|BRN) **and** a non-zero stat stage | **310** | **2.26** |
| **own** active (PAR\|BRN) **and** a non-zero stat stage | **148** | **1.08** |

That is the exact intersection on which rule W-ACTIVESTATS (§2.6) is wrong —
`(stored stats, boost stages, status)` does not determine `ActivePokemon.stats`
because gen 1 applies the status divisor to the *already-modified* stat while a
boost recomputes from the *stored* one, so Agility-then-Thunder-Wave and
Thunder-Wave-then-Agility have identical public descriptions and differ by 4× in
Speed. Outside that intersection the rule is exact.

Phase 0 adds one thing to §2.5's number: the σ subset **excludes the whole
intersection by construction** (no status *and* no boosts on either active), so
nothing in §3 below is contaminated by W-ACTIVESTATS. That was the point of the
restriction.

---

## 6. Measurement (4) — `last_selected_move` in poke-env 0.15

Installed version confirmed **0.15.0**
(`/opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env-0.15.0.dist-info/METADATA`).
The class moved in 0.15: it is `poke_env/battle/pokemon.py`, not
`poke_env/environment/`.

| engine field | poke-env 0.15 | verdict |
|---|---|---|
| `S_LAST_USED_MOVE` (183) | **`Pokemon.last_move` → `Optional[Move]`** (`pokemon.py:1123-1132`), a scan over `self.moves` for `Move.is_last_used` (`move.py:434-436`), set in `Pokemon.moved()` (`pokemon.py:474-475`) off the `\|move\|` handler (`abstract_battle.py:727,737,739`), cleared in `switch_out()` (`pokemon.py:617-618`) | **available by identity** |
| the charging move | **`Pokemon.preparing_move` → `Optional[Move]`** (`pokemon.py:1238-1244`), set by `Pokemon.prepare()` (`pokemon.py:505-513`) off `\|-prepare\|` (`abstract_battle.py:1012-1023`) — and `prepare()` *constructs* a `Move` when the id is unknown, so identity is always there. `Pokemon.preparing` (`:1222-1228`) is the derived bool the design doc was looking at | **available by identity** |
| `S_LAST_SELECTED_MOVE` (182) | **nothing.** No `last_selected` / `order_history` anywhere in the package; the `BattleOrder` is written to the socket (`player/player.py:349-352`) and dropped, and `AbstractBattle.__slots__` has no slot for it. The `\|cant\|` handler reads `pokemon, _ = event[2:4]` and **never looks at `event[4]`** (`abstract_battle.py:742-744`) | **not stored** |
| must-recharge | `Pokemon.must_recharge` → `bool` only (`pokemon.py:1168-1178`) | bool only — but Hyper Beam is the format's only recharge move, so the identity is free |

Also found: `AbstractBattle._replay_data: List[List[str]]` (`abstract_battle.py:106,146`)
is appended as the **first statement** of `parse_message` (`:565-566`), before the
ignore-list check, unconditionally and regardless of `save_replays`. The full
split protocol log **is** scannable on a live battle (private attribute, no
public property, never trimmed).

**Consequence for W-LASTMOVE, priced against the actual pool.** The only two
consumers of 182/183 that fire in `gen1randombattle` are Sky Attack's charge
release (8 pool species) and Mirror Move (4). PS's gen-1 Mirror Move reads the
foe's **last used** move (`showdown/data/mods/gen1/moves.ts:527-537`), which is
`last_move`. The charge release reads the preparing move, which is
`preparing_move`. Dig / Fly / Solar Beam / Razor Wind / Skull Bash, Thrash /
Petal Dance / Rage / Bide, Wrap / Bind / Fire Spin / Clamp, Metronome / Sleep
Talk / Copycat are all **zero** species in the pool. So:

> **On the LIVE path, W-LASTMOVE shrinks to the foe's *selected* move on a turn
> that produced no `|move|` line**, which gen 1 emits as
> `|cant|p2a: X|par` / `slp` / `frz` / `flinch` with **no move name**
> (`showdown/data/mods/gen1/conditions.ts:39,74,95,177,202`). That identity is
> genuinely not on the wire — `_replay_data` cannot recover it either — and
> **nothing in the pool reads it**. Our own 182 is exactly known if the player
> wrapper stores the `BattleOrder` it just sent: a one-line addition on our side,
> not a missing observation.
>
> **On the HARVEST path W-LASTMOVE does not shrink at all.** `freeze_battle`
> carries `must_recharge` and `preparing` as **booleans**
> (`rl/search/harvest.py:51-52`) and `moves` as `[(id, current_pp)]` with no
> `is_last_used` flag (`:53`), so `last_move` is unrecoverable from a snapshot
> too — not just the preparing identity. Any harvest-replay gate (R1-E) must
> declare 182 **and** 183; the live agent need declare neither.

Two gotchas that travel into Phase 1's write side:

1. **Switch-in clearing differs.** The engine clears `S_LAST_USED_MOVE` for
   **both** sides on any switch-in (`mechanics.zig:240-241`); poke-env clears
   `_is_last_used` only on the mon that **leaves**, on its own side
   (`pokemon.py:617-618`). The bridge must zero both sides' 183 on any switch-in
   rather than trusting `last_move` verbatim.
2. **The Sky Attack release turn does not update `last_move`** — poke-env
   special-cases `[from] lockedmove` / `[from] Sky Attack` with `use=False`
   (`abstract_battle.py:604-611`), so `last_move` stays as set on the charge
   turn, which happens to be the right answer here. That hardcoded set covers
   Sky Attack only; a gen-4 Dig/Fly release would fall through to the `else` at
   `:702-715`, log "Unmanaged move message format received" and double-deduct PP.
   Moot for gen 1, a live landmine if this code is reused for gen 4.

---

## 7. What this means for the block estimate

### 7.1 The measured cost, and where it actually goes

Per child, isolated on the same contended box (`scratchpad/micro.py`, 4 cells ×
4,000 updates; **descriptive only**):

| term | µs/child | |
|---|---:|---|
| `Battle.from_bytes` + `Battle.update` | **2.34** | the engine itself, through PyO3, including its two internal `choices()` legality calls |
| `Battle.bytes()` read-back | 0.66 | a fresh 384-byte copy per call |
| `child_state` dict, in Python | **66.21** | **the bottleneck** |
| `Tables.encode`, Rust | 21.53 | almost all of it `parse_state` walking the Python dict |
| critic forward, batched (1 thread, batch ≈ 400) | 43.41 | |
| **total, uncached** | **134.14** | |

Against poke_engine measured **on the same box in the same hour**:
**980.7 µs/leaf** (383.95 ms/decision at 391.5 leaves/decision, dose M, n = 388).
S1's clean-box figure was 65-68 ms/decision, so this box is running ~5.7×
inflated — consistent with `S1_S2_SCREENS.md`'s 6.3-6.6× and the reason **no
absolute number here is a budget number.**

Two conclusions, and the second is the one that matters:

1. The like-for-like contended ratio is **980.7 / 134.1 ≈ 7.3×** for a
   *Python-loop* engine path. (The end-to-end stage-b figure of **16.7 µs/child**
   is not comparable: it includes the value memo of §1.6, which exists only
   because sampled chance revisits public states — a mean of 12,944 distinct
   children per root out of ~179,000 samples. poke_engine's 6 branches have no
   such redundancy.)
2. **87 of those 134 µs — 65% — are Python dict construction and dict parsing
   that Phase 2 deletes outright.** The engine transition plus read-back is
   **3.0 µs**. So design §4.2's target of **5.7 µs/row for engine + tracker +
   encoder is credible**, and the 134 µs here is a spike artefact, not an engine
   cost. Phase 2's batched Rust leaf path is where the entire speedup lives;
   nothing can be inferred about the engine's ceiling from a Python loop.

### 7.2 The honest depth-1 speedup is ~4×, and the design should say so

poke_engine at dose M spends **3.506 leaves per (row, col, det)** (391.5 leaves ÷
6.670 rows × 4.185 cols × 4 dets) — the top-6 retention plus the KO-roll 2-point
expansion. The engine spends `S`. At design §4.2's 37.2× per-leaf throughput
(212 → 5.7 µs), the depth-1 speedup is `37.2 × 3.506 / S`:

| `S` | what it buys | leaf ratio vs poke_engine | **depth-1 speedup** |
|---:|---|---:|---:|
| 8 | — | 2.28× | 16.3× |
| **16** | **σ ≤ 0.5 × median margin (the stop rule)** | 4.56× | **8.2×** |
| 32 | argmax agreement 89.7% vs `det_blind` | 9.13× | 4.1× |
| **≈52** | **σ ≤ 0.2 × median margin (the design's own dose rule)** | 14.8× | **2.5×** |

> **Design §4.2 says "State the 3× until P0 says otherwise." P0 says: at the
> design's own dose rule (`S ≈ 52`) it is 2.5×; at the stop rule's looser bar
> (`S = 16`) it is 8.2×; at the dose that actually reproduces the enumerated
> answer 9 times in 10 (`S = 32`) it is 4.1×. Quote ~4× with the dose named, and
> never quote 17×.**

The 17× figure is arithmetically correct only at matched leaf count, and matched
leaf count is exactly what sampled chance cannot have.

### 7.3 Phase 1: still 3-4 blocks, but the *shape* of the risk changed

**What P0 retired.** The largest unknown in Phase 1 was whether a mid-battle
`Battle` can be constructed at all — §2.1 records that "there is no way to
construct a mid-battle `Battle` from a public view. That is the write side, and
it does not exist." It exists from Python today, via `from_bytes`'s total absence
of validation, and §3.2 shows the result round-trips **bitwise** through the
engine and the Rust encoder on the restricted subset, with **100% mask parity**.
The stat-model identity of §2.3 is confirmed, not assumed. That is a real
de-risking: the "we cannot do this" branch is closed.

**What P0 did not touch, and it is most of the work.** §8's list. The restriction
excludes 54.7% of roots and every one of those is a Phase-1 family:
W-ACTIVESTATS (the status×boost intersection, 2.26%/1.08%), W-SLEEP, W-CONF,
W-REQ's force-switch shapes (15.06% of roots), the hard-lock action mapping. The
tracker (`SideTracker::from_root`) is untouched — the spike hand-rolls its
projection in Python and has **no oracle for the child side** (§1.4b). And the
spike duplicated `layout.rs`'s offsets in Python with no test tying the two
copies together, which is precisely the drift hazard Phase 1's Rust mutable
writers exist to prevent.

> **Verdict: 3-4 blocks still looks right, and the honest point estimate moves
> toward 4, not 3.** The reason is not that the write side is harder than
> thought — it is easier — but that P0 proved it on the half of the corpus where
> it was already provable, so none of R1-E's difficulty has been absorbed.

**Concurrency note, recorded because it affects how this section should be
read.** While P0 ran, a **parallel session was already building Phase 1** in the
same working tree: `engine/pkmn_gen1/src/layout.rs` gained `PokemonViewMut` /
`ActiveViewMut` / `SideViewMut` / `BattleViewMut`, alongside new `spec.rs`,
`engine/pkmn_gen1/tests/write_side.rs`, `scripts/search_r1e_gate.py` and
`docs/search_relook/R1E_GATE.md`. **None of it touched these numbers**: the
importable `pkmn_gen1.cpython-313-darwin.so` is dated 12:25:12, hours before
stage b, and stage b stamped `engine_sha 9b88fd6c5467f703c38951d5b2e8a660314d410b`
into `p0.json`; the `layout.rs` diff is 334 insertions and **zero deletions**, so
every offset this spike transcribed is still the offset `layout.rs` declares.
But it does mean the 3-4 block figure above is a *prospective* estimate of work
that is already partly done elsewhere, and R1-E's real difficulty should be read
off `R1E_GATE.md` when it lands, not off this section.

**Phase 2: 2-3 blocks, unchanged, and now better-targeted.** §7.1 says 65% of the
per-child cost is marshalling, so the batched Rust leaf path is the whole prize
and the estimate should not be cut. One amendment P0 earns: Phase 2's parity
target must be stated **against `det_blind` and at a named `S`**. At `S = 32`
with CRN-1 the agreement is already **89.7%**, i.e. the ≥ 90% target is
reachable but only at a dose that is itself 9× poke_engine's leaf count —
so "Form A, like-for-like" is not free, and the gate should read
"≥ 90% at `S = 32` with CRN-1" rather than "≥ 90%".

### 7.4 Depth-2 is ALIVE

The stop rule passes at 0.51× (§2), so Form B is not killed, and three further
measurements say it is more than technically alive:

- **CRN-1 works** (×1.99 variance at `S = 32`), which is a free halving of the
  dose in the one place the design was least sure of itself.
- **Column pruning is free** (§4.4): `k = 3` keeps 98.7% of opponent mass and
  changes no argmax, so the `(cols)²` term in the depth-2 blowup can be cut
  from 4.19 to 3 at no measured cost.
- **Row pruning is not free** (§4.2, §4.3), and that is the constraint Phase 3
  should budget against: `root_k = 4`'s median gap (0.01273) is 1.5× the S=32
  sampling noise, and `child_k = 3` by the policy prior loses the best row on
  14% of decisions.

**Phase 3: 2-3 blocks, unchanged, with one pre-decided caution.** The dose the
design's own rule wants (`S ≈ 52`) is expensive at depth 2 — at `S = S' ≈ 52`
against §4.2's 26,450-leaf tree the chance factor alone is `(52/3.5)²` ≈ 220×,
which is far past the proposed ≤ 5 s per-decision cap. **The stop rule's `S = 16`
is what depth-2 can actually afford**, and at `S = 16` the root solve's σ is
0.01186 against a median margin of 0.0328 — resolvable, but with a third of the
margin as noise. Phase 3 should pre-register the dose from this table rather
than discovering it, and should report `sd(margin)` alongside the decisions/sec
that JOURNEY 11.5 already requires.

### 7.5 Total: the 8-11 block estimate stands

No phase moved. What moved is *where the uncertainty sits*: out of "can the write
side exist" (answered: yes, bitwise) and into "what dose can depth-2 afford"
(answered: `S = 16`, not the design's 52) and "how much does root pruning cost"
(answered: more than the design assumed).

*(Context, noted not acted on: `STATUS.md` changed during this session — the
maintainer's goal moved to "as high as possible" on the ladder and named
**search as the axis** ("we spend 63 ms of the ladder's 150 s/turn (0.04%)").
That raises the value of this whole line but changes no measurement here, and
"whether to build engine-native search at all" remains a maintainer ruling,
`STATUS.md` Next actions 3.)*

---

## 8. What Phase 1 still owes — the spike is not the bridge

`search_p0_write_spike.py` is a throwaway and must not be mistaken for Phase 1's
deliverable. Concretely, Phase 1 still owes:

1. **Mutable writers in Rust.** The spike transcribed `layout.rs`'s offsets into
   Python. Two copies of a byte layout is a drift hazard with no test between
   them; Phase 1's `PokemonViewMut` / `ActiveViewMut` exist precisely so there is
   one.
2. **`SideTracker::from_root` / `RootReveal`.** The spike hand-rolls the
   root→child observable projection in Python. The real thing has to produce the
   *same* `ObservableState` the collector's tracker produces, and be gated
   against it (R1-E legs A/B/C, controls C1-C7).
3. **Every root the restriction refused** — §3.1's table is the work list, and it
   is more than half the corpus. In descending order: opponent status, own
   status, force_switch (W-REQ's `(Switch, Pass)` shape), own and opponent
   boosts (W-ACTIVESTATS), must_recharge (W-LASTMOVE, and the hard-lock action
   mapping), confusion (W-CONF), preparing (W-LASTMOVE), asleep anywhere
   (W-SLEEP's hidden turns-left).
4. **The families the spike defaulted to zero** — W-LASTDMG (27 pool species
   carry Counter), W-LASTMOVE (§6: free on the live path, owed on the harvest
   path), W-SUB, W-CONF, W-SLEEP.
5. **A batched leaf path.** §7 has the measured reason.
6. **The one thing Phase 1 does NOT owe:** proving that a mid-battle state can be
   constructed at all, or that the stat model transfers. §1.5's gates settle
   both.
