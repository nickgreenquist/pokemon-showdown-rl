#!/bin/bash
# Foul Play's evaluator in our search (configs/eval/fp500_r5.yaml). Hacking
# run, detached and resume-safe; each arm skips if its JSON exists.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t fp500_r5_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/fp500_r5.yaml
OUT=results/fp500_r5
LOG=logs/fp500_r5
mkdir -p "$LOG" "$OUT"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no server on :8000"; exit 1; }
pgrep -f "bin/python -m rl.train" > /dev/null 2>&1 && { log "REFUSING: rl.train alive"; exit 1; }
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
  # SMOKE_BATTLES forces the runner to prefix the tag with `smoke_` so a smoke
  # can never overwrite a real arm's JSON -- so the existence check has to look
  # for the SAME name the runner will write, or it reports a successful smoke
  # as "NO JSON" (which is exactly what it did on the first run, 2026-09-17).
  case "$extra" in *SMOKE_BATTLES=*) tag="smoke_$tag";; esac
  if [ -f "$OUT/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching"
  env PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 $extra \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$OUT/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/$tag.json'))
print(round(d['our_win_rate'], 4), 'n', d['battles_finished'],
      'override', round(d.get('search/override_rate') or -1, 4),
      'ms', round(d.get('search/ms_mean') or -1, 1),
      'fired', round(d.get('heuristic/fired_rate') or -1, 3))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log"
  fi
  sleep 30
}

# No smoke: both vehicles crossed this seat path earlier today (fpeval_r5).
# No sweep and no pin: both arms are GREEDY (no selector, no delta).
log "PHASE R: W500 (500 battles @500ms, ~4.5 h), W020 (500 @20ms)"
for arm in W500 W020; do
  fparm "$arm" "$(echo $arm | tr 'A-Z' 'a-z')"
done
log "PHASE R DONE"
log "QUEUE DONE"
