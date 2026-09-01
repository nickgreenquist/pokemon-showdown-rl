#!/usr/bin/env bash
# CH5 STAGE-2 G9 BASIS (HANDOFF 2026-08-31 §1) — DESCRIPTIVE CONTROL SIDE.
#
# G9 is THROUGHPUT_SPEC §4's null-expected learning-equivalence gate. Its
# recorded 0.3890 basis predates both the entity trunk and the batch recipe,
# so it would misfire on any Stage-2 run of the current recipe. The control
# side is already on disk: all three batch-50M lanes' 12M rungs are clean
# (both resume seams — s66 @34.4M, s75 @47.2M — are far after 12M).
#
# This evaluates ckpt_012000000.pt for s66/s75/s83 under the locked protocol
# (n=3000/seed, deterministic policy, vs SimpleHeuristicsPlayer, ties as
# non-wins) and the POOLED equal-weight per-seed mean of the three is the
# re-based G9 basis. Pooling is load-bearing: one rung re-draws at ±0.02
# (three re-draws of one 50M checkpoint spread 0.0200), so a |Δ|<0.025 band
# against a single rung would be nearly untestable.
#
# CAVEAT THAT TRAVELS WITH THE BASIS: these rungs come from a 50M run with
# lr_anneal_steps 50,000,000 — the Stage-2 treatment must run the IDENTICAL
# 50M config (async collector aside) and stop at 12M, or the comparison is
# of learning-rate schedules, not collection loops.
#
# RESUME-SAFE: a rung whose JSON already exists is skipped. Rate: the s83
# scale-shape rungs (same script, same n) ran ~120 s each.
set -euo pipefail

cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
N="${N:-3000}"
SEEDS="${SEEDS:-66 75 83}"

for s in $SEEDS; do
  RUN="runs/showdown_sp_batch50m_s${s}"
  OUT="$RUN/g9_basis"
  mkdir -p "$OUT"
  ckpt="$RUN/ckpt_012000000.pt"
  out="$OUT/rung_12M_n${N}.json"
  if [ -f "$out" ]; then
    echo "[$(date -u +%FT%TZ)] SKIP s${s} (already have $out)"
    continue
  fi
  t0=$(date +%s)
  echo "[$(date -u +%FT%TZ)] START s${s} 12M"
  "$PY" scripts/eval_checkpoint.py "$ckpt" --episodes "$N" --out "$out.tmp" >/dev/null
  mv "$out.tmp" "$out"
  t1=$(date +%s)
  wr=$("$PY" -c "import json;print(json.load(open('$out'))['eval/win_rate'])")
  echo "[$(date -u +%FT%TZ)] DONE s${s} win_rate=$wr ELAPSED=$((t1-t0))s"
done

echo "[$(date -u +%FT%TZ)] ALL LANES DONE"
