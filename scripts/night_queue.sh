#!/bin/bash
# THE NIGHT CHAIN, 2026-09-19. Runs the box's remaining work in order once the
# Foul Play block in front of it finishes.
#
#   nohup bash scripts/night_queue.sh > logs/night/queue.nohup 2>&1 &
#
# WHY A CHAIN AND NOT THREE LAUNCHES. Every job here needs the Showdown server,
# and two Foul Play blocks at once divide the CPU and weaken BOTH opponents --
# which flatters both seats and confounds both blocks. The chain is the cheapest
# way to keep the box busy without ever running two.
#
# EACH STEP IS INDEPENDENT OF THE ONE BEFORE IT. The 8.6 screen and the
# antisymmetry test do not read backup_gate's result, so a bad outcome upstream
# cannot put a later step on a false premise -- the usual objection to chaining
# unattended work does not apply.
#
# EACH STEP IS ALSO IDEMPOTENT: the FP queues skip an arm whose JSON exists, and
# the antisymmetry run rewrites its own output. A death costs the step in flight.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t night_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
LOG=logs/night
mkdir -p "$LOG"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

# ---- 1. WAIT for the block in front. Poll the PROCESS, not the log: a queue
# that dies without writing QUEUE DONE would otherwise hold this one forever.
log "waiting for backup_gate_r5 to finish"
waited=0
while pgrep -f "backup_gate_queue|ch3_fp_h2h.py" > /dev/null 2>&1; do
  sleep 60
  waited=$((waited + 1))
  if [ $((waited % 30)) -eq 0 ]; then log "still waiting (${waited} min)"; fi
  if [ "$waited" -gt 900 ]; then log "GIVING UP after 15 h"; exit 1; fi
done
log "front block clear after ${waited} min"
sleep 60      # let Showdown reap the last rooms

# ---- 2. read out the block that just finished
"$PY" scripts/backup_gate_readout.py > results/backup_gate_r5/READOUT.txt 2>&1 \
  && log "backup_gate readout written" || log "backup_gate readout FAILED"

# ---- 3. IDEAS 8.6 phase S -- the mechanism screen (~50 min)
log "launching the 8.6 tree-budget screen"
bash scripts/tree_budget_queue.sh >> "$LOG/tree_budget.nohup" 2>&1
log "8.6 screen returned: $(tail -1 logs/tree_budget_r5/queue.log 2>/dev/null)"

# ---- 4. the antisymmetry test (~20 min, no Foul Play, server only)
log "launching the critic antisymmetry test"
"$PY" scripts/critic_antisymmetry.py --battles 300 --dets 4 \
  > "$LOG/antisymmetry.log" 2>&1 \
  && log "antisymmetry DONE: $(grep 'implied PER-SIDE' "$LOG/antisymmetry.log" || echo '?')" \
  || log "antisymmetry FAILED -- see $LOG/antisymmetry.log"

log "NIGHT QUEUE DONE"
