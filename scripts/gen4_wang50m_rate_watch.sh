#!/usr/bin/env bash
# gen4_wang50m RATE WATCH (the babysitter's instrument; 2026-09-06). Streams
# the wave log's death/stall/complete lines as they land and, every
# RATE_EVERY seconds (default 3600), a per-lane steps/s from rung cadence
# (ckpt_*.pt every 500k seat-1 steps) with the D-B alerts on the band
# RE-BASED from the fleet's own first conforming windows (expected 212;
# RECORD < 180; STOP-AND-INVESTIGATE < 106 sustained). A rung interval that
# contains a resume's downtime reads LOW by construction — confirm with
#   python scripts/merge_history.py runs/<lane> && python scripts/gen4_wang50m_gates.py runs/<lane> --history runs/<lane>/history_merged.csv
# (the gate reader excludes resume-gap windows). Exits on FLEET DONE or a
# sequencer failure line written after its own start. Run it as a session
# Monitor (each stdout line is an event) or detached with its stdout to a file.
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
SEQ=logs/gen4_launch_seq.log; WAVE=logs/gen4_wang50m_wave.log
START_MARK="[$(date -u +%FT%TZ)]"
seen_seq=$(grep -c "" "$SEQ" 2>/dev/null || echo 0); seen_wave=$(grep -cE "PREFLIGHT|launched|ALERT|STALLED|DEAD|died|COMPLETE|FLEET DONE|already complete" "$WAVE" 2>/dev/null || echo 0); last_rate=0; tick=0
declare -A slow_count
while :; do
  n=$(grep -c "" "$SEQ" 2>/dev/null || echo 0)
  if [ "${n:-0}" -gt "$seen_seq" ]; then tail -n $((n - seen_seq)) "$SEQ"; seen_seq=$n; fi
  awk -v m="$START_MARK" '$1 > m' "$SEQ" 2>/dev/null | grep -qE "NOT LAUNCHING|SERVER FAILED|SEQ2 ABORT|STALLED again" && { echo "SEQUENCER STOPPED — fleet not launched"; exit 1; }
  if [ -f "$WAVE" ]; then
    n=$(grep -cE "PREFLIGHT|launched|ALERT|STALLED|DEAD|died|COMPLETE|FLEET DONE|already complete" "$WAVE")
    if [ "${n:-0}" -gt "$seen_wave" ]; then grep -E "PREFLIGHT|launched|ALERT|STALLED|DEAD|died|COMPLETE|FLEET DONE|already complete" "$WAVE" | tail -n $((n - seen_wave)); seen_wave=$n; fi
    grep -q "FLEET DONE" "$WAVE" && { echo "FLEET DONE — run the frozen post-fleet schedule"; exit 0; }
    now=$(date +%s)
    if [ $((now - last_rate)) -ge ${RATE_EVERY:-3600} ]; then
      last_rate=$now; tick=$((tick+1))
      for s in 200 208 216; do
        d="runs/gen4_wang50m_s$s"; [ -d "$d" ] || continue
        rungs=$(ls "$d"/ckpt_*.pt 2>/dev/null | sort)
        k=$(echo "$rungs" | grep -c "ckpt_")
        launched=$(grep "lane s$s: launched" "$WAVE" | tail -n 1 | sed -E 's/^\[([^]]+)\].*/\1/')
        if [ "$k" -ge 2 ]; then
          a=$(echo "$rungs" | tail -n 2 | head -n 1); b=$(echo "$rungs" | tail -n 1)
          sa=$(basename "$a" .pt | sed 's/ckpt_0*//'); sb=$(basename "$b" .pt | sed 's/ckpt_0*//')
          ta=$(stat -f %m "$a"); tb=$(stat -f %m "$b")
          rate=$(( (sb - sa) / ( (tb - ta) > 0 ? (tb - ta) : 1 ) ))
          age=$(( (now - tb) / 60 ))
          echo "RATE lane s$s: ${rate} steps/s over the last rung ($(basename "$b"), ${age} min ago; band re-based 180-244, expected 212)"
          if [ "$rate" -lt 106 ]; then slow_count[$s]=$(( ${slow_count[$s]:-0} + 1 )); echo "ALERT VERY SLOW lane s$s: ${rate} steps/s < 106 (D-B STOP-AND-INVESTIGATE band, re-based; ${slow_count[$s]} consecutive)"
          elif [ "$rate" -lt 180 ]; then echo "ALERT SLOW lane s$s: ${rate} steps/s < 180 (D-B RECORD band, re-based)"; slow_count[$s]=0
          else slow_count[$s]=0; fi
          [ "$age" -gt 60 ] && echo "ALERT NO NEW RUNG lane s$s: last rung ${age} min ago (expected every ~41 min)"
        elif [ "$k" -eq 1 ]; then
          b=$(echo "$rungs" | tail -n 1); tb=$(stat -f %m "$b"); age=$(( (now - tb) / 60 ))
          echo "RATE lane s$s: first rung $(basename "$b") landed ${age} min ago (rate readable from the second rung)"
          [ "$age" -gt 60 ] && echo "ALERT NO SECOND RUNG lane s$s: ${age} min since the first (expected ~41 min)"
        elif [ -n "$launched" ]; then
          t0=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$launched" +%s 2>/dev/null || echo "$now")
          mins=$(( (now - t0) / 60 ))
          echo "RATE lane s$s: no rung yet, launched ${mins} min ago (first rung expected at ~41 min)"
          [ "$mins" -gt 60 ] && echo "ALERT NO FIRST RUNG lane s$s: ${mins} min since launch — check the lane log"
        fi
      done
      [ $((tick % 2)) -eq 0 ] && tail -n 1 "$WAVE" | grep "box:" 
    fi
  fi
  sleep 60
done
