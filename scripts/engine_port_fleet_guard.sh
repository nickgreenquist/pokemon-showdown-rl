#!/usr/bin/env bash
# Read-only "did my build hurt the fleet?" probe for the engine-port session.
#
# The gen-4 fleet's wave log carries CPU-time deltas (liveness) but no rate, and
# CLAUDE.md is explicit that a rate is the only progress instrument that counts.
# Checkpoints land every 500k steps, so dStep/dWall between the two newest
# checkpoints of each lane IS the lane rate, at ~40 min resolution.
#
# Reads the MAIN tree by absolute path and writes nothing (session brief §1.3).
# Band: >= 180 steps/s per lane (docs/engine_port_session_brief.md §2).
set -u
MAIN=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
for lane in s200 s208 s216; do
  d="$MAIN/runs/gen4_wang50m_$lane"
  read -r s1 t1 s2 t2 <<<"$(
    ls "$d"/ckpt_*.pt 2>/dev/null | sort | tail -2 |
    while read -r f; do
      st=$(basename "$f" .pt); st=${st#ckpt_}
      printf '%s %s ' "$((10#$st))" "$(stat -f %m "$f")"
    done
  )"
  if [ -z "${t2:-}" ]; then echo "$lane: <2 checkpoints yet"; continue; fi
  ds=$((s2 - s1)); dt=$((t2 - t1)); age=$(( $(date +%s) - t2 ))
  awk -v l="$lane" -v ds="$ds" -v dt="$dt" -v age="$age" -v s2="$s2" \
    'BEGIN{r=(dt>0?ds/dt:0); printf "%s: %.1f steps/s over %ds  (at %d steps; newest ckpt %dm old)%s\n",
     l, r, dt, s2, age/60, (r<180 ? "  *** BELOW 180 ***" : "")}'
done
echo "box: $(vm_stat | awk '/Pages free/{f=$3}/Pages inactive/{i=$3}END{printf "%.1fGB free+inactive", (f+i)*16384/1073741824}'), load$(uptime | sed 's/.*load averages://')"
