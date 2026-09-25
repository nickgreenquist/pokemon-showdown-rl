#!/bin/bash
# FP500_ITER_CALIB (configs/eval/fp500_iter_calib.yaml): REF500, the wall-clock FP@500
# reference (one slot, quiet box) -> the N/N_early read under the pre-stated rule -> SM500N, the
# FP@N install smoke -> results/fp500_iter_calib/calib.json.
#
# Launch ONLY once r7-runner has handed over the quiet box, and through bash, never a zsh `&`
# (BG_NICE would nice it, and the scheduler refuses a niced start):
#   bash -c 'nohup bash scripts/fp500_iter_calib_chain.sh > results/fp500_iter_calib/chain.log 2>&1 &'
# REF=REF500R2 re-runs the reference on the rerun pair (a killed arm's pair is poisoned for hours).
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
SCHED_PY="${SCHED_PY:-/opt/anaconda3/bin/python}"
PY="${PY:-/opt/anaconda3/envs/pokemon-showdown-rl/bin/python}"
REF="${REF:-REF500}"
OUT=results/fp500_iter_calib
mkdir -p "$OUT"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "chain start: $REF (wall-clock FP@500 reference, 1 slot, quiet box)"
"$SCHED_PY" scripts/fp_arms_parallel.py --prereg configs/eval/fp500_iter_calib.yaml \
    --arms "$REF" --slots 1 --gate-hold-min 60 || { log "$REF: scheduler rc=$? -- STOP"; exit 1; }
"$PY" scripts/fp500_iter_calib_read.py --ref "$REF" --write-smoke || { log "$REF read: VOID or error -- STOP"; exit 2; }
log "SM500N: the FP@N install smoke at the derived N/N_early"
"$SCHED_PY" scripts/fp_arms_parallel.py --prereg "$OUT/sm500n.yaml" --arms SM500N --slots 1 \
    || { log "SM500N: scheduler rc=$? -- STOP"; exit 3; }
"$PY" scripts/fp500_iter_calib_read.py --smoke || { log "SM500N FAILED -- STOP"; exit 4; }
log "chain DONE: $OUT/calib.json"
