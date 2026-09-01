#!/usr/bin/env bash
# CH5 MPS BENCHMARK runner (HANDOFF item 3, 2026-08-31). REPORT AND PROPOSE
# ONLY -- the maintainer rules on the CLAUDE.md:71 change; this script does
# not touch it.
#
# Three arms, run SERIALLY so the box is quiet for each (a timing number taken
# under contention is not a timing number). Each is four rollouts of s83's
# EXACT recipe; the pre-reg-style header lives in configs/ch5_mps_bench.yaml.
#
#   cpu1   device=cpu, torch_threads=1   -- PRODUCTION, the banked baseline
#   mps    device=mps, torch_threads=1   -- the thing under test
#   cpu6   device=cpu, torch_threads=6   -- the CHEAPER ALTERNATIVE. If the
#          learner is thread-starved on a 14-core box, that is a one-line
#          config change with no backend risk, and it must be priced before
#          anyone argues for a new device.
#
# Arms carry DISTINCT SEEDS even though they run serially (CLAUDE.md rule 2:
# poke-env derives Showdown usernames from the globally-seeded `random`, and
# same-seed lanes collide and die with a misleading TimeoutError).
#
# RESUME-SAFE: an arm whose history.csv exists is skipped, so a death costs
# one arm. Progress is readable as `time/steps_per_sec` against s83's own
# 438 mean, and each arm prints ELAPSED.
set -euo pipefail

cd "$(dirname "$0")/.."

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
BASE=configs/ch5_mps_bench.yaml
WORK="${WORK:-/private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/3a562df9-1b1c-49ef-9218-f0f001045200/scratchpad}"
ARMS="${ARMS:-cpu1 mps cpu6}"

mkdir -p "$WORK"

arm_config() {   # $1 = arm -> prints the config path
    case "$1" in
        cpu1) echo "$BASE" ;;
        mps)  sed 's/^device: cpu$/device: mps/' "$BASE" > "$WORK/ch5_mps_bench_mps.yaml"
              echo "$WORK/ch5_mps_bench_mps.yaml" ;;
        cpu6) sed 's/^torch_threads: 1$/torch_threads: 6/' "$BASE" > "$WORK/ch5_mps_bench_cpu6.yaml"
              echo "$WORK/ch5_mps_bench_cpu6.yaml" ;;
        *)    echo "unknown arm $1" >&2; exit 2 ;;
    esac
}

arm_seed() {
    case "$1" in cpu1) echo 9001 ;; mps) echo 9002 ;; cpu6) echo 9003 ;; esac
}

for arm in $ARMS; do
    run="ch5_mps_bench_$arm"
    if [ -f "runs/$run/history.csv" ]; then
        echo "[$(date -u +%FT%TZ)] SKIP $arm (runs/$run/history.csv exists)"
        continue
    fi
    cfg="$(arm_config "$arm")"
    seed="$(arm_seed "$arm")"
    echo "[$(date -u +%FT%TZ)] START $arm  cfg=$cfg seed=$seed"
    t0=$(date +%s)
    "$PY" -m rl.train --config "$cfg" --seed "$seed" --run-name "$run" \
        > "logs/$run.log" 2>&1
    t1=$(date +%s)
    "$PY" scripts/extract_history.py "runs/$run" >/dev/null
    echo "[$(date -u +%FT%TZ)] DONE $arm ELAPSED=$((t1-t0))s"
done

echo "[$(date -u +%FT%TZ)] ALL ARMS DONE"
"$PY" scripts/ch5_mps_report.py $ARMS
