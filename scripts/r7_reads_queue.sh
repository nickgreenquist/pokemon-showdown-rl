#!/bin/bash
# R7 READS queue -- the post-fleet reads of the R7 fleet, as its pre-reg (the header of every configs/r7_fleet_*.yaml)
# states them: configs/eval/r7_reads_offfp.yaml (off FP@N 25k/12k: THE PRIMARY credit read, then the OBJECT RULE's four
# committees, in ONE scheduler session in the pinned order), the MECHANISM READS (iii)/(vi) at the five END
# checkpoints (scripts/r7_mechanism_reads.py, one process = one instrument session, c6 on) and the in-loop ones
# (i)/(ii)/(iv)/(v) from each lane's history, then configs/eval/r7_reads.yaml (vs SH, locked form), then the readout.
# Detached, resume-safe, rate-readable (CLAUDE.md rule 4). Re-execs from a FROZEN temp copy: never edit a bash script
# an instance is executing (docs/landmines.md).
#
#   bash -c 'nohup bash scripts/r7_reads_queue.sh > logs/r7_reads/queue.nohup 2>&1 &'
#
# From bash, NEVER a niced shell: scripts/fp_arms_parallel.py refuses to run niced or at background QoS, and zsh's
# BG_NICE nices every `cmd &` by +5 (docs/landmines.md).
#
# PHASES:
#   WAIT     the watchdog log carries "DONE at step" for all five R7 lanes and no rl.train for them is alive; then
#            +15 min so Showdown reaps the rooms of the lanes' in-loop evals.
#   PIN      scripts/monster_reads_pin.py --trio s --commit, then --trio c --commit (real step names, sha256) --
#            refused on a dirty tree (rule 3).
#   FP       ONE scripts/fp_arms_parallel.py session over the pre-reg's run_order at --slots 8 (the FP-parallel ROI's
#            measured width): C1F S1F C2F S2F S3F (the primary, control first in each pair), then E6RR E3BR ES3F EC2F
#            (the object rule). FP@N is FIXED-BUDGET, so there is no quiet-box hold: load costs time, never strength
#            (the scheduler still refuses beside a FOREIGN wall-clock Foul Play). The runner's relaunch knobs are the
#            reads queues' 60 / 10 / 3. An arm with no JSON, or with fpn_counters_ok false, is LOGGED and re-run LAST
#            on its rerun pair by the operator -- never pooled (the pre-reg).
#   MECH     BESIDE the FP phase (a deterministic instrument: load cannot move it): extract_history.py for each lane
#            (the in-loop reads' windows), then r7_mechanism_reads.py over the five END checkpoints, c6 on, in the
#            fleet's own env (R0 gate 3 ran its test there).
#   SH       vs SH, locked form (no loop breaker), gs_* then gc_*, c6 on -- after FP, sequential (minutes each).
#   READOUT  scripts/r7_reads_readout.py -> results/r7_reads_offfp/READOUT.txt + readout.json.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t r7_reads_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
# Hold the box awake exactly as long as this queue runs (the training watchdog's caffeinate exits with the last lane).
caffeinate -i -s -w $$ &
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python          # FP seats (the runner's default), vs SH, the readout
ENGPY=/opt/anaconda3/envs/pkmn-engine-port/bin/python          # the mechanism reads: pkmn_gen1, the fleet's env
BASEPY=/opt/anaconda3/bin/python                               # the scheduler (yaml only)
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
FPPREREG=configs/eval/r7_reads_offfp.yaml
SHPREREG=configs/eval/r7_reads.yaml
FPRES=results/r7_reads_offfp
SHRES=results/r7_reads
MECHRES=results/r7_reads_mech
LOG=logs/r7_reads
WD=runs/train_watchdog.log
G0ROWS=results/r7_g0/rollout_q.rows.jsonl
SLOTS=${SLOTS:-8}
mkdir -p "$LOG" "$FPRES" "$SHRES" "$MECHRES"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

LANES="runs/r7_fleet_searched_f1_s376 runs/r7_fleet_searched_f2_s384 runs/r7_fleet_searched_f3_s392 runs/r7_fleet_control_f1_s400 runs/r7_fleet_control_f2_s408"
lanes_done() { for d in $LANES; do grep -q "$d DONE at step" "$WD" || return 1; done; return 0; }
# A RESUMED lane runs as `--resume runs/<dir>`, not `--run-name <dir>` (scripts/train_watchdog.sh): both are matched.
lanes_alive() { for d in $LANES; do pgrep -f "bin/python -m rl.train.*(--run-name ${d#runs/}\$|--resume ${d}\$)" > /dev/null && return 0; done; return 1; }

# Refuse a niced / background-QoS shell up front (the scheduler would refuse later, after the pin).
[ "$(ps -o nice= -p $$ | tr -d ' ')" = "0" ] || { log "REFUSING: this queue is niced ($(ps -o nice= -p $$)); launch it from bash"; exit 1; }
lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no local Showdown server on :8000"; exit 1; }

# Username hygiene, checked rather than remembered (pairwise prefix-free over configs/eval).
"$PY" - <<'PYEOF' || { log "USERNAME PREFIX CHECK FAILED"; exit 2; }
import glob, re, sys
names = set()
for f in glob.glob("configs/eval/*.yaml"):
    for m in re.finditer(r"(?:seat_username|fp_username|seat|fp):\s*([a-z0-9]+)\b", open(f).read()):
        names.add(m.group(1))
names = sorted(names)
bad = [(a, b) for a in names for b in names if a != b and b.startswith(a)]
if bad:
    print("PREFIX COLLISIONS:", bad[:10]); sys.exit(1)
print(f"username inventory: {len(names)} names, pairwise prefix-free")
PYEOF

# ---------------------------------------------------------------- WAIT
log "WAIT: holding until all five R7 lanes are DONE in $WD and no rl.train for them is alive"
until lanes_done && ! lanes_alive; do sleep 120; done
log "R7 fleet DONE; +15 min for room reaping"
sleep 900
lanes_alive && { log "REFUSING: an R7 lane is alive again after DONE"; exit 1; }

# ---------------------------------------------------------------- PIN
git status --porcelain --untracked-files=no | grep -q . && { log "DIRTY TREE -- refusing to pin/launch (rule 3)"; exit 1; }
for t in s c; do
  "$PY" scripts/monster_reads_pin.py --trio "$t" --commit >> "$LOG/pin_$t.log" 2>&1 || { log "PIN-$t FAILED -- see $LOG/pin_$t.log"; exit 1; }
  log "PIN-$t: $(grep -E "^[sc][0-9]+: " "$LOG/pin_$t.log" | tr '\n' ' ')"
done
git status --porcelain --untracked-files=no | grep -q . && { log "DIRTY TREE after the pins -- refusing"; exit 1; }
log "launch commit $(git rev-parse --short HEAD)"

# ---------------------------------------------------------------- MECH (beside FP)
mech() {
  local d ck=() sha=()
  for d in $LANES; do
    if "$PY" scripts/extract_history.py "$d" >> "$LOG/history.log" 2>&1; then
      log "HISTORY $d: $(tail -1 "$LOG/history.log" | cut -c1-80)"
    else
      log "HISTORY $d FAILED (a resume splits the wandb history: merge by hand, docs/landmines.md) -- see $LOG/history.log"
    fi
  done
  for lane in s376 s384 s392 c400 c408; do
    ck+=("$("$PY" -c "import yaml;print(yaml.safe_load(open('$FPPREREG'))['checkpoints']['$lane']['path'])")")
    sha+=("$("$PY" -c "import yaml;print(yaml.safe_load(open('$FPPREREG'))['checkpoints']['$lane']['sha256'])")")
  done
  if [ -f "$MECHRES/end.json" ]; then log "MECH SKIP (end.json exists)"; return; fi
  log "MECH: r7_mechanism_reads.py over the five END checkpoints (c6 on, $ENGPY)"
  POKEMON_RL_ENCODER_C6=1 "$ENGPY" scripts/r7_mechanism_reads.py --rows "$G0ROWS" --checkpoints "${ck[@]}" \
    --sha256 "${sha[@]}" --out "$MECHRES/end.json" >> "$LOG/mech.log" 2>&1 \
    && log "MECH DONE: $(grep -c '^\[mech\] ' "$LOG/mech.log") units" \
    || log "MECH FAILED -- see $LOG/mech.log"
}
mech &
MECH_PID=$!

# ---------------------------------------------------------------- FP
ARMS=$("$PY" -c "import yaml;print(','.join(yaml.safe_load(open('$FPPREREG'))['run_order']))")
log "PHASE FP: ONE scheduler session, --slots $SLOTS, arms $ARMS (off FP@N 25k/12k; fixed budget)"
STALL_POLLS=60 MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 PY="$PY" \
  "$BASEPY" scripts/fp_arms_parallel.py --prereg "$FPPREREG" --arms "$ARMS" --slots "$SLOTS" --out "$FPRES" \
  >> "$LOG/fp_parallel.log" 2>&1
log "PHASE FP returned (rc=$?)"
for arm in $(echo "$ARMS" | tr ',' ' '); do
  tag=$(echo "$arm" | tr 'A-Z' 'a-z')
  if [ -f "$FPRES/$tag.json" ]; then
    log "$arm: $("$PY" -c "
import json, os
s = json.load(open('$FPRES/$tag.json'))
r = json.load(open('$FPRES/$tag.runner.json')) if os.path.exists('$FPRES/$tag.runner.json') else {}
print(s.get('our_win_rate'), 'n', s.get('battles_finished'), 'ties', s.get('ties'), 'fpn_counters_ok', r.get('fpn_counters_ok'))")"
  else
    log "$arm NO JSON -- see $FPRES/$tag.runner.log (a killed arm's pair is POISONED: re-run it LAST on its rerun pair)"
  fi
done

# ---------------------------------------------------------------- SH
job() {  # one ch3_eval job (vs SH, locked form), blocking; skipped if its final exists
  local name="$1"
  if [ -f "$SHRES/$name.final.json" ]; then log "$name SKIP (final exists)"; return; fi
  log "$name launching (vs SH, locked form, c6 on)"
  POKEMON_RL_ENCODER_C6=1 "$PY" scripts/ch3_eval.py --prereg "$SHPREREG" --job "$name" >> "$LOG/$name.log" 2>&1
  if [ -f "$SHRES/$name.final.json" ]; then
    log "$name DONE: $("$PY" -c "import json;d=json.load(open('$SHRES/$name.final.json'));print(d.get('eval/win_rate'))")"
  else
    log "$name NO FINAL -- see $LOG/$name.log; a rerun resumes finished chunks"
  fi
}
log "PHASE SH: vs SH, locked form, sequential"
job gs_s376; job gs_s384; job gs_s392
job gc_c400; job gc_c408
log "PHASE SH DONE"

wait "$MECH_PID"
log "MECH phase joined"
"$PY" scripts/r7_reads_readout.py --json-out "$FPRES/readout.json" > "$FPRES/READOUT.txt" 2>&1
log "READOUT written to $FPRES/READOUT.txt (rc=$?)"
log "QUEUE DONE"
