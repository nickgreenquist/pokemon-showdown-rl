# Stage-1 history features — design audit (zero new state; plus one encoder bug found)

Provenance: audited 2026-08-07 by a session subagent against installed poke-env 0.15.0
source and measured over two tapes offline (20 battles/1,154 decisions + 50/1,273). No
server contact. Curated by the session.

## The core finding: no new state is needed

`AbstractBattle._replay_data` (abstract_battle.py:146) is an always-on, per-battle protocol
event log appended as the FIRST line of `parse_message` (:566) — BEFORE the ignore filter —
so `-crit`, `-supereffective`, `-resisted`, `-miss`, `-fail` (all in MESSAGES_TO_IGNORE,
recoverable from nowhere else) are in it. Both the live path (Player._handle_battle_message)
and the tape replay (tape_to_dataset.apply_message) funnel through the same `parse_message`,
so a history block derived from `_replay_data` CANNOT diverge between paths by construction
— the dispatch was diffed line by line (one asymmetry: `_strict_battle_tracking` on
parse_request; irrelevant to `_replay_data`) and measured: every `|request|` arrives alone in
its own frame (1,239/1,239), so the decision instant is a frame boundary in both paths. A
hand-maintained History object (option i) would need mirrors in SeamPlayer, RecordingPlayer,
poke-env's internal `_EnvPlayer` (unsubclassable), and apply_message — strictly dominated.

Also already on `Pokemon`, unread by our encoder: `last_move` (non-None on ~48% of decisions;
~95% when active ≥2 turns; set for the opponent too; cleared on switch-out), `_active_turns`
(turns since switch-in; public `first_turn`), and benched mons' live SLP `status_counter`
(we only encode it for actives). Opponent PP tracking measured reliable (2,015/2,021 slots).

## The proposed 22-dim block (env-var-gated, POKEMON_RL_ENCODER_HIST, default off)

Appended as a pure SUFFIX (stronger property than v2's in-block placement: `vec[:807]` stays
bitwise v2). Window = events since the second-to-last `|turn|` marker (mean 9.2 entries, p99
24, backward scan ~free — 78 µs/decision measured against embed_battle's ~1.7 ms).

  [0-1]  our/opp active turns-since-switch-in (/8, capped)
  [2-5]  our last move, one-hot over OUR 4 action-aligned move slots (zeroed on aliased
         placeholder turns, mirroring the aliasing fix)
  [6-9]  opp last move, one-hot over the opponent's 4 slots (prior-filled slots always 0)
  [10-13] we/they switched; we/they moved (last window)
  [14-15] our/their active was crit          [16-17] SE hit on us/them
  [18-19] we/they lost the turn to |cant|    [20] a move missed   [21] a move failed

Measured firing rates: switches ~51%, last-move resolution ~48%, crit 5-6%, SE 4-7%,
cant 5-6%, miss 5.5%, fail 7%. `|cant|` carries WHICH incapacity (par 66/51, recharge 32/48,
slp 24/73 across tapes) — the snapshot's PAR bit cannot distinguish "paralysed and moved"
from "full para, lost the turn".

Implementation: ~90 lines in showdown.py + stub attrs in test_showdown_env (read directly,
never getattr-defaulted) + subprocess test file + fidelity-gate COVERAGE_TAGS extension
(obs_fidelity_check.py:80 currently lacks -crit/-supereffective/-miss/cant/switch/move — a
coverage PASS today would not exercise these paths). Fidelity re-run ~4 min, needs server.
Screen = the v2 workflow: re-embed (~5 min for 180k rows measured at 580 rows/s) + refits.
Excluded deliberately: last-window damage magnitudes (needs a second unbounded scan — price
separately), effect turn counters (measured 0 nonzero in gen1), sleep-counter rescale (inert
by the Arm-B linear-in-encoded-features rule).

## BUG FOUND (applies to v1 AND v2, live now): the MUST_RECHARGE flag is structurally dead

`_VOLATILES` includes `Effect.MUST_RECHARGE` (written at active-extras offset +10), but
poke-env routes `|-mustrecharge|` to the bool `pokemon.must_recharge` (abstract_battle.py:
1009-1011) and NEVER starts an Effect; measured 0/2,427 decisions with the Effect set vs 185
(7.6%) with the bool set. Obs indices always-0: v1 207/513, v2 213/617. Consequence beyond a
wasted dim: on recharge and partial-trap placeholder turns there is no status bit and
`battle.trapped` is False (11/1,273), so those turns encode as all-zero move blocks with NO
indicator of why — the aliasing-fix comment's "state stays fully described" claim is wrong
for exactly these cases. Also measured never-firing: PARTIALLY_TRAPPED as an Effect (gen1
traps surface as `|cant|...|partiallytrapped`, no `|-start|`), FOCUS_ENERGY and LEECH_SEED
(reachable, just rare/absent in sample).

Fix (Stage-0, pre-registered with the history screen so reads aren't confounded — obs
semantics change again): replace the Effect.MUST_RECHARGE slot with `bool(mon.must_recharge)`
and add a 1-dim `_move_slots_aliased(battle)` flag. Two dims of truth for placeholder turns.
