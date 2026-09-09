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

# NO RATIFICATION GATE ON THE ARM. Maintainer, 2026-09-09: the A-1 ENGINE ARM
# is COMMON TO EVERY CANDIDATE DESIGN — gross-breakage screen or equivalence
# test, historical baseline or fresh — and extra seeds are ADDITIVE if k later
# rises, so running it early wastes nothing under any ruling. What stays
# forbidden is a VERDICT: this script computes no delta, no band comparison and
# no pass/fail, and it does not call the grader. See step 7.
AUTH=$("$PY" -c "
import yaml
d=yaml.safe_load(open('$PREREG'))
a=d.get('launch_authorization')
print('OK' if isinstance(a, dict) and a.get('granted_by') else 'NONE')" 2>/dev/null)
[ "$AUTH" = "OK" ] || die "no launch_authorization block in $PREREG"

# vm_stat's page size is NOT 4096 on this box — it is 16384, and the header
# states it. Hard-coding 4096 under-reports free memory by 4x and would refuse
# a launch on a box with 10 GB free. Read the page size rather than assume it.
# (`set -u` is on, so PAGE must be assigned before it is referenced.)
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
# ORDER MATTERS INSIDE D-1. The ENGINE leg needs NO server and refuses to
# measure while one is up (a server doing work is contention for an
# engine-only read). The SERVER leg needs a fresh one. So: engine leg first
# with the box quiet, THEN bring the server up for its half.
stop_server || exit 1
unit "$D1OUT/engine.json" "$PY" scripts/engine_d1.py --leg engine --bank "$BANK" --out "$D1OUT" || exit 1
# A FRESH server for the server leg: it is compared against the engine, so one
# carrying hours of another run's state is not the instrument we want.
restart_server || exit 1
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

# ---- 3. T-1 (a)(b) — IDLE BOX. Nothing of ours may run beside these. -------
# A throughput number taken against our own job measures nothing (the earlier
# engine_smoke run sat at 106% of a core). Server DOWN, no lanes, no builds.
stop_server || exit 1
if pgrep -f "rl\.train|pytest|cargo|maturin" > /dev/null; then
  die "something of ours is running — T-1 (a)/(b) are IDLE-BOX measurements"
fi
unit "$T1OUT/leg_a.json" "$PY" scripts/engine_t1.py --leg a --bank "$BANK" --out "$T1OUT" || \
  say "T-1 (a) FAILED — recorded, continuing (an independent unit)"
unit "$T1OUT/leg_b.json" "$PY" scripts/engine_t1.py --leg b --bank "$BANK" --out "$T1OUT" || \
  say "T-1 (b) FAILED — recorded, continuing"
say "STEP 3 DONE (T-1 a,b)"

# ---- 4. THE A-1 ENGINE ARM — arms only, NO VERDICT --------------------------
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
say "STEP 4: three engine lanes launched (seeds $SEEDS)"

# ---- 5. T-1 (c)(d) MEASURED WHILE THE LANES RUN -----------------------------
# This is the real fleet-width case. A solo number repeats the
# showdown_throughput.py mistake (~7x overstatement) — width and scope travel
# with every figure. Wait for startup to settle first: a window straddling
# startup invents a record.
say "STEP 5: settling 20 min before the fleet-width read"
[ "$DRY" = 1 ] || sleep 1200
if pgrep -f "engine_a1_s" > /dev/null; then
  unit "$T1OUT/leg_d.json" "$PY" scripts/engine_t1.py --leg d \
      $(for s in $SEEDS; do printf -- "--run-dir %s " "$(run_dir_of "$s")"; done) --out "$T1OUT" || \
    say "T-1 (d) FAILED — recorded, continuing"
else
  say "STEP 5: no lane alive — T-1 (d) NOT MEASURED (a fleet-width number cannot be reconstructed later)"
fi

# ---- 6. wait for the rung, then stop the lanes ------------------------------
while :; do
  done_n=0
  for s in $SEEDS; do [ -n "$(rung_ckpt "$s")" ] && done_n=$((done_n+1)); done
  [ "$done_n" -ge 3 ] && break
  [ "$DRY" = 1 ] && break
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
# rl/train.py writes the checkpoint BEFORE that step's eval, so killing the
# moment ckpt_0120*.pt appears drops the 48th in-loop rung. Measured
# time/eval_sec is ~5.1 s; 120 s is a ~23x margin.
say "12M rung reached on all lanes — holding 120 s so the 48th in-loop eval lands"
[ "$DRY" = 1 ] || sleep 120
for s in $SEEDS; do
  pid=$(pgrep -f "engine_a1_s$s" | head -n 1)
  [ -n "$pid" ] && { say "lane s$s stopping at $(basename "$(rung_ckpt "$s")")"; run kill "$pid"; }
done
# T-1 (c) is a full-loop read off a lane's own history; it needs the lane
# FINISHED, not running, so it lands here rather than in step 5.
for s in $SEEDS; do
  [ -f "$(run_dir_of "$s")/history.csv" ] || run "$PY" scripts/extract_history.py "$(run_dir_of "$s")" || \
    say "extract_history failed for s$s (a resume splits the history — merge_history.py)"
done
unit "$T1OUT/leg_c.json" "$PY" scripts/engine_t1.py --leg c --config "$CONFIG" \
    --run-dir "$(run_dir_of 66)" --out "$T1OUT" || say "T-1 (c) FAILED — recorded, continuing"
say "STEP 6 DONE (lanes at the 12M rung; T-1 c)"

# ---- 7. DESCRIPTIVE evals of the engine arm's own finals ---------------------
# PER-SEED NUMBERS ONLY. Not a comparison, not a grade, no delta, no band.
# The A-1 band is UNRESOLVED (maintainer, 2026-09-09) and a verdict computed
# off an unresolved band is worse than no verdict, so scripts/engine_a1_grade.py
# is NOT called and the banked arm is NOT re-evaluated here.
start_server || exit 1
for s in $SEEDS; do
  ck=$(rung_ckpt "$s")
  [ -n "$ck" ] || { say "lane s$s has no 12M rung — no eval"; continue; }
  unit "$OUT/rung12m_s$s.json" "$PY" scripts/eval_checkpoint.py "$ck" \
      --episodes "$EVAL_N" --opponent heuristics --out "$OUT/rung12m_s$s.json" || \
    say "eval s$s FAILED — recorded, continuing"
done
say "STEP 7 DONE — DESCRIPTIVE per-seed engine-arm numbers:"
for s in $SEEDS; do
  [ -f "$OUT/rung12m_s$s.json" ] && say "  s$s n=$EVAL_N win_rate=$(wr_of "$OUT/rung12m_s$s.json")"
done
say "NO A-1 VERDICT COMPUTED. The band is unresolved; the pre-reg resolves it."
say "ENGINE GATES DONE"
