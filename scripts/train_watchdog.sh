#!/bin/bash
# TRAINING WATCHDOG WITH AUTO-RESUME.
#
#   nohup bash scripts/train_watchdog.sh runs/lane1 runs/lane2 ... \
#     > /dev/null 2>&1 &
#
# Written 2026-09-11 for an UNATTENDED multi-day fleet. `ch5_watchdog.sh` is
# the eval-side one and it deliberately only alerts -- "It never kills
# anything, the runner owns that" -- which is correct when someone is watching
# and useless when nobody is. This one acts.
#
# THE FAILURE IT EXISTS FOR is the worst one this repo has recorded: a lane
# STALLS MID-RUN with the process ALIVE and at ZERO CPU. Twice in R2, ~10 h
# apart, at 68.9% and 94.3%. Every `pgrep` check passes forever, so an
# alerting watchdog reports healthy while the run is dead. The root cause (the
# orphaned-room deadlock) was found and fixed 2026-08-31, but the CPU-delta
# check stays the instrument because NOTHING ELSE CATCHES THIS SHAPE, and a
# multi-day unattended run is exactly where a recurrence costs everything.
#
# WHAT IT DOES, per lane, per poll:
#   ALIVE + CPU advancing         -> healthy, log a rate line
#   ALIVE + CPU flat over CPU_WIN -> STALLED: kill the process group, resume
#   GONE  + step >= total_steps   -> DONE, stop watching this lane
#   GONE  + step <  total_steps   -> DEAD: resume
#
# Liveness is CPU-TIME DELTA, never elapsed wall clock and never the existence
# of a process -- `ps -o time=` twice, which is the 15-second check the
# landmines file prescribes.
#
# TWO THINGS IT DELIBERATELY DOES NOT DO:
#   * It does not touch a lane that has hit total_steps. A finished run is not
#     a dead one, and resuming it would append a spurious wandb segment.
#   * It gives up on a lane after MAX_RESUMES. A crash loop that relaunches
#     forever burns the box for three days and produces nothing; the cap turns
#     that into a logged, diagnosable stop.
#
# EVERY RESUME IS A DISCLOSURE. A resume SPLITS the wandb history into two
# offline runs with OVERLAPPING steps, `extract_history.py` then HARD-FAILS,
# and `checkpoint.pt` lags the last logged step by much more than one update
# (R2 lost 190,776 and 170,680 steps). So the log line is the record: read the
# real `from_step` from meta.yaml, and expect `updates_done` one short per
# resume. RESUMES= in the summary line is what the readout must disclose.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO" || exit 1
PY="${PY:-/opt/anaconda3/envs/pokemon-showdown-rl/bin/python}"
POLL="${POLL:-300}"          # seconds between sweeps
CPU_WIN="${CPU_WIN:-20}"     # seconds over which CPU time must advance
CPU_MIN="${CPU_MIN:-2}"      # seconds of CPU that must accrue in CPU_WIN
MAX_RESUMES="${MAX_RESUMES:-12}"
GRACE="${GRACE:-600}"        # seconds after a resume before judging a lane
LOG="${LOG:-runs/train_watchdog.log}"

# The encoder flags are part of the OBSERVATION CONTRACT, not a convenience:
# a lane resumed without them builds a different-width encoder and the
# checkpoint will not load. Inherit them if already exported, else set them.
export POKEMON_RL_ENCODER_V2="${POKEMON_RL_ENCODER_V2:-1}"
export POKEMON_RL_ENCODER_IDS="${POKEMON_RL_ENCODER_IDS:-1}"

say() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

[ "$#" -ge 1 ] || { echo "usage: $0 runs/lane1 [runs/lane2 ...]"; exit 2; }

LANES=("$@")
declare -a RESUMES LASTACT
for i in "${!LANES[@]}"; do RESUMES[$i]=0; LASTACT[$i]=0; done
# Counted separately because retiring a lane sets RESUMES[i]=-1 and would
# otherwise erase its history -- and this total is the DISCLOSURE the readout
# has to carry, so it must survive a retirement.
TOTAL_RESUMES=0

# --- helpers -----------------------------------------------------------
# pgrep MUST anchor on bin/python: a bare match on the run name also catches
# this watchdog, the tee, and any shell whose command line mentions the lane,
# and killing those instead of the trainer is how a guard becomes the outage.
lane_pid() {
  pgrep -f "bin/python.*(--resume ${1}|--run-name $(basename "$1"))" 2>/dev/null | head -1
}

cpu_secs() {  # PID -> cumulative CPU seconds (ps prints [dd-]hh:mm:ss)
  local t; t="$(ps -o time= -p "$1" 2>/dev/null | tr -d ' ')"
  [ -n "$t" ] || { echo ""; return; }
  echo "$t" | awk -F'[:-]' '{
    if (NF==4) print $1*86400+$2*3600+$3*60+$4;
    else if (NF==3) print $1*3600+$2*60+$3;
    else if (NF==2) print $1*60+$2;
    else print $1 }'
}

lane_step() {  # run dir -> "step total" from checkpoint.pt + config.yaml
  "$PY" - "$1" <<'PYEOF' 2>/dev/null
import sys, torch, yaml, os
d = sys.argv[1]
try:
    step = int(torch.load(os.path.join(d, "checkpoint.pt"),
                          map_location="cpu", weights_only=False)["step"])
except Exception:
    step = -1
try:
    total = int(yaml.safe_load(open(os.path.join(d, "config.yaml")))["total_steps"])
except Exception:
    total = -1
print(step, total)
PYEOF
}

resume_lane() {  # run dir -> relaunch detached, IN ITS OWN SESSION
  local d="$1"
  # os.setsid() is not a nicety. A child started with plain `nohup ... &`
  # INHERITS THIS WATCHDOG'S PROCESS GROUP, so the next time that lane stalls,
  # `kill -TERM -$pgid` would kill the watchdog itself -- and on an unattended
  # box that is the whole fleet gone with nothing left watching. Giving every
  # resumed lane its own session means the group-kill can only ever reach that
  # lane. (macOS has no setsid(1); Python's is the portable one.)
  nohup "$PY" -c 'import os,sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' \
    "$PY" -m rl.train --resume "$d" >> "${d}.resume.log" 2>&1 &
  say "  RESUMED $d -> pid $! (own session; log ${d}.resume.log)"
}

# --- PREFLIGHT: refuse to start rather than fail on resume #1 at 3am -------
# The engine collector imports pkmn_gen1, which lives ONLY in the
# pkmn-engine-port env -- not in pokemon-showdown-rl, which is this script's
# default interpreter. A watchdog that starts happily and then resumes an
# engine lane with the wrong python produces an ImportError per resume until
# it burns the cap, on an unattended box, silently. So the interpreter is
# checked against what each lane's own config asks for, BEFORE watching.
for d in "${LANES[@]}"; do
  [ -d "$d" ] || { echo "REFUSING: $d is not a directory"; exit 2; }
  mode="$(grep -A3 '^collector:' "$d/config.yaml" 2>/dev/null \
          | grep -E '^\s*mode:' | awk '{print $2}')"
  if [ "${mode:-}" = "engine" ]; then
    if ! "$PY" -c 'import pkmn_gen1' 2>/dev/null; then
      echo "REFUSING TO START: $d is collector mode=engine, but"
      echo "  $PY"
      echo "cannot import pkmn_gen1. Re-run with the engine env, e.g."
      echo "  PY=/opt/anaconda3/envs/pkmn-engine-port/bin/python bash $0 $*"
      exit 2
    fi
  fi
done

say "WATCHDOG START poll=${POLL}s cpu_win=${CPU_WIN}s cpu_min=${CPU_MIN}s max_resumes=${MAX_RESUMES}"
say "  lanes: ${LANES[*]}"

live=1
while [ "$live" -gt 0 ]; do
  live=0
  for i in "${!LANES[@]}"; do
    d="${LANES[$i]}"
    [ -d "$d" ] || { say "$d MISSING -- not a run dir, skipping forever"; continue; }
    [ "${RESUMES[$i]}" -lt 0 ] && continue          # retired lane

    read -r step total <<<"$(lane_step "$d")"
    if [ "${step:-0}" -ge 1 ] && [ "${total:-0}" -ge 1 ] && [ "$step" -ge "$total" ]; then
      say "$d DONE at step $step/$total (resumes=${RESUMES[$i]})"
      RESUMES[$i]=-1
      continue
    fi
    live=$((live+1))

    now=$(date +%s)
    pid="$(lane_pid "$d")"

    if [ -z "$pid" ]; then
      if [ $((now - ${LASTACT[$i]})) -lt "$GRACE" ]; then
        say "$d no pid yet, inside grace ($((now - ${LASTACT[$i]}))s < ${GRACE}s)"
        continue
      fi
      if [ "${RESUMES[$i]}" -ge "$MAX_RESUMES" ]; then
        say "ALERT $d DEAD and at the resume cap (${RESUMES[$i]}) -- RETIRING, needs a human"
        RESUMES[$i]=-1; continue
      fi
      say "ALERT $d DEAD at step ${step}/${total} -- resuming (${RESUMES[$i]} prior)"
      RESUMES[$i]=$(( ${RESUMES[$i]} + 1 )); LASTACT[$i]=$now
      TOTAL_RESUMES=$((TOTAL_RESUMES+1))
      resume_lane "$d"
      continue
    fi

    # ALIVE. The only question that matters: is it doing anything?
    c0="$(cpu_secs "$pid")"
    sleep "$CPU_WIN"
    c1="$(cpu_secs "$pid")"
    if [ -z "$c0" ] || [ -z "$c1" ]; then
      say "$d pid $pid vanished mid-check -- next sweep will resume it"
      continue
    fi
    dcpu=$(awk -v a="$c0" -v b="$c1" 'BEGIN{print b-a}')
    ok=$(awk -v d="$dcpu" -v m="$CPU_MIN" 'BEGIN{print (d>=m)?1:0}')

    if [ "$ok" -eq 1 ]; then
      say "$d ok pid=$pid step=${step}/${total} cpu+${dcpu}s/${CPU_WIN}s resumes=${RESUMES[$i]}"
    else
      if [ $((now - ${LASTACT[$i]})) -lt "$GRACE" ]; then
        say "$d cpu flat (+${dcpu}s) but inside grace -- not acting yet"
        continue
      fi
      if [ "${RESUMES[$i]}" -ge "$MAX_RESUMES" ]; then
        say "ALERT $d STALLED and at the resume cap (${RESUMES[$i]}) -- RETIRING, needs a human"
        RESUMES[$i]=-1; continue
      fi
      say "ALERT $d STALLED: alive at pid $pid, step ${step}/${total}, only +${dcpu}s CPU in ${CPU_WIN}s"
      # Kill the GROUP: the trainer owns poke-env websocket threads and any
      # child it spawned, and a survivor holds the Showdown seat name, which
      # poisons the resume with a `nametaken` that parks on an UNTIMED queue
      # get -- i.e. the resume would hang exactly like the stall it replaced.
      pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
      mypgid="$(ps -o pgid= -p $$ | tr -d ' ')"
      if [ -n "$pgid" ] && [ "$pgid" != "$mypgid" ]; then
        kill -TERM -"$pgid" 2>/dev/null; sleep 10; kill -KILL -"$pgid" 2>/dev/null
      else
        # Belt and braces: if a lane somehow shares our group, kill ONLY it.
        # Never group-kill ourselves, whatever the resume path did.
        say "  (pgid $pgid == watchdog's; killing pid $pid alone)"
        kill -TERM "$pid" 2>/dev/null; sleep 10; kill -KILL "$pid" 2>/dev/null
      fi
      sleep 20   # let Showdown reap the abandoned rooms before reconnecting
      RESUMES[$i]=$(( ${RESUMES[$i]} + 1 )); LASTACT[$i]=$now
      TOTAL_RESUMES=$((TOTAL_RESUMES+1))
      resume_lane "$d"
    fi
  done
  [ "$live" -gt 0 ] && sleep "$POLL"
done

say "WATCHDOG EXIT -- every lane DONE or retired. RESUMES=$TOTAL_RESUMES"
say "  DISCLOSURE: each resume split the wandb history. Read the real"
say "  from_step from each meta.yaml before extract_history.py, and expect"
say "  updates_done one short per resume."
