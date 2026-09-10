#!/usr/bin/env bash
# The THIRD A/B variant: width 3, both arms, same box, same hour.
#
# WHY IT IS SEPARATE. The queue's two variants are width 1 and answer "how fast
# is ONE lane". The maintainer asked a different question — whether the engine
# lets the box run more games in parallel — and the only honest same-box answer
# is to run both collectors at the fleet width the project actually works in.
# Everything comparing a 3-wide engine fleet to a 3-wide Node fleet so far has
# leaned on a Node basis banked 2026-09-01, which is the cross-day subtraction
# this project already rejected once.
#
# It runs at the SHIPPED recipe (torch_threads 1, minibatches 120), not at the
# fastest configuration found tonight. The 1.51x crossed threads/minibatch
# result changes LEARNING and is not adopted, so measuring at it would be
# measuring a machine nobody runs.
set -uo pipefail
if [ "${FLEET_FROZEN:-0}" != "1" ]; then
  F=$(mktemp -t engine_ab_fleet); cat "$0" > "$F"
  FLEET_FROZEN=1 exec bash "$F" "$@"
fi
cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
EPY=/opt/anaconda3/envs/pkmn-engine-port/bin/python
LOG=logs/ab_fleet.log
say(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

say "QUEUED: waiting for the post-lane queue to finish both width-1 variants"
while pgrep -f "engine_queue" >/dev/null; do sleep 60; done
say "queue done — box is mine; starting the width-3 A/B"

"$EPY" scripts/engine_ab_speed.py --steps 1000000 --order ABBA --width 3 \
     --engine-k 256 --out results/engine_a1/ab_speed_w3_k256.json >> "$LOG" 2>&1
say "width-3 A/B rc=$? -> results/engine_a1/ab_speed_w3_k256.json"
say "AB FLEET DONE"
