#!/bin/bash
# IDEAS 2.10 + 8.5 in one session (configs/eval/backup_gate_r5.yaml). Hacking
# run, detached and resume-safe; each arm skips if its JSON exists.
#
#   nohup bash scripts/backup_gate_queue.sh > logs/backup_gate_r5/queue.nohup 2>&1 &
#
# SEQUENTIAL THROUGHOUT, and not as a preference: a second concurrent Foul Play
# weakens both opponents and flatters both seats.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t backup_gate_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/backup_gate_r5.yaml
OUT=results/backup_gate_r5
LOG=logs/backup_gate_r5
mkdir -p "$LOG" "$OUT"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no server on :8000"; exit 1; }
pgrep -f "bin/python -m rl.train" > /dev/null 2>&1 && { log "REFUSING: rl.train alive"; exit 1; }
# A SECOND FP BLOCK WOULD FLATTER BOTH SEATS. Refuse rather than interleave.
pgrep -f "ch3_fp_h2h.py" > /dev/null 2>&1 && { log "REFUSING: another FP seat is alive"; exit 1; }
"$PY" - <<'PYEOF2' || { log "USERNAME PREFIX CHECK FAILED"; exit 2; }
import glob, re, sys
names = set()
for f in glob.glob("configs/eval/*.yaml"):
    for m in re.finditer(r"(?:seat_username|fp_username|seat|fp|bot):\s*([a-z0-9]+)\b", open(f).read()):
        names.add(m.group(1))
bad = [(a, b) for a in sorted(names) for b in sorted(names) if a != b and b.startswith(a)]
if bad:
    print("PREFIX COLLISIONS:", bad[:10]); sys.exit(1)
print(f"{len(names)} usernames, prefix-free")
PYEOF2
log "guards ok"

fparm() {
  local arm="$1" tag="$2" extra="${3:-}"
  case "$extra" in *SMOKE_BATTLES=*) tag="smoke_$tag";; esac
  if [ -f "$OUT/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching"
  env PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 $extra \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$OUT/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/$tag.json'))
def g(k, nd=4):
    v = d.get(k)
    return round(v, nd) if isinstance(v, (int, float)) else v
print(g('our_win_rate'), 'n', d['battles_finished'],
      'override', g('search/override_rate'),
      'ms', g('search/ms_mean', 1),
      'oppreplies', g('depth2/opp_replies_mean', 2),
      'drop', g('depth2/minimax_drop', 3),
      'searchrate', g('disagree/search_rate', 3))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log"
  fi
  sleep 30
}

# SMOKE FIRST on a THROWAWAY pair: neither opp_k nor disagree has ever crossed
# the FP seat path, and a crash on a real pair poisons it for hours.
if [ ! -f "$OUT/smoke_smk.json" ]; then
  log "SMOKE: opp_k + the disagreement gate through the FP seat, throwaway pair"
  fparm SMK smk "SMOKE_BATTLES=2"
  [ -f "$OUT/smoke_smk.json" ] || { log "SMOKE FAILED -- not starting phase S"; exit 1; }
  log "SMOKE: $("$PY" -c "
import json; d=json.load(open('$OUT/smoke_smk.json'))
print('oppreplies', d.get('depth2/opp_replies_mean'),
      'searchrate', d.get('disagree/search_rate'),
      'ms', d.get('search/ms_mean'))")"
fi

log "PHASE S: B2 delta sweep toward D1O's 0.193 override + GV's realized gate rate"
for arm in B2A B2B B2C GV; do
  fparm "$arm" "$(echo $arm | tr 'A-Z' 'a-z')"
done
log "PHASE S DONE"

git status --porcelain | grep -q . && { log "DIRTY TREE -- refusing to pin (rule 3)"; exit 1; }
if grep -q "PINB\|PIND" "$PREREG"; then
  "$PY" scripts/backup_gate_pin.py --commit >> "$LOG/pin.log" 2>&1 || { log "PIN FAILED -- see $LOG/pin.log"; exit 1; }
else
  log "PIN already applied"
fi
log "PIN: $(grep -- '->' "$LOG/pin.log" | tr '\n' ' ')"

log "PHASE R: D1O/B2O/B2R/DGV/DRV/DUM/GC, 1000 each"
for arm in D1O B2O B2R DGV DRV DUM GC; do
  fparm "$arm" "$(echo $arm | tr 'A-Z' 'a-z')"
done
log "PHASE R DONE"
log "QUEUE DONE -- readout is scripts/backup_gate_readout.py"
