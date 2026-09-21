#!/usr/bin/env bash
# The R7 architecture screen's six fits, EXACTLY as configs/bc_arch_screen.yaml
# pre-registers them. Sequential, niced, one fit at a time, single-threaded
# (train_bc calls torch.set_num_threads(1) itself) -- an FP evaluation arm
# shares this box and nothing here may compete with it.
#
# RESUME-SAFE: a fit whose results file already exists is SKIPPED, so a death
# costs one fit rather than the block. Progress is readable as a RATE from the
# per-epoch lines in each arm's log.
#
# Run under bash (CLAUDE.md: shell loops are not zsh):
#   bash scripts/arch_screen_fits.sh
set -u -o pipefail

WORKTREE="${WORKTREE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MAIN="${MAIN:-/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl}"
PY="${PY:-/opt/anaconda3/envs/pokemon-showdown-rl/bin/python}"
DATA="$MAIN/data/fp_all_v2i/v2i"
RES="$MAIN/results/arch_screen"

export PYTHONPATH="$WORKTREE"
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

mkdir -p "$RES"
cd "$WORKTREE" || exit 1

run_fit () {
  local name="$1"; shift
  if [ -f "$RES/$name.json" ] && [ -f "$RES/${name}_val_rows.npz" ]; then
    echo "SKIP $name (already in $RES)"
    return 0
  fi
  echo "=== $name  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  nice -n 19 "$PY" scripts/train_bc.py \
    --data "$DATA" --target soft --max-rows 180000 \
    --epochs 20 --batch-size 512 --lr 1e-3 \
    --run-name "$name" "$@" 2>&1 | tee "$RES/$name.log"
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    echo "FAILED $name (rc=$rc) -- stopping the block"
    return "$rc"
  fi
  cp "runs/$name/bc_metrics.json" "$RES/$name.json"
  cp "runs/$name/val_rows.npz" "$RES/${name}_val_rows.npz"
  echo "=== $name done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

for s in 0 1 2; do
  run_fit "arch_screen_entity_s$s" --trunk entity_deepsets --seed "$s" || exit 1
  run_fit "arch_screen_attn_s$s" --trunk attention \
    --d-model 128 --n-layers 2 --n-heads 4 --seed "$s" || exit 1
done
echo "ALL SIX FITS DONE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
