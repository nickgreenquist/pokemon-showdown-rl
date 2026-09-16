#!/bin/bash
# JOURNEY 11.5 -- depth-1 vs depth-2 on the R5 ladder committee, under
# configs/eval/depth2_r5.yaml. Detached, resume-safe, rate-readable
# (CLAUDE.md rule 4). Re-execs from a FROZEN temp copy: never edit a bash
# script an instance is executing (docs/landmines.md).
#
#   nohup bash scripts/depth2_r5_queue.sh > logs/depth2_r5/queue.nohup 2>&1 &
#
# PHASES
#   PRE      username prefix-freeness across every configs/eval/*.yaml, and a
#            2-battle SMOKE of the depth-2 seat on a THROWAWAY pair -- the
#            depth2 kwarg has never crossed the FP seat path, and a crash
#            there poisons a real pair for hours (CLAUDE.md foul-play ops).
#   S        the delta sweep: 7 cells x 60 battles. Measures OVERRIDE RATE and
#            COST. No win rate from phase S is a read.
#   PIN      scripts/depth2_r5_pin.py --commit applies rule R1 from the phase-S
#            override rates, writing D2M's delta over the placeholder.
#   R        the read: D1 (n=3000), D2M (n=3000), D2N (n=1500), G0 (n=1500).
#   READOUT  scripts/depth2_r5_readout.py -> results/depth2_r5/READOUT.txt
#
# SEQUENTIAL THROUGHOUT, and not as a preference: a second concurrent Foul Play
# weakens both opponents and flatters both seats, and every arm carries a
# wall-clock budget. Each arm skips if its JSON exists, so a death costs one arm.
#
# COST, from the 2026-09-16 engineering smoke on this exact object: depth-1
# 78.6 ms/decision, depth-2 260.7 ms (3.3x), ~37 decisions/battle, plus Foul
# Play's own ~40 ms. Phase S ~40 min; phase R ~18 h. That is why this is
# detached and resume-safe rather than run in the foreground.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t depth2_r5_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/depth2_r5.yaml
OUT=results/depth2_r5
LOG=logs/depth2_r5
mkdir -p "$LOG" "$OUT"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

# ---------------------------------------------------------------- PRE
lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no local Showdown server on :8000"; exit 1; }
if pgrep -f "bin/python -m rl.train" > /dev/null 2>&1; then
  log "REFUSING: an rl.train process is alive"; exit 1
fi
"$PY" - <<'PYEOF' || { log "USERNAME PREFIX CHECK FAILED"; exit 2; }
import glob, re, sys
names = set()
for f in glob.glob("configs/eval/*.yaml"):
    for m in re.finditer(r"(?:seat_username|fp_username|seat|fp|bot):\s*([a-z0-9]+)\b", open(f).read()):
        names.add(m.group(1))
names = sorted(names)
bad = [(a, b) for a in names for b in names if a != b and b.startswith(a)]
if bad:
    print("PREFIX COLLISIONS:", bad[:10]); sys.exit(1)
print(f"username inventory: {len(names)} names, pairwise prefix-free")
PYEOF
log "guards ok: server up, no training, usernames prefix-free"

fparm() {  # one off-FP arm through the incident-hardened runner, blocking
  local arm="$1" tag="$2"
  if [ -f "$OUT/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching"
  PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$OUT/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/$tag.json'))
print(round(d['our_win_rate'], 4), 'n', d['battles_finished'],
      'override', round(d.get('search/override_rate') or -1, 4),
      'ms', round(d.get('search/ms_mean') or -1, 1),
      'fired', round(d.get('depth2/fired_rate') or -1, 3))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log and $OUT/$tag.runner.log"
  fi
  sleep 30   # let Showdown reap the finished rooms before the next pair connects
}

# SMOKE on a THROWAWAY pair (D2N's rerun pair), because the depth2 kwarg has
# never crossed this seat path. SMOKE_BATTLES forces a smoke_ tag prefix, so it
# can never overwrite a real arm's JSON.
if [ ! -f "$OUT/smoke_d2m.json" ]; then
  log "SMOKE: depth-2 seat, 2 battles, throwaway pair"
  # ARM=D2S, a REAL arm in the pre-reg carrying the throwaway pair. Passing
  # SEAT_USER/FP_USER as env vars would NOT have worked: the runner derives
  # both FROM THE PRE-REG whenever the arm is defined there (ch3_r4_fp_runner.sh
  # lines 69-78, the MA-10 fix), so the env values are overwritten and the smoke
  # would have burned D2N's REAL pair.
  PREREG="$PREREG" ARM=D2S TAG=d2m OUT="$OUT" SMOKE_BATTLES=2 \
    STALL_POLLS=60 MAX_RELAUNCHES=3 \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/smoke.driver.log" 2>&1
  if [ -f "$OUT/smoke_d2m.json" ]; then
    log "SMOKE DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/smoke_d2m.json'))
print('fired', d.get('depth2/fired_rate'), 'gc/dec',
      round(d.get('depth2/grandchildren_per_decision') or -1, 1),
      'ms', round(d.get('search/ms_mean') or -1, 1))")"
  else
    log "SMOKE FAILED -- see $LOG/smoke.driver.log; NOT starting phase S"; exit 1
  fi
  sleep 30
fi

# ---------------------------------------------------------------- PHASE S
log "PHASE S: the delta sweep (7 cells x 60 battles; override rate and cost only)"
for arm in S1A S1B S1C S2A S2B S2C S2D; do
  fparm "$arm" "$(echo $arm | tr 'A-Z' 'a-z')"
done
log "PHASE S DONE"

# ---------------------------------------------------------------- PIN
git status --porcelain | grep -q . && { log "DIRTY TREE -- refusing to pin (rule 3)"; exit 1; }
"$PY" scripts/depth2_r5_pin.py --commit >> "$LOG/pin.log" 2>&1 || { log "PIN FAILED -- see $LOG/pin.log"; exit 1; }
log "PIN: $(grep 'RULE R1 ->' "$LOG/pin.log")"

# ---------------------------------------------------------------- PHASE R
log "PHASE R: the read (D1 3000, D2M 3000, D2N 1500, G0 1500)"
for arm in D1 D2M D2N G0; do
  fparm "$arm" "$(echo $arm | tr 'A-Z' 'a-z')"
done
log "PHASE R DONE"

"$PY" scripts/depth2_r5_readout.py > "$OUT/READOUT.txt" 2>&1
log "READOUT written to $OUT/READOUT.txt"
log "QUEUE DONE"
