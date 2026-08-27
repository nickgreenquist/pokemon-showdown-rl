#!/bin/bash
# CH5 R1 watchdog. Written 2026-08-27 after a wave in which THREE arms died
# in 30 s each and a fourth stalled at 93%, and none of it was noticed for
# hours because "monitoring" meant looking when someone remembered to.
#
#   nohup bash scripts/ch5_watchdog.sh > /dev/null 2>&1 &
#
# Appends one line per poll to $OUT/watchdog.log and, on anything abnormal,
# a line beginning ALERT. It never kills anything -- the runner owns that.
# It exists so a failure is DISCOVERABLE within a minute instead of a night.
#
# The two failure shapes it is built for, both seen on 2026-08-27:
#   (a) arm starts, dies in <60 s, no JSON      -> B80/81/82, KeyError: 'dose'
#   (b) arm progresses then flatlines           -> CE7, stalled at 2811/3000
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO" || exit 1
OUT="results/ch5_r1_offsh"
LOG="$OUT/watchdog.log"
POLL="${POLL:-60}"

# 60 / s_per_battle, from wave_plan.expected_winners_per_min
ref_for() { case "$1" in b*) echo 22.4 ;; ce7) echo 34.9 ;; ce3) echo 38.5 ;; c0) echo 37.5 ;; *) echo 40.4 ;; esac; }

say() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

say "WATCHDOG START poll=${POLL}s"
prev_tag=""; prev_n=0; prev_t=0; started=0

while pgrep -f 'ch5_r1_wave.sh' >/dev/null; do
    tag="$(grep -E '^\[.*\] [A-Za-z0-9]+ start' "$OUT/wave.log" 2>/dev/null | tail -1 \
           | sed -E 's/^\[[^]]*\] ([A-Za-z0-9]+) start.*/\1/' | tr 'A-Z' 'a-z')"
    [ -n "$tag" ] || { sleep "$POLL"; continue; }
    now=$(date +%s)
    n="$(grep -c 'Winner:' "$OUT/$tag.fp.stdout" 2>/dev/null)"; [ -n "$n" ] || n=0

    if [ "$tag" != "$prev_tag" ]; then
        say "ARM $tag started"
        prev_tag="$tag"; prev_n=0; prev_t=$now; started=$now
    fi

    # (a) an arm that has been up a while with zero battles is the B-arm shape
    if [ "$n" -eq 0 ] && [ $((now - started)) -gt 180 ]; then
        say "ALERT $tag: 0 battles after $((now - started))s -- seat may have died at startup; check $OUT/$tag.seat.stdout"
    fi

    if [ $((now - prev_t)) -ge 120 ]; then
        rate=$(echo "scale=1; ($n - $prev_n) * 60 / ($now - $prev_t)" | bc 2>/dev/null || echo 0)
        ref=$(ref_for "$tag")
        pct=$(echo "scale=0; $rate * 100 / $ref" | bc 2>/dev/null || echo 0)
        say "$tag $n battles, ${rate}/min = ${pct}% of ${ref}/min reference"
        # (b) the CE7 shape: progress then flatline
        [ "${pct:-0}" -lt 20 ] && say "ALERT $tag: ${pct}% of reference -- STALLED, not slow (CLAUDE.md: a 10x discrepancy means stalled)"
        [ "${pct:-0}" -ge 20 ] && [ "${pct:-0}" -lt 50 ] && say "ALERT $tag: ${pct}% of reference -- investigate"
        prev_n=$n; prev_t=$now
    fi

    for s in NO_PROGRESS USERNAME_DEADLOCK TOO_MANY_CRASHES; do
        [ -f "$OUT/$tag.$s" ] && say "ALERT $tag: $s sentinel written -- arm will not be graded"
    done
    sleep "$POLL"
done
say "WATCHDOG STOP (no wave process)"
