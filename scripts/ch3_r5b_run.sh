#!/bin/bash
# CH3 R5b BI-8: the wave runner (configs/eval/ch3_r5b_exit.yaml SCHEDULE).
# bash-3.2-safe (no ${var,,}, no assoc arrays). Liveness = chunk-file
# progress, never directory existence. ~30 s start stagger (torch lazy-init
# SIGSEGV landmine). F-U: realized usernames grepped from the wave's logs
# and asserted pairwise-distinct after every wave start.
#
# PHASES (run in order; each is resumable by re-running):
#   PHASE=collect   Stage-2a self-play collection, 4 lanes 4-wide  (~2.8 h)
#   PHASE=fits      distill -> gates -> placebo -> gates+PL -> diag -> stamp
#                   (offline, sequential; STOPS with commit instructions)
#   PHASE=read      B-13 era-pin X0 first, mechanical F-T check, then
#                   WAVE_A + WAVE_B lane-paired X0/X1                (~24 min)
#   PHASE=pl_anchors  IFF the graded cell is B1a/B1b/B2: WAVE_P, CA/CB,
#                   FA (fp runner), then regrade
#
#   PHASE=collect nohup bash scripts/ch3_r5b_run.sh > results/ch3_r5b/run_collect.log 2>&1 &
set -u
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
PREREG=configs/eval/ch3_r5b_exit.yaml
RDIR=results/ch3_r5b
CDIR=$RDIR/collect
ERA_DIR=results/ch3_r5b_era_pin
ANCH_DIR=results/ch3_r5b_anchors
PHASE=${PHASE:-collect}
LANES="s62 s63 s64 s65"
mkdir -p "$RDIR"

fu_check() {
  # F-U: every 'realized usernames' line across the given logs must be
  # pairwise distinct (usernames are per-process entropy; a collision dies
  # with the misleading 'Agent is not challenging' timeout).
  # Full usernames are quoted and contain spaces ('ShowdownSing xxxxx');
  # extract the complete quoted strings — splitting on whitespace flagged
  # the shared 'ShowdownSing' PREFIX as a duplicate (false-fired
  # 2026-08-25 on the era-pin wave).
  DUP=$(grep -h "realized usernames" "$@" 2>/dev/null \
        | grep -o "'[^']*'" | sort | uniq -d)
  if [ -n "$DUP" ]; then
    echo "F-U FAIL: duplicate usernames across concurrent jobs: $DUP"
    return 1
  fi
  echo "F-U ok ($# logs)"
}

phase_collect() {
  echo "PHASE collect start $(date '+%H:%M:%S')"
  LOGS=""
  for L in $LANES; do
    if [ -f "$CDIR/$L.final.json" ]; then echo "$L collection done"; continue; fi
    $PY scripts/ch3_r5b_collect.py --prereg "$PREREG" --lane "$L" \
      > "$RDIR/collect_$L.log" 2>&1 &
    echo "launched collect $L pid $!"
    LOGS="$LOGS $RDIR/collect_$L.log"
    sleep 30
  done
  if [ -n "$LOGS" ]; then sleep 60; fu_check $LOGS || exit 1; fi
  wait
  MISS=0
  for L in $LANES; do
    [ -f "$CDIR/$L.final.json" ] || { echo "MISSING $L collection final"; MISS=1; }
  done
  [ "$MISS" = 0 ] || { echo "collection incomplete — re-run PHASE=collect"; exit 1; }
  echo "PHASE collect COMPLETE $(date '+%H:%M:%S') — next: PHASE=fits"
}

phase_fits() {
  echo "PHASE fits start $(date '+%H:%M:%S') (offline, sequential)"
  for L in $LANES; do
    [ -f "$RDIR/fit/${L}_tau_grid.json" ] || \
      $PY scripts/ch3_r5b_distill.py --prereg "$PREREG" --lane "$L" || exit 1
    [ -f "$RDIR/gates/${L}_gates.json" ] || \
      $PY scripts/ch3_r5b_gates.py --prereg "$PREREG" --lane "$L" || exit 1
    [ -f "$RDIR/fit/${L}_placebo.json" ] || \
      $PY scripts/ch3_r5b_placebo.py --prereg "$PREREG" --lane "$L" || exit 1
    # rerun gates so the PL dose/D-5 block lands in the lane report
    $PY scripts/ch3_r5b_gates.py --prereg "$PREREG" --lane "$L" || exit 1
    [ -f "$RDIR/diag/${L}_diag.json" ] || \
      $PY scripts/ch3_r5b_diag.py --prereg "$PREREG" --lane "$L" || exit 1
  done
  $PY scripts/ch3_r5b_gates.py --prereg "$PREREG" --merge || exit 1
  GREEN=$($PY -c "import json; print(json.load(open('$RDIR/gates/d_gates.json'))['all_blocking_green'])")
  [ "$GREEN" = "True" ] || { echo "B-10 FAIL: D-gates not all green — STOP, no battles"; exit 1; }
  $PY scripts/ch3_r5b_stamp.py --prereg "$PREREG" || exit 1
  echo "PHASE fits COMPLETE — COMMIT NOW (B-2), then PHASE=read:"
  echo "  git add $PREREG configs/eval/ch3_r5b_fp_anchor.yaml && git commit -m 'R5b B-5/B-10 stamp'"
}

phase_read() {
  DIRTY=$(git status --porcelain)
  [ -z "$DIRTY" ] || { echo "B-2 FAIL: tree dirty — commit first"; exit 1; }
  mkdir -p "$ERA_DIR"
  if [ ! -f "$ERA_DIR/era_prereg.yaml" ]; then
    $PY -c "
import pathlib
t = pathlib.Path('$PREREG').read_text()
assert t.count('results_dir: results/ch3_r5b') == 1
pathlib.Path('$ERA_DIR/era_prereg.yaml').write_text(
    t.replace('results_dir: results/ch3_r5b', 'results_dir: $ERA_DIR'))
print('era-pin prereg derived (results_dir only)')" || exit 1
  fi
  echo "WAVE_0 (B-13 era pin) start $(date '+%H:%M:%S')"
  LOGS=""
  for L in $LANES; do
    [ -f "$ERA_DIR/x0_$L.final.json" ] && continue
    $PY scripts/ch3_eval.py --prereg "$ERA_DIR/era_prereg.yaml" --job "x0_$L" \
      > "$ERA_DIR/x0_$L.log" 2>&1 &
    echo "launched era-pin x0_$L pid $!"
    LOGS="$LOGS $ERA_DIR/x0_$L.log"
    sleep 30
  done
  if [ -n "$LOGS" ]; then sleep 60; fu_check $LOGS || exit 1; fi
  wait
  $PY -c "
import json, sys
rates = []
for l in '$LANES'.split():
    rates.append(json.load(open('$ERA_DIR/x0_%s.final.json' % l))['eval/win_rate'])
pooled = sum(rates) / len(rates)
print('F-T era pin: X0 pooled %.5f' % pooled, rates)
if not (0.650 <= pooled <= 0.770):
    print('F-T STOP: outside [0.650, 0.770] — X1 does NOT launch; diagnose'); sys.exit(1)
if 0.689 <= pooled <= 0.744:
    print('F-T GREEN')
else:
    print('F-T DISCLOSED band: B1a unclaimable, quote the value')" || exit 1
  for WAVE in "s62 s63" "s64 s65"; do
    echo "paired wave [$WAVE] start $(date '+%H:%M:%S')"
    LOGS=""
    for L in $WAVE; do
      D=$(echo "$L" | sed 's/s/d/')
      for JOB in "x0_$L" "x1_$D"; do
        [ -f "$RDIR/$JOB.final.json" ] && continue
        $PY scripts/ch3_eval.py --prereg "$PREREG" --job "$JOB" \
          > "$RDIR/$JOB.log" 2>&1 &
        echo "launched $JOB pid $!"
        LOGS="$LOGS $RDIR/$JOB.log"
        sleep 30
      done
    done
    if [ -n "$LOGS" ]; then sleep 60; fu_check $LOGS || exit 1; fi
    wait
  done
  MISS=0
  for L in $LANES; do
    D=$(echo "$L" | sed 's/s/d/')
    [ -f "$RDIR/x0_$L.final.json" ] || { echo "MISSING x0_$L"; MISS=1; }
    [ -f "$RDIR/x1_$D.final.json" ] || { echo "MISSING x1_$D"; MISS=1; }
  done
  [ "$MISS" = 0 ] || { echo "read incomplete — re-run PHASE=read"; exit 1; }
  echo "PHASE read COMPLETE $(date '+%H:%M:%S') — grade with:"
  echo "  $PY scripts/ch3_r5b_grade.py --prereg $PREREG"
}

phase_pl_anchors() {
  CELL=$($PY -c "import json; print(json.load(open('$RDIR/r5b_readout.json'))['cell_IF_NO_VOIDING_GATE'])")
  case "$CELL" in
    B1a|B1b|B2) echo "cell $CELL — PL + anchors fire" ;;
    *) echo "cell $CELL — PL and anchors do NOT run (pre-reg Q10)"; exit 0 ;;
  esac
  echo "WAVE_P start $(date '+%H:%M:%S')"
  LOGS=""
  for L in $LANES; do
    P=$(echo "$L" | sed 's/s/p/')
    [ -f "$RDIR/pl_$P.final.json" ] && continue
    $PY scripts/ch3_eval.py --prereg "$PREREG" --job "pl_$P" \
      > "$RDIR/pl_$P.log" 2>&1 &
    echo "launched pl_$P pid $!"
    LOGS="$LOGS $RDIR/pl_$P.log"
    sleep 30
  done
  if [ -n "$LOGS" ]; then sleep 60; fu_check $LOGS || exit 1; fi
  wait
  mkdir -p "$ANCH_DIR"
  for ARM in CA CB; do
    A=$(echo "$ARM" | tr '[:upper:]' '[:lower:]')
    [ -f "$ANCH_DIR/$A.final.json" ] && continue
    $PY scripts/ch3_r4_anchors.py --prereg "$PREREG" --arm "$ARM" \
      --out-dir "$ANCH_DIR" > "$ANCH_DIR/$A.log" 2>&1 || exit 1
  done
  echo "FA (fp runner; crash-forfeit discipline lives in the runner):"
  echo "  PREREG=configs/eval/ch3_r5b_fp_anchor.yaml ARM=FA bash scripts/ch3_r4_fp_runner.sh"
  echo "then REGRADE:  $PY scripts/ch3_r5b_grade.py --prereg $PREREG"
}

case "$PHASE" in
  collect) phase_collect ;;
  fits) phase_fits ;;
  read) phase_read ;;
  pl_anchors) phase_pl_anchors ;;
  *) echo "unknown PHASE=$PHASE (collect|fits|read|pl_anchors)"; exit 1 ;;
esac
