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

# THE GUARD HAS TO SURVIVE THE GAP BETWEEN ARMS, and the first version did not.
# On 2026-09-19 this chain started the 2.13 screen 23 SECONDS after the block in
# front launched its next arm, because:
#   (i) a queue script re-execs from a FROZEN mktemp copy, so its process name
#       is /var/.../night_queue.XXXX and `pgrep -f night_queue.sh` never matched
#       it; and
#   (ii) the FP queues sleep 30 s between arms, so a single point-in-time check
#        can land in a window where nothing is running and still be wrong.
# The fix is both halves: match the frozen names too, and require the box to be
# clear for SEVERAL CONSECUTIVE CHECKS spanning more than the inter-arm sleep.
BUSY='night_queue|tree_budget_queue|backup_gate_queue|ch3_fp_h2h\.py|critic_antisymmetry|foul-play/bin/python'
CLEAR_NEEDED=6          # x 30 s = 3 min, comfortably longer than a 30 s gap
log "waiting for the box to be clear for ${CLEAR_NEEDED} consecutive checks"
waited=0; clear=0
while [ "$clear" -lt "$CLEAR_NEEDED" ]; do
  # EXCLUDE OUR OWN PID: the frozen copy is named night_queue2.XXXX, which
  # matches the pattern, so without this the loop never sees a clear box.
  busy=$(pgrep -f "$BUSY" 2>/dev/null | grep -vx "$$" || true)
  if [ -n "$busy" ]; then
    if [ "$clear" -gt 0 ]; then log "busy again after ${clear} clear checks -- resetting"; fi
    clear=0
  else
    clear=$((clear + 1))
  fi
  sleep 30
  waited=$((waited + 1))
  if [ $((waited % 60)) -eq 0 ]; then log "still waiting ($((waited / 2)) min)"; fi
  if [ "$waited" -gt 1800 ]; then log "GIVING UP after 15 h"; exit 1; fi
done
log "box clear after $((waited / 2)) min"
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
