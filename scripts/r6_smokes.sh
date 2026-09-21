#!/bin/bash
# R6 400k SMOKES, orchestrated (HANDOFF 2026-09-21 section 2, items 2-3): smoke A (trio A's
# file, WITH the kill-one-lane RESUME test at its 200k checkpoint), then smoke B (trio B), then
# smoke B-fallback -- ONE AT A TIME through scripts/monster_fleet.sh, each read by
# scripts/r6_smoke_check.py (verdict JSON in results/r6_smokes/<name>.json). It runs BESIDE the
# 4.12 screen by design (the window is disclosed in the screen read; only time/* is affected).
# Resumable: a smoke whose check already says PASS is skipped; a run dir that exists without a
# PASS is refused, never clobbered. Refuses beside a Foul Play arm (its budget is wall-clock).
# Re-execs from a FROZEN copy (never edit a bash script an instance is executing).
#
#   nohup bash scripts/r6_smokes.sh > logs/r6_smokes/smokes.nohup 2>&1 &
#   DRY=1 bash scripts/r6_smokes.sh        # prints the plan, launches nothing
#
# The kill for the resume test is the watchdog's own shape: the lane's PROCESS GROUP (the
# launcher started it under os.setsid, so the group is the lane alone), TERM then KILL; the
# watchdog (poll 300 s) sees the lane GONE and resumes it from checkpoint.pt with the c6 flag
# read back from meta.yaml -- that RESUMED line, with c6=1, is what the check looks for.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t r6_smokes)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PYB=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
WD=runs/train_watchdog.log
OUT=results/r6_smokes; LOGD=logs/r6_smokes; mkdir -p "$OUT" "$LOGD"
LOG="$LOGD/smokes.log"
STEPS=400000
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

# name|config|seed|resume-test  (seeds 904/912/920: the smoke files' own; distinct from every fleet seed)
SMOKES=(
  "a|configs/showdown_r6_trio_a_smoke400k.yaml|904|1"
  "b|configs/showdown_r6_trio_b_smoke400k.yaml|912|0"
  "bf|configs/showdown_r6_trio_b_fallback_smoke400k.yaml|920|0"
)

lane_pid() { pgrep -f "bin/python -m rl.train.*(--run-name $1\$|--resume runs/$1\$)" 2>/dev/null | head -1; }
wait_for() {  # <desc> <timeout s> <cmd...>: poll every 30 s until cmd succeeds
  local desc="$1" t="$2"; shift 2
  local t0; t0=$(date +%s)
  until "$@"; do
    sleep 30
    if [ $(( $(date +%s) - t0 )) -ge "$t" ]; then log "TIMEOUT waiting for $desc (${t}s)"; return 1; fi
  done
}

if [ "${DRY:-0}" != "1" ]; then
  pgrep -f "foul-play/bin/python run.py" > /dev/null && { log "REFUSING: a Foul Play arm is alive (never a training lane beside an FP arm)"; exit 1; }
fi
log "=== R6 SMOKES start (DRY=${DRY:-0}); tree $(git rev-parse --short HEAD) ==="

for entry in "${SMOKES[@]}"; do
  IFS='|' read -r name cfg seed rtest <<<"$entry"
  base="$(basename "$cfg" .yaml)_s${seed}"; dir="runs/$base"
  if [ -f "$OUT/$name.json" ] && grep -q '"verdict": "PASS"' "$OUT/$name.json"; then
    log "smoke $name already PASS ($OUT/$name.json) -- skipping"; continue
  fi
  if [ -e "$dir" ]; then
    log "REFUSING: $dir exists without a PASS -- check it by hand: $PYB scripts/r6_smoke_check.py $dir $([ "$rtest" = 1 ] && echo --expect-resume)"; exit 1
  fi
  if [ "${DRY:-0}" = "1" ]; then log "DRY: would launch $cfg $STEPS $seed -> $dir (resume test: $rtest)"; continue; fi

  log "=== smoke $name: bash scripts/monster_fleet.sh $cfg $STEPS $seed -> $dir ==="
  if ! bash scripts/monster_fleet.sh "$cfg" "$STEPS" "$seed" >> "$LOGD/launcher_$name.log" 2>&1; then
    log "LAUNCHER FAILED for smoke $name -- $LOGD/launcher_$name.log:"; tail -6 "$LOGD/launcher_$name.log" | tee -a "$LOG"; exit 1
  fi
  log "launched: $(grep -E 'lanes up|seed .* up:' "$LOGD/launcher_$name.log" | tail -2 | tr '\n' ' ')"

  if [ "$rtest" = "1" ]; then
    has_ckpt() { ls "$dir"/ckpt_0002*.pt > /dev/null 2>&1; }
    wait_for "the 200k checkpoint in $dir" 2400 has_ckpt || exit 1
    pid="$(lane_pid "$base")"
    [ -n "$pid" ] || { log "RESUME TEST: no lane pid for $base after the 200k checkpoint -- see $dir.nohup.log"; exit 1; }
    pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
    log "RESUME TEST: killing $base (pid $pid, pgid $pgid) at $(ls "$dir"/ckpt_0002*.pt | head -1)"
    kill -TERM -"$pgid" 2>/dev/null; sleep 10; kill -KILL -"$pgid" 2>/dev/null
    resumed() { grep -q "RESUMED $dir ->" "$WD"; }
    wait_for "the watchdog's RESUMED line for $dir" 1200 resumed || exit 1
    log "$(grep "RESUMED $dir ->" "$WD" | tail -1)"
  fi

  done_line() { grep -q "$dir DONE at step" "$WD"; }
  t0=$(date +%s); maxrss=0
  until done_line; do
    if grep -q "ALERT $dir .*RETIRING" "$WD"; then log "LANE RETIRED by the watchdog: $(grep "ALERT $dir" "$WD" | tail -2 | tr '\n' ' ')"; exit 1; fi
    # peak RSS of the lane (the resource gates are calibrated at a fleet width; trio B's x4
    # rollout is a new width -- docs/landmines.md), sampled every poll
    lp="$(lane_pid "$base")"
    if [ -n "$lp" ]; then r="$(ps -o rss= -p "$lp" 2>/dev/null | tr -d ' ')"; [ "${r:-0}" -gt "$maxrss" ] && maxrss="$r"; fi
    sleep 30
    if [ $(( $(date +%s) - t0 )) -ge 5400 ]; then log "TIMEOUT waiting for $dir DONE (90 min)"; exit 1; fi
  done
  log "$(grep "$dir DONE at step" "$WD" | tail -1)"
  log "peak RSS sampled for $base: $((maxrss / 1024)) MB (30 s polls; a lower bound on the true peak)"
  sleep 20
  args=("$dir" --json-out "$OUT/$name.json"); [ "$rtest" = "1" ] && args+=(--expect-resume)
  "$PYB" scripts/r6_smoke_check.py "${args[@]}" 2>&1 | tee -a "$LOG"
  if grep -q '"verdict": "PASS"' "$OUT/$name.json" 2>/dev/null; then
    log "smoke $name PASS"
  else
    log "smoke $name FAIL -- diagnose; do NOT hand over that trio"; exit 1
  fi
done
summary=""
for e in "${SMOKES[@]}"; do n=${e%%|*}; v=$(grep -o '"verdict": "[A-Z]*"' "$OUT/$n.json" 2>/dev/null | head -1 | cut -d'"' -f4); summary+="$n=${v:-none} "; done
log "SMOKES DONE: $summary"
