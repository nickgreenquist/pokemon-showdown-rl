#!/usr/bin/env bash
# CH5 SCALE-SHAPE READ (HANDOFF item 2, 2026-08-31) — DESCRIPTIVE ONLY.
#
# Question: under the BATCH recipe, is vs-SH still climbing at 50M or already
# flat? D29r2's R-B FLAT tested the OLD recipe; the batch recipe's scaling is
# UNMEASURED at any point but 50M.
#
# NOT a protocol number and NOT a comparator:
#   - ONE seed (s83). The locked protocol is 3 seeds pooled.
#   - s83 is the ONLY clean lane: s66/s75 were resumed and their histories
#     cross a seam where checkpoint step and training history disagree.
#   - No bar, no credit line, no arms. It credits nothing and routes nothing.
#     A 100M run is credit-seeking and needs its OWN pre-registration.
# n=3000/rung is the locked protocol's PER-SEED count (the handoff allowed
# n=1000; 3000 costs ~2 min more per rung on this box, so we bought the
# precision: se ~0.0075 instead of ~0.013).
#
# Comparisons across rungs are UNPAIRED: the server rolls teams and damage, so
# every pass draws fresh battles regardless of the episode seed ladder (all
# rungs share seed_start = cfg.eval_episodes = 100).
#
# RESUME-SAFE: a rung whose JSON already exists is skipped, so a death costs
# at most one rung. Rate is readable from the per-rung ELAPSED lines below.
set -euo pipefail

cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
RUN=runs/showdown_sp_batch50m_s83
OUT="$RUN/scale_shape"
N="${N:-3000}"
STEPS="${STEPS:-005 010 015 020 025 030 035 040 045 050}"

mkdir -p "$OUT"
echo "[$(date -u +%FT%TZ)] scale-shape read: n=$N rungs=$STEPS"

for s in $STEPS; do
  ckpt="$RUN/ckpt_${s}000000.pt"
  out="$OUT/rung_${s}M_n${N}.json"
  if [ -f "$out" ]; then
    echo "[$(date -u +%FT%TZ)] SKIP ${s}M (already have $out)"
    continue
  fi
  t0=$(date +%s)
  echo "[$(date -u +%FT%TZ)] START ${s}M"
  # --out writes the report; stdout is the same JSON and is discarded.
  "$PY" scripts/eval_checkpoint.py "$ckpt" --episodes "$N" --out "$out.tmp" >/dev/null
  mv "$out.tmp" "$out"
  t1=$(date +%s)
  wr=$("$PY" -c "import json,sys;print(json.load(open('$out'))['eval/win_rate'])")
  echo "[$(date -u +%FT%TZ)] DONE ${s}M win_rate=$wr ELAPSED=$((t1-t0))s"
done

echo "[$(date -u +%FT%TZ)] ALL RUNGS DONE"
