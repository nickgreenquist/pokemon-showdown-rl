#!/usr/bin/env bash
# A-1 RE-EXECUTION on the FIXED engine build (bd3d06a: a foe's revealed-move PP
# is the client's count of observed uses; A-1a caught the 1.0 hard-code).
# Maintainer, 2026-09-10: "rerun a-1 yes". Same design as configs/engine_a1.yaml
# (seeds 66/75/83, k=8, 12M crossing rung, bank teams_a1_5000000.bin, n=12,000
# per rung eval); run dirs engine_a1b_s<seed> so the pre-fix lanes stay intact.
# Waits for the time-budgeted Foul Play leg (F3B112) to finish before launching
# — a fixed-time search opponent under CPU contention plays weaker and would
# inflate someone else's anchor. Detached, resume-safe (re-run this script),
# rate-readable (CPU-time deltas, rung checkpoints). Frozen-copy re-exec.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t engine_a1_rerun); cat "$0" > "$FROZEN"; QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pkmn-engine-port/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
SEEDS="66 75 83"; CONFIG=configs/engine_a1.yaml; OUT=results/engine_a1; EVAL_N=12000
LOG=logs/engine_a1_rerun.log; mkdir -p logs "$OUT"
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
rung_ckpt() { ls "runs/engine_a1b_s$1"/ckpt_0120*.pt 2>/dev/null | head -1; }
lane_pid() { pgrep -f "bin/python -m rl.train.*engine_a1b_s$1" | head -1; }

say "waiting for the time-budgeted FP leg (results/search_s3_100m_offfp/f3b112.json)"
while [ ! -f results/search_s3_100m_offfp/f3b112.json ]; do sleep 120; done
say "F3B112 finished"
git status --porcelain | grep -q . && { say "DIRTY TREE — refusing to launch (rule 3)"; exit 1; }
curl -s -o /dev/null --max-time 3 http://localhost:8000/ || { say "Showdown server down — refusing (in-loop evals need it)"; exit 1; }
[ -f data/engine/teams_a1_5000000.bin ] || { say "team bank missing"; exit 1; }
say "engine build: $("$PY" -c 'import pkmn_gen1,json; print(json.dumps(pkmn_gen1.build_info()))')"
say "git HEAD: $(git rev-parse HEAD)"

for s in $SEEDS; do
  if [ -n "$(rung_ckpt "$s")" ]; then say "SKIP s$s (rung exists)"; continue; fi
  if [ -d "runs/engine_a1b_s$s" ]; then
    say "RESUME s$s"; nohup "$PY" -m rl.train --resume "runs/engine_a1b_s$s" > "runs/engine_a1b_s$s.nohup.log" 2>&1 &
  else
    say "START s$s"; nohup "$PY" -m rl.train --config "$CONFIG" --seed "$s" --run-name "engine_a1b_s$s" > "runs/engine_a1b_s$s.nohup.log" 2>&1 &
  fi
  sleep 90   # stagger: lanes can SIGSEGV at startup before any log line
done
say "three lanes launched"

while :; do
  n=0; for s in $SEEDS; do [ -n "$(rung_ckpt "$s")" ] && n=$((n+1)); done
  [ "$n" -ge 3 ] && break
  for s in $SEEDS; do
    [ -n "$(rung_ckpt "$s")" ] && continue
    pid=$(lane_pid "$s")
    [ -z "$pid" ] && { say "s$s: NO PROCESS — re-run this script to resume it"; continue; }
    c0=$(ps -p "$pid" -o time=); sleep 15; c1=$(ps -p "$pid" -o time=)
    [ "$c0" = "$c1" ] && say "s$s: ALIVE AT ZERO CPU over 15 s (pid $pid) — the stall shape; kill and re-run to --resume"
  done
  sleep 600
done
# rl/train.py writes the crossing checkpoint BEFORE that step's eval: hold so
# the 48th in-loop rung lands (engine_gates.sh:252-255; eval_sec ~5 s).
say "12M rung on all lanes — holding 120 s for the 48th in-loop eval"; sleep 120
for s in $SEEDS; do pid=$(lane_pid "$s"); [ -n "$pid" ] && { say "stop s$s at $(basename "$(rung_ckpt "$s")")"; kill "$pid"; }; done
sleep 30

for s in $SEEDS; do
  [ -f "$OUT/rerun_rung12m_s$s.json" ] && continue
  nohup "$PY" scripts/eval_checkpoint.py "$(rung_ckpt "$s")" --episodes "$EVAL_N" --opponent heuristics \
    --out "$OUT/rerun_rung12m_s$s.json" > "logs/engine_a1_rerun_eval_s$s.log" 2>&1 &
  sleep 30
done
while :; do n=0; for s in $SEEDS; do [ -f "$OUT/rerun_rung12m_s$s.json" ] && n=$((n+1)); done; [ "$n" -ge 3 ] && break; sleep 120; done
say "rung evals done; grading on the ratified sidecar (own output file)"
"$PY" scripts/engine_a1_grade.py "$OUT/rerun_rung12m_s66.json" "$OUT/rerun_rung12m_s75.json" "$OUT/rerun_rung12m_s83.json" \
  --prereg configs/engine_a1.prereg.yaml --out "$OUT/primary_fixed.json" 2>&1 | tee -a "$LOG"
say "A-1 RERUN DONE"
