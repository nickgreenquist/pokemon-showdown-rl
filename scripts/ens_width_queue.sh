#!/bin/bash
# ENS WIDTH queue -- configs/eval/ens_width.yaml (vs SH) then
# configs/eval/ens_width_offfp.yaml (off FP@20). Detached, resume-safe,
# rate-readable (CLAUDE.md rule 4). Re-execs from a FROZEN temp copy: never
# edit a bash script an instance is executing (docs/landmines.md).
#
#   nohup bash scripts/ens_width_queue.sh > logs/ens_width/queue.nohup 2>&1 &
#
# SEQUENTIAL throughout, on purpose:
#   * ch3_eval jobs derive poke-env usernames from the globally-seeded
#     `random`, so two jobs on one checkpoint seed collide (rule 2);
#   * the FP arms carry a WALL-CLOCK budget -- a second concurrent Foul Play
#     weakens both opponents and flatters both seats, which is the load
#     confound the off-FP read has to stay clear of.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t ens_width_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/ens_width.yaml
FPPREREG=configs/eval/ens_width_offfp.yaml
RES=results/ens_width
FPRES=results/ens_width_offfp
LOG=logs/ens_width
mkdir -p "$LOG" "$RES" "$FPRES"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

# Username hygiene, checked rather than remembered: every name issued by any
# pre-reg under configs/eval must be pairwise prefix-free (poke-env matches
# names by prefix on reconnect; a shared prefix is a shared seat).
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

job() {  # one ch3_eval job, blocking; skipped if its final exists
  if [ -f "$RES/$1.final.json" ]; then log "$1 SKIP (final exists)"; return; fi
  log "$1 launching"
  "$PY" scripts/ch3_eval.py --prereg "$PREREG" --job "$1" >> "$LOG/$1.log" 2>&1
  if [ -f "$RES/$1.final.json" ]; then
    log "$1 DONE: $("$PY" -c "import json;d=json.load(open('$RES/$1.final.json'));print(d.get('eval/win_rate'))")"
  else
    log "$1 NO FINAL (rc=$?) -- see $LOG/$1.log; resume skips finished chunks"
  fi
}

fparm() {  # one off-FP arm through the incident-hardened runner, blocking
  local arm="$1" tag="$2"
  if [ -f "$FPRES/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching (off FP@20, n from pre-reg)"
  PREREG="$FPPREREG" ARM="$arm" TAG="$tag" OUT="$FPRES" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$FPRES/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "import json;d=json.load(open('$FPRES/$tag.json'));print(d['our_win_rate'], 'n', d['battles_finished'], 'ties', d['ties'])")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log and $FPRES/$tag.runner.log"
  fi
  sleep 30   # let Showdown reap the finished rooms before the next pair connects
}

log "PHASE 1: vs SH (minutes each, sequential)"
job a50_s66; job a50_s75; job a50_s83
job e350_b0; job e350_b1; job e350_b2
job e4_b0; job e5_b0
job e6mix_b0; job e6mix_b1; job e6mix_b2
log "PHASE 1 DONE"

log "PHASE 2: off FP@20 (sequential; ~27-35 min each)"
fparm G112F g112f; fparm G104F g104f; fparm G120F g120f
fparm E6MIXF e6mixf; fparm E350F e350f
fparm G66F g66f; fparm G75F g75f; fparm G83F g83f
fparm ENS3FR ens3fr
log "QUEUE DONE"
