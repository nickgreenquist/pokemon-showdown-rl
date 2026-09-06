#!/usr/bin/env bash
# THE GEN-4 WANG-RECIPE WAVE (configs/gen4_wang50m.yaml is the pre-reg; this
# file is only ops — scripts/ch5_100m_wave.sh's pattern on the SYNC path):
#   0. PREFLIGHT: the zero-lane gates readable only at launch time — clean
#      tree (R0-k), the pre-reg test + the hash gates (R0-a/R0-c), disk
#      >= 40 GiB (R0-h), memory >= 8 GB reclaimable (R0-i), FRESH Showdown
#      server (R0-j: started within the last 15 min, simulator: 4 verified;
#      restart it yourself first — this script never kills a server),
#      seeds' run dirs: an existing one is logged and RESUMED, never fatal
#      (R0-l is the seed-window test, run in the pytest line). R0-k2 (the
#      bare full suite) is the MAINTAINER's check before launch — this
#      script runs only the offline pre-reg / hash-gate / trunk files.
#   1. Three SYNC lanes, seeds 200/208/216, staggered 60 s, detached, run to
#      completion (the loop exits itself at step 50,000,000; the completion
#      rung is ckpt_050000000.pt exactly — 8 | 50M).
#   2. Watch loop: CPU-delta stall detection (the only instrument for
#      alive-at-zero-CPU), bounded auto-resume (3 zero-deltas -> resume,
#      3 retries/lane), progress lines with the latest rung, per-lane RSS.
#   3. On fleet completion it STOPS. The post-fleet schedule is FROZEN in
#      the pre-reg and runs separately — NOTHING evaluates while any lane
#      trains, and this script starts no eval.
# NO ENCODER ENV VARS: the gen-4 encoder reads none (POKEMON_RL_ENCODER_V2 /
# _IDS are gen-1 only).
# Launch (the maintainer's, > 5 h rule):
#   nohup caffeinate -dims bash scripts/gen4_wang50m_wave.sh > /dev/null 2>&1 < /dev/null &
#   (< /dev/null REQUIRED: nohup leaves stdin on the tty and zsh job control
#   SUSPENDS the launch — it bit the 2026-09-01 launch, SESSION_LOGS)
# RESUME-SAFE: re-running skips finished lanes and --resumes started ones
# (a resume loses the open seat-2 battles' harvested rows — disclosed in
# the pre-reg's lane-failure rule).
set -u
cd "$(dirname "$0")/.."

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
LOG=logs/gen4_wang50m_wave.log
SEEDS="200 208 216"
CONFIG=configs/gen4_wang50m.yaml
DONE_STEP=50000000

mkdir -p logs
say() { echo "[$(date -u +%FT%TZ)] $*" >> "$LOG"; }
run_dir() { echo "runs/gen4_wang50m_s$1"; }
done_rung() { ls "$1"/ckpt_0${DONE_STEP}.pt 2>/dev/null | head -1; }

say "WAVE START (pre-reg: $CONFIG)"

# --- 0. preflight (every check fatal) ------------------------------------
fail() { say "PREFLIGHT FAIL: $*"; echo "PREFLIGHT FAIL: $*" >&2; exit 1; }

[ -z "$(git status --porcelain)" ] || fail "tree not clean (R0-k)"
"$PY" -m pytest tests/test_gen4_prereg.py tests/test_gen4_encoder.py tests/test_entity_trunk_gen4.py -q >/dev/null 2>&1 \
  || fail "pre-reg / hash-gate / trunk tests red (R0-a / R0-c / R0-d)"
# R0-c: both hash gates must PASS, not skip (the corpus gate skips when the
# local tapes are absent, and -q >/dev/null hides a skip).
"$PY" -m pytest tests/test_gen4_encoder.py -q -k "hash_is_pinned" 2>&1 | grep -q "2 passed" \
  || fail "hash gates not both GREEN (R0-c: a skip is not a pass)"
free_gib=$(df -g . | tail -1 | awk '{print $4}')
[ "$free_gib" -ge 40 ] || fail "disk ${free_gib}GiB < 40GiB (R0-h)"
mem_gb=$(vm_stat | awk -F': *' '/free|inactive|purgeable|speculative/ \
  {gsub(/\./,"",$2); s+=$2} END {printf "%d", s*16384/1e9}')
[ "$mem_gb" -ge 8 ] || fail "reclaimable memory ${mem_gb}GB < 8GB (R0-i: close the browser and other apps, re-run)"
node_pid=$(pgrep -f "node pokemon-showdown start" | head -1)
[ -n "$node_pid" ] || fail "no Showdown server running (R0-j)"
node_start=$(ps -p "$node_pid" -o lstart= | xargs -I{} date -j -f "%a %b %d %T %Y" "{}" +%s 2>/dev/null)
[ -n "$node_start" ] || fail "could not read the server's start time (R0-j)"
node_age=$(( $(date +%s) - node_start ))
[ "$node_age" -le 900 ] || fail "server pid $node_pid is ${node_age}s old — restart it fresh first (R0-j)"
grep -q "simulator: 4" showdown/config/config.js || fail "simulator: 4 missing (R0-j / rule 5)"
[ -z "${POKEMON_RL_ENCODER_V2:-}${POKEMON_RL_ENCODER_IDS:-}" ] || say "note: gen-1 encoder env vars are set; the gen-4 path ignores them"
say "R0-j: fresh server pid $node_pid, age ${node_age}s, simulator: 4 verified"
for s in $SEEDS; do
  [ ! -d "$(run_dir "$s")" ] || say "lane s$s: run dir exists — will RESUME"
done
say "PREFLIGHT PASS (disk ${free_gib}GiB, mem ${mem_gb}GB)"

# --- 1+2. launch and watch ------------------------------------------------
getv() { eval "echo \${$1:-}"; }
setv() { eval "$1=\"$2\""; }
launch() {  # $1 seed, $2 fresh|resume
  local d; d="$(run_dir "$1")"
  if [ "$2" = resume ]; then
    nohup "$PY" -m rl.train --resume "$d" >> "logs/gen4_wang50m_lane_s$1.log" 2>&1 < /dev/null &
  else
    nohup "$PY" -m rl.train --config "$CONFIG" \
      --seed "$1" --run-name "gen4_wang50m_s$1" \
      >> "logs/gen4_wang50m_lane_s$1.log" 2>&1 < /dev/null &
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
  sleep 60  # stagger: the SIGSEGV-at-start landmine (sync lanes: 60 s)
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
        say "lane s$s: DEAD and out of retries — manual attention; the LANE-FAILURE RULE applies (fleet does not wait)"
        setv "PID_$s" ""
      else
        setv "RETRIES_$s" $(( $(getv "RETRIES_$s") + 1 ))
        say "lane s$s: died (retry $(getv "RETRIES_$s")/3); resuming"
        tail -3 "logs/gen4_wang50m_lane_s$s.log" >> "$LOG" 2>/dev/null
        if [ -f "$d/checkpoint.pt" ]; then launch "$s" resume; else launch "$s" fresh; fi
        alive=1
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
        say "lane s$s: STALLED — killing and resuming (retry $(getv "RETRIES_$s")/3)"
        kill -9 "$p" 2>/dev/null; sleep 5
        if [ -f "$d/checkpoint.pt" ]; then launch "$s" resume; else launch "$s" fresh; fi
      fi
    else
      setv "STALLS_$s" 0
    fi
  done
  box_free=$(vm_stat | awk -F': *' '/free|inactive/ {gsub(/\./,"",$2); s+=$2} END {printf "%.1f", s*16384/1e9}')
  swapouts=$(vm_stat | awk -F': *' '/Swapouts/ {gsub(/\./,"",$2); print $2}')
  # D-E reads the swapouts DELTA between polls: vm_stat's counter is cumulative.
  swap_delta=$(( ${swapouts:-0} - ${SWAP_PREV:-${swapouts:-0}} )); SWAP_PREV=${swapouts:-0}
  say "box: free+inactive ${box_free}GB swapouts_delta ${swap_delta} (cum ${swapouts:-?}) disk $(df -g . | tail -1 | awk '{print $4}')GiB"
  [ "$alive" = 0 ] && break
  sleep 300
done
say "FLEET DONE — run the FROZEN post-fleet schedule (pre-reg order): vs-SH 3x3000 -> FP@20 -> MDT -> S-SHAPE -> FP@500 -> clone h2h -> Q38 pin -> readout"
