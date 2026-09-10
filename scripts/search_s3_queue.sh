#!/usr/bin/env bash
# S3 queue — configs/eval/search_s3_100m.yaml (+ _offfp.yaml) — detached,
# resume-safe, rate-readable (CLAUDE.md rule 4). Re-execs from a FROZEN
# temp copy: never edit a bash script an instance is executing
# (byte-offset resume into garbage — docs/landmines.md).
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t search_s3_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
PREREG=configs/eval/search_s3_100m.yaml
FPPREREG=configs/eval/search_s3_100m_offfp.yaml
RES=results/search_s3_100m
FPRES=results/search_s3_100m_offfp
LOG=logs/search_s3
STAGGER="${STAGGER:-45}"
mkdir -p "$LOG" "$RES" "$FPRES"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

job() {  # one ch3_eval job, skipped if its final exists; staggered start
  if [ -f "$RES/$1.final.json" ]; then log "$1 SKIP (final exists)"; return; fi
  nohup "$PY" scripts/ch3_eval.py --prereg "$PREREG" --job "$1" >> "$LOG/$1.log" 2>&1 &
  log "$1 launched pid $!"
  sleep "$STAGGER"
}
wait_finals() {  # block until every named job has a final
  while :; do
    all=1
    for n in "$@"; do [ -f "$RES/$n.final.json" ] || all=0; done
    [ "$all" = 1 ] && return
    sleep 300
  done
}

log "PHASE 1: A0 x3 + S3L s112 + off-FP leg"
job a0_s104; job a0_s112; job a0_s120; job s3l_s112
if [ ! -f "$FPRES/f3m112.json" ]; then
  ( PREREG="$FPPREREG" ARM=F3M112 TAG=f3m112 OUT="$FPRES" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 \
    nohup bash scripts/ch3_r4_fp_runner.sh >> "$LOG/f3m112.driver.log" 2>&1 & )
  log "F3M112 (off-FP@20, search@M, n=1000) launched"
else
  log "F3M112 SKIP (json exists)"
fi
wait_finals a0_s104 a0_s112 a0_s120
log "PHASE 2: S3M x3"
job s3m_s104; job s3m_s112; job s3m_s120
wait_finals s3m_s104 s3m_s112 s3m_s120
log "PHASE 3: A1E x3 — HELD behind $REPO/.s3_e_go (F5 pool generalisation + R4-13 PASS first)"
while [ ! -f "$REPO/.s3_e_go" ]; do sleep 300; done
rm -f "$REPO/.s3_e_go"
job a1e_s104; job a1e_s112; job a1e_s120
wait_finals a1e_s104 a1e_s112 a1e_s120 s3l_s112
log "QUEUE DONE"
