#!/bin/bash
# FP@N CALIBRATION (configs/eval/fp_iter_calib.yaml), control first: CAL20 (FP@20, k=1, the
# reads queue's quiet-box gate, 3000 battles), then -- only if CAL20 produced its seat JSON --
# the FP@N wave CALN1..8 (8 slots x 375 battles). Detached, resume-safe (the scheduler skips
# arms whose seat JSON exists), frozen copy, and holds the box awake through the scheduler.
# LAUNCH THROUGH BASH (zsh's BG_NICE would nice it +5 and the scheduler refuses niced runs):
#   bash -c 'nohup bash scripts/fp_iter_calib_chain.sh > /dev/null 2>&1 &'
# STATUS: results/fp_iter_calib/STATUS -- RUNNING_CAL20 | RUNNING_CALN | DONE | FAILED ...
set -u
if [ "${FROZEN:-0}" != "1" ]; then
  F=$(mktemp -t fpcal_chain); cat "$0" > "$F"; FROZEN=1 exec bash "$F" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-fpprobe
FPDIR=/Users/nickgreenquist/Documents/Projects/foul-play-fpprobe
PRE=configs/eval/fp_iter_calib.yaml
OUT=$REPO/results/fp_iter_calib
cd "$REPO" || exit 1
mkdir -p "$OUT"
st() { echo "[$(date -u +%FT%TZ)] $*" >> "$OUT/STATUS.log"; echo "$*" > "$OUT/STATUS"; }
st "RUNNING_CAL20 (FP@20 control, k=1, 3000 battles; chain pid $$)"
/opt/anaconda3/bin/python scripts/fp_arms_parallel.py --prereg "$PRE" --arms CAL20 --slots 1 \
  --fpdir "$FPDIR" --gate-hold-min 30 >> "$OUT/chain.nohup" 2>&1
if [ ! -f "$OUT/cal20.json" ]; then
  st "FAILED: CAL20 produced no seat JSON -- the FP@N wave NOT run; box released (see parallel.log)"
  exit 1
fi
st "RUNNING_CALN (FP@N wave, 8 slots x 375 battles)"
/opt/anaconda3/bin/python scripts/fp_arms_parallel.py --prereg "$PRE" \
  --arms CALN1,CALN2,CALN3,CALN4,CALN5,CALN6,CALN7,CALN8 --slots 8 --stagger 15 \
  --fpdir "$FPDIR" >> "$OUT/chain.nohup" 2>&1
rc=$?
n=$(ls "$OUT"/caln[1-8].json 2>/dev/null | wc -l | tr -d ' ')
if [ "$rc" -eq 0 ] && [ "$n" -eq 8 ]; then
  st "DONE: CAL20 + 8/8 CALN slices -- box released"
else
  st "DONE_PARTIAL: CAL20 + $n/8 CALN slices (scheduler rc $rc) -- box released; rerun missing slices on their R2 pairs"
fi
