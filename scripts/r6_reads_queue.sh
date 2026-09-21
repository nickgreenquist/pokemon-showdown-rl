#!/bin/bash
# R6 READS queue -- the post-fleet reads of the R6 trios: configs/eval/r6_reads_offfp.yaml
# (off FP@20; THE PRIMARY READ under the trio headers' credit line, and the read that PICKS
# LADDER R6's OBJECT) then configs/eval/r6_reads.yaml (vs SH, locked form). Detached,
# resume-safe, rate-readable (CLAUDE.md rule 4). Re-execs from a FROZEN temp copy: never
# edit a bash script an instance is executing (docs/landmines.md).
#
#   nohup bash scripts/r6_reads_queue.sh > logs/r6_reads/queue.nohup 2>&1 &
#
# PHASES:
#   WAIT     both trios' watchdogs print "DONE at step" for all six lanes and no rl.train
#            for them is alive; +15 min so Showdown reaps the rooms.
#   PIN      scripts/monster_reads_pin.py --trio a --commit, then --trio b --commit
#            (real names, sha256) -- refused on a dirty tree (rule 3).
#   PHASE FP off-FP@20 arms in the pre-reg's run_order, SEQUENTIAL, each under the
#            per-arm encoder setting from `arm_encoder` (c6 on for R6 finals, off for the
#            R5 W re-draws, on + ALLOW_MISMATCH for the mixed E9RF).
#   PHASE SH vs SH, every job in run_order (minutes each), c6 on; E9R jobs mixed.
#   READOUT  scripts/r6_reads_readout.py -> results/r6_reads_offfp/READOUT.txt + readout.json.
#
# SEQUENTIAL throughout: ch3_eval jobs derive poke-env seat names from (cfg.seed, seat_tag,
# "e") -- the SAME names the lane's own in-loop eval used -- so they run only after the lanes
# EXITED; the FP arms carry a WALL-CLOCK budget, so a second concurrent Foul Play weakens
# both opponents and flatters both seats. REFUSES to start beside a training lane or another
# FP process; anything that starts later is the operator's disclosure.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t r6_reads_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/r6_reads.yaml
FPPREREG=configs/eval/r6_reads_offfp.yaml
RES=results/r6_reads
FPRES=results/r6_reads_offfp
LOG=logs/r6_reads
WD=runs/train_watchdog.log
mkdir -p "$LOG" "$RES" "$FPRES"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

LANES="runs/r6_trio_a_s304 runs/r6_trio_a_s312 runs/r6_trio_a_s320 runs/r6_trio_b_s328 runs/r6_trio_b_s336 runs/r6_trio_b_s344"

lanes_done() { for d in $1; do grep -q "$d DONE at step" "$WD" || return 1; done; return 0; }
lanes_alive() { for d in $1; do pgrep -f "bin/python -m rl.train.*--run-name ${d#runs/}\$" > /dev/null && return 0; done; return 1; }

# Guards: no training lane, no other Foul Play process, the server up.
pgrep -f "bin/python -m rl.train" > /dev/null && { log "REFUSING: an rl.train lane is alive (never an FP arm beside a training lane)"; exit 1; }
pgrep -f "foul-play/bin/python run.py" > /dev/null && { log "REFUSING: another Foul Play process is alive (FP's budget is wall-clock)"; exit 1; }
lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no local Showdown server on :8000"; exit 1; }

# Username hygiene, checked rather than remembered (pairwise prefix-free over configs/eval).
"$PY" - <<'PYEOF' || { echo "USERNAME PREFIX CHECK FAILED"; exit 2; }
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

arm_c6() {  # arm -> "on" | "off" | "mixed" from the pre-reg's arm_encoder block
  "$PY" - "$FPPREREG" "$1" <<'PYEOF'
import sys, yaml
e = (yaml.safe_load(open(sys.argv[1])).get("arm_encoder") or {}).get(sys.argv[2])
if e is None: sys.exit(f"no arm_encoder entry for {sys.argv[2]}")
print("mixed" if e.get("allow_mismatch") else ("on" if e.get("c6") else "off"))
PYEOF
}

fparm() {  # one off-FP arm through the incident-hardened runner, blocking
  local arm="$1" tag="$2" c6
  if [ -f "$FPRES/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  c6="$(arm_c6 "$arm")" || { log "$arm: $c6"; exit 1; }
  case "$c6" in
    on)    export POKEMON_RL_ENCODER_C6=1; unset POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH ;;
    off)   unset POKEMON_RL_ENCODER_C6 POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH ;;
    mixed) export POKEMON_RL_ENCODER_C6=1 POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH=1 ;;
  esac
  log "$arm launching (off FP@20, n from pre-reg, c6=$c6)"
  PREREG="$FPPREREG" ARM="$arm" TAG="$tag" OUT="$FPRES" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$FPRES/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "import json;d=json.load(open('$FPRES/$tag.json'));print(d['our_win_rate'], 'n', d['battles_finished'], 'ties', d['ties'])")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log and $FPRES/$tag.runner.log (a killed arm's pair is POISONED: re-run it on its rerun pair)"
  fi
  sleep 30
}

job() {  # one ch3_eval job (vs SH), blocking; skipped if its final exists
  local name="$1" mixed="${2:-0}"
  if [ -f "$RES/$name.final.json" ]; then log "$name SKIP (final exists)"; return; fi
  export POKEMON_RL_ENCODER_C6=1
  if [ "$mixed" = 1 ]; then export POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH=1; else unset POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH; fi
  log "$name launching (vs SH, locked form, c6 on$( [ "$mixed" = 1 ] && echo ', MIXED with the c6-off W finals'))"
  "$PY" scripts/ch3_eval.py --prereg "$PREREG" --job "$name" >> "$LOG/$name.log" 2>&1
  if [ -f "$RES/$name.final.json" ]; then
    log "$name DONE: $("$PY" -c "import json;d=json.load(open('$RES/$name.final.json'));print(d.get('eval/win_rate'))")"
  else
    log "$name NO FINAL (rc=$?) -- see $LOG/$name.log; resume skips finished chunks"
  fi
}

# ---------------------------------------------------------------- WAIT
log "WAIT: holding until all six R6 lanes are DONE in $WD and no rl.train for them is alive"
until lanes_done "$LANES" && ! lanes_alive "$LANES"; do sleep 120; done
log "R6 trios DONE; +15 min for room reaping"
sleep 900
git status --porcelain | grep -q . && { log "DIRTY TREE -- refusing to pin/launch (rule 3)"; exit 1; }
for t in a b; do
  "$PY" scripts/monster_reads_pin.py --trio "$t" --commit >> "$LOG/pin_$t.log" 2>&1 || { log "PIN-$t FAILED -- see $LOG/pin_$t.log"; exit 1; }
  log "PIN-$t: $(grep -E "^[ab][0-9]" "$LOG/pin_$t.log" | tr '\n' ' ')"
done

# ---------------------------------------------------------------- PHASE FP
log "PHASE FP: off FP@20, sequential, in the pre-reg's run_order (~1.4 h per arm at ~1.6 s/battle)"
for arm in $("$PY" -c "import yaml;print(' '.join(yaml.safe_load(open('$FPPREREG'))['run_order']))"); do
  fparm "$arm" "$(echo "$arm" | tr 'A-Z' 'a-z')"
done
log "PHASE FP DONE"

# ---------------------------------------------------------------- PHASE SH
log "PHASE SH: vs SH, locked form, sequential (c6 on; E9R mixed)"
job ga_a304; job ga_a312; job ga_a320
job gb_b328; job gb_b336; job gb_b344
job e3a_b0; job e3a_b1; job e3a_b2
job e3b_b0; job e3b_b1; job e3b_b2
job e6r_b0; job e6r_b1; job e6r_b2
job e9r_b0 1; job e9r_b1 1; job e9r_b2 1
log "PHASE SH DONE"

"$PY" scripts/r6_reads_readout.py --json-out "$FPRES/readout.json" > "$FPRES/READOUT.txt" 2>&1
log "READOUT written to $FPRES/READOUT.txt"
log "QUEUE DONE"
