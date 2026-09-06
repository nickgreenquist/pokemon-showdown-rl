#!/usr/bin/env bash
# THE GEN-4 CLONE'S TEACHER TAPES (BI-G4-5; configs/gen4_wang50m.yaml, CLONE):
# Foul Play @20 ms vs stock SimpleHeuristics on the LOCAL server, FP's OWN seat
# taped through the shared ../foul-play clone's tape hook (FP_TAPE_DIR), in
# CHUNKS so that a death or a server restart costs one chunk, never the corpus.
#   6 chunks x 1,200 battles = 7,200 (≈ 24 min/chunk at the measured
#   1.18 s/battle); each chunk is ONE FP process => one run_<pid>.jsonl under
#   FP_TAPE_DIR; our seat's tape + summary land under --out with the chunk tag.
#   scripts/tape_to_dataset.py --gen 4 --tapes data/gen4_fp_tapes merges every
#   run_*.jsonl it finds, so re-running a failed chunk (a new pid, a new file)
#   is the resume. Rate: watch the summary's s_per_battle against 1.18.
# Agent-side under CLAUDE.md rule 4: detached (nohup), resume-safe (chunk),
# rate-readable. Never training data: the clone is an anchor (purity).
#   nohup bash scripts/gen4_clone_tapes.sh > logs/gen4_clone_tapes.log 2>&1 < /dev/null &
set -u
cd "$(dirname "$0")/.."
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
# ABSOLUTE: Foul Play runs with cwd = ../foul-play, so a relative dir lands there.
export FP_TAPE_DIR="${FP_TAPE_DIR:-$(pwd)/data/gen4_fp_tapes}"
OUT="${OUT:-data/gen4_fp_clone}"
CHUNKS="${CHUNKS:-6}"
PER="${PER:-1200}"
mkdir -p "$FP_TAPE_DIR" "$OUT" logs
say() { echo "[$(date -u +%FT%TZ)] $*"; }
server_up() { pgrep -f "node pokemon-showdown start" >/dev/null 2>&1; }
say "CLONE TAPES START: $CHUNKS x $PER FP@20 vs heuristics -> $FP_TAPE_DIR (FP seat) + $OUT (our seat)"
for k in $(seq 1 "$CHUNKS"); do
  if [ -f "$OUT/clone_c$k.summary.json" ] && grep -q '"fp_exit_code": 0' "$OUT/clone_c$k.summary.json"; then
    say "chunk $k: already done, skipping"; continue
  fi
  tries=0
  until server_up; do say "chunk $k: no server, waiting"; sleep 30; done
  while :; do
    tries=$((tries + 1))
    say "chunk $k: attempt $tries"
    "$PY" scripts/gen4_fp_smoke.py --battles "$PER" --search-time-ms 20 --port 8000 \
      --seat heuristics --tag "clone_c$k" --out "$OUT" --timeout 3600
    rc=$?
    if [ -f "$OUT/clone_c$k.summary.json" ] && grep -q '"fp_exit_code": 0' "$OUT/clone_c$k.summary.json"; then
      say "chunk $k: done (rc $rc) $(grep -o '"s_per_battle": [0-9.]*' "$OUT/clone_c$k.summary.json")"; break
    fi
    say "chunk $k: FAILED (rc $rc)"; [ "$tries" -ge 3 ] && { say "chunk $k: giving up after 3"; break; }
    until server_up; do say "chunk $k: no server, waiting"; sleep 30; done
    sleep 30
  done
done
say "CLONE TAPES DONE: $(ls "$FP_TAPE_DIR"/run_*.jsonl 2>/dev/null | wc -l | tr -d ' ') FP tape files"
