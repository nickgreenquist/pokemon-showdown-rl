#!/bin/bash
# IDEAS 8.6 phase S -- the MECHANISM screen for the tree's budget
# (configs/eval/tree_budget_r5.yaml). Hacking run, detached and resume-safe;
# each arm skips if its JSON exists.
#
#   nohup bash scripts/tree_budget_queue.sh > logs/tree_budget_r5/queue.nohup 2>&1 &
#
# It is SHORT on purpose. The read is per-DECISION (KL(pi'||prior), pi_top1,
# argmax_moved) with ~1,300 samples in a 40-battle arm, so the mechanism is far
# better determined here than a win rate would be at n=4,375. If the budget does
# not move pi' off the prior, the expensive rungs never run.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t tree_budget_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/tree_budget_r5.yaml
OUT=results/tree_budget_r5
LOG=logs/tree_budget_r5
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
  env PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=90 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 $extra \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$OUT/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/$tag.json'))
def g(k, nd=4):
    v = d.get(k)
    return round(v, nd) if isinstance(v, (int, float)) else v
print('win', g('our_win_rate'), 'ms', g('search/ms_mean', 1),
      'KL', g('tree/kl_pi_prior'), 'pi_top1', g('tree/pi_top1', 3),
      'moved', g('tree/argmax_moved', 3))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log"
  fi
  sleep 30
}

# SMOKE: the expert counters have never crossed the FP seat path, and a crash on
# a real pair poisons it for hours.
if [ ! -f "$OUT/smoke_bsm.json" ]; then
  log "SMOKE: the expert counters through the FP seat, throwaway pair"
  fparm BSM bsm "SMOKE_BATTLES=2"
  [ -f "$OUT/smoke_bsm.json" ] || { log "SMOKE FAILED -- not starting phase S"; exit 1; }
  log "SMOKE: $("$PY" -c "
import json; d=json.load(open('$OUT/smoke_bsm.json'))
print('KL', d.get('tree/kl_pi_prior'), 'pi_top1', d.get('tree/pi_top1'),
      'moved', d.get('tree/argmax_moved'), 'ms', d.get('search/ms_mean'))")"
fi

# CHEAPEST RUNG FIRST. iters 900 costs ~9x iters 100 per decision, so if the
# smoke or BS1 reveals a problem it is found for two minutes rather than twenty.
log "PHASE S: gumbel at iters 100/300/900 + visits at 900, n=40 each"
for arm in BS1 BS3 BS9 BSV; do
  fparm "$arm" "$(echo $arm | tr 'A-Z' 'a-z')"
done
log "PHASE S DONE"
"$PY" scripts/tree_budget_readout.py > "$OUT/READOUT.txt" 2>&1
log "READOUT written to $OUT/READOUT.txt"
log "QUEUE DONE"
