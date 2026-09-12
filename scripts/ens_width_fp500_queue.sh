#!/bin/bash
# FP@500 follow-on for configs/eval/ens_width_offfp.yaml -- waits for the
# 20 ms queue (scripts/ens_width_queue.sh) to print QUEUE DONE, then runs the
# two 500 ms arms SEQUENTIALLY. Foul Play's budget is wall-clock: nothing else
# may share the box with these arms, which is why this is a separate waiter
# rather than an edit to the running (frozen) queue.
#
#   nohup bash scripts/ens_width_fp500_queue.sh > logs/ens_width/fp500.nohup 2>&1 &
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t ens_width_fp500_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
FPPREREG=configs/eval/ens_width_offfp.yaml
FPRES=results/ens_width_offfp
LOG=logs/ens_width
mkdir -p "$LOG" "$FPRES"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

log "FP500 waiter: holding until the 20 ms queue prints QUEUE DONE"
until grep -q "QUEUE DONE" "$LOG/queue.log" 2>/dev/null; do sleep 60; done
sleep 60   # let Showdown reap the last 20 ms pair's rooms

fparm() {  # one off-FP arm through the incident-hardened runner, blocking
  local arm="$1" tag="$2"
  if [ -f "$FPRES/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching (off FP@500, n from pre-reg)"
  PREREG="$FPPREREG" ARM="$arm" TAG="$tag" OUT="$FPRES" STALL_POLLS=120 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$FPRES/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "import json;d=json.load(open('$FPRES/$tag.json'));print(d['our_win_rate'], 'n', d['battles_finished'], 'ties', d['ties'], 's/battle', d['sec_per_battle'], 'budget', d.get('declared_search_time_ms'))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log and $FPRES/$tag.runner.log"
  fi
  sleep 30
}

log "PHASE 3: off FP@500 (sequential; ~2.2 h + ~1.1 h)"
fparm ENS3F500 ens3f500
fparm G112F500 g112f500
log "FP500 QUEUE DONE"
