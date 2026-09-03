#!/usr/bin/env bash
# CH5 100M — FROZEN EVAL SCHEDULE STEPS 3+4: S-SHAPE then S-ANNEAL.
# Pre-reg: configs/showdown_sp_100m.yaml (RATIFIED 2026-09-01). Both are
# DESCRIPTIVE, never verdict inputs. "flat"/"plateau" BARRED on every
# branch; the MANDATORY anneal sentence travels with every S-SHAPE quote
# (sub-100M treatment rungs are on the 100M anneal — not comparable to a
# finished run at the same step). S-ANNEAL measures anneal AND wire
# jointly and says so in the same sentence, always.
#   S-SHAPE: rungs nearest >= 5M..100M step 5M (M4: crossing rungs) x 3
#     treatment lanes, n=3000 vs-SH (locked protocol) -> 60 evals ~2.0 h.
#   S-ANNEAL: the sync control's own exact-grid rungs 5M..50M step 5M x 3
#     lanes, n=3000 -> 30 evals ~1.0 h.
# Serial throughout (one seat connected at a time). RESUME-SAFE: existing
# JSONs are skipped. Rate read: ~120 s/eval (ch5_g9_basis realized).
# Outputs: results/ch5_100m/sshape/s{seed}_{MM}M.json and
#          results/ch5_100m/sanneal/s{seed}_{MM}M.json (eval_checkpoint
# format; the readout pools per-rung across the 3 lanes).
set -euo pipefail
cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
N="${N:-3000}"

run_one() {  # $1 ckpt, $2 out.json
  if [ -f "$2" ]; then echo "[$(date -u +%FT%TZ)] SKIP $2"; return 0; fi
  t0=$(date +%s)
  "$PY" scripts/eval_checkpoint.py "$1" --episodes "$N" --out "$2.tmp" >/dev/null
  mv "$2.tmp" "$2"
  t1=$(date +%s)
  wr=$("$PY" -c "import json;print(json.load(open('$2'))['eval/win_rate'])")
  echo "[$(date -u +%FT%TZ)] DONE $2 win_rate=$wr ELAPSED=$((t1-t0))s"
}

# ---- S-SHAPE: treatment lanes, nearest crossing rung >= each 5M grid ----
mkdir -p results/ch5_100m/sshape
for s in 104 112 120; do
  RUN="runs/showdown_sp_100m_s${s}"
  for m in $(seq 5 5 100); do
    grid=$(printf "%09d" $((m * 1000000)))
    ckpt=$(ls "$RUN"/ckpt_*.pt | sort | awk -v g="$RUN/ckpt_${grid}.pt" '$0 >= g' | head -1)
    [ -n "$ckpt" ] || { echo "[$(date -u +%FT%TZ)] MISSING rung >= ${m}M for s${s}"; exit 1; }
    run_one "$ckpt" "results/ch5_100m/sshape/s${s}_$(printf %03d "$m")M.json"
  done
done
echo "[$(date -u +%FT%TZ)] S-SHAPE DONE"

# ---- S-ANNEAL: sync control lanes, exact grid rungs 5M..50M ------------
mkdir -p results/ch5_100m/sanneal
for s in 66 75 83; do
  RUN="runs/showdown_sp_batch50m_s${s}"
  for m in $(seq 5 5 50); do
    ckpt="$RUN/ckpt_$(printf "%09d" $((m * 1000000))).pt"
    [ -f "$ckpt" ] || { echo "[$(date -u +%FT%TZ)] MISSING $ckpt"; exit 1; }
    run_one "$ckpt" "results/ch5_100m/sanneal/s${s}_$(printf %03d "$m")M.json"
  done
done
echo "[$(date -u +%FT%TZ)] S-ANNEAL DONE"
echo "[$(date -u +%FT%TZ)] STEPS 3+4 DONE"
