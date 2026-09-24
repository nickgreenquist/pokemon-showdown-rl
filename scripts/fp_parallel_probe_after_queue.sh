#!/bin/bash
# The FP-parallel THROUGHPUT probe's launcher (maintainer's FP-parallel ROI task, Phase 1). It WAITS
# for the R6 reads queue's "QUEUE DONE" line -- gated on the LINE, never on a clock (r6-runner,
# 2026-09-24) -- then runs scripts/fp_parallel_probe.py --ks 1,2,4,6 --k8-if-headroom and the read.
# Slot agreed 2026-09-24 with r6-runner and the R7 runner (purity-line-ordering-system): the probe
# goes FIRST after QUEUE DONE; R7's order waits for it. So it never starts after START_DEADLINE and
# never starts a k that cannot end by END_BY: a late queue means SKIPPED_LATE and a re-slot.
# Detached, resume-safe (a k whose summary.json exists is skipped), holds the box awake itself, and
# re-execs from a frozen copy (never edit a bash script an instance is executing).
#
#   nohup bash scripts/fp_parallel_probe_after_queue.sh > /dev/null 2>&1 &
#
# STATUS: results/fp_parallel_probe/STATUS holds ONE word-led line (history in STATUS.log):
#   WAITING | RUNNING  -> the probe owns (or will own) the box after QUEUE DONE
#   DONE | FAILED | HELD_OUT | SKIPPED_LATE | SKIPPED_END_BY -> the box is RELEASED
set -u
if [ "${FROZEN:-0}" != "1" ]; then
  F=$(mktemp -t fpq_after); cat "$0" > "$F"; FROZEN=1 exec bash "$F" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-fpprobe
QLOG=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/logs/r6_reads/queue.log
START_DEADLINE="${START_DEADLINE:-2026-09-25T02:20:00Z}"
END_BY="${END_BY:-2026-09-25T03:00:00Z}"
OUT=$REPO/results/fp_parallel_probe
cd "$REPO" || exit 1
mkdir -p "$OUT"
caffeinate -i -s -w $$ &
st() { echo "[$(date -u +%FT%TZ)] $*" >> "$OUT/STATUS.log"; echo "$*" > "$OUT/STATUS"; }
epoch() { date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%s; }
DL=$(epoch "$START_DEADLINE")

st "WAITING for QUEUE DONE in $QLOG (pid $$; start deadline $START_DEADLINE, end by $END_BY)"
until grep -q "QUEUE DONE" "$QLOG" 2>/dev/null; do
  if [ "$(date +%s)" -gt "$DL" ]; then
    st "SKIPPED_LATE: no QUEUE DONE by $START_DEADLINE -- box released; re-slot with the R7 runner"
    exit 0
  fi
  sleep 60
done
if [ "$(date +%s)" -gt "$DL" ]; then
  st "SKIPPED_LATE: QUEUE DONE came after $START_DEADLINE -- box released; re-slot with the R7 runner"
  exit 0
fi
st "RUNNING (QUEUE DONE seen; driver pid follows in driver.log)"
/opt/anaconda3/bin/python scripts/fp_parallel_probe.py --ks 1,2,4,6 --k8-if-headroom \
  --hold-max-min 15 --end-by "$END_BY" >> "$OUT/driver.nohup" 2>&1
rc=$?
/opt/anaconda3/bin/python scripts/fp_parallel_probe_read.py >> "$OUT/read.nohup" 2>&1
case "$rc" in
  0) st "DONE: every k OK -- box released (read: $OUT/roi.json)" ;;
  4) st "HELD_OUT: the quiet-box gate held past 15 min -- box released; see driver.log" ;;
  5) st "SKIPPED_END_BY: a k would have ended after $END_BY -- box released; partial read in roi.json" ;;
  *) st "FAILED rc=$rc -- box released; see driver.log / driver.nohup" ;;
esac
