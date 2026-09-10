# det_blind — the information-boundary-preserving leaf encoding

Built 2026-09-10, acting on screen **S1** (`S1_S2_SCREENS.md` §3–4). S1 fired
on all four 12M lanes: the depth-1 search's LEAF ENCODING moves the critic by
**+0.0497 mean (+16.3 se), sd 0.1254**, against a median Dose-M decision
margin of **0.0277** — 4.5× the decision. The next build is therefore the leaf
encoder, not depth.

`det_blind` is an **option**, not a replacement. With it off — the default,
and what every banked search arm ran — the search path is byte-for-byte
unchanged; §3 pins that against a golden computed before the edit.

**Result (§4).** On the same 800 decisions, det_blind takes pooled sd(Delta)
from **0.1254 to 0.0078** and the mean signed Delta from **+0.0497 (+16.3 se)
to +0.0002 (+0.6 se)**; the ratio against the median decision margin goes
**4.52 → 0.29**, so **S1 no longer fires on any lane**. The within-decision
spread across the four determinizations is **exactly zero** — the root
encoding is now determinization-independent, which is the property the live
encoder has. **11.4% of argmaxes change** (91/800) at **identical leaf
counts**.

Nothing here is a win-rate measurement. §6 is the pre-stated read for the
online screen that would be one.

---

## 1. The mechanism, with the dims

A leaf is valued by `critic(embed_battle(shadow_battle(leaf_state), chart))`.
`leaf_state` descends from `battle_to_state(battle1, det)` — the poke-env
public view PLUS one RSD determinization (`rl/search/determinize.py`). The
determinization invents a full opponent team: species for every bench slot
poke-env has never seen, and a four-move set for every mon whose moves are
unknown. `shadow_battle` then hands all of it to the encoder as if it were
on the table, because the engine State has no notion of *revealed*.

The critic was trained on LIVE encodings only, where those slots are zeros
behind a zero `revealed` flag. So every leaf is out of distribution, in a
direction the design already names as optimistic, by more than the decision.

**Measured, 2026-09-10** — 1,600 root encodings (the four D26 lanes ×100
strided non-aliased harvested decisions ×4 determinizations), shadow-root vs
the harvested LIVE obs, at encoder v2+ids (828-d). Names are
`block.field` in the encoder's own layout.

| family | dims/root | max abs | what it is |
| --- | ---: | ---: | --- |
| `opp_mon.base_stats` | 12.560 | 0.980 | invented bench mon's five base stats |
| `opp_mon.types` | 3.230 | 1.0 | its type one-hot |
| `opp_mon.hp` | 3.060 | 1.0 | 2.50 of these are the invented bench at hp=1.0; the rest is the HP grain |
| `opp_mon.speed_edge` | 2.539 | 0.877 | v2 speed edge vs our active |
| `opp_mon.matchup_def` | 2.521 | 4.0 | our active's best multiplier into it |
| `opp_mon.matchup_off` | 2.506 | 4.0 | its best multiplier into our active |
| `opp_mon.revealed` | 2.503 | 1.0 | **the flag itself** — 2.50 invented mons per root |
| `opp_mon.level` | 2.503 | 1.0 | its randbats level |
| `id.opp_species*` | 2.503 | 0.590 | its species-embedding index |
| `opp_move.known` | 0.903 | 0.789 | the det shows p=1.0 where battle1 shows the set prior's p |
| `opp_move.pp` | 0.895 | 1.0 | the det defaults PP to max; battle1 tracks the opponent's |
| `our_mon.*`, `opp_mon.*`, `*_move.matchup` (ditto) | 0.130 | 1.5 | transformed-Ditto base stats and everything downstream |
| `opp_active.preparing` | 0.005 | 1.0 | FLY/DIG modelled as volatiles we do not map back |
| **total** | **35.930** | | **0.8% of roots (12/1600) encode exactly** |

The nine bench families sum to **33.4 dims/root**, matching FG-6's
`det_unrevealed_bench` of 33.86 over 13,396 roots
(`results/ch3_r1/fg_battery.json`). **2.50 mons per root are pure invention**,
at ~13.3 dims each.

---

## 2. The design

`det_blind` re-imposes the LIVE encoder's information boundary on the leaf.
The carrier is `rl/search/shadow_battle.PublicView` — the ROOT battle's
opponent-side public view (revealed species; revealed move ids in reveal
order; battle1's tracked PP for each) — built once per decision by
`public_view(battle)` and threaded to every leaf's `shadow_battle` through
`solve_decision(..., leaf_view=...)`.

**(a) An opponent mon the root never saw is not in the leaf's team.** It is
dropped from `opponent_team` entirely, so its block stays the zeros the live
encoder emits, `revealed` included. The ONE exception is the leaf's own
active: a determinized mon that switched or was dragged in is ON THE FIELD,
and the live game would then name its species. It is included, and — because
the engine orders `side_two` as [revealed, in reveal order] then [invented] —
it lands exactly where poke-env would append it.

**(b) The opponent active's move slots are the live encoder's own fill.**
The shadow's `moves` dict is restricted to the ROOT's revealed moves, in
reveal order. `_opponent_move_slots` then does the rest itself: revealed
first at p=1.0, then the most probable unrevealed candidates from the
vendored randbats prior at their prior p. That is the same function, reading
the same table, that runs on `battle1` — no second fill path to drift.
A newly switched-in mon has an empty revealed set, so all four of its slots
come from the prior, at the prior's probabilities, exactly as live.

**(c) A move the transition USED becomes revealed.** `PublicView.plus_move`
appends it last and ticks its PP down one, mirroring poke-env's
`_add_move` + `Move.use()`. The view is therefore **per column**, not per
decision: `solve_decision` builds one view per opponent column
(≤ 6 of them) before the cell loop. A SWITCH column names a species and a
locked/force-switch column names `"none"`; neither reveals a move, and the
membership test is against the active's own four slots, so a species that
happens to spell a move id cannot leak in.

**(d) Everything the live encoder observes still comes from the engine
leaf**: HP fraction, status, boosts, volatiles, faint flags, force-switch,
turn, and our own side in full. Our side is never given a view — it is fully
observed in both encodings.

**PP is public.** poke-env DOES track opponent PP (this is measurable: the
`opp_move.pp` family disappears entirely once battle1's PP is carried — §5),
so det_blind carries battle1's value rather than the engine's leaf value.
The engine is not a usable source here in any case — poke-engine emits
`DecrementPP` only for low-PP moves (measured 2026-09-10: Blizzard at 8 PP
decrements, Body Slam at 24 does not, same state, same turn).

**Cost: zero.** Identical determinizations, identical branches, identical
leaf count — measured over the full 800-decision re-run: **350.7725
leaves/decision under BOTH arms**, pooled and on every lane (§4). The only
work added is one small frozenset/dict per decision and a few dict copies
per column.

### Plumbing

| site | change |
| --- | --- |
| `rl/search/shadow_battle.py` | `PublicView`, `public_view()`, `shadow_battle(..., view=None)` |
| `rl/search/matrix.py` | `solve_decision(..., leaf_view=None)`; per-column views |
| `rl/search/agent.py` | `SearchAgent(..., leaf_encoding=None)`; `LEAF_ENCODINGS = (None, "det_blind")`, asserted |
| `scripts/ch3_eval.py` | a `kind: search` arm may declare `leaf_encoding: det_blind`; every chunk JSON and the merged final carry `search_leaf_encoding` (`"as_is"` when absent) |
| `scripts/ch3_fp_h2h.py` | same for `kind: search_seat`; `search_leaf_encoding` in the report |
| `scripts/search_s1_s2_screens.py` | `--det-blind` re-runs S1 only, to `s1_det_blind.json` |

---

## 3. The two tests

`tests/test_search_det_blind.py`, 15 tests, offline (no server, no
checkpoints — the critic is a pinned cosine projection so that any change to
any leaf's encoding moves `search/ev_matrix`).

**T1 — OFF IS BYTE-IDENTICAL.** A golden sha256 over `solve_decision`'s full
output (action + every stat) on (i) a synthetic two-a-side battle at Dose S,
99 leaves, and (ii) **10 real harvested decisions at Dose M, 3,707 leaves**.
The six digests (two fixtures × three encoder fingerprints v1/612, v2/808,
v2+ids/828) were computed **in a detached worktree at the commit before the
edit** and are reproduced exactly by the post-edit code. `git worktree` was
used precisely so the golden is a pre-change measurement, not a post-hoc
re-statement.

**T2 — ON, THE ROOT IS THE LIVE OBS.** With det_blind on, a determinized
ROOT (no instruction applied) is encoded and compared dim-by-dim against the
harvest's recorded LIVE observation, over 4 lanes × 25 decisions × 4
determinizations. Every differing dim must fall in a DECLARED family (§5);
the classifier is derived from the encoder's own offsets, and the
transformed-Ditto allowance is conditional on a Ditto actually being in play.
Alongside it, `test_as_is_root_fails_the_same_parity_check` runs the
identical assertion on the as-is encoding and requires it to FAIL — without
that control the parity test measures nothing.

Also covered: the per-column reveal (three columns each add exactly one move,
last); the switch-in reveal (species known, moveset from the prior); PP
carriage and the `plus_move` tick; `SearchAgent` rejecting an unknown
`leaf_encoding` and passing a `PublicView` only when asked; `ch3_eval._jobs`
carrying the key with `None` when absent.

One pre-existing test was touched: `test_ch3_evaluator_dials.py`'s
`solve_decision` spy pinned the argument list positionally and now takes
`**kw`, so the next dial does not break it.

---

## 4. The S1 re-run

Run 2026-09-10 12:42–12:54 EDT, one process, `taskpolicy -b`, torch threads 2,
**the same 800 decisions** (200/lane over `s62..s65`, the same `np.linspace`
stride over the same public harvest), `results/search_s1_s2/s1_det_blind.json`.
Wall 11.6 min. Zero watchdog trips, zero placeholder skips, 800/800 searched at
both arms; 781 decisions / 3,124 Deltas usable (the same 19 one-legal-action
decisions are dropped, as in the original).

**Timing is CONTENDED** — four `search_s3_100m` `ch3_eval` jobs plus the
Showdown server were on the box throughout (the original screen ran against a
seven-wide fleet) — and is not a budget number for any dose. What is NOT
contention-sensitive is the leaf count, and it is identical between the arms.

### S1 — pooled, side by side

| quantity | as-is (`s1.json`) | **det_blind** |
| --- | ---: | ---: |
| **pooled sd(Delta)** | 0.12544 | **0.00782** |
| **median row_ev margin** | 0.02773 | 0.02680 |
| **ratio sd(Delta) / median margin** | **4.52** | **0.29** |
| **S1 FIRES** | **YES** | **NO** |
| **mean signed Delta** | **+0.04974** (+16.3 se) | **+0.00018** (+0.6 se) |
| se of mean signed Delta, by decision | 0.00304 | 0.00028 |
| median signed Delta | +0.02931 | +0.00000 |
| fraction of Deltas > 0 | 0.661 | **0.504** |
| fraction of decisions with \|mean Delta\| > margin | 0.612 | **0.0435** |
| mean \|mean Delta\| | 0.07079 | 0.00105 |
| median \|mean Delta\| | 0.04946 | 0.00004 |
| **mean within-decision sd(Delta) over the 4 dets** | 0.08569 | **0.00000** |
| between-decision sd of mean Delta | 0.08507 | 0.00773 |
| mean row_ev margin | 0.05142 | 0.05085 |
| mean v_root | +0.24213 | +0.24213 |

Delta percentiles, det_blind: p1 −0.0015, p5 −0.0006, p25 −0.0000,
p50 0.0000, p75 +0.0001, p95 +0.0006, p99 +0.0176 (as-is: −0.272 … +0.381).

**The bias is gone (+0.0497 → +0.0002, 0.6 se, 50.4% positive) and the spread
is 16× smaller.** Priced against the ORIGINAL as-is median margin of 0.02773
rather than det_blind's own, the ratio is 0.282 — the same answer.

**The within-decision sd is EXACTLY 0.0 on all 800 decisions.** That is not a
rounding artefact: with det_blind the root encoding no longer depends on the
determinization at all, because every det-dependent input has been removed
from it. That is precisely the property the live encoder has, and it is the
sharpest single statement of what this build did. The as-is screen's finding
that **70.6% of decisions had their within-decision spread alone exceeding
their own margin** is now structurally impossible.

### S1 — per lane

| lane | sd as-is | **sd det_blind** | ratio as-is | **ratio det_blind** | mean Delta as-is | **mean Delta det_blind** | fires | n |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :-: | ---: |
| s62 | 0.11898 | **0.00625** | 4.64 | **0.26** | +0.05623 | **−0.00007** | NO | 196 |
| s63 | 0.13157 | **0.00471** | 4.33 | **0.16** | +0.05170 | **+0.00014** | NO | 195 |
| s64 | 0.11564 | **0.00828** | 4.10 | **0.32** | +0.04713 | **+0.00108** | NO | 192 |
| s65 | 0.13420 | **0.01065** | 5.03 | **0.38** | +0.04391 | **−0.00041** | NO | 198 |

All four lanes fired before; none fires now; the four mean Deltas straddle
zero instead of all being positive at +0.044…+0.056.

### Flip rate — det_blind@M vs as-is@M

Both arms key the same `decision_rng`, so they draw the identical four
determinizations and expand the identical branches: **leaves/decision is
350.7725 for both, pooled and on every lane.** The ONLY difference between
the arms is how a leaf is encoded, so the flip rate below is the artefact's
decision footprint with nothing else moving.

| quantity | value |
| --- | ---: |
| **flip rate det_blind vs as-is** | **0.11375** (91/800) |
| flip rate det_blind vs recorded greedy | 0.4975 |
| flip rate as-is vs recorded greedy | 0.48875 |
| mean det_blind margin at the flips | 0.01212 |
| median det_blind margin at the flips | 0.00774 |
| mean det_blind margin at non-flips | 0.05596 |
| median det_blind margin at non-flips | 0.03044 |
| leaves/decision, det_blind and as-is | 350.7725 / 350.7725 |
| ms/decision (CONTENDED, descriptive) | 406.9 / 442.2 |

Per lane: s62 0.1300 (26/200), s63 0.1200 (24/200), s64 0.0950 (19/200),
s65 0.1100 (22/200).

**Reading it.** 11.4% of decisions change argmax — **1.7× the 6.75% that a
4× budget (Dose M → L) moved**, at zero extra leaves where the budget change
cost 4.00×. Against the recorded greedy action the two arms disagree at
essentially the same rate (0.4975 vs 0.48875), so det_blind is not collapsing
the search back onto the policy — it is re-deciding a different 11% of the
same decisions. As with the budget flips, the flips are **close calls**: mean
margin 0.0121 at a flip vs 0.0560 at a non-flip (4.6×).

**Flips are not wins.** R3's E-cells measured flip rate RISING while win rate
FELL (0.732 → 0.480 as noise rose, flips 0.561 → 0.649). 11.4% is the size of
the footprint, not evidence of its sign. §6 is the read that would settle the
sign.

---

## 5. What remains

Under det_blind the root residual is **0.945 dims/root** and **47.5% of roots
(760/1600) encode bit-identically to the live obs**. Everything left is one
of three declared families — verified by attribution, not assumed:

| family | dims/root | max abs | why it is left |
| --- | ---: | ---: | --- |
| **opp HP grain** | 0.558 | **0.0023** | the engine carries exact HP; battle1 only the server's /100 public fraction. Quantising is possible and was deliberately NOT done — it is a different defect from the information boundary, and S1's residual should price it honestly. |
| **transformed Ditto** | 0.375 | 3.0 | a transformed Ditto's copied base stats reach battle1 but not the static dex `ShadowBattle` reads, so base stats, types, both matchups, the speed edge and the move matchups all move. **32/1600 roots, every one of them with a Ditto in play** (checked directly). |
| **preparing** | 0.005 | 1.0 | the engine models FLY/DIG as volatiles the bridge does not map back. 8/1600 roots. |

In the S1 re-run the same three families are the whole residual, checked
decision by decision: **13 of 781 decisions carry a \|mean Delta\| above
0.01**, and every one of them is either a transformed Ditto (7, touching up
to 27 dims — the single largest residual is −0.1358) or a `preparing` turn
(6, touching **one** dim). 31 decisions exceed 0.001; the other 750 sit at
the HP grain's ~1e-5.

Two more are declared but did not occur in this sample: `root_trapped`
(FG-6: 0.0002/root — `ShadowBattle` hard-codes `trapped=False`) and the
sleep/Rest counter split (FG-6: 0.0001/root). Light Screen remains a NAMED
UNMODELLABLE: poke-env 0.15 has no `Effect.LIGHT_SCREEN`, so it is invisible
to both encodings and is not a diff.

**Known approximations inside det_blind itself:**

1. **Faint-before-acting over-reveals.** On branches where the opponent's
   active fainted before it could move, the live game would reveal nothing,
   but the column's move is still marked revealed. The engine gives no usable
   signal for this (the `DecrementPP` finding above), and the cost is one
   opponent move slot moving from its prior p to 1.0, plus the slot reorder
   that implies.
2. **A leaf's reveals are the DETERMINIZED world's reveals.** When a
   determinized bench mon switches in, det_blind reveals *that* species —
   which is the right thing inside the search's own world model, but it is
   not the species the real game would have shown. The determinizer's error
   is untouched by this build; only the encoder's is.
3. **Root parity is not leaf parity.** S1 prices the artefact at the root
   because that is the one state where both encodings exist (S1_S2_SCREENS.md
   §4, "Not claimed"). A residual of 0.945 dims/root at the root does not
   prove the same residual at a leaf; it proves the leaf encoder now applies
   the same boundary rule the live encoder applies.

---

## 6. Pre-stated read for the ONLINE screen

Written before the screen runs. This is the read, not the pre-reg: the arm
needs its own config header naming its `journey_step` and restating that
step's exit condition verbatim, per CLAUDE.md, before it launches.

**Object.** The three 100M finals `s104 / s112 / s120`, sha256-pinned in
`configs/eval/search_s3_100m.yaml`. Two of the three arms already exist or
are running there: **A0** (greedy, FRESH this session — the banked
`final_s1xx.json` are explicitly NOT the comparator) and **S3M** (depth-1
search, dose M, as-is leaf encoding). The new arm is **S3B**: identical to
S3M with `leaf_encoding: det_blind`.

**Protocol.** vs `SimpleHeuristicsPlayer`, locked protocol, deterministic
seat, ties as non-wins, **3000 battles per lane**, 10 chunks, all three
lanes. `ch3_eval.py`, same driver, same chunking, same battle2 sentinel on
chunk 0.

**Pairing and aggregation.** Paired by lane. Across-lane aggregator: the
**equal-weight mean of the per-lane paired deltas** — the same aggregator
S3 registered, named here so it is not chosen after the numbers.

**Primary read.** `delta_B = mean over lanes of (S3B − S3M)`. Cells:

- **POS** iff pooled `delta_B` ≥ +0.025 **and** ≥ 2·se_diff;
- **NEG** iff pooled ≤ 0 **and** per-lane ≤ 0 in ≥ 2 of 3;
- **FLAT** otherwise.

Credit line, restated verbatim from CLAUDE.md: *"a lever is credited iff
pooled delta ≥ +0.025 and ≥ 2·se_diff"*, with the **larger-of** clause —
se_diff is the LARGER of the pooled-binomial se_diff and the seed-clustered
se_diff, the latter computed from the per-lane finals at read time. Both
bands read the same side: the band is on `delta_B`, and POS needs the LOWER
edge above the line.

**Secondary reads,** declared in advance, none of them the firing condition:

- `delta_BA = mean over lanes of (S3B − A0)` — does searching at all beat
  greedy on the 100M object once the encoder artefact is removed? This is
  the question S1 was actually raised against (s66 50M: greedy 0.474 →
  search@M 0.381 off FP@20).
- the same three cells applied to `delta_BA`, against A0 as the comparator;
- decision-level agreement between S3B and S3M, from the search counters;
- `search/ms_mean`, `leaves_mean` per arm — det_blind is predicted to be
  cost-neutral (identical leaf counts), and a leaves delta would mean the
  option changed the search tree, which it must not;
- `search/flip_rate` (vs the policy argmax) per arm.

**Dose is NOT matched** between A0 and either search arm — the generic-compute
confound survives, exactly as in R2/S3, and is disclosed rather than
controlled. It IS matched between S3B and S3M, which is the primary read.

**Expected direction: det_blind ≥ as-is.** The artefact is a bias of
+0.0497 in the same direction on 66% of samples, at 4.5× the decision
margin, and it is uncorrelated with margin (r = +0.02) so it is not confined
to decisions that were easy anyway. Removing an out-of-distribution input
from a trained critic should not hurt.

**What a null means.** A FLAT or NEG `delta_B` says the encoding artefact was
**not the binding defect** — the search is limited by the EVALUATOR itself,
not by what the evaluator is being shown. That routes the relook to the
evaluator lever (R4's leave-one-out ensemble measured +0.0224 at credit
grade, cell B3 FLAT; the S3 `A1E` arm is the 100M version of exactly that),
and it makes the "value-limited, not dose-limited" reading on the STATUS
record stronger, not weaker. It would NOT license depth: S2 returned silence,
and R3 already measured the M→L 4× at +0.0025 [−0.0086, +0.0136].

**One rung is worth ±0.02** (three n=3000 redraws of one checkpoint spread
0.0200). Read the three lanes' shapes together; never one cell against its
neighbour.
