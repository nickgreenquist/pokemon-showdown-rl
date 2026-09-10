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
#      running makes both arms wrong and the ratio meaningless. This step is
#      additionally HELD behind a sentinel file (`.ab_go`) that a human
#      touches, because "idle" includes the maintainer's own work and Chrome,
#      which no check in here can see.
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
  # THE HAZARD, and it bit twice while this was being written. `runs/`,
  # `results/`, `logs/` and `data/` are ALL GITIGNORED, and `git worktree
  # remove` counts a worktree carrying only ignored files as CLEAN — it deletes
  # them without a word. First miss: migrating directory-by-directory, when
  # `results/t1` exists in BOTH trees (the worktree has leg_a/leg_b from the
  # chain, main has the leg_d re-run by hand), so a whole-directory skip would
  # have stranded two files. Second miss: `data/` was not on the list at all,
  # and it holds the 480 MB, 5,000,000-pair team bank whose sha256 every gate
  # record cites — 41 minutes to regenerate and a different sha at the end.
  #
  # So the list is not hand-maintained any more. MIGRATE is what comes home,
  # DISPOSABLE is what is provably rebuildable, and ANY OTHER ignored path
  # blocks the removal. A new gitignored directory added six months from now
  # fails this closed instead of vanishing.
  MIGRATE="runs results logs data"
  DISPOSABLE_RE='^(\.pytest_cache/|engine/pkmn_gen1/target/|pokemon_showdown_rl\.egg-info/|.*__pycache__/)$'

  for d in $MIGRATE; do
    [ -d "$WT/$d" ] || continue
    mkdir -p "$MAIN/$d"
    # --remove-source-files deletes each file ONLY after rsync has verified the
    # transfer, so what is LEFT BEHIND afterwards is exactly the set of
    # collisions --ignore-existing declined to touch. That makes the leftovers
    # the verification: no separate checksum pass, and no window in which a
    # file exists in neither tree.
    rsync -a --ignore-existing --remove-source-files "$WT/$d/" "$MAIN/$d/" 2>>"$LOG" \
      && say "  merged $d/ into main (files already in main were left alone)" \
      || say "  RSYNC FAILED for $d/ — nothing will be removed"
  done

  # Anything still in a migrated directory collided. Report each with whether
  # the two copies actually differ, keep both, and block the removal — two
  # trees disagreeing about a result is a thing to look at, not to resolve
  # with a coin flip.
  orphans=0; collisions=0
  for d in $MIGRATE; do
    [ -d "$WT/$d" ] || continue
    while IFS= read -r rel; do
      if [ ! -e "$MAIN/$d/$rel" ]; then
        say "  ORPHAN, in the worktree only: $d/$rel"; orphans=$((orphans+1))
      elif cmp -s "$WT/$d/$rel" "$MAIN/$d/$rel"; then
        say "  duplicate, identical both sides: $d/$rel"; collisions=$((collisions+1))
      else
        say "  COLLISION, contents DIFFER: $d/$rel (kept on both sides)"
        collisions=$((collisions+1))
      fi
    done < <(cd "$WT/$d" && find . -type f -print | sed 's|^\./||')
  done

  # THE FAIL-CLOSED CHECK: every gitignored path git still sees in the worktree
  # must be one we migrated or one we can prove is rebuildable.
  unknown=0
  while IFS= read -r ig; do
    # Match the FIRST PATH SEGMENT: git reports `results/d1/`, `results/t1/`
    # and friends separately, because `results/` itself is partially tracked.
    # A top-level ignored FILE has no segment to strip, so it falls through to
    # the disposable test and is flagged — which is the fail-closed behaviour.
    case " $MIGRATE " in *" ${ig%%/*} "*) continue ;; esac
    if ! printf '%s' "$ig" | grep -Eq "$DISPOSABLE_RE"; then
      say "  UNRECOGNISED IGNORED PATH: $ig — not migrated, not known-disposable"
      unknown=$((unknown+1))
    fi
  done < <(git -C "$WT" status --ignored --porcelain 2>/dev/null | awk '{print $2}' | sort -u)
  say "teardown check: $orphans orphan(s), $collisions collision(s), $unknown unrecognised ignored path(s)"

  if [ "$orphans" -eq 0 ] && [ "$collisions" -eq 0 ] && [ "$unknown" -eq 0 ]; then
    # `git worktree remove` also refuses on a dirty tree, which is a second,
    # independent safety: a refusal means something is uncommitted in there.
    if git worktree remove "$WT" 2>>"$LOG"; then
      say "worktree removed"
    else
      say "worktree NOT removed — git refused it; left in place on purpose"
    fi
    git worktree prune
  else
    say "worktree KEPT — removing it now would delete gitignored files outright"
  fi
fi

# ---- 2. the test suite ------------------------------------------------------
say "=== pytest tests/ (engine env, main tree) ==="
POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
  "$EPY" -m pytest tests/ -q -rf > logs/pytest_main.log 2>&1
say "pytest rc=$? :: $(tail -n 3 logs/pytest_main.log | tr '\n' ' ')"

# ---- 2.5 the thread bench ---------------------------------------------------
# Runs HERE, before the A/B, for two reasons. It needs an idle box (it is a
# timing measurement), and its answer may change what the A/B should measure:
# if the update parallelises, the config anyone would actually run is not
# torch_threads 1, and an A/B of the un-tuned config would be measuring a
# machine nobody uses. It needs the teardown to have landed the checkpoint and
# the team bank in main, which step 1 did.
CKPT=runs/engine_a1_s66/ckpt_012000008.pt
BANK=data/engine/teams_a1_5000000.bin
if [ -e "$CKPT" ] && [ -e "$BANK" ]; then
  say "=== thread bench: does the PPO update parallelise? ==="
  POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
    "$EPY" scripts/engine_thread_bench.py "$CKPT" --threads 1,2,4,8 --repeats 3 \
    --team-bank "$BANK" >> "$LOG" 2>&1
  say "thread bench rc=$? -> results/engine_a1/thread_bench.json"
else
  say "thread bench SKIPPED: $CKPT or $BANK not in main (teardown did not land it)"
fi

# ---- 3. the head-to-head A/B ------------------------------------------------
# HOLD GATE. The A/B is the one thing here that measures WALL CLOCK, so it must
# not start while anyone else is using the box — including the maintainer, who
# asked (2026-09-10) to close their own work and Chrome first. Everything above
# this line runs unattended; nothing below it starts until the sentinel exists.
GO="$MAIN/.ab_go"
if [ ! -e "$GO" ]; then
  say "HOLDING: the A/B needs an idle box. Waiting for $GO"
  say "         release it with:  touch $GO"
  while [ ! -e "$GO" ]; do sleep 30; done
fi
say "hold released — starting the A/B"
# One-shot: consumed here so a later re-run of this script holds again rather
# than silently inheriting a stale go-ahead.
rm -f "$GO"

say "=== A/B variant 1: production-vs-production (engine k=256), ABBA ==="
"$EPY" scripts/engine_ab_speed.py --steps 1000000 --order ABBA --engine-k 256 \
     --out results/engine_a1/ab_speed_k256.json >> "$LOG" 2>&1
say "variant 1 rc=$?"
say "=== A/B variant 2: matched concurrency (engine k=8), ABBA ==="
"$EPY" scripts/engine_ab_speed.py --steps 1000000 --order ABBA --engine-k 8 \
     --out results/engine_a1/ab_speed_k8.json >> "$LOG" 2>&1
say "variant 2 rc=$?"

# ---- 4. the readout ---------------------------------------------------------
# Rendered from the JSON rather than typed, because the port has produced
# several speed numbers today and only one of them is an A/B. The renderer
# carries the scope and the disclosures with the number so the wrong one
# cannot be quoted by accident.
say "=== rendering the speed readout ==="
"$EPY" scripts/engine_speed_readout.py --write docs/engine_port/SPEEDUP.md >> "$LOG" 2>&1
say "readout rc=$? -> docs/engine_port/SPEEDUP.md"
say "POST-LANE QUEUE DONE"
