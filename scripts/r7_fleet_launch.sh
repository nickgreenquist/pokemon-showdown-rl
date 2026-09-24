#!/usr/bin/env bash
# R7 FLEET LAUNCHER -- a fleet of PER-LANE configs (each lane warm-starts from its own donor, so each lane has its own
# config; scripts/derive_r7_fleet.py writes them and the manifest), launched through scripts/monster_fleet.sh one lane
# per call with every one of its preflight refusals intact, then watched by ONE watchdog.
#
#   ALLOW_SIX_WIDE_DISCLOSED=1 bash scripts/r7_fleet_launch.sh configs/r7_fleet_lanes.txt
#   DRY=1 bash scripts/r7_fleet_launch.sh configs/r7_fleet_lanes.txt     # checks and prints the plan, launches nothing
#
# Why one watchdog (the fleet pre-reg's wiring review, 2026-09-24): monster_fleet.sh starts a watchdog per call, and
# every watchdog runs ensure_node on the SHARED Showdown server -- six of them can race, one killing a server another
# just restarted -- and the RESUMES= / NODE_RESTARTS= disclosure would be split across six EXIT lines. Each call here
# runs with WATCHDOG=0 (launch + CPU-delta verify only, the dirs that came up appended to UP_FILE) and FLEET_WIDTH=N
# (so the two-core width guard counts the fleet, not the call: six lanes need ALLOW_SIX_WIDE_DISCLOSED=1).
#
# Manifest: one "<config> <seed>" per line, '#' comments; the order is the launch order (the stagger is per call).
# Refuses before launching anything on: a missing config, duplicate seeds, an existing run dir, a width above five
# without the disclosure flag, a config whose horizon is not its anneal (monster_fleet.sh re-checks per lane).
# Re-execs from a FROZEN copy (never edit a bash script an instance is executing).
set -uo pipefail
if [ "${LAUNCH_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t r7_fleet_launch)
  cat "$0" > "$FROZEN"
  LAUNCH_FROZEN=1 REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)" exec bash "$FROZEN" "$@"
fi
cd "$REPO_DIR" || exit 1
MANIFEST="${1:-}"
[ -n "$MANIFEST" ] && [ -f "$MANIFEST" ] || { echo "usage: $0 <lane manifest>"; exit 2; }
PY="${PY:-/opt/anaconda3/envs/pkmn-engine-port/bin/python}"
LOG="logs/monster_fleet.log"; mkdir -p logs runs
say(){ echo "[$(date -u +%FT%TZ)] r7_fleet_launch: $*" | tee -a "$LOG"; }
die(){ say "REFUSING TO LAUNCH: $*"; exit 2; }

CFGS=(); SEEDS=()
while read -r cfg seed rest; do
  case "$cfg" in ''|'#'*) continue ;; esac
  [ -n "$seed" ] && [ -z "$rest" ] || die "manifest line '$cfg $seed $rest': want '<config> <seed>'"
  [ -f "$cfg" ] || die "no such config: $cfg"
  CFGS+=("$cfg"); SEEDS+=("$seed")
done < "$MANIFEST"
N=${#CFGS[@]}
[ "$N" -ge 1 ] || die "empty manifest: $MANIFEST"
say "=== FLEET: $N lanes from $MANIFEST at $(git rev-parse --short HEAD) ==="

[ "$(printf '%s\n' "${SEEDS[@]}" | sort -u | wc -l | tr -d ' ')" -eq "$N" ] \
  || die "duplicate seeds ${SEEDS[*]} (CLAUDE.md rule 2): lanes collide on Showdown usernames"
if [ "$N" -gt 5 ] && [ "${ALLOW_SIX_WIDE_DISCLOSED:-0}" != "1" ]; then
  die "$N two-core lanes > 5 (ruling 7); ALLOW_SIX_WIDE_DISCLOSED=1 only with the pre-registered disclosure"
fi
STEPS=()
for i in $(seq 0 $((N - 1))); do
  cfg="${CFGS[$i]}"; seed="${SEEDS[$i]}"
  d="runs/$(basename "$cfg" .yaml)_s${seed}"
  [ -e "$d" ] && die "$d already exists -- never resume-or-clobber"
  read -r total anneal cseed <<<"$("$PY" - "$cfg" <<'PYEOF'
import sys, yaml
c = yaml.safe_load(open(sys.argv[1]))
print(int(c.get("total_steps", -1)), int((c.get("agent") or {}).get("lr_anneal_steps", -1)), int(c.get("seed", -1)))
PYEOF
)"
  [ "$total" = "$anneal" ] || die "$cfg: total_steps $total != lr_anneal_steps $anneal (a fleet never runs an anneal over its horizon)"
  [ "$cseed" = "$seed" ] || die "$cfg: the manifest's seed $seed != the config's seed $cseed"
  STEPS+=("$total")
  say "  lane $((i + 1)): $cfg seed $seed -> $d ($total steps)"
done

if [ "${DRY:-0}" = "1" ]; then say "DRY: checks passed, nothing launched"; exit 0; fi
# zsh's BG_NICE runs a backgrounded `cmd &` at nice +5; the lanes would inherit it. Run this in the FOREGROUND.
[ "$(ps -o nice= -p $$ | tr -d ' ')" = "0" ] || die "this launcher is niced ($(ps -o nice= -p $$ | tr -d ' ')) -- run it in the foreground, never with '&' from zsh"

UP_FILE="$(mktemp -t r7_fleet_up)"
for i in $(seq 0 $((N - 1))); do
  say "--- lane $((i + 1))/$N: bash scripts/monster_fleet.sh ${CFGS[$i]} ${STEPS[$i]} ${SEEDS[$i]} (WATCHDOG=0 FLEET_WIDTH=$N)"
  if ! WATCHDOG=0 FLEET_WIDTH="$N" UP_FILE="$UP_FILE" PY="$PY" \
       bash scripts/monster_fleet.sh "${CFGS[$i]}" "${STEPS[$i]}" "${SEEDS[$i]}"; then
    say "ALERT lane $((i + 1)) (${CFGS[$i]} seed ${SEEDS[$i]}): the launcher refused or no lane came up -- see $LOG"
    # STOP launching: a preflight refusal is fleet-wide (tree, server, env) and a startup crash wants a human. The
    # lanes already up still get the watchdog below; the pre-reg's LANE LOSS cell then governs the read.
    [ -s "$UP_FILE" ] || die "the first lane did not come up; nothing launched"
    say "STOPPED after lane $((i + 1)): lanes $((i + 2))..$N NOT launched"
    break
  fi
done
UP=(); while read -r d; do [ -n "$d" ] && UP+=("$d"); done < "$UP_FILE"
say "=== ${#UP[@]}/$N lanes up: ${UP[*]} ==="
[ "${#UP[@]}" -lt "$N" ] && say "ALERT: $(( N - ${#UP[@]} )) lane(s) did not come up -- the pre-reg's LANE LOSS cell; diagnose before counting"
[ "${#UP[@]}" -eq 0 ] && die "no lane came up"

PY="$PY" nohup bash scripts/train_watchdog.sh "${UP[@]}" > /dev/null 2>&1 &
WD=$!
say "ONE watchdog pid $WD over ${#UP[@]} lanes -- log runs/train_watchdog.log (it also keeps the Showdown server alive)"
nohup caffeinate -i -s -w "$WD" > /dev/null 2>&1 &
say "caffeinate pid $! holding the box awake until watchdog $WD exits; verify with: pmset -g assertions | grep caffeinate"
say "DONE. Monitor with:  tail -f runs/train_watchdog.log"
