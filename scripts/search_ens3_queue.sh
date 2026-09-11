#!/bin/bash
# ENS3 — the 3-seed log-prob ensemble on the 100M checkpoints.
# Pre-reg: AMENDMENT 2026-09-11 (b) in configs/eval/search_s3_100m.yaml.
# SEQUENTIAL on purpose: the box is carrying the EG10 verdict arm and the FP
# leg, and each ENS3 batch is only ~20 min, so serialising costs ~40 min of
# wall and protects the arm that matters.
#   nohup bash scripts/search_ens3_queue.sh > results/search_s3_100m/ens3_queue.log 2>&1 &
set -u
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
PREREG=configs/eval/search_s3_100m.yaml
RDIR=results/search_s3_100m
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }
for J in ens3_b0 ens3_b1 ens3_b2; do
  TRY=0
  while [ $TRY -le 2 ]; do
    if [ -f "$RDIR/$J.final.json" ]; then log "$J: final exists"; break; fi
    log "$J: launching (try $TRY)"
    taskpolicy -b $PY scripts/ch3_eval.py --prereg "$PREREG" --job "$J" \
      > "$RDIR/$J.log" 2>&1
    if [ -f "$RDIR/$J.final.json" ]; then log "$J: DONE"; break; fi
    log "$J: no final after try $TRY (resume skips finished chunks)"
    TRY=$((TRY+1))
  done
done
log "ENS3 ALL DONE"
