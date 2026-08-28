#!/usr/bin/env bash
# Supervise a ladder run across websocket drops. Usage:
#   source .env && scripts/ladder_supervise.sh <arm> <target_battles>
#
# WHY THIS EXISTS, measured 2026-08-27 at n=10 of LADDER R3. The run died with
#   `websockets.exceptions.ConnectionClosedError: sent 1011 (internal error)
#   keepalive ping timeout; no close frame received`
# and **poke-env does not reconnect**: `ps_client.listen()` wraps its whole
# `async for message in websocket` loop in `except Exception as e:
# self.logger.exception(e)` and then RETURNS. There is no retry. The process
# stays ALIVE with no TCP connection at all (confirmed by lsof) and hangs
# forever on `player.ladder(1)`, sitting at 0.0% CPU -- which reads as "slow",
# exactly like the poke-env deadlock BI-6 closed, and is a different bug.
#
# Over a 16-19 h unattended rated run a single network blip therefore costs
# the whole night. CLAUDE.md rule 4 (ii) asks that a death cost ONE UNIT OF
# WORK, not the wave; `--battles` is a CUMULATIVE target and the JSONL is the
# truth on resume, so relaunching with the SAME target is already the correct
# recovery. This just does it automatically.
#
# IT IS NOT A RETRY LOOP IN THE SENSE CLAUDE.md WARNS ABOUT. The 3.6-hour
# zero-progress failure came from retrying something that could never succeed.
# Here every attempt is checked for PROGRESS against the JSONL: a relaunch
# that adds no battles counts toward a hard no-progress limit and backs off
# 10 minutes, so a genuinely stuck seat (a held username, a ban) stops the
# supervisor instead of grinding. Progress resets the counter.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARM="${1:?arm, e.g. R3S}"
TARGET="${2:?cumulative battle target, e.g. 200}"
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
JSONL="$REPO/results/ladder/$ARM.battles.jsonl"
LOG="$REPO/results/ladder/$ARM.run.log"
MAX_ATTEMPTS=50
MAX_NOPROGRESS=5          # x 600 s = ~50 min of patience for a held username
noprog=0

count() { local n; n=$(wc -l < "$JSONL" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  n0=$(count)
  if [ "$n0" -ge "$TARGET" ]; then
    echo "SUPERVISOR: target $TARGET reached (n=$n0) — done" | tee -a "$LOG"; break
  fi
  echo "SUPERVISOR: attempt $i from n=$n0 at $(date '+%F %T')" | tee -a "$LOG"
  # PYTHONUNBUFFERED is not cosmetic. Python block-buffers stdout when it is a
  # PIPE OR FILE rather than a TTY, so with a plain `>> log` the runner's
  # startup lines ("resuming: N battles", the seat line, the starting rating)
  # sit in the buffer until something flushes -- and the only flushing print is
  # the per-battle one. A seat that hangs BEFORE its first battle therefore
  # writes NOTHING, and is indistinguishable from a seat that is merely slow.
  # Measured 2026-08-27: a hung resume showed an empty log for 10 minutes and
  # the diagnosis had to come from `lsof` instead. LG-6 also requires READING
  # the startup lines, which is impossible if they are buffered.
  PYTHONUNBUFFERED=1 "$PY" "$REPO/scripts/ladder.py" \
        --prereg "$REPO/configs/eval/ladder_r3.yaml" \
        --arm "$ARM" --battles "$TARGET" --out-dir "$REPO/results/ladder" >> "$LOG" 2>&1
  rc=$?
  n1=$(count)
  echo "SUPERVISOR: attempt $i exited rc=$rc, n $n0 -> $n1" | tee -a "$LOG"

  # The pre-registered stop is the runner's to declare, never the supervisor's.
  if grep -q "STOPPING RULE MET" "$LOG"; then
    echo "SUPERVISOR: stopping rule met — not relaunching" | tee -a "$LOG"; break
  fi
  if [ "$n1" -ge "$TARGET" ]; then
    echo "SUPERVISOR: target $TARGET reached (n=$n1) — done" | tee -a "$LOG"; break
  fi
  if [ "$n1" -le "$n0" ]; then
    noprog=$((noprog + 1))
    echo "SUPERVISOR: NO PROGRESS ($noprog/$MAX_NOPROGRESS consecutive)" | tee -a "$LOG"
    if [ "$noprog" -ge "$MAX_NOPROGRESS" ]; then
      echo "SUPERVISOR: $MAX_NOPROGRESS consecutive no-progress attempts — ABORTING rather than retry-storming (CLAUDE.md)" | tee -a "$LOG"; break
    fi
    sleep 600
  else
    noprog=0
    sleep 30   # let the server drop the old session before re-using the name
  fi
done
echo "SUPERVISOR: exiting at n=$(count) at $(date '+%F %T')" | tee -a "$LOG"
