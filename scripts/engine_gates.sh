#!/usr/bin/env bash
# engine_gates — THE FROZEN GATE ORDER for the pkmn/engine collector port
# (docs/PKMN_ENGINE_RUST_PLAN.md §9, configs/engine_a1.yaml). Agent-side,
# detached, RESUME-SAFE (every unit skips when its output exists),
# RATE-READABLE (ELAPSED per unit). NOTHING here runs while anything else owns
# the box or the server — step 0 refuses.
#
# CLAUDE.md rule 4 permits an agent-side run of any length only if it is
# (i) DETACHED from the agent's process tree, (ii) RESUME-SAFE so a death costs
# one unit of work, and (iii) progress readable as a RATE against a comparable
# completed arm. This script is what makes all three true for D-1 -> T-1 -> A-1.
# The A-1 lanes are TRAINING jobs; ownership of those is the maintainer's call
# under the same rule, which is why step 4 refuses without an explicit launch
# authorization in the sidecar.
#
#   0  preflight: exclusive box, clean tree, env vars, resources, ratification
#   1  team bank (>= 1,000,000 pairs) — RW-6 picks the size
#   2  D-1 dynamics smoke, BOTH matchups. HARD STOP on failure: nothing
#      downstream of a failed gate runs, and A-1 on a failed D-1 measures
#      nothing (it becomes a joint test of collector and dynamics).
#   3  T-1 (a) engine-only battles/s, (b) COLLECTION-ONLY steps/s vs K.
#      Server DOWN for these: they are idle-box measurements.
#   4  A-1: three engine lanes, seeds 66/75/83, killed at the 12M crossing
#      rung. Server UP (the in-loop evals go through poke-env).
#   5  T-1 (c) full-loop and (d) FLEET WIDTH, measured ON the A-1 fleet —
#      the only place k lanes of the production recipe exist at once.
#   6  A-1 evals: the 12M rung, n=3000/seed, locked protocol.
#   7  grade -> results/engine_a1/primary.json
#
# The RESULTS addendum / README row / STATUS / SESSION_LOGS are authored BY
# HAND from these files, in ONE commit. This script never writes them.
#
# Launch: nohup bash scripts/engine_gates.sh > /dev/null 2>&1 < /dev/null &
# DRY=1 prints every command instead of running it.
set -u
cd "$(dirname "$0")/.."
PY=/opt/anaconda3/envs/pkmn-engine-port/bin/python
LOG=logs/engine_gates.log
OUT=results/engine_a1
T1OUT=results/t1
D1OUT=results/d1
SEEDS="${SEEDS:-66 75 83}"
CONFIG=configs/engine_a1.yaml
PREREG=configs/engine_a1.prereg.yaml
RUNG=12000000
BANK="${BANK:-data/engine/teams_a1_5000000.bin}"
BANK_PAIRS="${BANK_PAIRS:-5000000}"   # RW-6 ratified; ~2.75 h, 480 MB,
                                     # and the generator streams now (review 2, M4)
EVAL_N="${EVAL_N:-12000}"          # review 2, M5: precision here is bought by
                                   # battles, not seeds — ~71% of the
                                   # regime-matched sigma is eval-replicate noise
BANKED_RUNS="${BANKED_RUNS:-/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/runs}"
DRY="${DRY:-0}"
# OBS_DIM 828 comes from these two and nothing else (CLAUDE.md's OBS_DIM
# landmine); the banked arm A-1 compares against was trained with both set.
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

mkdir -p "$OUT" "$T1OUT" "$D1OUT" logs data/engine
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
# The server lives in the MAIN tree (showdown/ is gitignored, so this worktree
# has none). The runner OWNS its lifecycle: D-1 and the evals need it up, and
# T-1 (a)/(b) are idle-box measurements that need it down. A chain that asked an
# operator to start and stop it between steps would not be detached, which is
# the whole point of rule 4's (i).
MAIN="${MAIN:-/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl}"
server_pid() { pgrep -f "node pokemon-showdown start" | head -n 1; }
stop_server() {
  local pid; pid=$(server_pid)
  [ -z "$pid" ] && return 0
  say "stopping Showdown server (pid $pid)"
  [ "$DRY" = 1 ] && return 0
  kill "$pid" 2>/dev/null; sleep 3; kill -9 "$pid" 2>/dev/null
  local i=0
  while [ -n "$(server_pid)" ]; do sleep 1; i=$((i+1)); [ $i -gt 60 ] && { say "SERVER FAILED: old server would not die"; return 1; }; done
  return 0
}
start_server() {
  [ -n "$(server_pid)" ] && { say "server already up (pid $(server_pid))"; return 0; }
  say "starting Showdown server from $MAIN/showdown"
  [ "$DRY" = 1 ] && return 0
  ( cd "$MAIN/showdown" && nohup node pokemon-showdown start --no-security >> "$MAIN/logs/showdown_server.log" 2>&1 < /dev/null & )
  local i=0
  until nc -z localhost 8000 2>/dev/null; do sleep 1; i=$((i+1)); [ $i -gt 120 ] && { say "SERVER FAILED: nothing listening on 8000 after 120 s"; return 1; }; done
  sleep 5
  say "server up (pid $(server_pid)); simulator: $(grep -o 'simulator: [0-9]*' "$MAIN/showdown/config/config.js" | head -1 | tr -d '\n')"
  return 0
}
restart_server() { stop_server && start_server; }
run() { if [ "$DRY" = 1 ]; then say "DRY: $*"; return 0; fi; "$@"; }
die() { say "REFUSED: $*"; exit 1; }
run_dir_of() { echo "runs/engine_a1_s$1"; }
rung_ckpt() {  # first checkpoint at or after the 12M rung
  ls "$(run_dir_of "$1")"/ckpt_0120*.pt 2>/dev/null | head -n 1
}
wr_of() { "$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['eval/win_rate'])" "$1"; }

unit() {  # $1 output path, $2.. command — skip when the output exists
  local out="$1"; shift
  if [ -f "$out" ]; then say "SKIP $out (exists)"; return 0; fi
  local t0; t0=$(date +%s)
  say "START $out :: $*"
  if run "$@" >> "$LOG" 2>&1; then
    say "DONE  $out ELAPSED=$(( $(date +%s) - t0 ))s"
  else
    say "FAILED $out (rc $?) — re-run resumes here"; return 1
  fi
}

# ---- 0. preflight ------------------------------------------------------------
say "=== engine_gates preflight ==="
pgrep -f "rl\.train" > /dev/null && die "a training lane is alive — this script owns the box or does not run"
pgrep -f "gen4_wang50m_postfleet" > /dev/null && die "the gen-4 post-fleet chain is running"
# An IDLE Showdown server left over from a finished chapter is not contention —
# step 2 restarts it fresh anyway. A server doing WORK would be, but nothing on
# this box may be training (checked above) and the evals are ours.
if [ -f logs/gen4_wang50m_postfleet.log ] && ! grep -q "POST-FLEET DONE" logs/gen4_wang50m_postfleet.log; then
  die "logs/gen4_wang50m_postfleet.log has no POST-FLEET DONE line — the gen-4 chapter still owns the box"
fi
[ -n "$(git status --porcelain)" ] && die "working tree is dirty — one untracked file stamps git_dirty on every run (CLAUDE.md rule 3)"
[ "${POKEMON_RL_ENCODER_V2:-}" = "1" ] && [ "${POKEMON_RL_ENCODER_IDS:-}" = "1" ] \
  || die "POKEMON_RL_ENCODER_V2 / _IDS unset — the lane would build a width that compares to no checkpoint"

# Ratification. The pre-reg is DRAFT until the maintainer answers RW-1..RW-8;
# launching before that would make the run's own design a fait accompli.
AUTH=$("$PY" -c "
import yaml,sys
d=yaml.safe_load(open('$PREREG'))
owed=[k for k in d.get('rulings_wanted',{}) if k not in (d.get('ratified_decisions') or {})]
print('OWED:'+','.join(sorted(owed)) if owed else 'OK')
print(d.get('launch_authorization','NONE'))" 2>/dev/null | tr '\n' ' ')
case "$AUTH" in
  "OK NONE "*|*"NONE "*) die "pre-reg not ratified / no launch authorization ($AUTH). Answer RW-1..RW-8 in $PREREG first." ;;
  "OWED:"*) die "rulings still owed ($AUTH)" ;;
esac

# vm_stat's page size is NOT 4096 on this box — it is 16384, and the header
# states it. Hard-coding 4096 under-reports free memory by 4x and would refuse
# a launch on a box with 10 GB free. Read the page size rather than assume it.
PAGE=$(vm_stat | awk 'NR==1{for(i=1;i<=NF;i++) if ($i+0>1024) {print $i+0; exit}}')
PAGE=${PAGE:-4096}
FREE_GB=$(vm_stat | awk -v pg="$PAGE" '/Pages free|Pages inactive/ {gsub(/\./,"");s+=$NF} END {print int(s*pg/1073741824)}')
DISK_GB=$(df -g . | awk 'NR==2{print $4}')
say "box: free+inactive ${FREE_GB}GB, disk ${DISK_GB}GiB, width 3"
[ "${FREE_GB:-0}" -lt 6 ] && die "free+inactive ${FREE_GB}GB < 6GB — RAM is the local ceiling, not cores"
[ "${DISK_GB:-0}" -lt 20 ] && die "disk ${DISK_GB}GiB < 20GiB"
say "preflight OK"

# ---- 1. team bank ------------------------------------------------------------
if [ ! -f "$BANK" ]; then
  say "team bank $BANK missing — generating $BANK_PAIRS pairs (RW-6)"
  unit "$BANK" "$PY" scripts/engine_team_bank.py --showdown-root "$MAIN/showdown" \
      --pairs "$BANK_PAIRS" --seed-prefix a1a1 --out "$BANK" || exit 1
fi
say "STEP 1 DONE (team bank $BANK)"

# ---- 2. D-1 ------------------------------------------------------------------
# Needs a server, and a FRESH one: the engine leg is compared against real
# Showdown, so a server carrying hours of another run's state is not the
# instrument we want.
restart_server || exit 1
unit "$D1OUT/engine.json" "$PY" scripts/engine_d1.py --leg engine --bank "$BANK" --out "$D1OUT" || exit 1
# the server leg needs the SAME bank: D-1 compares the two engines on matched
# team pairs, so a bankless server leg is not the comparison (engine_d1.py:410).
unit "$D1OUT/server.json" "$PY" scripts/engine_d1.py --leg server --bank "$BANK" --out "$D1OUT" || exit 1
unit "$D1OUT/compare.json" "$PY" scripts/engine_d1.py --leg compare --out "$D1OUT" || exit 1
if ! "$PY" -c "
import json,sys; d=json.load(open('$D1OUT/compare.json'))
sys.exit(0 if d.get('pass') else 1)"; then
  say "D-1 FAILED — A-1 DOES NOT LAUNCH. On a failed D-1 the engine and real"
  say "Showdown disagree about the GAME, so A-1 would be a joint test of"
  say "collector correctness and dynamics parity and neither verdict could be"
  say "attributed. Diagnose parity (plan §9); never tune."
  exit 1
fi
say "STEP 2 DONE (D-1 PASS)"

# ---- 3. T-1 (a)(b), idle box, server DOWN ------------------------------------
stop_server || exit 1
unit "$T1OUT/leg_a.json" "$PY" scripts/engine_t1.py --leg a --bank "$BANK" --out "$T1OUT" || exit 1
unit "$T1OUT/leg_b.json" "$PY" scripts/engine_t1.py --leg b --bank "$BANK" --out "$T1OUT" || exit 1
say "STEP 3 DONE (T-1 a,b)"

# ---- 4. A-1 lanes ------------------------------------------------------------
# Server UP from here: the in-loop evals go through poke-env.
start_server || exit 1
for s in $SEEDS; do
  d=$(run_dir_of "$s")
  if [ -n "$(rung_ckpt "$s")" ]; then say "SKIP lane s$s (12M rung exists)"; continue; fi
  if [ -d "$d" ]; then
    say "RESUME lane s$s from $d"
    run nohup "$PY" -m rl.train --resume "$d" > "$d.nohup.log" 2>&1 &
  else
    say "START lane s$s"
    run nohup "$PY" -m rl.train --config "$CONFIG" --seed "$s" \
        --run-name "engine_a1_s$s" > "runs/engine_a1_s$s.nohup.log" 2>&1 &
  fi
  sleep 90   # stagger: lanes can SIGSEGV at startup before any log line
done

# Wait for every lane to cross the rung, checking liveness by CPU-TIME DELTA —
# a lane can STALL ALIVE AT ZERO CPU and every pgrep passes forever.
while :; do
  done_n=0
  for s in $SEEDS; do [ -n "$(rung_ckpt "$s")" ] && done_n=$((done_n+1)); done
  [ "$done_n" -ge 3 ] && break
  for s in $SEEDS; do
    [ -n "$(rung_ckpt "$s")" ] && continue
    pid=$(pgrep -f "engine_a1_s$s" | head -n 1)
    if [ -z "$pid" ]; then say "lane s$s: NO PROCESS — re-run this script to resume it"; continue; fi
    c0=$(ps -p "$pid" -o time= 2>/dev/null); sleep 15; c1=$(ps -p "$pid" -o time= 2>/dev/null)
    if [ "$c0" = "$c1" ]; then
      say "lane s$s: ALIVE AT ZERO CPU over 15 s (pid $pid) — the orphaned-room stall shape. Kill it and re-run this script to --resume."
    fi
  done
  sleep 600
done
# Kill at the rung: the lane's own horizon is 50M (the control's schedule).
# NOT IMMEDIATELY. rl/train.py writes the checkpoint BEFORE it runs that step's
# eval, so killing the moment ckpt_0120*.pt appears drops the 48th in-loop rung
# — the one P-AUC's denominator needs. Measured time/eval_sec is ~5.1 s; 120 s
# is a ~23x margin.
say "12M rung reached on all lanes — holding 120 s so the 48th in-loop eval lands"
[ "$DRY" = 1 ] || sleep 120
for s in $SEEDS; do
  pid=$(pgrep -f "engine_a1_s$s" | head -n 1)
  [ -n "$pid" ] && { say "lane s$s stopping at $(basename "$(rung_ckpt "$s")")"; run kill "$pid"; }
done
say "STEP 4 DONE (A-1 lanes at the 12M rung)"

# ---- 5. T-1 (c)(d) on the A-1 fleet ------------------------------------------
# NOTE: (d) must run while the lanes are ALIVE. If step 4 already stopped them,
# these legs are recorded as NOT MEASURED rather than faked from a dead fleet.
if pgrep -f "engine_a1_s" > /dev/null; then
  unit "$T1OUT/leg_c.json" "$PY" scripts/engine_t1.py --leg c --config "$CONFIG" \
      --run-dir "$(run_dir_of 66)" --out "$T1OUT"
  unit "$T1OUT/leg_d.json" "$PY" scripts/engine_t1.py --leg d \
      $(for s in $SEEDS; do printf -- "--run-dir %s " "$(run_dir_of "$s")"; done) --out "$T1OUT"
else
  say "STEP 5: T-1 (c)/(d) NOT MEASURED — the lanes are no longer alive and a"
  say "fleet-width number cannot be reconstructed from a finished run. Re-run"
  say "them during the next engine fleet; A-1 does not depend on them."
fi
say "STEP 5 DONE (T-1 c,d)"

# ---- 6. A-1 evals, locked protocol -------------------------------------------
for s in $SEEDS; do
  ck=$(rung_ckpt "$s")
  [ -n "$ck" ] || { say "lane s$s has no 12M rung — A1-VOID-K applies, see the header"; continue; }
  unit "$OUT/rung12m_s$s.json" "$PY" scripts/eval_checkpoint.py "$ck" \
      --episodes "$EVAL_N" --opponent heuristics --out "$OUT/rung12m_s$s.json" || exit 1
done
# THE BASELINE IS RE-EVALUATED AT THE SAME n, FROM ITS BANKED CHECKPOINTS.
# Raising n is only honest if BOTH arms get it: the banked g9_treat JSONs are
# n=3000, and comparing a 12,000-battle arm against a 3,000-battle basis would
# buy precision on one side only. The checkpoints are on disk and sha-pinned,
# so this costs eval time and no training.
for s in $SEEDS; do
  bck="$BANKED_RUNS/showdown_sp_batch50m_async_s$s"
  ck=$(ls "$bck"/ckpt_0120*.pt 2>/dev/null | head -n 1)
  [ -n "$ck" ] || { say "banked lane s$s has no 12M rung at $bck — cannot re-evaluate"; exit 1; }
  unit "$OUT/banked_s$s.json" "$PY" scripts/eval_checkpoint.py "$ck" \
      --episodes "$EVAL_N" --opponent heuristics --out "$OUT/banked_s$s.json" || exit 1
done
say "STEP 6 DONE (A-1 evals, both arms at n=$EVAL_N)"

# ---- 7. grade ----------------------------------------------------------------
run "$PY" scripts/engine_a1_grade.py --out "$OUT/primary.json" \
    --banked $(for s in $SEEDS; do printf -- "%s " "$OUT/banked_s$s.json"; done) \
    $(for s in $SEEDS; do printf -- "%s " "$OUT/rung12m_s$s.json"; done) 2>&1 | tee -a "$LOG"
say "ENGINE GATES DONE — author the readout by hand from $OUT/ (one commit)"
