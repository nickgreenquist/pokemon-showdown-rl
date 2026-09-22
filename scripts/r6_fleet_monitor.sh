#!/bin/bash
# R6 FLEET MONITOR (2026-09-22): one line per lane per poll to logs/r6_fleet/monitor.log -- the lane's
# rate from its two newest 500k rung checkpoints (step in the filename, mtime as the clock: exact at the
# rung boundaries, unlike the watchdog's checkpoint.pt step), RSS and %CPU, the watchdog's latest verdict
# for the lane and its RESUMED / ALERT counts -- plus box lines (load, free memory, Node). An ALERT line is
# written when a lane's rate falls below ALERT_FRAC x the W fleet's per-lane six-wide reference (W s104
# realized steps/s, mean over 5M..195M: 1,254; first 5M: 991) after its first hour, or when the watchdog
# raises ALERT/RETIRING/DEAD for it. The maintainer's 2026-09-22 ruling: a fleet much slower than the W
# fleet was is killed on the morning ping and relaunched from the maintainer's own terminal.
#
#   nohup bash scripts/r6_fleet_monitor.sh > logs/r6_fleet/monitor.nohup 2>&1 &
set -u
cd "$(cd "$(dirname "$0")/.." && pwd)" || exit 1
WD=runs/train_watchdog.log
OUT=logs/r6_fleet/monitor.log; mkdir -p logs/r6_fleet
POLL="${POLL:-600}"
W_REF="${W_REF:-1254}"
ALERT_FRAC="${ALERT_FRAC:-0.6}"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$OUT"; }
lane_pid() { pgrep -f "bin/python -m rl.train.*(--run-name $1\$|--resume runs/$1\$)" 2>/dev/null | head -1; }
rate_from_rungs() {  # dir -> "rate step_hi age_s" from the two newest rungs, or "" if fewer than two
  local d="$1"; local -a f
  f=($(ls -t "$d"/ckpt_*.pt 2>/dev/null | head -2))
  [ "${#f[@]}" -ge 2 ] || { echo ""; return; }
  local s1 s0 t1 t0
  s1=$(basename "${f[0]}" .pt | sed 's/ckpt_0*//'); s0=$(basename "${f[1]}" .pt | sed 's/ckpt_0*//')
  t1=$(stat -f %m "${f[0]}"); t0=$(stat -f %m "${f[1]}")
  [ "$t1" -gt "$t0" ] || { echo ""; return; }
  echo "$(( (s1 - s0) / (t1 - t0) )) $s1 $(( $(date +%s) - t1 ))"
}
log "MONITOR START poll=${POLL}s W_REF=${W_REF} steps/s per lane (six-wide, 5M..195M) alert below ${ALERT_FRAC}x"
declare -A seen_alerts
while true; do
  lanes=$(ls -d runs/showdown_r6_trio_[ab]_s* 2>/dev/null | grep -v smoke)
  n_done=0; n_lanes=0
  for d in $lanes; do
    n_lanes=$((n_lanes+1)); b=$(basename "$d")
    pid=$(lane_pid "$b"); rss=""; cpu=""
    if [ -n "$pid" ]; then rss=$(( $(ps -o rss= -p "$pid" | tr -d ' ') / 1024 )); cpu=$(ps -o %cpu= -p "$pid" | tr -d ' '); fi
    read -r rate step age <<<"$(rate_from_rungs "$d")"
    started=$(stat -f %m "$d/meta.yaml" 2>/dev/null || echo 0); uptime_s=$(( $(date +%s) - started ))
    wl=$(grep -E "$d (ok|DONE|no pid|cpu flat|pid .* vanished)|ALERT $d" "$WD" | tail -1 | cut -c1-140)
    resumes=$(grep -c "RESUMED $d ->" "$WD"); alerts=$(grep -c "ALERT $d" "$WD")
    grep -q "$d DONE at step" "$WD" && n_done=$((n_done+1))
    log "$b pid=${pid:-none} rss=${rss:-?}MB cpu=${cpu:-?}% rate=${rate:-n/a} steps/s (last rung ${step:-n/a}, ${age:-?}s ago) uptime=$((uptime_s/60))min resumes=$resumes alerts=$alerts | $wl"
    if [ -n "$rate" ] && [ "$uptime_s" -ge 3600 ]; then
      slow=$(awk -v r="$rate" -v w="$W_REF" -v f="$ALERT_FRAC" 'BEGIN{print (r < w*f) ? 1 : 0}')
      [ "$slow" = 1 ] && log "ALERT $b SLOW: $rate steps/s < ${ALERT_FRAC} x $W_REF (the W fleet six-wide)"
    fi
    if [ "$alerts" -gt "${seen_alerts[$b]:-0}" ]; then log "ALERT $b WATCHDOG: $(grep "ALERT $d" "$WD" | tail -1 | cut -c1-160)"; seen_alerts[$b]=$alerts; fi
    [ -z "$pid" ] && ! grep -q "$d DONE at step" "$WD" && [ "$uptime_s" -ge 900 ] && log "ALERT $b NO PROCESS and not DONE (the watchdog resumes within its poll; escalate if it repeats)"
  done
  free_mb=$(( $(vm_stat | awk '/Pages free/{gsub("\\.","",$3); print $3}') * 16384 / 1048576 ))
  node=$(curl -s -o /dev/null -m 5 -w '%{http_code}' http://localhost:8000/ 2>/dev/null || echo "down")
  log "BOX load=$(uptime | sed 's/.*load averages: //') free=${free_mb}MB node=$node lanes=$n_lanes done=$n_done screens=$(pgrep -f 'rl.train --config configs/showdown_r6_batch12m' | wc -l | tr -d ' ')"
  if [ "$n_lanes" -ge 6 ] && [ "$n_done" -ge 6 ]; then log "ALL LANES DONE"; exit 0; fi
  sleep "$POLL"
done
