#!/bin/bash
# MONSTER READS queue -- the [RWL-3] SECONDARY reads on the 200M finals:
# configs/eval/monster_reads_offfp.yaml (off FP@20; PICKS THE LADDER OBJECT)
# then configs/eval/monster_reads.yaml (vs SH, locked protocol). Detached,
# resume-safe, rate-readable (CLAUDE.md rule 4). Re-execs from a FROZEN temp
# copy: never edit a bash script an instance is executing (docs/landmines.md).
#
#   nohup bash scripts/monster_reads_queue.sh > logs/monster_reads/queue.nohup 2>&1 &
#
# PHASES (maintainer 2026-09-14: the L2LAM reads may start while the W trio
# still trains "if it doesn't massively slow down train or break anything";
# fleet 2 is skipped; ladder + results by Saturday night):
#   WAIT-L   the L2LAM watchdog prints DONE for l2lam_s128/136/144 and its
#            WATCHDOG EXIT line; +15 min so Showdown reaps the rooms and the
#            W trio's 3-wide steps/s baseline can be measured with nothing
#            else running.
#   PIN-L    scripts/monster_reads_pin.py --trio l --commit (real names, sha256).
#   PHASE A  off-FP arms on the L2LAM finals + the 100M re-draws, SEQUENTIAL.
#            GUARD before every arm: the W trio's last-30-min steps/s must be
#            >= 90% of the post-L2LAM baseline, else HOLD phase A until the W
#            trio exits (the maintainer's condition, made mechanical).
#   WAIT-W   the W watchdog prints DONE for w_s104/112/120 + WATCHDOG EXIT; +15 min.
#   PIN-W    scripts/monster_reads_pin.py --trio w --commit.
#   PHASE B  the remaining off-FP arms (W finals, committees, floor, bridge).
#   PHASE C  vs SH, every job in run_order (minutes each).
#   READOUT  scripts/monster_reads_readout.py (pre-stated reads, PENDING where absent).
#
# SEQUENTIAL throughout, on purpose:
#   * ch3_eval jobs derive poke-env seat names from (cfg.seed, seat_tag, "e") --
#     the SAME names the lane's own in-loop eval used -- so a job may only run
#     after its lane has EXITED, and two jobs on one seed collide (rule 2);
#   * the FP arms carry a WALL-CLOCK budget -- a second concurrent Foul Play
#     weakens both opponents and flatters both seats.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t monster_reads_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/monster_reads.yaml
FPPREREG=configs/eval/monster_reads_offfp.yaml
RES=results/monster_reads
FPRES=results/monster_reads_offfp
LOG=logs/monster_reads
WD=runs/train_watchdog.log
mkdir -p "$LOG" "$RES" "$FPRES"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

L_LANES="runs/showdown_monster200m_l2lam_s128 runs/showdown_monster200m_l2lam_s136 runs/showdown_monster200m_l2lam_s144"
W_LANES="runs/showdown_monster200m_w_s104 runs/showdown_monster200m_w_s112 runs/showdown_monster200m_w_s120"

trio_done() {  # every lane of the trio has a DONE line in the watchdog log
  for d in $1; do grep -q "$d DONE at step" "$WD" || return 1; done
  return 0
}
trio_alive() {  # any rl.train for the trio still alive
  # rl.train's argv carries `--run-name showdown_monster200m_w_s104`, NOT the
  # run dir `runs/...` (found 2026-09-15 03:55Z: the dir pattern matched
  # nothing, so the phase-A guard silently never fired -- the DONE-line
  # checks were binding and unaffected). Match on the run name.
  for d in $1; do pgrep -f "bin/python -m rl.train.*--run-name ${d#runs/}\$" > /dev/null && return 0; done
  return 1
}
w_rate() {  # W trio's pooled steps/s over the last N seconds of watchdog ok lines
  local win="$1"
  awk -v win="$win" '/^\[2026-/ && / ok / && /monster200m_w_/{ lane=$2; split($1,t,/[\[\]T:Z-]/); s=(t[4]*86400)+t[5]*3600+t[6]*60+t[7]; sub(/step=/,"",$5); split($5,st,"/"); n[lane]++; S[lane,n[lane]]=s; P[lane,n[lane]]=st[1]} END{tot=0; k=0; for(l in n){m=n[l]; j=m; while(j>1 && S[l,m]-S[l,j-1]<win) j--; dt=S[l,m]-S[l,j]; if(dt>0){tot+=(P[l,m]-P[l,j])/dt; k++}} if(k>0) printf "%.0f\n", tot/k; else print 0}' "$WD"
}

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
  log "$1 launching (vs SH)"
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

# ---------------------------------------------------------------- WAIT-L
log "WAIT-L: holding until the L2LAM trio is DONE in $WD"
until trio_done "$L_LANES" && ! trio_alive "$L_LANES"; do sleep 120; done
log "L2LAM trio DONE; +15 min for room reaping and the W 3-wide baseline"
sleep 900
git status --porcelain | grep -q . && { log "DIRTY TREE -- refusing to pin/launch (rule 3)"; exit 1; }
"$PY" scripts/monster_reads_pin.py --trio l --commit >> "$LOG/pin_l.log" 2>&1 || { log "PIN-L FAILED -- see $LOG/pin_l.log"; exit 1; }
log "PIN-L: $(grep -E '^l1' "$LOG/pin_l.log" | tr '\n' ' ')"
W_BASE=$(w_rate 900)
log "W trio 3-wide baseline (15 min, nothing else running): ${W_BASE} steps/s; hold phase A if < 90%"

# ---------------------------------------------------------------- PHASE A
phase_a_guard() {  # returns 0 to proceed, 1 to hold phase A until W exits
  if ! trio_alive "$W_LANES"; then return 0; fi
  local r; r=$(w_rate 1800)
  if [ "$W_BASE" -gt 0 ] && [ "$r" -lt $((W_BASE * 9 / 10)) ]; then
    log "GUARD: W trio ${r} steps/s < 90% of ${W_BASE} -- HOLDING phase A until the W trio exits"
    return 1
  fi
  log "guard ok: W trio ${r} steps/s (baseline ${W_BASE})"
  return 0
}
log "PHASE A: off FP@20 on the L2LAM finals + the 100M re-draws (sequential, ~80-115 min each)"
HELD=0
for arm in E3LF GL128F GL136F GL144F G112R G104R G120R; do
  tag=$(echo "$arm" | tr 'A-Z' 'a-z')
  if [ "$HELD" = 0 ] && ! phase_a_guard; then HELD=1; fi
  if [ "$HELD" = 1 ]; then
    until trio_done "$W_LANES" && ! trio_alive "$W_LANES"; do sleep 120; done
    log "W trio DONE (held phase A resumes)"
  fi
  fparm "$arm" "$tag"
done
log "PHASE A DONE"

# ---------------------------------------------------------------- WAIT-W
log "WAIT-W: holding until the W trio is DONE in $WD"
until trio_done "$W_LANES" && ! trio_alive "$W_LANES"; do sleep 120; done
log "W trio DONE; +15 min for room reaping"
sleep 900
git status --porcelain | grep -q . && { log "DIRTY TREE -- refusing to pin/launch (rule 3)"; exit 1; }
"$PY" scripts/monster_reads_pin.py --trio w --commit >> "$LOG/pin_w.log" 2>&1 || { log "PIN-W FAILED -- see $LOG/pin_w.log"; exit 1; }
log "PIN-W: $(grep -E '^w1' "$LOG/pin_w.log" | tr '\n' ' ')"

# ---------------------------------------------------------------- PHASE B
log "PHASE B: off FP@20 on the W finals, the committees, the floor, the bridge (idle box)"
for arm in E3WF E6MF E9F E3HF GW104F GW112F GW120F G112B; do
  fparm "$arm" "$(echo "$arm" | tr 'A-Z' 'a-z')"
done
log "PHASE B DONE"

# ---------------------------------------------------------------- PHASE C
log "PHASE C: vs SH, locked protocol (minutes each, sequential)"
job gl_l128; job gl_l136; job gl_l144
job e3l_b0; job e3l_b1; job e3l_b2
job gw_w104; job gw_w112; job gw_w120
job e3w_b0; job e3w_b1; job e3w_b2
job e6m_b0; job e6m_b1; job e6m_b2
job e9_b0; job e9_b1; job e9_b2
job e3h_b0
log "PHASE C DONE"

"$PY" scripts/monster_reads_readout.py > "$RES/READOUT.txt" 2>&1
log "READOUT written to $RES/READOUT.txt"
log "QUEUE DONE"
