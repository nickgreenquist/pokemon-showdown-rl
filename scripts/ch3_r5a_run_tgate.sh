#!/bin/bash
# BI-A2: T-GATE wave runner (configs/eval/ch3_r5a_tgate.yaml SCHEDULE).
# bash-3.2-safe. Per lane, T_M launches when that lane's ts_s6N.chunk04
# exists (T_S midpoint) so T_M's span sits inside T_S's span (F-P teeth).
# Liveness polls chunk-file progress. ~30 s stagger (SIGSEGV landmine).
#   nohup bash scripts/ch3_r5a_run_tgate.sh > results/ch3_r5a/run.log 2>&1 &
set -u
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
PREREG=configs/eval/ch3_r5a_tgate.yaml
RDIR=results/ch3_r5a
mkdir -p "$RDIR"

run_wave() {
  L1=$1; L2=$2
  echo "WAVE $L1/$L2 start $(date '+%H:%M:%S')"
  for L in $L1 $L2; do
    TSARM=$(echo "TS_$L" | tr '[:lower:]' '[:upper:]')
    if [ ! -f "$RDIR/ts_$L.final.json" ]; then
      $PY scripts/ch3_r4_anchors.py --prereg "$PREREG" --arm "$TSARM" \
        --out-dir "$RDIR" > "$RDIR/ts_$L.log" 2>&1 &
      echo "launched $TSARM pid $!"
      sleep 30
    fi
  done
  for L in $L1 $L2; do
    TMARM=$(echo "TM_$L" | tr '[:lower:]' '[:upper:]')
    if [ -f "$RDIR/tm_$L.final.json" ]; then continue; fi
    until [ -f "$RDIR/ts_$L.chunk04.json" ] || [ -f "$RDIR/ts_$L.final.json" ]; do
      sleep 20
    done
    $PY scripts/ch3_r4_anchors.py --prereg "$PREREG" --arm "$TMARM" \
      --out-dir "$RDIR" > "$RDIR/tm_$L.log" 2>&1 &
    echo "launched $TMARM at TS midpoint pid $! $(date '+%H:%M:%S')"
    sleep 30
  done
  wait
  MISS=0
  for L in $L1 $L2; do
    [ -f "$RDIR/ts_$L.final.json" ] || { echo "MISSING ts_$L final"; MISS=1; }
    [ -f "$RDIR/tm_$L.final.json" ] || { echo "MISSING tm_$L final"; MISS=1; }
  done
  return $MISS
}

run_wave s62 s63 || { echo "WAVE_T1 incomplete — resume by re-running this script"; exit 1; }
run_wave s64 s65 || { echo "WAVE_T2 incomplete — resume by re-running this script"; exit 1; }
echo "T-GATE battles COMPLETE $(date '+%H:%M:%S') — grade with:"
echo "  $PY scripts/ch3_r5a_grade.py --prereg $PREREG"
