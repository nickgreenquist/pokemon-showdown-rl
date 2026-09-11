# R1-E — the root-init parity gate

`scripts/search_r1e_gate.py` · tests `tests/test_search_r1e_gate.py` ·
report `results/search_r1e/r1e.json` ·
design `ENGINE_SEARCH_DESIGN.md` §3.2/§3.3 (Phase 1)

Built 2026-09-11, **before** the Rust write side, and run end to end against
the existing `poke_engine` construction so the gate's own machinery is
measured before the thing it gates exists. A gate whose plumbing is first
exercised on the artefact it is supposed to judge has no null.

---

## 0. Why this gate is the whole point

Phase 1 builds a bridge that constructs a mid-battle engine state from a
poke-env public view plus one determinization. If that bridge is subtly wrong,
every downstream search number is a number **about a different game**, and
nothing else in the pipeline would notice.

That is not hypothetical. It is the shape of the defect **A-1a** caught in the
collector: `track.rs` hard-coded a foe's revealed-move PP to `max_pp`, giving a
constant 1.0 in dims 627/673/719 with SMD ≈ 0.94 against the real collector.
Gate **P-1 structurally could not see it**, because P-1 fills the observable
state *from poke-env* and therefore shared the defect with its own reference.
R1-E is the independent check, and control **C2** re-introduces that exact
defect so the gate is proved able to see it.

**One-directional, in the `scripts/engine_a1a.py` style.** Failing R1-E blocks
the write side and names the field to fix. Passing it licenses one thing:
**build Phase 2.** §6 says what it does not license, in terms.

---

## 1. The three legs

| leg | what it compares | oracle | can it fail on its own? |
|---|---|---|---|
| **A** | the constructed root, encoded, vs the harvested LIVE `row["obs"]`, **bitwise** | external — the vector the policy actually acted on | yes, and any dim outside a declared family is a **BUG, not a family** |
| **B** | the construction against **itself** | **none** | reported, **never a parity verdict** |
| **C** | `mask_for(constructed)` vs the harvested `row["mask"]` | external — the server's own offered set | yes; **< 99.5% is the design's HARD STOP** |

### Leg A — observation parity

`embed_battle(shadow_battle(battle_to_state(battle1, det), turn,
view=public_view(battle1)))` compared bitwise (uint32 view, no tolerance)
against `row["obs"]`. Every differing dim is attributed to a declared family by
`classify_family`, and the block boundaries come from `rl.envs.showdown`'s
`GLOBAL_DIM` / `MON_DIM` / `ACTIVE_DIM` / `MOVE_DIM` / `ID_DIM` — never
hard-coded, so an encoder-width change moves the classifier with the encoder.
`tests/test_search_r1e_gate.py` cross-checks all 828 dims against
`scripts/engine_p1.py::describe_index`, an independently written classifier
over the same constants.

**What leg A cannot see** (this is the important half — §2's table):
`order`, the `forced()` set, `PP > 0`, fainted-ness as it reaches `choices()`,
and every declared family whose field the encoder never reads — **W-STATS,
W-ACTIVESTATS, W-LASTDMG, W-SEED, W-CONF, W-SUB, W-LS, W-ORDER, W-SLEEP's
hidden turns, W-LASTMOVE**. Leg A reporting 0 dims for those families is not
evidence they are right. It is evidence leg A is blind to them.

### Leg B — internal consistency. **INTERNAL-ONLY, NEVER PARITY.**

The design requires this disclosure and the report carries it verbatim.
There is **no harvested foe observation** and no external oracle for a one-turn
transition at the root, so nothing in leg B compares the construction against
ground truth. It can only catch a construction that disagrees with itself.

What it runs today:

* **W-VALIDATE** (design §2.4) on the constructed root — both sides ≥ 1
  unfainted, `order[0]` names a live mon, the offered set is non-empty under a
  non-forced request, four move slots, `hp ≤ maxhp`, every id in range.
  `from_bytes` accepts anything, so the write side must validate before
  handing a state to `update`; the same discipline applies to the stand-in.
* **Transition invariants** that follow from the chosen action alone: branch
  mass sums to 100 (tolerance 1e-3, an order of magnitude above the measured
  worst case of 1.29e-05), a switch action lands the named species as active,
  and the leaf passes W-VALIDATE (with terminal leaves exempt — a depth-1 leaf
  may legitimately have a side wiped).
* **The cross-simulator comparison is `SELF-COMPARISON — VACUOUS` on the
  `poke_engine` backend** and the report says so in those words. The
  constructed state *is* the poke_engine path there, so the comparison
  compares the path to itself.

What leg B **owes** on the engine backend, recorded in the JSON rather than
dropped: cross-seat agreement (`tracker_properties.rs:9-12`), the privileged
block's value test (`docs/proposals/privileged_critic_engine_route.md:215-230`),
and the real one-turn agreement with the poke_engine path.

### Leg C — mask parity. **The load-bearing leg.**

`mask_for(constructed)` mirrors the engine's own `action_to_choice`
(`env.rs:82-124`) clause for clause, and it reads **the constructed state
only** — never `battle.available_moves`, never `battle.trapped`, never the
harvested mask. Sharing an input with the reference is what made the first
version of gate P-1 unfalsifiable; the same trap is available here.

The law:

1. **W-REQ first.** Our active fainted → `Request::Switch`, offered set = the
   live bench only. `forced()` is irrelevant under a Switch request: the
   engine clears a fainted active's volatiles, while poke-env leaves
   `must_recharge` standing on the corpse (87 of 13,396 roots).
2. Otherwise `Request::Move`. Under a **hard lock** (`recharging | rage |
   thrashing | charging`) the engine offers exactly `Move(1)` and no switch,
   and poke-env maps that to `6 + the locked move's STORED SLOT` — which needs
   `S_LAST_SELECTED_MOVE`. `freeze_battle` does not carry it (family
   W-LASTMOVE), so the harness leaves the mask empty rather than guessing.
3. Otherwise: every live non-active party member, plus every live move slot
   with `pp > 0`.

---

## 2. The family table

`obs-visible` is the column that matters: it says whether **leg A** can see the
family at all. The measured columns are the full 13,396-root non-aliased R1
corpus at `n_det = 1`, `--backend poke_engine`.

| family | field(s) | class | obs-visible | measured on the stand-in | seen by |
|---|---|---|---|---|---|
| **W-HP** | opponent `P_HP` | grain | **yes** (`opp_mon<k>.hp`) | **0.5888 dims/root, max \|Δ\| 0.00249**, 7,400 roots | leg A |
| **W-TRANSFORM** | a transformed Ditto's copied base stats + everything downstream | unrepresentable from the dex | **yes** | **0.3118 dims/root**, 209 roots, max \|Δ\| 3.5 | leg A |
| **W-DET** | the determinization itself | inherited | **yes** (`opp_mon<k>` for `k ≥ n_revealed`) | **0 dims** — the boundary holds; control C5 removes it and it becomes **37.08** | leg A |
| **W-REQ** | the `(Request, Request)` pair | derived from fainted-ness | **yes** (`global.force_switch`) | **0 dims** | leg A **and leg C** |
| **W-ORDER** | `S_ORDER[1..6]` | free | no | **0 dims** (required) | **leg C** |
| **W-SEED** | `B_RNG` | the chance dial | no | **0 dims** (required) | neither |
| **W-STATS** | opponent `P_STATS` | determinized | **no** — the encoder reads BASE stats and level, never the computed block | — | neither; reaches the search only through damage |
| **W-ACTIVESTATS** ⟵ *amended A1* | `A_STATS` | path-dependent | **no** — `_spe_est` derives speed from base stats + stage + PAR (`encoder.rs:101-118`) | known wrong on **≤ 28.031%** of roots (either active PAR\|BRN); opp alone 24.224%, own alone 5.875% | neither; only turn order and damage see it |
| **W-DISABLE** ⟵ *added A2* | `V_DISABLE_MOVE`, `V_DISABLE_DURATION` | owner-visible, carried; **not a residual** | **no** — the disabled slot is not encoded | **0 of 13,396 roots** — vacuous on this corpus, declared anyway | **leg C**, and only leg C |
| **W-SLEEP** | `P_STATUS` bits 0-2, EXT | sampled per det | **no** — turns *remaining* are hidden; the encoded `status_counter` is `sleep_observed`, which is poke-env's own value | — | neither directly (control C3 moves it) |
| **W-CONF** | `V_CONFUSION_TURNS` | sampled per det | **no** — the flag is encoded and exact; the turns are hidden | — | neither |
| **W-SUB** | `V_SUBSTITUTE_HP` | defaulted | **no** — the flag is encoded; the HP is hidden | vacuous (0/13,702 roots) | neither |
| **W-LASTDMG** | `B_LAST_DAMAGE`, `B_LAST_MOVES` | reconstructed | **no** — not encoded at all | — | neither |
| **W-LASTMOVE** | `S_LAST_SELECTED_MOVE`, `S_LAST_USED_MOVE` | sampled / defaulted | **no** | — | **leg C** — a hard lock offers one move action and this says which |
| **W-LS** | `V_LIGHT_SCREEN` | NAMED UNMODELLABLE | **no** — poke-env 0.15 has no `Effect.LIGHT_SCREEN`, so it is invisible to **both** encodings and can never be a diff | vacuous | neither |
| *S-PREPARING* | `*_active.preparing` | **stand-in artefact** | yes | **0.0035 dims/root**, 47 roots | leg A |
| *S-TRAPPED* | `global.trapped` | **stand-in artefact** | yes | **0.0002 dims/root**, 3 roots | leg A |
| *S-SLEEPREST* | `*_active.status_counter` | **stand-in artefact** | yes | 0 on this corpus | leg A |

### 2a. Two amendments, and the order they happened in

§7's failure branch pre-decided against loosening families after seeing
results — "do **not** extend and do **not** loosen the families silently" — so
the sequence has to be visible or the amendment is worthless.

**Both amendments POST-DATE the first full-corpus run**, which is banked
unamended at `results/search_r1e/r1e_prebar_2026-09-11T2136.json`. Both are
sourced from **engine semantics** measured by cargo unit tests in
`engine/pkmn_gen1/tests/write_side.rs`, produced by the write-side spike
running in parallel — **not** from anything about R1-E's own results. They
correct a bar that was **wrong**, not a bar that **failed**.

**A1 — W-ACTIVESTATS incidence 2.26% → ≤ 28.031%, and the domain was wrong.**
§2.6's "exact when there are no boosts" is **false**. The engine re-applies
`statusModify` to the **defender's already-modified** active stats at the end
of every stat change **the foe** makes (`mechanics.zig:2580-2581` boost,
`:2688-2689` unboost, both labelled *"GLITCH: Stat modification errors
glitch"*). The cargo test
`the_stat_modification_glitch_compounds_status_on_the_defender` pins it: stored
spe 188, **no boosts**, PAR → the engine holds 11 (188/4/4) where §2.6's rule
gives 47, and nothing in the defender's public description changed. Correct
domain: **exact iff the active is neither paralysed nor burned.** Measured
here: opp active PAR|BRN **24.224%**, own **5.875%**, either **28.031%** of
13,396 non-aliased roots.

**A2 — add W-DISABLE.** §2.4 classes Disable **V**. That is true for the
*pool* (0 of 146 species, and 0 of 13,396 roots show `Effect.DISABLE`) and
false as a statement about the *field*: dropping `disable_move` **re-offers a
move the request omits** (`choices()` skips the slot, `mechanics.zig:3231`).
That is **leg C's hard stop, not a residual**. The slot and the duration move
together — a slot set with duration 0 disables the move **forever**, because
`beforeMove` only clears inside `if (disable_duration > 0)` — so the spec must
reject that pair (`spec.rs:486-489`, `:1151-1154`).

**Neither amendment moves a measured quantity in this report.**
W-ACTIVESTATS is obs-invisible on both legs, and W-DISABLE has incidence 0 on
this corpus. The old-bar and amended-bar verdicts are therefore **identical leg
for leg** — §4 records both. What A1 changes is the *disclosure*: the thing
neither leg can see is now known to be wrong on up to **28%** of roots rather
than 2–3%, which makes §6's exclusion of W-ACTIVESTATS considerably more
load-bearing than it looked.

**`S-*` families are declared on `--backend poke_engine` ONLY.** They are the
shadow's own limitations — it hard-codes `trapped=False` and
`preparing=False`, and it sums `sleep_turns + rest_turns` where the engine
tracker carries poke-env's own `sleep_observed`. On `--backend engine` they are
**undeclared, i.e. a FAIL**: the gate gets stricter when the real surface
lands, which is the only direction a stand-in may fail in.

---

## 3. The controls

§3.3's seven, plus one. Each corrupts exactly **one** rule in the
**construction** — never in the reference, which is the harvested row and is
immutable by construction. Measured on a 3,000-root strided subsample of the
full corpus, `--backend poke_engine`. `exposed` = roots where the corrupted
rule is actually present (`engine_p1_run.py`'s family-EXPOSURE precedent —
without it, a zero is true by construction and says nothing).

| id | corrupts | exposed | roots moved | leg A dims/root | leg C exact |
|---|---|---:|---:|---|---:|
| **C1** | swap two entries of the opponent's `reveal_order` | 2,519 | 2,519 | 0.927 → **21.65** | 2,994 → 2,994 |
| **C2** | zero `move_uses` — **the A-1a defect, exactly** | 2,840 | 2,234 | 0.927 → **1.847**, and the moved dims are `opp_move<j>.pp` | 2,994 → 2,994 |
| **C3** | `sleep_observed` off by one | 216 | 216 | 0.927 → **0.999** | 2,994 → 2,994 |
| **C4** | drop `flags_before_faint` | 211 | 203 | 0.927 → **0.995** | 2,994 → **3,000** |
| **C5** | **the as-is control**: every opponent slot revealed | 2,611 | 2,977 | 0.927 → **37.08** | 2,994 → 2,994 |
| **C6** | flip the sign of a negative boost | 232 | 232 | 0.927 → **1.088** | 2,994 → 2,994 |
| **C7** | write HP with `floor` instead of `round` | 1,751 | 731 | 0.927 → **0.927** (dims unchanged; **731 roots move in magnitude**, and W-HP stays inside its max-\|Δ\| bar — exactly what §3.3 predicts) | 2,994 → 2,994 |
| **C8** ⟵ *beyond §3.3* | revive a fainted bench mon | 2,284 | 2,284 | 0.927 → **3.211** | 2,994 → **715** |

**All eight fire.** Three things are worth reading off that table.

* **C7 needed a firing test that is not a dim count.** `floor` vs `round`
  leaves the *set* of differing dims unchanged and moves only their
  magnitudes, so a count-only test reads a working control as BLIND — it did,
  on the first 400-root sample. The harness now compares a per-root signature
  `(n_differing_dims, Σ|Δ| quantised)`, and the bug is pinned by
  `test_control_report_fires_on_magnitude_alone_not_only_on_dim_counts`.
* **C4 makes leg C *better*** — 2,994 → 3,000. Dropping poke-env's
  `must_recharge` repairs exactly the six mask mismatches in that subsample.
  That is finding **F1** confirmed from the other direction.
* **C1–C7 move leg C by zero.** See §5, finding F3.

---

## 4. The pass rule

Restated verbatim from §3.2, and restated in exactly one place in the code
(`BAR_*` constants) so it cannot drift from this doc.

**Leg A passes iff all of:**

* no undeclared dims (an undeclared dim is a **BUG, not a family**);
* total ≤ **1.5 dims/root**;
* ≥ **40%** of roots bit-identical;
* **W-HP** ≤ **0.60 dims/root** and max \|Δ\| ≤ **0.01**;
* **W-ORDER**, **W-SEED**, **W-DET**, **W-REQ** contribute **zero** dims — "if
  they do not, the claim that they are free is false".

**Leg C passes iff exact ≥ 99.5%.** Target is **100%**. Below 99.5% is the
design's **hard stop**: "it means the constructed state does not offer the
actions the real one offered, and every downstream number is about a different
game."

**Leg B is reported and is never a verdict input.**

`R1E_PASS = leg A pass AND leg C pass AND no BLIND control.` A control that is
`NOT_EXPOSED` on a sample is a **coverage gap**, not gate blindness, and does
not fail the gate — it is printed loudly instead.

### Measured, 2026-09-11, `--backend poke_engine`, full 13,396-root corpus

**Both verdicts, because the amendments post-date the first run.** The
unamended-bar run is banked at
`results/search_r1e/r1e_prebar_2026-09-11T2136.json`; the amended-bar run
overwrote `r1e.json`. **They are identical leg for leg** — leg A 44.3%
bit-identical / 0.9044 dims/root / one undeclared dim; leg B PASS; leg C
13,354 / 13,396 = 99.686%; controls 8/8 — because neither amendment touches a
quantity either leg measures (§2a). **Leg A does not pass only under the
amended bar. It fails under both, on the same single dim, for the reason
finding F5 names.**

| leg | result |
|---|---|
| **A** | **FAIL on exactly one dim.** 44.3% bit-identical (bar 40%), **0.9044 dims/root** (bar 1.5), W-HP 0.5888 / max \|Δ\| 0.00249 (bars 0.60 / 0.01), free families 0. **One undeclared dim on one root** — `own_active.status_counter`, s64 ep48 step15. See finding **F5**. |
| **B** | PASS. W-VALIDATE 1000/1000 clean; branch mass 1000/1000; switch-lands-named-species 189/189; leaf-valid 1000/1000. Cross-simulator: SELF-COMPARISON. |
| **C** | **PASS: 13,354 / 13,396 = 99.686%** (hard stop 99.5%, target 100%). Two causes and nothing else: **39 roots** are finding **F1** (stale `must_recharge`), **3** are the stand-in's `preparing` gap, which is a declared W-LASTMOVE root on the engine backend — excluding those, **99.709%**. Separately: **47 roots** the engine backend must **refuse** rather than build (F6). |
| controls | **8 / 8 fire.** |

Wall: **108 s** for legs A/B/C over 13,396 roots plus eight controls at
`--control-limit 3000`, single-threaded under `taskpolicy -b`.

The leg-A FAIL is the gate working. It is one dim, on one root, with a named
cause and a one-line fix, found on a corpus the existing search line has been
running over for weeks.

---

## 5. Findings

These are standing statements about the construction rules and about §3's spec,
carried in the report's `findings` block beside the numbers that back them.

**F6 — a charging root must be REFUSED, not defaulted, on the engine backend.**
`VolatileSpec::charging` carries the one-based live **slot**, and the engine
derives *both* `S_LAST_SELECTED_MOVE` and `B_LAST_MOVES[p].index` from it
(`spec.rs:613`, cargo test
`charging_drives_both_derived_bytes_and_the_engine_releases_the_move`). An
index of **0 is an unconditional out-of-bounds read** — `moves[-1]` — and
`build.rs:220` pins `-Doptimize=ReleaseFast` in **every** profile, so the
`mslot > 0` assert is compiled out: the engine reads garbage rather than
trapping. **Measured: 47 of 13,396 non-aliased roots have a charging active**
(43 opponent, 4 own; 0.351%), and `freeze_battle` carries `preparing` as a
**boolean only** (`harvest.py:53`), so the slot is unrecoverable on harvest
replay — declared W-LASTMOVE. *Recommendation:* `_build_engine_root` refuses
those roots via `charging_roots_unbuildable()` rather than defaulting them, and
they are reported as harvest-unbuildable. The **live** path can fill the slot
(poke-env retains `_preparing_move`), which is one more reason §3.2's fresh
100M-lane harvest should record it.

**F1 — poke-env's `must_recharge` outlives the server's lock.** On roots where
the request offered a full choice set (not aliased, not trapped), poke-env still
reports `must_recharge=True`. Writing that flag straight into `V_RECHARGING`
makes `forced()` true, and the constructed state then offers **no switch and one
move** where the real game offered everything. **Measured: 39 of 13,396
non-aliased roots (0.291%)**; 87 more carry it on a *fainted* active, which
W-REQ already handles. *Recommendation:* gate `V_RECHARGING` on the request, not
on poke-env's flag — write it only when the root is aliased or trapped.
**Only leg C can see this**: the encoded
`own_active.volatile[MUST_RECHARGE]` dim agrees between the two encoders
precisely *because* both read poke-env's flag. That is the A-1a shape again.

**F2 — `bridge._our_transform_stats_override` misses a transformed Ditto whose
base stats did not change.** It detects our own transformed Ditto by base-stat
inequality against the dex. Measured on s62 ep8 step6: poke-env carried the
**copied types** (`['WATER']`) while leaving `base_stats` at Ditto's own dex
values (48 across the board), so the base-stat test is False and the transform
is missed. Design §2.4 says to **reuse this function** on the engine side, which
would inherit the miss. *Recommendation:* detect on **either** signal. This gate
does; the bridge and the future spec builder should.

**F3 — §3.3 as written leaves leg C without a positive control.** C1–C7 are all
observation-side: every "must move" cell names encoder dims. So the leg §3.2
itself calls load-bearing has no falsifier, and a leg C reporting 100% would be
indistinguishable from one that reports 100% unconditionally. **Measured: C1–C7
move leg C's exact count by 0.** C8 (marked `beyond_design_section_3_3`)
corrupts fainted-ness, one of the four things §3.2 says obs parity cannot see,
and moves leg C from 2,994 to 715. *Recommendation:* keep C8, and on the engine
backend add the three controls that are leg-C-only **there**: permute
`S_ORDER[1..6]` (W-ORDER claims **zero** effect — that claim is testable only on
the engine), flip one bit of `Volatiles::forced()`, and mis-set
`S_LAST_SELECTED_MOVE` under a hard lock.

**F4 — the stand-in's reach.** On `--backend poke_engine` there is **no**
construction corruption that leg C sees and leg A does not, because every field
the stand-in can express is also encodable. The genuinely leg-C-only fields —
`S_ORDER[1..6]`, the `forced()` bits as distinct from the request,
`S_LAST_SELECTED_MOVE` — are **engine** fields with no poke_engine analogue.
*Read leg C's independence claim as PENDING until the engine backend runs.*
Today leg C's value is that it uses a **different derivation** (the engine's
`choices()` law) of the same underlying state, not a different field set.

**F5 — a mon that faints while asleep keeps its sleep counter.** poke-env sets
the status to FNT and leaves `status_counter` standing. The live encoder writes
it into `*_active.status_counter`, so a construction rule keyed on
`status == SLP` writes 0 where the live obs has 1/16.
`rl/search/bridge._our_pokemon` has that rule, and so did this gate's own
`RootReveal` builder until the full-corpus run caught it. **Measured: exactly 1
of 13,396 roots** (s64 ep48 step15, a Slowbro at FNT / counter 1) — the only
undeclared dim on the whole corpus. Census: 741 actives carry a non-zero counter
under SLP, **1 under FNT**, 0 under anything else. *Recommendation:*
`SideTracker::from_root` must seed `sleep_observed` for a **fainted** slot too —
the same reason `flags_before_faint` exists (§3.1). `root_reveals()` here does.
It was deliberately **not** widened into a declared family: the engine can get
this exactly right, so declaring it would license a defect.

---

## 6. What a PASS would and would not license

Modelled on `scripts/engine_a1a.py`'s docstring, which states in terms what it
cannot decide and why. The report carries this list verbatim.

**A PASS LICENSES, and this is the whole of it:**

* **Build Phase 2** — the batched leaf path and Form A.

**A PASS DOES NOT LICENSE:**

* **Any search number.** R1-E measures the **root**. It does not touch a
  decision, a win rate, or a rung.
* **Any claim about the transition.** Phase 2's decision-level agreement read
  owns that (≥ 90% argmax agreement proposed, < 85% blocks Phase 3).
* **Any claim about leaves.** A root residual is not a leaf residual —
  `DET_BLIND.md` §5.3 states exactly this: a 0.945 dims/root residual at the
  root "does not prove the same residual at a leaf; it proves the leaf encoder
  now applies the same boundary rule the live encoder applies."
* **Any claim about the 100M-lane state distribution.** §3.2 requires a **fresh
  100M-lane harvest** (≥ 3,000 roots × 3 lanes, `configs/eval/search_s3_100m.yaml`)
  and says it is "not optional: a write-side bridge graded only on 12M-era
  states is graded on the wrong distribution." The run banked here is the
  12M-era R1 corpus. **That leg is OWED.**
* **Any claim about W-ACTIVESTATS, W-STATS, W-LASTDMG, W-SEED, W-CONF, W-SUB,
  W-LS, W-ORDER or W-LASTMOVE.** Neither leg can see them (§2). A zero there is
  blindness, not correctness. W-ACTIVESTATS in particular is *known* wrong on
  2.26% (opp) / 1.08% (own) of roots by the design's own measurement, and both
  legs report clean anyway.
* **Anything about the stand-in's numbers standing in for the engine's.** The
  `poke_engine` backend is a stand-in for the gate's machinery. Its residual is
  the *shadow's* residual. Only `--backend engine` grades the write side.

---

## 7. Running it

One command per block.

<command>
POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 python scripts/search_r1e_gate.py --limit 200
</command>

<command>
POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 python scripts/search_r1e_gate.py --all --control-limit 3000 --leg-b-limit 1000 --out results/search_r1e
</command>

<command>
POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 pytest tests/test_search_r1e_gate.py -q
</command>

Offline throughout: no server, no websocket, no battles, no checkpoints.
PUBLIC harvest only (`harvest_<lane>.pkl`, never `harvest_priv_*` — FG-4).
Measured wall time, single-threaded under `taskpolicy -b` on a shared box:
**41 s** for legs A/B/C over all 13,396 roots, **7–10 s per control** at
`--control-limit 3000`, **108 s** end to end. Determinizations are keyed
`decision_rng(7000 + lane_index, episode, turn, step)` so a re-run reproduces
the same dets; the key and `n_det` are stamped in the report's provenance
alongside the four corpus sha256s and the encoder fingerprint.

**The engine backend is one function.** `_build_engine_root` in
`scripts/search_r1e_gate.py` names the three Rust symbols it waits on and
raises with that list rather than degrading — a gate that silently fell back to
the stand-in would report the stand-in's numbers under the engine's name.
`root_reveals()` (design §3.1's `RootReveal` payload) is **already real**: it is
pure battle1 data, it carries the A-1a rule and F5's fix, and it is unit-tested
today. What remains is the `BattleSpec` builder plus:

1. `pkmn_gen1.BattleSpec` / `Battle::from_spec` — design §2.4's field-by-field
   write, with `W-VALIDATE` inside it;
2. `BattleTracker::from_root(&Battle, &RootReveal, &RootReveal)` — design §3.1;
3. a seat-X encode of arbitrary battle bytes, and `mask_for(b, p, req, aliased)`
   exposed to Python (`env.rs:167-173`).
