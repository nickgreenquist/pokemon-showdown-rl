#!/usr/bin/env bash
# THE 100M WAVE (configs/showdown_sp_100m.yaml is the RATIFIED pre-reg;
# this file is only ops — the ch5_g9_wave pattern, adapted):
#   0. PREFLIGHT: the R0 zero-lane gates readable only at launch time —
#      clean tree (R0-k), suite green, one-diff test, grader selftest
#      (R0-e), disk >= 40 GiB (R0-h), memory >= 12 GB reclaimable (R0-i),
#      FRESH Showdown server (R0-j: started within the last 15 min, with
#      simulator: 4 verified; restart it yourself first — this script
#      never kills a server), seeds' run dirs absent (R0-l).
#   1. Three async lanes, seeds 104/112/120, staggered 40 s, detached,
#      run to completion (the loop exits itself at step >= 1e8; the
#      100M crossing rung is ckpt_1000*.pt).
#   2. Watch loop: CPU-delta stall detection (the only instrument for
#      alive-at-zero-CPU), bounded auto-resume (3 zero-deltas -> resume,
#      3 retries/lane), progress lines with the latest rung.
#   3. On fleet completion it STOPS. The post-fleet eval schedule is
#      FROZEN in the pre-reg (order: vs-SH -> PRIMARY off-FP -> S-SHAPE
#      -> S-ANNEAL -> BC-clone -> A-COLL iff P1) and runs separately —
#      NOTHING evaluates while any lane trains, and this script starts
#      no eval.
# Launch (the maintainer's, >5 h rule):
#   nohup caffeinate -dims bash scripts/ch5_100m_wave.sh > /dev/null 2>&1 < /dev/null &
#   (< /dev/null REQUIRED: nohup leaves stdin on the tty and zsh job
#   control SUSPENDS the launch — it bit the 2026-09-01 launch, SESSION_LOGS)
# RESUME-SAFE: re-running skips finished lanes and --resumes started ones.
# Per-lane RSS/box sampling: run scripts alongside per the D-E gate (the
# ch5_g9 rss sampler pattern, keyed to ch5_100m_wave.sh).
set -u
cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
LOG=logs/ch5_100m_wave.log
SEEDS="104 112 120"

say() { echo "[$(date -u +%FT%TZ)] $*" >> "$LOG"; }
run_dir() { echo "runs/showdown_sp_100m_s$1"; }
# Completion = the 100M crossing rung (async names rungs at the crossing
# step; ckpt_1000*.pt covers 100.0M-100.099M and cannot collide with the
# 10M rung, which is ckpt_0100*.pt).
done_rung() { ls "$1"/ckpt_1000*.pt 2>/dev/null | head -1; }

say "WAVE START (ratified pre-reg: configs/showdown_sp_100m.yaml)"

# --- 0. preflight (every check fatal) ------------------------------------
fail() { say "PREFLIGHT FAIL: $*"; echo "PREFLIGHT FAIL: $*" >&2; exit 1; }

[ -z "$(git status --porcelain)" ] || fail "tree not clean (R0-k)"
"$PY" -m pytest tests/test_100m_prereg.py -q >/dev/null 2>&1 \
  || fail "one-diff/prereg tests red (R0-a)"
"$PY" scripts/ch5_100m_grade.py --selftest >/dev/null 2>&1 \
  || fail "grader selftest red (R0-e)"
free_gib=$(df -g . | tail -1 | awk '{print $4}')
[ "$free_gib" -ge 40 ] || fail "disk ${free_gib}GiB < 40GiB (R0-h)"
mem_gb=$(vm_stat | awk -F': *' '/free|inactive|purgeable|speculative/ \
  {gsub(/\./,"",$2); s+=$2} END {printf "%d", s*16384/1e9}')
[ "$mem_gb" -ge 12 ] || fail "reclaimable memory ${mem_gb}GB < 12GB (R0-i)"
node_pid=$(pgrep -f "node pokemon-showdown start" | head -1)
[ -n "$node_pid" ] || fail "no Showdown server running (R0-j)"
node_age=$(( $(date +%s) - $(ps -p "$node_pid" -o lstart= | xargs -I{} date -j -f "%a %b %d %T %Y" "{}" +%s) ))
[ "$node_age" -le 900 ] || fail "server pid $node_pid is ${node_age}s old — restart it fresh first (R0-j)"
grep -q "simulator: 4" showdown/config/config.js || fail "simulator: 4 missing (R0-j / rule 5)"
say "R0-j: fresh server pid $node_pid, age ${node_age}s, simulator: 4 verified"
for s in $SEEDS; do
  [ ! -d "$(run_dir "$s")" ] || say "lane s$s: run dir exists — will RESUME"
done
say "PREFLIGHT PASS (disk ${free_gib}GiB, mem ${mem_gb}GB)"

# --- 1+2. launch and watch (the ch5_g9_wave pattern) ---------------------
getv() { eval "echo \${$1:-}"; }
setv() { eval "$1=\"$2\""; }
launch() {  # $1 seed, $2 fresh|resume
  local d; d="$(run_dir "$1")"
  if [ "$2" = resume ]; then
    nohup "$PY" -m rl.train --resume "$d" >> "logs/ch5_100m_lane_s$1.log" 2>&1 &
  else
    nohup "$PY" -m rl.train --config configs/showdown_sp_100m.yaml \
      --seed "$1" --run-name "showdown_sp_100m_s$1" \
      >> "logs/ch5_100m_lane_s$1.log" 2>&1 &
  fi
  setv "PID_$1" $!
  setv "STALLS_$1" 0
  say "lane s$1: launched ($2) pid $(getv "PID_$1")"
}

for s in $SEEDS; do
  d="$(run_dir "$s")"
  setv "RETRIES_$s" 0
  if [ -n "$(done_rung "$d")" ]; then
    say "lane s$s: already complete, skipping"
    setv "PID_$s" ""
    continue
  fi
  if [ -f "$d/checkpoint.pt" ]; then launch "$s" resume; else launch "$s" fresh; fi
  sleep 40  # stagger: the SIGSEGV-at-start landmine
done

while :; do
  alive=0
  for s in $SEEDS; do
    d="$(run_dir "$s")"; p="$(getv "PID_$s")"
    [ -n "$p" ] || continue
    if ! kill -0 "$p" 2>/dev/null; then
      if [ -n "$(done_rung "$d")" ]; then
        say "lane s$s: COMPLETE ($(basename "$(done_rung "$d")"))"
        setv "PID_$s" ""
        continue
      fi
      if [ "$(getv "RETRIES_$s")" -ge 3 ]; then
        say "lane s$s: DEAD and out of retries — manual attention; the "
        say "lane s$s: LANE-FAILURE RULE applies (fleet does not wait)"
        setv "PID_$s" ""
      else
        setv "RETRIES_$s" $(( $(getv "RETRIES_$s") + 1 ))
        say "lane s$s: died (retry $(getv "RETRIES_$s")/3); resuming"
        tail -3 "logs/ch5_100m_lane_s$s.log" >> "$LOG" 2>/dev/null
        if [ -f "$d/checkpoint.pt" ]; then launch "$s" resume; else launch "$s" fresh; fi
        alive=1
      fi
      continue
    fi
    alive=1
    t1=$(ps -o time= -p "$p" | tr -d ' ')
    sleep 15
    t2=$(ps -o time= -p "$p" 2>/dev/null | tr -d ' ')
    latest=$(ls -t "$d"/ckpt_*.pt 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null)
    say "lane s$s: alive cpu=$t1->$t2 latest=${latest:-none}"
    if [ -n "$t2" ] && [ "$t1" = "$t2" ]; then
      setv "STALLS_$s" $(( $(getv "STALLS_$s") + 1 ))
      say "lane s$s: ALERT zero CPU delta ($(getv "STALLS_$s") consecutive)"
      if [ "$(getv "STALLS_$s")" -ge 3 ] && [ "$(getv "RETRIES_$s")" -lt 3 ]; then
        setv "RETRIES_$s" $(( $(getv "RETRIES_$s") + 1 ))
        say "lane s$s: STALLED — killing and resuming (retry $(getv "RETRIES_$s")/3)"
        kill -9 "$p" 2>/dev/null; sleep 5
        launch "$s" resume
      fi
    else
      setv "STALLS_$s" 0
    fi
  done
  [ "$alive" = 0 ] && break
  sleep 300
done
say "FLEET DONE — run the FROZEN post-fleet eval schedule (pre-reg order), then scripts/ch5_100m_grade.py"
