#!/usr/bin/env bash
# Kill a HUNG ladder runner so its supervisor can relaunch it. Usage:
#   scripts/ladder_watchdog.sh <arm> [stall_seconds]
#
# WHY THIS IS SEPARATE FROM ladder_supervise.sh. The supervisor only acts when
# its child EXITS. The failure measured on R3 at n=10 was the opposite: after
# the websocket died, the process stayed ALIVE with no TCP connection at all,
# sitting at 0.0% CPU forever. poke-env's `ps_client.listen()` catches the
# ConnectionClosedError, logs it and RETURNS -- there is no reconnect -- so
# `await player.ladder(1)` never completes and the supervisor waits on a child
# that will never exit. A supervisor alone therefore does NOT survive the
# failure it was written for.
#
# ** THE TEST IS THE SOCKET, NOT THE CLOCK, AND THAT IS THE WHOLE DESIGN. **
# "No new battle for N minutes" cannot distinguish a hang from the turn-1000
# auto-tie, which is a REAL game that legitimately runs for hours and which
# search arms hit far more often than greedy (4/5/8 per 1000 vs 1/0/0). Killing
# one of those would forfeit a live rated game against a human -- the single
# most damaging thing that can happen to this run. So a stall is only ever
# treated as a hang when the runner ALSO has no ESTABLISHED TCP connection:
#   socket up   -> matchmaking or a long game. LEAVE IT ALONE, however long.
#   socket gone -> nothing is in flight, nothing can be forfeited. Kill it.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARM="${1:?arm, e.g. R3S}"
STALL="${2:-900}"                 # 15 min; a normal battle is ~300 s
JSONL="$REPO/results/ladder/$ARM.battles.jsonl"
LOG="$REPO/results/ladder/$ARM.run.log"

count() { local n; n=$(wc -l < "$JSONL" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }
runner_pid() { pgrep -f "scripts/ladder.py .*--arm $ARM" | head -1; }

last=$(count); last_t=$(date +%s)
echo "WATCHDOG: armed for $ARM, stall=${STALL}s, starting n=$last"
while true; do
  sleep 60
  pid=$(runner_pid)
  [ -z "$pid" ] && { last_t=$(date +%s); continue; }   # between attempts
  n=$(count); now=$(date +%s)
  if [ "$n" -gt "$last" ]; then last=$n; last_t=$now; continue; fi
  idle=$(( now - last_t ))
  [ "$idle" -lt "$STALL" ] && continue
  if lsof -p "$pid" -iTCP -sTCP:ESTABLISHED -n -P 2>/dev/null | grep -q ESTABLISHED; then
    echo "WATCHDOG: ${idle}s with no battle at n=$n, but the socket is ESTABLISHED — a long game or matchmaking, NOT a hang. Leaving it." | tee -a "$LOG"
    last_t=$now
  else
    echo "WATCHDOG: ${idle}s with no battle at n=$n AND NO ESTABLISHED SOCKET — hung (poke-env does not reconnect). Killing $pid so the supervisor relaunches." | tee -a "$LOG"
    kill -9 "$pid" 2>/dev/null
    last_t=$(date +%s)
  fi
done
