#!/bin/bash
# THE SECOND NIGHT CHAIN: runs after night_queue.sh, on the same rule -- one
# Showdown-facing job at a time, because two divide the CPU and weaken both
# opponents.
#
#   nohup bash scripts/night_queue2.sh > logs/night/queue2.nohup 2>&1 &
#
# STEP: the IDEAS 2.13 action-difference screen. It answers, EXACTLY and with no
# sampling error, whether recalibrating the leaf value changes the action the
# search picks -- both selectors run on the same decisions with the same rng.
# 2.13 is justified by +0.0195 of EXPLAINED VARIANCE, and EV has been measured
# three times not to track strength here, so this is the screen that decides
# whether the row gets an arm or closes.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t night_queue2); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
LOG=logs/night
mkdir -p "$LOG"
log() { echo "[$(date -u +%FT%TZ)] [q2] $*" | tee -a "$LOG/queue.log"; }

log "waiting for night_queue.sh and anything Showdown-facing"
waited=0
while pgrep -f "night_queue.sh|tree_budget_queue|ch3_fp_h2h.py|critic_antisymmetry" > /dev/null 2>&1; do
  sleep 60
  waited=$((waited + 1))
  if [ $((waited % 30)) -eq 0 ]; then log "still waiting (${waited} min)"; fi
  if [ "$waited" -gt 900 ]; then log "GIVING UP after 15 h"; exit 1; fi
done
log "clear after ${waited} min"
sleep 30

if [ -f results/outcome_variance/calib_action_diff.json ]; then
  log "2.13 screen SKIP (json exists)"
else
  log "launching the 2.13 action-difference screen"
  "$PY" scripts/calibration_action_diff.py --battles 200 \
    > "$LOG/calib_action_diff.log" 2>&1 \
    && log "2.13 screen DONE: $(grep 'ACTION CHANGED' "$LOG/calib_action_diff.log" || echo '?')" \
    || log "2.13 screen FAILED -- see $LOG/calib_action_diff.log"
fi
log "QUEUE2 DONE"
