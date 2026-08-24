#!/bin/bash
# CH4 R1 wave driver — STRICTLY SERIAL (k=1 everywhere, so gate G7 never
# triggers and the concurrency confound is structurally absent; recorded in
# the readout). Order: V62-V65 (SH-side era pin / rho inputs) then the FP
# arms H1 H2 L62 L63 L64 L65 C1 C1b S1 E1. Arm-scoped VOIDs never stop the
# wave; each arm's rc is logged and the grader refuses voided arms.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
PY="${PY:-/opt/anaconda3/envs/pokemon-showdown-rl/bin/python}"
PREREG="configs/eval/ch4_r1_offsh_instrument.yaml"
OUT="results/ch4_r1_offsh"
WLOG="$OUT/wave.log"
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1
mkdir -p "$OUT"

wlog() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$WLOG"; }

wlog "WAVE START serial k=1, prereg sha $(shasum -a 256 $PREREG | cut -c1-12)"

for lane in 62 63 64 65; do
    wlog "V$lane start (vs SH, 3000, locked form)"
    "$PY" scripts/eval_checkpoint.py "runs/showdown_sp_recipe12m_s$lane/checkpoint.pt" \
        --episodes 3000 --out "$OUT/v$lane.json" > "$OUT/v$lane.stdout" 2>&1
    wlog "V$lane done rc=$?"
done

for arm in H1 H2 L62 L63 L64 L65 C1 C1b S1 E1; do
    tag="$(echo "$arm" | tr 'A-Z' 'a-z')"
    wlog "$arm start"
    PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=60 \
        bash scripts/ch3_r4_fp_runner.sh >> "$OUT/$tag.driver.log" 2>&1
    rc=$?
    if [ -f "$OUT/$tag.TOO_MANY_CRASHES" ]; then
        wlog "$arm VOID (TOO_MANY_CRASHES) rc=$rc — continuing"
    else
        wlog "$arm done rc=$rc"
    fi
done

wlog "WAVE COMPLETE"
