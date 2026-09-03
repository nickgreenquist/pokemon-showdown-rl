#!/usr/bin/env bash
# CH5 100M — FROZEN POST-FLEET EVAL SCHEDULE, STEP 1: vs-SH finals.
# Pre-reg: configs/showdown_sp_100m.yaml (RATIFIED 2026-09-01), schedule
# order frozen; HANDOFF §2.1. Locked protocol: completion checkpoint
# (ckpt_1000*.pt, the >=1e8 crossing rung), n=3000/seed, deterministic
# policy, vs SimpleHeuristicsPlayer, ties as non-wins. Serial (one seat
# connected at a time — no username collisions). RESUME-SAFE: a final
# whose JSON exists is skipped. Rate check: ~120 s/lane (the ch5_g9_basis
# realized rate at identical n and script).
set -euo pipefail
cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
N="${N:-3000}"
SEEDS="${SEEDS:-104 112 120}"

for s in $SEEDS; do
  RUN="runs/showdown_sp_100m_s${s}"
  ckpt=$(ls "$RUN"/ckpt_1000*.pt | head -1)
  out="results/ch5_100m/final_s${s}.json"
  if [ -f "$out" ]; then
    echo "[$(date -u +%FT%TZ)] SKIP s${s} (already have $out)"
    continue
  fi
  t0=$(date +%s)
  echo "[$(date -u +%FT%TZ)] START s${s} $(basename "$ckpt")"
  "$PY" scripts/eval_checkpoint.py "$ckpt" --episodes "$N" --out "$out.tmp" >/dev/null
  mv "$out.tmp" "$out"
  t1=$(date +%s)
  wr=$("$PY" -c "import json;print(json.load(open('$out'))['eval/win_rate'])")
  echo "[$(date -u +%FT%TZ)] DONE s${s} win_rate=$wr ELAPSED=$((t1-t0))s"
done
echo "[$(date -u +%FT%TZ)] STEP 1 DONE"
