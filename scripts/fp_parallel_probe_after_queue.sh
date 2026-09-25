#!/bin/bash
# The FP-parallel THROUGHPUT probe's launcher (maintainer's FP-parallel ROI task, Phase 1). It WAITS
# for the R6 reads queue's "QUEUE DONE" line -- gated on the LINE, never on a clock (r6-runner,
# 2026-09-24) -- then runs scripts/fp_parallel_probe.py --ks 1,2,4,6 --k8-if-headroom and the read.
# Slot agreed 2026-09-24 with r6-runner and the R7 runner (purity-line-ordering-system): the probe
# goes FIRST after QUEUE DONE; R7's order waits for it. So it never starts after START_DEADLINE and
# the driver never starts a k that cannot end by END_BY: a late queue means SKIPPED_LATE, re-slot.
# Detached, resume-safe (a k whose summary.json exists is skipped), holds the box awake itself, and
# re-execs from a frozen copy (never edit a bash script an instance is executing).
#
# LAUNCH THROUGH BASH, NEVER A ZSH `&`: zsh's BG_NICE (on by default) runs every background job at
# nice +5, and the driver refuses to time anything niced (the maintainer's rule):
#   bash -c 'nohup bash scripts/fp_parallel_probe_after_queue.sh > /dev/null 2>&1 &'
#
# STATUS: results/fp_parallel_probe/STATUS holds ONE word-led line (history in STATUS.log):
#   WAITING | RUNNING  -> the probe owns (or will own) the box after QUEUE DONE
#   DONE | DONE_DISTURBED | FAILED | HELD_OUT | SKIPPED_LATE | SKIPPED_END_BY -> box RELEASED
# STOP: SIGTERM the DRIVER (`pkill -TERM -f scripts/fp_parallel_probe.py`); its finally kills
# every child group. Killing this bash alone leaves a running driver behind.
set -u
if [ "${FROZEN:-0}" != "1" ]; then
  F=$(mktemp -t fpq_after); cat "$0" > "$F"; FROZEN=1 exec bash "$F" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-fpprobe
QLOG=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/logs/r6_reads/queue.log
START_DEADLINE="${START_DEADLINE:-2026-09-25T02:20:00Z}"
END_BY="${END_BY:-2026-09-25T03:00:00Z}"
OUT=$REPO/results/fp_parallel_probe
LOCK=$OUT/.chain.lock
cd "$REPO" || exit 1
mkdir -p "$OUT"
st() { echo "[$(date -u +%FT%TZ)] $*" >> "$OUT/STATUS.log"; echo "$*" > "$OUT/STATUS"; }
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "[$(date -u +%FT%TZ)] REFUSED: $LOCK exists (another chain; remove it only if none runs)" >> "$OUT/STATUS.log"
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
NICE=$(ps -o nice= -p $$ | tr -d ' ')
if [ "$NICE" != "0" ]; then
  st "FAILED: this chain runs at nice $NICE (a zsh \`&\` launch?) -- relaunch through bash; box released"
  exit 1
fi
caffeinate -i -s -w $$ &
epoch() { date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%s 2>/dev/null; }
DL=$(epoch "$START_DEADLINE")
EB=$(epoch "$END_BY")
if [ -z "$DL" ] || [ -z "$EB" ]; then
  st "FAILED: unparseable START_DEADLINE '$START_DEADLINE' or END_BY '$END_BY' -- box released"
  exit 1
fi

st "WAITING for QUEUE DONE in $QLOG (pid $$, nice $NICE; start deadline $START_DEADLINE, end by $END_BY)"
until grep -qE '^\[[^]]*\] QUEUE DONE$' "$QLOG" 2>/dev/null; do
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
st "RUNNING (QUEUE DONE seen; driver starting, see driver.log)"
/opt/anaconda3/bin/python scripts/fp_parallel_probe.py --ks 1,2,4,6 --k8-if-headroom \
  --hold-max-min 15 --end-by "$END_BY" >> "$OUT/driver.nohup" 2>&1
rc=$?
/opt/anaconda3/bin/python scripts/fp_parallel_probe_read.py >> "$OUT/read.nohup" 2>&1
rrc=$?
case "$rc" in
  0) st "DONE: every k OK -- box released (read rc $rrc: $OUT/roi.json)" ;;
  3) st "DONE_DISTURBED: every k ran, at least one DISTURBED -- box released (read rc $rrc)" ;;
  4) st "HELD_OUT: the quiet-box gate held to its limit -- box released; see driver.log (read rc $rrc)" ;;
  5) st "SKIPPED_END_BY: a k would have ended after $END_BY -- box released; partial read rc $rrc" ;;
  6) st "FAILED: the driver refused to run niced -- box released" ;;
  *) st "FAILED rc=$rc -- box released; see driver.log / driver.nohup (read rc $rrc)" ;;
esac
