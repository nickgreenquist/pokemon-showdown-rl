#!/usr/bin/env bash
# STAGE-2 ACCEPTANCE WAVE (configs/showdown_sp_batch50m_async.yaml header
# is the pre-registration; this file is only ops). Sequence:
#   0. WAIT for the box to go quiet (R4S66's h2h wave owns it first) —
#      the G8 medians and the solo bench are garbage on a loaded box.
#   1. Solo on/off bench: configs/ch5_stage2_bench.yaml (~5 min), the
#      async side of HANDOFF §1's "measure it on/off, both directions".
#   2. Three async lanes, seeds 66/75/83, staggered 40 s, detached.
#      Each lane is killed once ckpt_012000000.pt lands (the G9 stop; the
#      config keeps the control's own 50M schedule).
#   3. Locked-protocol eval of each lane's 12M rung (n=3000, serial), then
#      the pooled G9 read against the banked basis 0.64889 and per-lane
#      G8 medians.
#
# RESUME-SAFE at every stage: done rungs skip, dead lanes relaunch with
# --resume (bounded), existing eval JSONs skip. Rate is readable from the
# per-poll PROGRESS lines (compare against the control fleet's 444
# steps/s/lane median; a lane 10x off is stalled). Stall detection is
# CPU-TIME DELTAS, never pgrep — the known stall shape is ALIVE at ZERO
# CPU with a quiet log.
set -u
cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
LOG=logs/ch5_g9_wave.log
SEEDS="66 75 83"
RUNG=ckpt_012000000.pt
BASIS=0.6488888888888889

say() { echo "[$(date -u +%FT%TZ)] $*" >> "$LOG"; }
run_dir() { echo "runs/showdown_sp_batch50m_async_s$1"; }

say "WAVE START"

# --- 0. wait for the box -------------------------------------------------
while pgrep -f 'ch5_r2_wave.sh|ch3_fp_h2h.py' >/dev/null; do
  say "waiting: R4S66 wave still holds the box"
  sleep 120
done
say "box is quiet"

# --- 1. solo on/off bench ------------------------------------------------
if [ -f runs/ch5_stage2_bench/checkpoint.pt ]; then
  say "bench: already done, skipping"
else
  say "bench: START ch5_stage2_bench (4 rollouts, solo)"
  "$PY" -m rl.train --config configs/ch5_stage2_bench.yaml >> "$LOG" 2>&1
  say "bench: DONE exit $?"
fi

# --- 2. the fleet --------------------------------------------------------
declare -A PID STALLS RETRIES
launch() {  # $1 seed, $2 fresh|resume
  local d; d="$(run_dir "$1")"
  if [ "$2" = resume ]; then
    nohup "$PY" -m rl.train --resume "$d" >> "logs/ch5_g9_lane_s$1.log" 2>&1 &
  else
    nohup "$PY" -m rl.train --config configs/showdown_sp_batch50m_async.yaml \
      --seed "$1" --run-name "showdown_sp_batch50m_async_s$1" \
      >> "logs/ch5_g9_lane_s$1.log" 2>&1 &
  fi
  PID[$1]=$!
  STALLS[$1]=0
  say "lane s$1: launched ($2) pid ${PID[$1]}"
}

for s in $SEEDS; do
  d="$(run_dir "$s")"
  RETRIES[$s]=0
  if [ -f "$d/$RUNG" ]; then
    say "lane s$s: rung already on disk, skipping"
    PID[$s]=""
    continue
  fi
  if [ -f "$d/checkpoint.pt" ]; then launch "$s" resume; else launch "$s" fresh; fi
  sleep 40  # stagger: the SIGSEGV-at-start landmine
done

# --- watch loop ----------------------------------------------------------
while :; do
  alive=0
  for s in $SEEDS; do
    d="$(run_dir "$s")"; p="${PID[$s]}"
    [ -n "$p" ] || continue
    if [ -f "$d/$RUNG" ]; then
      say "lane s$s: 12M rung landed — stopping pid $p"
      kill "$p" 2>/dev/null; sleep 20; kill -9 "$p" 2>/dev/null
      PID[$s]=""
      continue
    fi
    if ! kill -0 "$p" 2>/dev/null; then
      if [ "${RETRIES[$s]}" -ge 3 ]; then
        say "lane s$s: DEAD and out of retries — manual attention needed"
        PID[$s]=""
      else
        RETRIES[$s]=$((RETRIES[$s] + 1))
        say "lane s$s: died (retry ${RETRIES[$s]}/3); resuming"
        tail -3 "logs/ch5_g9_lane_s$s.log" >> "$LOG" 2>/dev/null
        if [ -f "$d/checkpoint.pt" ]; then launch "$s" resume; else launch "$s" fresh; fi
      fi
      alive=1
      continue
    fi
    alive=1
    # CPU-delta stall check (the only instrument that catches the shape).
    t1=$(ps -o time= -p "$p" | tr -d ' ')
    sleep 15
    t2=$(ps -o time= -p "$p" 2>/dev/null | tr -d ' ')
    latest=$(ls -t "$d"/ckpt_0*.pt 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null)
    say "lane s$s: alive cpu=$t1->$t2 latest=${latest:-none}"
    if [ -n "$t2" ] && [ "$t1" = "$t2" ]; then
      STALLS[$s]=$((STALLS[$s] + 1))
      say "lane s$s: ALERT zero CPU delta (${STALLS[$s]} consecutive)"
      if [ "${STALLS[$s]}" -ge 3 ] && [ "${RETRIES[$s]}" -lt 3 ]; then
        RETRIES[$s]=$((RETRIES[$s] + 1))
        say "lane s$s: STALLED — killing and resuming (retry ${RETRIES[$s]}/3)"
        kill -9 "$p" 2>/dev/null; sleep 5
        launch "$s" resume
      fi
    else
      STALLS[$s]=0
    fi
  done
  [ "$alive" = 0 ] && break
  sleep 120
done
say "fleet done"

# --- 3. evals + the reads ------------------------------------------------
for s in $SEEDS; do
  d="$(run_dir "$s")"
  out="$d/g9_treat/rung_12M_n3000.json"
  if [ -f "$out" ]; then say "eval s$s: already done"; continue; fi
  if [ ! -f "$d/$RUNG" ]; then say "eval s$s: NO RUNG — skipped"; continue; fi
  mkdir -p "$d/g9_treat"
  say "eval s$s: START (locked protocol, n=3000)"
  "$PY" scripts/eval_checkpoint.py "$d/$RUNG" --episodes 3000 --out "$out.tmp" >/dev/null 2>>"$LOG"
  mv "$out.tmp" "$out" 2>/dev/null
  say "eval s$s: DONE"
done

"$PY" - >> "$LOG" 2>&1 <<EOF
import csv, json, statistics
ws = []
for s in (66, 75, 83):
    d = f"runs/showdown_sp_batch50m_async_s{s}"
    try:
        w = json.load(open(f"{d}/g9_treat/rung_12M_n3000.json"))["eval/win_rate"]
        ws.append(w)
        print(f"G9 s{s}: {w:.5f}")
    except FileNotFoundError:
        print(f"G9 s{s}: MISSING")
    try:
        import subprocess
        subprocess.run(["$PY", "scripts/extract_history.py", d],
                       capture_output=True, check=True)
        rows = list(csv.DictReader(open(f"{d}/history.csv")))
        sps = [float(r["time/steps_per_sec"]) for r in rows
               if r.get("time/steps_per_sec") and int(r["_step"]) > 200000]
        print(f"G8 s{s}: median steps/s = {statistics.median(sps):.1f} (n={len(sps)})")
    except Exception as e:
        print(f"G8 s{s}: history read failed ({e}) — if resume-split, "
              "merge per the landmine protocol before reading")
if len(ws) == 3:
    pooled = sum(ws) / 3
    delta = pooled - $BASIS
    print(f"G9 pooled: {pooled:.5f}  basis: $BASIS  delta: {delta:+.5f}  "
          f"{'PASS (null holds)' if abs(delta) < 0.025 else 'FAIL — do not launch 100M; bisect per the pre-reg header'}")
EOF
say "WAVE DONE"
