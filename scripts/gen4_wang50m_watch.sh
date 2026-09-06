#!/usr/bin/env bash
# gen4_wang50m WATCHER v2 (2026-09-06, mid-fleet replacement for the watch
# loop in scripts/gen4_wang50m_wave.sh; same log, same line formats, so the
# rate watch and the FLEET DONE auto-chain keep reading it).
# What v1 got wrong, measured twice today: on a lane death it resumed
# IMMEDIATELY, the resume died at reset on the dead process's still-open
# rooms ("Can not reset player's battles while they are still running" —
# the seed-derived usernames are the same), and that crash burned a second
# retry. v2:
#   ADOPTS running lanes at start (pgrep by run name / resume dir) instead
#     of launching; a lane with the completion rung is skipped; a lane with
#     neither is resumed.
#   RESUMES only after the rooms have had time to close (ROOM_WAIT s, the
#     timer's tight path is 150 s/turn), then VERIFIES the resume is still
#     alive 60 s later; a resume that dies inside 60 s is a crash-at-reset,
#     retried after RESET_RETRY_WAIT s up to 3 times WITHOUT charging the
#     lane's death budget (3 real deaths/lane, then manual attention).
#   ROLLOVER: touching runs/<lane>/.rollover asks the watcher to kill that
#     lane and resume it through the safe path — the way a code fix reaches
#     a running lane, one lane at a time (each rollover is a resume: it
#     splits the wandb history and loses <= one rollout of seat-2 rows —
#     disclosed per resume in the pre-reg's lane-failure rule).
#   Stall detection (CPU delta, 3 consecutive zero deltas), RSS / box /
#     swapouts-delta / disk lines and the completion rung: as v1.
# Launch (detached; keeps the box awake like v1):
#   nohup caffeinate -dims bash scripts/gen4_wang50m_watch.sh > /dev/null 2>&1 < /dev/null &
# DRY=1 prints the adoption decisions and exits.
set -u
cd "$(dirname "$0")/.."
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
LOG=logs/gen4_wang50m_wave.log
SEEDS="${SEEDS:-200 208 216}"
CONFIG=configs/gen4_wang50m.yaml
DONE_STEP=50000000
ROOM_WAIT="${ROOM_WAIT:-300}"
RESET_RETRY_WAIT="${RESET_RETRY_WAIT:-180}"
DRY="${DRY:-0}"
say() { echo "[$(date -u +%FT%TZ)] $*" >> "$LOG"; [ "$DRY" = 1 ] && echo "$*"; }
run_dir() { echo "runs/gen4_wang50m_s$1"; }
done_rung() { ls "$1"/ckpt_0${DONE_STEP}.pt 2>/dev/null | head -1; }
live_pid() { pgrep -f "python -m rl.train .*(--run-name gen4_wang50m_s$1( |$)|--resume runs/gen4_wang50m_s$1( |$))" | head -1; }
getv() { eval "echo \${$1:-}"; }
setv() { eval "$1=\"$2\""; }

start_lane() {  # $1 seed, $2 fresh|resume  (no waiting here)
  local d; d="$(run_dir "$1")"
  if [ "$2" = resume ]; then
    nohup "$PY" -m rl.train --resume "$d" >> "logs/gen4_wang50m_lane_s$1.log" 2>&1 < /dev/null &
  else
    nohup "$PY" -m rl.train --config "$CONFIG" --seed "$1" --run-name "gen4_wang50m_s$1" \
      >> "logs/gen4_wang50m_lane_s$1.log" 2>&1 < /dev/null &
  fi
  setv "PID_$1" $!
  setv "STALLS_$1" 0
  say "lane s$1: launched ($2) pid $(getv "PID_$1")"
}

safe_resume() {  # $1 seed: wait for the rooms to close, resume, verify; up to 3 crash-at-reset retries
  local d k; d="$(run_dir "$1")"
  say "lane s$1: waiting ${ROOM_WAIT}s for its rooms to close before resuming (v2)"
  sleep "$ROOM_WAIT"
  for k in 1 2 3; do
    if [ -f "$d/checkpoint.pt" ]; then start_lane "$1" resume; else start_lane "$1" fresh; fi
    sleep 60
    if kill -0 "$(getv "PID_$1")" 2>/dev/null; then say "lane s$1: resume alive after 60 s (attempt $k)"; return 0; fi
    say "lane s$1: resume died inside 60 s (attempt $k/3 — crash-at-reset shape, not charged); $(tail -n 1 "logs/gen4_wang50m_lane_s$1.log" | cut -c1-160)"
    sleep "$RESET_RETRY_WAIT"
  done
  say "lane s$1: three resumes died at start — manual attention"
  setv "PID_$1" ""
  return 1
}

say "WATCHER v2 START (pre-reg: $CONFIG; ROOM_WAIT ${ROOM_WAIT}s)"
for s in $SEEDS; do
  d="$(run_dir "$s")"; setv "RETRIES_$s" 0; setv "STALLS_$s" 0
  if [ -n "$(done_rung "$d")" ]; then say "lane s$s: already complete, skipping"; setv "PID_$s" ""; continue; fi
  p="$(live_pid "$s")"
  if [ -n "$p" ]; then say "lane s$s: ADOPTED running pid $p"; setv "PID_$s" "$p"; continue; fi
  say "lane s$s: no live process and no completion rung — resuming through the safe path"
  [ "$DRY" = 1 ] || safe_resume "$s"
done
[ "$DRY" = 1 ] && { say "DRY exit"; exit 0; }

while :; do
  alive=0
  for s in $SEEDS; do
    d="$(run_dir "$s")"; p="$(getv "PID_$s")"
    [ -n "$p" ] || continue
    if [ -f "$d/.rollover" ]; then
      rm -f "$d/.rollover"
      say "lane s$s: ROLLOVER requested — killing pid $p and resuming through the safe path"
      kill "$p" 2>/dev/null; sleep 10; kill -9 "$p" 2>/dev/null
      safe_resume "$s" && alive=1
      continue
    fi
    if ! kill -0 "$p" 2>/dev/null; then
      if [ -n "$(done_rung "$d")" ]; then say "lane s$s: COMPLETE ($(basename "$(done_rung "$d")"))"; setv "PID_$s" ""; continue; fi
      if [ "$(getv "RETRIES_$s")" -ge 3 ]; then
        say "lane s$s: DEAD and out of retries — manual attention; the LANE-FAILURE RULE applies (fleet does not wait)"; setv "PID_$s" ""
      else
        setv "RETRIES_$s" $(( $(getv "RETRIES_$s") + 1 ))
        say "lane s$s: died (retry $(getv "RETRIES_$s")/3); resuming through the safe path"
        grep -E "^[A-Za-z_.]*(Error|Exception|Exceeded)" "logs/gen4_wang50m_lane_s$s.log" | tail -n 1 | cut -c1-200 >> "$LOG"
        safe_resume "$s" && alive=1
      fi
      continue
    fi
    alive=1
    t1=$(ps -o time= -p "$p" | tr -d ' ')
    sleep 15
    t2=$(ps -o time= -p "$p" 2>/dev/null | tr -d ' ')
    rss_kb=$(ps -o rss= -p "$p" 2>/dev/null | tr -d ' ')
    rss_mb=$(( ${rss_kb:-0} / 1024 ))
    latest=$(ls -t "$d"/ckpt_*.pt 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null)
    say "lane s$s: alive cpu=$t1->$t2 rss=${rss_mb}MB latest=${latest:-none}"
    if [ -n "$t2" ] && [ "$t1" = "$t2" ]; then
      setv "STALLS_$s" $(( $(getv "STALLS_$s") + 1 ))
      say "lane s$s: ALERT zero CPU delta ($(getv "STALLS_$s") consecutive)"
      if [ "$(getv "STALLS_$s")" -ge 3 ] && [ "$(getv "RETRIES_$s")" -lt 3 ]; then
        setv "RETRIES_$s" $(( $(getv "RETRIES_$s") + 1 ))
        say "lane s$s: STALLED — killing and resuming through the safe path (retry $(getv "RETRIES_$s")/3)"
        kill -9 "$p" 2>/dev/null; sleep 5
        safe_resume "$s"
      fi
    else
      setv "STALLS_$s" 0
    fi
  done
  box_free=$(vm_stat | awk -F': *' '/free|inactive/ {gsub(/\./,"",$2); s+=$2} END {printf "%.1f", s*16384/1e9}')
  swapouts=$(vm_stat | awk -F': *' '/Swapouts/ {gsub(/\./,"",$2); print $2}')
  swap_delta=$(( ${swapouts:-0} - ${SWAP_PREV:-${swapouts:-0}} )); SWAP_PREV=${swapouts:-0}
  say "box: free+inactive ${box_free}GB swapouts_delta ${swap_delta} (cum ${swapouts:-?}) disk $(df -g . | tail -1 | awk '{print $4}')GiB"
  [ "$alive" = 0 ] && break
  sleep 300
done
say "FLEET DONE — run the FROZEN post-fleet schedule (pre-reg order): vs-SH 3x3000 -> FP@20 -> MDT -> S-SHAPE -> FP@500 -> clone h2h -> Q38 pin -> readout"
