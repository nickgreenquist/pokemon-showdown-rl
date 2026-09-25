#!/usr/bin/env bash
# MONSTER FLEET LAUNCHER — one command, preflighted, watchdogged.
#
#   bash scripts/monster_fleet.sh <config.yaml> <steps> <seed> [seed ...]
#
# e.g.  bash scripts/monster_fleet.sh configs/showdown_monster100m.yaml 200000000 104 112 120
#
# Written 2026-09-11 so that the command run before an 8-hour drive is one
# that has already worked once, and so that every rule which has cost this
# project hours is CHECKED rather than remembered.
#
# WHAT IT REFUSES TO LAUNCH ON, and why each one is here:
#
#  1. WRONG ENV. `collector: mode: engine` imports pkmn_gen1, which lives only
#     in pkmn-engine-port. The repo's default env does not have it.
#  2. DIRTY TREE. CLAUDE.md rule 3 -- one untracked .md stamps git_dirty on
#     every run in the fleet, and the fleet is the thing we will publish.
#  3. COLLIDING SEEDS. CLAUDE.md rule 2. Engine mode still builds poke-env
#     seats for the IN-LOOP EVAL (rl/train.py's make_eval_env), and poke-env
#     derives usernames from the globally-seeded `random`, so same-seed lanes
#     still collide and still die with a misleading TimeoutError.
#  4. simulator < 4 in showdown/config/config.js -- CLAUDE.md rule 5. The file
#     is gitignored, so a re-clone silently loses it.
#  5. NO NODE SERVER. Same reason as 3: the in-loop eval needs it.
#  6. MISSING TEAM BANK, or one below the config's own min_bank_pairs.
#  7. AN EXISTING RUN DIR. Never silently resume-or-clobber; say which.
#
# AND WHAT IT DOES AFTER LAUNCH, which matters as much:
#   * Lanes are STAGGERED. A lane can SIGSEGV at startup before writing any
#     log line, so they go up one at a time.
#   * Liveness is verified per lane by CPU-TIME DELTA, not by "the process
#     exists" -- the R2 stall shape passes every pgrep check forever.
#   * The watchdog is started LAST, on the lanes that actually came up, with
#     the same interpreter the fleet is running.
set -uo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)" || exit 1

CFG="${1:-}"; STEPS="${2:-}"; shift 2 2>/dev/null || true
SEEDS=("$@")
[ -n "$CFG" ] && [ -n "$STEPS" ] && [ "${#SEEDS[@]}" -ge 1 ] || {
  echo "usage: $0 <config.yaml> <total_steps> <seed> [seed ...]"; exit 2; }

PY="${PY:-/opt/anaconda3/envs/pkmn-engine-port/bin/python}"
STAGGER="${STAGGER:-90}"      # seconds between lane launches
VERIFY="${VERIFY:-20}"        # CPU-delta window per lane
TAG="${TAG:-$(basename "$CFG" .yaml)}"
LOG="logs/monster_fleet.log"; mkdir -p logs runs
# A FLEET OF PER-LANE CONFIGS (R7: each lane warm-starts from its own donor, so each has its own config) is launched
# by scripts/r7_fleet_launch.sh, one call here per lane, with two opt-in hooks; unset, this script is unchanged:
#   WATCHDOG=0   launch and verify only; the caller starts ONE watchdog over every lane (one ensure_node on the
#                shared server -- six watchdogs would race it -- and one RESUMES= line). The dirs that came up are
#                appended to $UP_FILE.
#   FLEET_WIDTH  the fleet's lane count, so the two-core width guard counts the FLEET, not this call's seeds.
WATCHDOG="${WATCHDOG:-1}"
FLEET_WIDTH="${FLEET_WIDTH:-0}"
WIDTH=$(( FLEET_WIDTH > ${#SEEDS[@]} ? FLEET_WIDTH : ${#SEEDS[@]} ))

# THE ENCODER FLAGS ARE PART OF THE OBSERVATION CONTRACT, and they are read at
# IMPORT time by rl/networks/entity_deepsets.py -- so a lane launched without
# them does not train a slightly different model, it dies on the spot with
# "entity trunk needs the id suffix". Found by dry-running this script rather
# than by reading it: the first smoke launched two lanes and both were dead
# inside a second. Exported here, and re-asserted in the child, because a
# fleet that fails at 23:00 on the night before an 8-hour drive is the exact
# failure this script exists to prevent.
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
# C6 (IDEAS 4.6 form (a); ported to the Rust encoder 2026-09-20) is exported ONLY
# for a config whose header carries the marker line `# ENCODER_C6: on`. The
# observation contract is PER CONFIG: a screen matched against c6-off history
# (configs/showdown_r6_batch12m.yaml) must not inherit the flag from a shell,
# and an R6 lane must not lose it to one. Both encoders read the same variable
# (Python at import, Rust via build_tables), the collector refuses a pairing
# mismatch, and meta.yaml stamps encoder.c6 -- which the watchdog reads back on
# every resume (scripts/train_watchdog.sh).
if grep -qE '^# ENCODER_C6: on' "$CFG"; then
  export POKEMON_RL_ENCODER_C6=1
else
  unset POKEMON_RL_ENCODER_C6
fi
say(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
die(){ say "REFUSING TO LAUNCH: $*"; exit 2; }

say "=== PREFLIGHT: $CFG, ${STEPS} steps, seeds ${SEEDS[*]} ==="
say "encoder: V2=$POKEMON_RL_ENCODER_V2 IDS=$POKEMON_RL_ENCODER_IDS C6=${POKEMON_RL_ENCODER_C6:-0} (marker '# ENCODER_C6: on' in the config header)"
"$PY" -c 'import os,sys
v,i = os.environ.get("POKEMON_RL_ENCODER_V2"), os.environ.get("POKEMON_RL_ENCODER_IDS")
sys.exit(0 if v=="1" and i=="1" else 1)' \
  || die "encoder flags not visible to $PY -- the entity trunk reads them at import"

[ -f "$CFG" ] || die "no such config: $CFG"

# R7 B4 (plan amendment box 3, item 1): a TWO-CORE LANE (collector.process: true)
# must launch at NORMAL QoS -- `taskpolicy -b` schedules to the four efficiency
# cores at ~6.8x per decision, and under a wall-matched fleet a lane there trains
# FEWER steps, a confound -- and at most FIVE lanes ride the ten performance
# cores (ruling 7; six only under a pre-registered disclosure, opt-in here).
# The collector refuses a background QoS at construction too; this is the
# launch-time face of the same rule, before any lane spends a minute.
if "$PY" - "$CFG" <<'PYEOF'
import yaml, sys
c = yaml.safe_load(open(sys.argv[1]))
sys.exit(0 if bool(((c.get("collector") or {}).get("process", False))) else 1)
PYEOF
then
  "$PY" -c 'import os, sys; sys.exit(1 if os.getpriority(4, 0) != 0 else 0)' \
    || die "collector.process lanes need NORMAL QoS: this shell is background (taskpolicy -b / nice); relaunch from a plain shell"
  if [ "$WIDTH" -gt 5 ] && [ "${ALLOW_SIX_WIDE_DISCLOSED:-0}" != "1" ]; then
    die "collector.process: $WIDTH two-core lanes > 5 on ten performance cores (ruling 7); ALLOW_SIX_WIDE_DISCLOSED=1 only with the pre-registered degraded-lane disclosure"
  fi
  say "two-core lanes: normal QoS asserted, $WIDTH lanes x 2 cores (this call: ${#SEEDS[@]})"
fi

# THE ANNEAL TRAP, checked. `rl.train` has NO --total-steps flag: the horizon
# comes from the config and ONLY from the config, so a STEPS argument that
# disagreed with it would silently run the config's number. Worse, the config
# names the real trap itself -- "lr_anneal_steps: 100000000 # == total_steps.
# THE ANNEAL TRAP" -- because a 200M run against a 100M anneal drives the
# learning rate to zero at the halfway mark and trains the entire second half
# at lr~0. That failure is invisible until the readout. Both are checked, and
# the fix is printed rather than described.
read -r CFG_STEPS CFG_ANNEAL <<<"$("$PY" - "$CFG" <<'PYEOF'
import yaml, sys
c = yaml.safe_load(open(sys.argv[1]))
print(int(c.get("total_steps", -1)),
      int((c.get("agent") or {}).get("lr_anneal_steps", -1)))
PYEOF
)"
# ALLOW_ANNEAL_OVER_HORIZON=1 (2026-09-19): a MECHANISM SCREEN may run the first
# N steps of a longer schedule so its LR at every step matches the fleet it is
# read against (configs/showdown_r6_batch12m.yaml). anneal > horizon is the
# OPPOSITE direction from the trap this check guards (anneal < horizon trains
# the tail at lr~0), and rl/train.py permits it; but a FLEET must never get it
# by accident (RWL-4: anneal = horizon, no floor), so it is opt-in and loud.
if [ "${ALLOW_ANNEAL_OVER_HORIZON:-0}" = "1" ] && [ "$CFG_STEPS" = "$STEPS" ] && [ "$CFG_ANNEAL" -gt "$STEPS" ]; then
  say "ANNEAL OVER HORIZON, opted in: total_steps = $STEPS, lr_anneal_steps = $CFG_ANNEAL (a matched-schedule screen; never a fleet)"
elif [ "$CFG_STEPS" != "$STEPS" ] || [ "$CFG_ANNEAL" != "$STEPS" ]; then
  say "  config total_steps     = $CFG_STEPS"
  say "  config lr_anneal_steps = $CFG_ANNEAL"
  say "  requested              = $STEPS"
  die "config horizon != requested. Derive a matching config first:
    $PY scripts/derive_monster_config.py $CFG $STEPS
  (both total_steps AND agent.lr_anneal_steps must equal $STEPS -- a
   mismatched anneal silently trains the tail of the run at lr~0)"
fi
say "horizon: total_steps = lr_anneal_steps = $STEPS"

MODE="$("$PY" -c "import yaml,sys;print((yaml.safe_load(open(sys.argv[1])).get('collector') or {}).get('mode',''))" "$CFG")"
say "collector mode: ${MODE:-<none>}"
if [ "$MODE" = "engine" ]; then
  "$PY" -c 'import pkmn_gen1' 2>/dev/null \
    || die "mode=engine but $PY cannot import pkmn_gen1 (use the pkmn-engine-port env)"
  if [ "${POKEMON_RL_ENCODER_C6:-0}" = "1" ]; then
    "$PY" -c 'import pkmn_gen1,sys; sys.exit(0 if getattr(pkmn_gen1,"ENCODER_C6",False) else 1)' \
      || die "config asks for C6 but the installed pkmn_gen1 does not implement it (stale editable install: pip install -e engine/pkmn_gen1 in the port env)"
    say "C6: on, and the extension implements it"
  fi
  BANK="$("$PY" -c "import yaml,sys;print((yaml.safe_load(open(sys.argv[1])).get('collector') or {}).get('team_bank',''))" "$CFG")"
  [ -n "$BANK" ] && [ -f "$BANK" ] || die "team_bank missing: ${BANK:-<unset>}"
  say "team bank: $BANK ($(du -h "$BANK" | cut -f1))"
fi

# rule 3 -- and it must be CLEAN, not merely committed
[ -z "$(git status --porcelain)" ] || {
  git status --short | head -10
  die "dirty tree (CLAUDE.md rule 3): one untracked file stamps git_dirty on every lane"
}
say "tree clean at $(git rev-parse --short HEAD)"

# rule 2
if [ "$(printf '%s\n' "${SEEDS[@]}" | sort -u | wc -l | tr -d ' ')" -ne "${#SEEDS[@]}" ]; then
  die "duplicate seeds ${SEEDS[*]} (CLAUDE.md rule 2): lanes collide on Showdown usernames"
fi

# rule 5
SIM="$(grep -E '^\s*simulator:' showdown/config/config.js 2>/dev/null | grep -oE '[0-9]+' | head -1)"
[ "${SIM:-0}" -ge 4 ] || die "showdown/config/config.js simulator=${SIM:-unset}, need >=4 (CLAUDE.md rule 5)"
say "simulator: $SIM"

pgrep -f "node pokemon-showdown" >/dev/null \
  || die "no Showdown server -- engine mode still builds poke-env seats for the in-loop eval"
say "node server up"

for s in "${SEEDS[@]}"; do
  d="runs/${TAG}_s${s}"
  [ -e "$d" ] && die "$d already exists -- move it or pick another TAG; this script never resumes-or-clobbers"
done

pgrep -f "bin/python -m rl.train" >/dev/null && say "WARNING: rl.train already running; the fleet will contend"

# THE BOX ITSELF, checked. Two things kill an unattended fleet that no lane
# check can see (2026-09-11 review): the laptop SLEEPING (this MacBook's AC
# profile is `sleep 1`, held off only by whatever caffeinate someone left in a
# terminal tab), and macOS REBOOTING ITSELF to install an update on a box
# that is idle at the keyboard for three days. The first is handled below --
# the launcher holds its own assertion for the watchdog's lifetime. The second
# needs a human and a password, so it is said loudly here and again at DONE.
SLEEP_MIN="$(pmset -g 2>/dev/null | awk '$1=="sleep"{print $2}')"
[ "${SLEEP_MIN:-0}" != "0" ] && say "NOTE: pmset AC sleep=${SLEEP_MIN} min -- a caffeinate assertion is held for the watchdog's lifetime; belt and braces: sudo pmset -c sleep 0 disksleep 0. Keep the LID OPEN (clamshell sleeps without an external display)."
if [ "$(defaults read /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates 2>/dev/null)" = "1" ]; then
  say "WARNING: macOS 'Install macOS updates' is ON -- an idle box can reboot itself mid-fleet and nothing relaunches the lanes. Turn it off before leaving: System Settings > General > Software Update > Automatic Updates."
fi

say "=== LAUNCH (stagger ${STAGGER}s) ==="
UP=(); DOWN=()
for s in "${SEEDS[@]}"; do
  d="runs/${TAG}_s${s}"
  say "launching seed $s -> $d"
  nohup "$PY" -c 'import os,sys; os.setsid(); os.execv(sys.argv[1], sys.argv[1:])' \
    "$PY" -m rl.train --config "$CFG" --seed "$s" --run-name "$(basename "$d")" \
    > "${d}.nohup.log" 2>&1 &
  sleep "$STAGGER"

  pid="$(pgrep -f "bin/python -m rl.train.*--run-name $(basename "$d")" | head -1)"
  if [ -z "$pid" ]; then
    say "  ALERT seed $s: NO PROCESS after ${STAGGER}s -- see ${d}.nohup.log"
    tail -5 "${d}.nohup.log" 2>/dev/null | sed 's/^/    /'
    DOWN+=("$s"); continue
  fi
  # PROGRESS, not existence: a lane can be alive at zero CPU.
  c0="$(ps -o time= -p "$pid" | tr -d ' ')"; sleep "$VERIFY"
  c1="$(ps -o time= -p "$pid" | tr -d ' ')"
  if [ "$c0" = "$c1" ]; then
    say "  ALERT seed $s: pid $pid alive but ZERO CPU in ${VERIFY}s -- not counting it up"
    DOWN+=("$s"); continue
  fi
  say "  seed $s up: pid $pid, cpu $c0 -> $c1"
  UP+=("$d")
done

say "=== ${#UP[@]}/${#SEEDS[@]} lanes up ==="
[ "${#DOWN[@]}" -gt 0 ] && say "ALERT lanes that did not come up: ${DOWN[*]}"
[ "${#UP[@]}" -eq 0 ] && die "no lane came up"
if [ "$WATCHDOG" = "0" ]; then
  [ -n "${UP_FILE:-}" ] && printf '%s\n' "${UP[@]}" >> "$UP_FILE"
  say "WATCHDOG=0: no watchdog started here -- the caller starts ONE over the fleet (${UP[*]})"
  exit 0
fi

say "starting watchdog on the lanes that came up"
PY="$PY" nohup bash scripts/train_watchdog.sh "${UP[@]}" > /dev/null 2>&1 &
WD=$!
say "watchdog pid $WD -- log runs/train_watchdog.log (it also keeps the Showdown server alive)"
# Sleep assertion bound to the watchdog: -i (idle sleep), -s (while on AC),
# -w (release when the watchdog exits). Independent of any terminal tab.
nohup caffeinate -i -s -w "$WD" > /dev/null 2>&1 &
say "caffeinate pid $! holding the box awake until watchdog $WD exits; verify with: pmset -g assertions | grep caffeinate"
say "DONE. Monitor with:  tail -f runs/train_watchdog.log"
say "BEFORE YOU LEAVE: lid open; 'Install macOS updates' OFF; optionally: sudo pmset -c sleep 0 disksleep 0"
