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

last=$(count); last_t=$(date +%s); nosock=0
echo "WATCHDOG: armed for $ARM, stall=${STALL}s, starting n=$last"
while true; do
  sleep 60
  pid=$(runner_pid)
  [ -z "$pid" ] && { last_t=$(date +%s); nosock=0; continue; }   # between attempts
  n=$(count); now=$(date +%s)
  [ "$n" -gt "$last" ] && { last=$n; last_t=$now; }

  # ---- FAST PATH: SOCKET ABSENCE, which needs no battle clock at all. ----
  # Measured 2026-08-28: a seat died 4.5 min into attempt 3 and BEFORE its
  # first battle, so the battle clock had nothing to measure from; it took the
  # 900 s stall rule 15 MINUTES to notice. The stall rule only exists to avoid
  # killing a live long game -- and a live long game HAS A SOCKET. So socket
  # absence is sufficient on its own and is checked far sooner.
  # `age` guards startup: torch import takes ~60-90 s with no socket yet, and
  # killing during that would be an infinite loop of our own making.
  age=$(ps -p "$pid" -o etimes= 2>/dev/null | tr -d ' '); age=${age:-0}
  if lsof -a -p "$pid" -iTCP -sTCP:ESTABLISHED -n -P 2>/dev/null | grep -q ESTABLISHED; then
    nosock=0
  elif [ "$age" -gt 240 ]; then
    nosock=$(( nosock + 1 ))
    if [ "$nosock" -ge 3 ]; then
      echo "WATCHDOG: NO ESTABLISHED SOCKET for 3 consecutive checks at n=$n (pid $pid, age ${age}s) — hung, poke-env does not reconnect. Killing so the supervisor relaunches." | tee -a "$LOG"
      kill -9 "$pid" 2>/dev/null
      nosock=0; last_t=$(date +%s)
      continue
    fi
  fi

  # ---- SLOW PATH: a stall WITH a socket. Informational only. ----
  idle=$(( now - last_t ))
  [ "$idle" -lt "$STALL" ] && continue
  # ** THE `-a` IS LOAD-BEARING. ** lsof combines its selection flags with a
  # logical OR by default, so `lsof -p PID -iTCP` means "this PID *OR* any
  # internet socket" and happily returns Chrome's connections. Measured
  # 2026-08-27: the first version of this line matched 29 ESTABLISHED sockets
  # for a runner that had NONE, so the watchdog reported a hung seat as a long
  # game and sat out a 35-minute stall -- the exact failure it exists to catch.
  # `-a` ANDs them: 29 matches -> 0.
  if lsof -a -p "$pid" -iTCP -sTCP:ESTABLISHED -n -P 2>/dev/null | grep -q ESTABLISHED; then
    echo "WATCHDOG: ${idle}s with no battle at n=$n, but the socket is ESTABLISHED — a long game or matchmaking, NOT a hang. Leaving it." | tee -a "$LOG"
    last_t=$now
  else
    echo "WATCHDOG: ${idle}s with no battle at n=$n AND NO ESTABLISHED SOCKET — hung (poke-env does not reconnect). Killing $pid so the supervisor relaunches." | tee -a "$LOG"
    kill -9 "$pid" 2>/dev/null
    last_t=$(date +%s)
  fi
done
