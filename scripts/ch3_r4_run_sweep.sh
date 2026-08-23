#!/bin/bash
# BI-6: the R4 sweep runner (pre-reg configs/eval/ch3_r4_ensemble_critic.yaml,
# SCHEDULE section). bash-3.2-safe: no ${var,,}, no associative arrays, no
# mapfile. Liveness = chunk-file progress via the driver's own resume logic;
# a died job is relaunched (resume skips finished chunks), max 2 relaunches
# per job. Order: A0 (4-wide) -> F4 band read (STOP outside the stop band)
# -> WAVE_A -> WAVE_B. ~30 s start stagger per job (torch lazy-init SIGSEGV
# landmine). Run from the repo root:
#   nohup bash scripts/ch3_r4_run_sweep.sh > results/ch3_r4/sweep.log 2>&1 &
set -u
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
PREREG=configs/eval/ch3_r4_ensemble_critic.yaml
RDIR=results/ch3_r4
mkdir -p "$RDIR"

run_group() {
  # run_group "label" job1 job2 ... : launch 4-wide with stagger, wait,
  # relaunch any job missing its final (resume), up to 2 times.
  GROUP_LABEL=$1; shift
  JOBS="$*"
  TRY=0
  while [ $TRY -le 2 ]; do
    PIDS=""
    LAUNCHED=0
    for J in $JOBS; do
      if [ -f "$RDIR/$J.final.json" ]; then
        echo "[$GROUP_LABEL] $J: final exists, skipping"
        continue
      fi
      echo "[$GROUP_LABEL] launching $J (try $TRY) $(date '+%H:%M:%S')"
      $PY scripts/ch3_eval.py --prereg "$PREREG" --job "$J" \
        > "$RDIR/$J.log" 2>&1 &
      PIDS="$PIDS $!"
      LAUNCHED=1
      sleep 30
    done
    [ $LAUNCHED -eq 0 ] && return 0
    for P in $PIDS; do
      wait "$P" || echo "[$GROUP_LABEL] a job exited nonzero (will check finals)"
    done
    MISSING=0
    for J in $JOBS; do
      [ -f "$RDIR/$J.final.json" ] || MISSING=1
    done
    [ $MISSING -eq 0 ] && return 0
    TRY=$((TRY + 1))
    echo "[$GROUP_LABEL] finals missing after wait; relaunch round $TRY"
  done
  echo "[$GROUP_LABEL] FAILED after 2 relaunches — stopping the sweep"
  return 1
}

echo "R4 sweep start $(date '+%Y-%m-%d %H:%M:%S')"

run_group A0 a0_s62 a0_s63 a0_s64 a0_s65 || exit 1

# F4 era read BEFORE any search battle (pre-reg R4-10 / F4 bands)
$PY - <<'EOF' || exit 1
import json, sys, yaml
pre = yaml.safe_load(open("configs/eval/ch3_r4_ensemble_critic.yaml"))
lanes = pre["arms"]["A0"]["lanes"]
p = [json.load(open(f"results/ch3_r4/a0_{l}.final.json"))["eval/win_rate"] for l in lanes]
pooled = sum(p) / len(p)
g_lo, g_hi = pre["f4_era_green_band"]
s_lo, s_hi = pre["f4_era_stop_band"]
print(f"F4 read: A0 pooled {pooled:.5f} per-lane {p}")
if not (s_lo <= pooled <= s_hi):
    print(f"F4 STOP: outside [{s_lo}, {s_hi}] — NO search battle launches")
    sys.exit(1)
if not (g_lo <= pooled <= g_hi):
    print(f"F4 DISCLOSED: outside green [{g_lo}, {g_hi}] — sweep proceeds, disclosed")
else:
    print("F4 green")
EOF

run_group WAVE_A a1s_s62 a1e_s62 a1s_s63 a1e_s63 || exit 1
run_group WAVE_B a1s_s64 a1e_s64 a1s_s65 a1e_s65 || exit 1

echo "R4 sweep COMPLETE $(date '+%Y-%m-%d %H:%M:%S') — run the grader:"
echo "  $PY scripts/ch3_r4_grade.py --prereg $PREREG"
