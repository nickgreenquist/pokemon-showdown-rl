#!/bin/bash
# R7 FLEET MONITOR (2026-09-25): scripts/r6_fleet_monitor.sh pointed at the R7 lanes -- one line per lane per poll
# to logs/r7_fleet/monitor.log (rate from the two newest 500k rungs, RSS, the watchdog's verdict, resumes), box lines,
# and an ALERT when a lane runs below ALERT_FRAC x W_REF after its first hour. THE MAINTAINER'S BAR (2026-09-25):
# "only stop it or alert me if wayyyyyyy slower than expected". W_REF 650 steps/s per lane is the pre-launch ESTIMATE
# for five two-core lanes (the LR smokes ran ~830 three-wide, the shakedown ~1,000 two-wide); ALERT_FRAC 0.4 puts the
# alarm at 260 steps/s, i.e. a ~4-day fleet instead of ~2. Re-anchor W_REF on the first hour's realized rate.
#   nohup bash scripts/r7_fleet_monitor.sh > logs/r7_fleet/monitor.nohup 2>&1 &
LANES_GLOB='runs/r7_fleet_*_s*' OUTDIR=logs/r7_fleet N_LANES="${N_LANES:-5}" \
W_REF="${W_REF:-650}" ALERT_FRAC="${ALERT_FRAC:-0.4}" REF_LABEL="${REF_LABEL:-the R7 five-wide estimate}" \
  exec bash "$(dirname "$0")/r6_fleet_monitor.sh" "$@"
