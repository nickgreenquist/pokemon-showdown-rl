#!/bin/bash
# The BC-clone anchor leg for the LADDER R5 committee, under
# configs/eval/monster_bcclone.yaml. Detached, resume-safe (chunks skip when
# their JSON exists), rate-readable. SEQUENTIAL: one arm at a time, rule 2.
#
#   nohup bash scripts/monster_bcclone_queue.sh > logs/monster_bcclone/queue.nohup 2>&1 &
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t monster_bcclone_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT=results/monster_bcclone
LOG=logs/monster_bcclone
mkdir -p "$LOG" "$OUT"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }
lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no local Showdown server on :8000"; exit 1; }
log "guard ok: server up"
for arm in CEW CW104 CW112 CW120 CH104 CH112 CH120; do
  f="$OUT/$(echo $arm | tr 'A-Z' 'a-z').final.json"
  if [ -f "$f" ]; then log "$arm SKIP (final exists)"; continue; fi
  log "$arm launching (500 battles vs the clone)"
  "$PY" scripts/ch3_r4_anchors.py --prereg configs/eval/monster_bcclone.yaml \
      --arm "$arm" --out-dir "$OUT" >> "$LOG/$arm.log" 2>&1
  if [ -f "$f" ]; then
    log "$arm DONE: $("$PY" -c "import json;d=json.load(open('$f'));print(round(d['eval/win_rate'],4),'n',d['episodes'],'ties',round(d['ties_from_returns'],4))")"
  else
    log "$arm NO FINAL -- see $LOG/$arm.log"
  fi
  sleep 10
done
log "QUEUE DONE"
