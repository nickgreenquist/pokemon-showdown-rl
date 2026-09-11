#!/bin/bash
# EG10/EG05 — the EVALUATOR axis re-asked under a WORKING selector.
# Pre-reg: the AMENDMENT 2026-09-11 block in configs/eval/search_s3_100m.yaml.
#
# bash-3.2-safe. Liveness = chunk-file progress via ch3_eval's own resume
# logic (a died job relaunches and skips finished chunks), max 2 relaunches
# per job. ~45 s stagger (the torch lazy-init SIGSEGV landmine: a lane can die
# at startup before any log line, so stagger AND verify individually).
# EG05 is EXPLORATORY and runs LAST, only after the verdict arm is done, so it
# never competes with EG10 for the box.
#   nohup bash scripts/search_evalgate_queue.sh > results/search_s3_100m/eg_queue.log 2>&1 &
set -u
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1
# Unbuffered: stdout is redirected to a file, so without this the job's
# startup provenance (realized usernames, evaluator members, the SF-13
# sentinel line) is invisible until the first chunk flushes -- which on a
# search arm is 15+ minutes of not knowing whether the arm is even right.
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
PREREG=configs/eval/search_s3_100m.yaml
RDIR=results/search_s3_100m
mkdir -p "$RDIR"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

run_group() {
  GROUP=$1; shift
  JOBS="$*"
  TRY=0
  while [ $TRY -le 2 ]; do
    PIDS=""
    LAUNCHED=0
    for J in $JOBS; do
      if [ -f "$RDIR/$J.final.json" ]; then
        log "$GROUP: $J final exists, skipping"
        continue
      fi
      log "$GROUP: launching $J (try $TRY)"
      taskpolicy -b $PY scripts/ch3_eval.py --prereg "$PREREG" --job "$J" \
        > "$RDIR/$J.log" 2>&1 &
      PIDS="$PIDS $!"
      LAUNCHED=1
      sleep 45
    done
    [ $LAUNCHED -eq 0 ] && return 0
    # Verify each lane individually rather than trusting the group.
    sleep 120
    for J in $JOBS; do
      [ -f "$RDIR/$J.final.json" ] && continue
      if pgrep -f "ch3_eval.py --prereg $PREREG --job $J" > /dev/null; then
        log "$GROUP: $J alive"
      else
        log "$GROUP: $J NOT RUNNING 165 s after launch -- will relaunch"
      fi
    done
    for P in $PIDS; do
      wait "$P" || log "$GROUP: a job exited nonzero (finals checked below)"
    done
    MISSING=0
    for J in $JOBS; do
      [ -f "$RDIR/$J.final.json" ] || { MISSING=1; log "$GROUP: $J has no final"; }
    done
    [ $MISSING -eq 0 ] && { log "$GROUP: complete"; return 0; }
    TRY=$((TRY+1))
  done
  log "$GROUP: GIVING UP after 3 tries"
  return 1
}

log "START. Tree state at launch: the only uncommitted paths are another"
log "agent's in-progress monster pre-reg files. ch3_eval records NO git"
log "provenance (git_dirty is stamped by rl/train.py only), and the pre-reg,"
log "ch3_eval and rl/search that these jobs depend on are all committed."
log "Banked comparators at the SAME delta 0.10: s104 0.80900, s112 0.82400,"
log "s120 0.80667. Greedy: s104 0.78933, s112 0.78233, s120 0.79433."
run_group EG10 eg10_s104 eg10_s112 eg10_s120
log "EG10 done; starting the exploratory EG05"
run_group EG05 eg05_s112
log "ALL DONE"
