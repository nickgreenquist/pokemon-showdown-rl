#!/usr/bin/env bash
# POST-LANE QUEUE — everything that needs the box to itself, in order.
#
# Each step below is blocked on the A-1 lanes for a DIFFERENT reason, and the
# reasons are why this is a queue rather than three things run in parallel:
#
#   1. TEARDOWN of the engine worktree. The lanes' run dirs and the gate
#      chain's results live inside it, so they move first and the directory
#      goes last. (The `pkmn-engine-port` env already resolves `rl` to MAIN
#      and `pkmn_gen1` to site-packages, so nothing needs re-pointing —
#      verified 2026-09-10.)
#   2. `pytest tests/` — the suite contains LIVE-SERVER tests whose poke-env
#      seats would collide with the lanes' in-loop eval seats and cost A-1 its
#      rungs. Also the documented flake: the full-episode contract test fails
#      only when the whole suite runs with a server up.
#   3. the head-to-head A/B — a WALL-CLOCK measurement, so anything else
#      running makes both arms wrong and the ratio meaningless.
#
# The A/B runs ABBA: two replicates per arm, alternated so that a linear drift
# in the box (thermal, background creep) lands on both arms equally. ABAB would
# NOT do that — it leaves A at mean position 2.0 against B at 3.0. More
# replicates are available (--order ABBAABBA) but buy little: the ratio's
# STATISTICAL se is already 0.62% at 1M steps, and drift, not sample size, is
# the binding error term.
set -uo pipefail
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
MAIN=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
WT=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-engine
EPY=/opt/anaconda3/envs/pkmn-engine-port/bin/python
LOG=logs/post_lane_queue.log
say(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

say "QUEUED: waiting for the gate chain and all A-1 lanes to finish"
while pgrep -f "bash scripts/engine_gates.sh" >/dev/null \
   || pgrep -f "bin/python -m rl.train --config configs/engine_a1" >/dev/null; do
  sleep 60
done
say "gate chain and lanes done — box is mine"

# ---- 1. teardown: bring the worktree's artifacts home, then drop it ---------
if [ -d "$WT" ]; then
  say "=== teardown: migrating engine-worktree artifacts into main ==="
  for d in runs results logs; do
    [ -d "$WT/$d" ] || continue
    mkdir -p "$MAIN/$d"
    # -n so an existing file in main is never clobbered by the worktree copy;
    # collisions are reported and left for a human rather than resolved here.
    for p in "$WT/$d"/*; do
      [ -e "$p" ] || continue
      b=$(basename "$p")
      if [ -e "$MAIN/$d/$b" ]; then
        say "  SKIP $d/$b — already present in main (left in the worktree)"
      else
        mv "$p" "$MAIN/$d/$b" && say "  moved $d/$b"
      fi
    done
  done
  # `git worktree remove` REFUSES on a dirty or untracked-carrying worktree,
  # which is the safety we want: a refusal means something is still in there.
  if git worktree remove "$WT" 2>>"$LOG"; then
    say "worktree removed"
  else
    say "worktree NOT removed — it still holds something; left in place on purpose"
  fi
  git worktree prune
fi

# ---- 2. the test suite ------------------------------------------------------
say "=== pytest tests/ (engine env, main tree) ==="
POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
  "$EPY" -m pytest tests/ -q -rf > logs/pytest_main.log 2>&1
say "pytest rc=$? :: $(tail -n 3 logs/pytest_main.log | tr '\n' ' ')"

# ---- 3. the head-to-head A/B ------------------------------------------------
say "=== A/B variant 1: production-vs-production (engine k=256), ABBA ==="
"$EPY" scripts/engine_ab_speed.py --steps 1000000 --order ABBA --engine-k 256 \
     --out results/engine_a1/ab_speed_k256.json >> "$LOG" 2>&1
say "variant 1 rc=$?"
say "=== A/B variant 2: matched concurrency (engine k=8), ABBA ==="
"$EPY" scripts/engine_ab_speed.py --steps 1000000 --order ABBA --engine-k 8 \
     --out results/engine_a1/ab_speed_k8.json >> "$LOG" 2>&1
say "variant 2 rc=$?"
say "POST-LANE QUEUE DONE"
