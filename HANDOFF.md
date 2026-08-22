# Handoff — written 2026-08-22 at the maintainer's option ("keep going or
# handoff — up to you"; context was very deep, and R1's remaining pieces are
# verdict-critical, so: handoff). **NOTHING IS RUNNING. Tree green and
# committed (suite 400 passed / 17 skipped). `main` is AHEAD of origin by 7
# commits — push is pending an explicit maintainer word (asked twice).**

Read this, then STATUS.md. Fold anything durable into STATUS/SESSION_LOGS and
restore the empty stub. SESSION_LOGS 2026-08-21 -> -22 has full detail of
everything below; this file is the map, not the record.

## 1. STATE

- **Chapter 3 (SEARCH) is RATIFIED** — 2026-08-21, rulings 1-4 approved
  verbatim; **depth-1 only** ("one turn lookahead is valid"); R4+ needs its
  own pre-reg + ratification. The design is
  `results/design_ch3/ch3_search_design_r2.md` (self-contained; 2-Opus round;
  27 review must-fixes folded; backed up).
- **R0 COMPLETE AND READ OUT: B1 CREDIT** — ensemble-of-4 **0.74633**
  (+0.03600 vs fresh greedy mean 0.71033, bar 0.025, clustered se governed);
  licensed sentence: "ensembling THESE four checkpoints helps" — never
  "ensembling helps". **K0-1 PASS** (V-head AUC pooled deciles 2-8 = 0.780
  >= 0.60) -> V-leaf search allowed. Flip anchor 0.103. placeholder stratum
  1.1% (+0.5% recharge). 27.2 decisions/battle vs SH. mask_desyncs 0/33,000.
  README row added; D26 0.71825 stays the single-agent headline. Readout:
  `results/ch3_r0/r0_readout.json` (+ audit_summary.json), backed up.
- **R1 is ~2/3 BUILT** (parts 1-2 committed, 90b1053 + 311be00):
  poke-engine 0.0.48 gen1 INSTALLED in our 3.13 env + attested 7/0/1
  (`requirements-search.txt` has the exact command — the ONLY valid one);
  `rl/search/bridge.py` (battle1+det -> State), `rl/search/determinize.py`
  (RSD, containment law: active's moves = the encoder's 4 slots),
  `rl/search/shadow_battle.py` (State -> embed_battle surface).
  8 tests in tests/test_ch3_bridge.py; whole pipeline runs end-to-end on
  synthetic battles. Measured: per-branch leaf ~90us; implied Dose-M
  ~73 ms/decision (~1.8 h/seed) — cheaper than all design estimates.

## 2. WHAT'S NEXT — R1 part 3 (fresh session; read design r2 §3-§5 FIRST)

1. **Harvest recorder**: 500 battles, both seats logged (seat-2 offline-only;
   FG-4 discipline), joint actions + next decision states. ~14.5k
   transitions. Server needed.
2. **FG battery** (`scripts/ch3_fidelity_check.py`): FG-1..FG-8 per the r2
   design §5 table — FG-2's HP comparison is BANDED to the roll interval
   (review-2 MF-2: exact match is impossible under average damage), FG-2k
   `ko_disagreement` (>0.05 -> build the 2-point roll expansion), FG-6
   budget = field FAMILIES measured then frozen, FG-7 support >= 0.99.
3. **`rl/search/matrix.py`**: the L6 -> engine-action mapping LAW (r2 §3
   table: slots -> determinized Move.id; OTHER_MOVE -> renormalize q, mass
   recorded; SWITCH -> uniform-over-legal-bench per det), renormalized
   top-6 cell fill, BR solve, tie-break matrix -> prior -> index, SHARED
   determinizations across all cells, raising watchdog.
4. **R1-0 spike**: 200 real harvest decisions through the complete Dose-M
   search -> freezes ms/decision + leaves/decision -> R2-8's baseline, F3's
   baseline, watchdog constants. (My 73ms is synthetic-stub grade only.)
5. **Cap-of-2 rejection** in the bench sampler (determinize.py TODO; FG-7
   is the arbiter of whether the uniform shortcut survives).
6. R1 kill: any blocking FG unfixable in 3 evenings -> A-sidecar fallback
   (design §2) or chapter stops.

## 3. OPS

- Server up on :8000 (simulator 4). No lanes, no crons, **no monitors** (all
  session-scoped/dead; the R0 completion monitor served its purpose).
- Push pending: 7 local commits (ratification, R0 build, R0 readout, R1
  parts 1-2, this handoff). Seeds 66/67, 75/76, 83/84, 93/94 still held —
  chapter 3 burns none.
- Backups current: design_ch3 + ch3_r0 both copied to
  ../pokemon-showdown-rl-d25-backup-20260815/.

## 4. LANDMINES THIS SESSION ADDED

- **poke-engine State.to_string/from_string DROPS all volatile_statuses**
  (valid names included). Construct State OBJECTS; never round-trip through
  strings for anything load-bearing. FG-1 is a string-stability check only.
- **Applied-state readback UPPERCASES mon ids**, and sides are padded to 6
  with filler mons (id "none") — shadow_battle normalizes/skips; anything
  new reading engine states must too.
- **poke-engine's DEFAULT build is GEN 4** and pip's wheel cache ignores
  config-settings: only ever install via the requirements-search.txt
  command; run FG-5's 7/0/1 discriminator on every rung (a gen4/gen9 .so is
  the failure it exists to catch).
- The engine does NOT enforce partialtrap/mustrecharge (sleep/freeze it
  does); Reflect/LightScreen are gen1 VOLATILES in-engine (side_conditions
  mapping is a silent no-op); **Light Screen is unobservable from battle1**
  (no poke-env Effect member) — named unmodellable, out of FG-2's field set.
- `rl/envs/showdown._opponent_move_slots` yields (Move OBJECT, prob) tuples,
  not id strings.
- **macOS `find` has no GNU `-newermt '-10 minutes'`** — it errors silently
  in $( ) and the branch reads empty. The Monitor stall-check bug cost one
  false alarm; use `stat -f %m` mtimes.
- `scripts/ch3_eval.py` asserts both encoder env vars, checkpoint sha256s
  vs the pre-reg, and simulator:4 at preflight — a lane that dies instantly
  probably tripped one of those, not the server.
