#!/bin/bash
# CH3 R4 BI-5: the auto-relaunch / crash-forfeit runner for anchor arm FE3.
#
#   bash scripts/ch3_r4_fp_runner.sh
#   BATTLES=5 TAG=smoke_fe3 bash scripts/ch3_r4_fp_runner.sh      # G1 smoke
#
# Implements the CRASH-FORFEIT READ RULE pre-stated 2026-08-23 and carried
# verbatim into the R4 pre-reg (ANCHOR BATTERY / FP BLOCK): an FP crash
# forfeits the in-flight battle TO US server-side, so crash-forfeited
# battles are EXCLUDED -- n_eff = seat-finished minus crash-forfeits,
# our_wins reduced by the same count; the relaunch count and every crash
# point are disclosed beside the number; >= MAX_RELAUNCHES relaunches VOIDs
# the arm. The 2026-08-23 recovery ran this loop BY HAND; this is it in a
# file. It writes $OUT/$TAG.runner.json, which
# scripts/ch3_r4_anchor_grade.py reads to apply the n_eff correction.
#
# bash-3.2-safe by construction (macOS /bin/bash): no ${var,,}, no
# associative arrays, no `mapfile`, no `wait -n`.
#
# LIVENESS IS OUTPUT-FILE PROGRESS, NEVER DIRECTORY EXISTENCE (the repo
# landmine): the poll reads the Foul Play log's byte count and its
# completed-battle count. A log that stops growing for STALL_POLLS polls is
# a hung FP and is killed and relaunched exactly like a crashed one; the
# run directory existing proves nothing and is never consulted.

set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1

PY="${PY:-/opt/anaconda3/envs/pokemon-showdown-rl/bin/python}"
FPPY="${FPPY:-/opt/anaconda3/envs/foul-play/bin/python}"
FPDIR="${FPDIR:-$REPO/../foul-play}"
PREREG="${PREREG:-configs/eval/ch3_r4_fp_anchor.yaml}"
ARM="${ARM:-FE3}"
TAG="${TAG:-fe3}"
OUT="${OUT:-results/ch3_r4_fp_anchor}"
BATTLES="${BATTLES:-250}"
SEARCH_TIME_MS="${SEARCH_TIME_MS:-100}"
SEARCH_PARALLELISM="${SEARCH_PARALLELISM:-1}"
FORMAT="${FORMAT:-gen1randombattle}"
WS="${WS:-ws://localhost:8000/showdown/websocket}"
SEAT_USER="${SEAT_USER:-r4anchorseat}"
FP_USER="${FP_USER:-r4anchorfp}"
MAX_RELAUNCHES="${MAX_RELAUNCHES:-30}"
POLL_SECS="${POLL_SECS:-10}"
STALL_POLLS="${STALL_POLLS:-60}"
START_STAGGER="${START_STAGGER:-30}"

export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1

# CH4 R1 BI-6 + G8: when the pre-reg's arms block defines this arm, its
# kind/usernames/battles/budget come FROM THE PRE-REG, never from free env
# vars (review 1 MA-10: a mis-exported SEARCH_TIME_MS used to produce a JSON
# indistinguishable from a correct one). Older pre-regs without these keys
# keep the env-var path untouched.
ARM_KIND="$("$PY" -c "
import yaml,sys
arm = yaml.safe_load(open('$PREREG'))['arms'].get('$ARM') or {}
print(arm.get('kind',''))" 2>/dev/null || echo "")"
if [ -n "$ARM_KIND" ]; then
    eval "$("$PY" -c "
import yaml
arm = yaml.safe_load(open('$PREREG'))['arms']['$ARM']
for shell, key in (('SEAT_USER','seat_username'),('FP_USER','fp_username'),
                   ('BATTLES','battles'),('SEARCH_TIME_MS','search_time_ms')):
    v = arm.get(key)
    if v is not None:
        print(f'{shell}={v}')")"
fi

# G1 smokes: SMOKE_BATTLES (if set) wins over the pre-reg battle count —
# the ONLY sanctioned post-derivation override, and it also forces a
# smoke_ tag prefix so a smoke can never overwrite a real arm JSON.
if [ -n "${SMOKE_BATTLES:-}" ]; then
    BATTLES="$SMOKE_BATTLES"
    case "$TAG" in smoke_*) ;; *) TAG="smoke_$TAG" ;; esac
fi

mkdir -p "$OUT"
SEAT_LOG="$OUT/$TAG.seat.stdout"
FP_LOG="$OUT/$TAG.fp.stdout"
RUNNER_LOG="$OUT/$TAG.runner.log"
RUNNER_JSON="$OUT/$TAG.runner.json"
# BI-6: arm-scoped VOID marker — concurrent arms in one OUT dir must not
# share a crash sentinel (review 1 MA-18).
VOID_MARKER="$OUT/$TAG.TOO_MANY_CRASHES"

rm -f "$VOID_MARKER"
: > "$FP_LOG"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$RUNNER_LOG"
}

fp_completed() {
    # completed-battle count from FP's own log; cumulative because every
    # relaunch APPENDS. Crash-forfeited battles have no Winner line here --
    # that asymmetry IS the n_eff correction. (grep -c exits 1 on a zero
    # count while still PRINTING 0, so `|| echo 0` would double-print.)
    c="$(grep -c "Winner:" "$FP_LOG" 2>/dev/null)"
    [ -n "$c" ] || c=0
    echo "$c"
}

log_bytes() {
    b="$(wc -c < "$FP_LOG" 2>/dev/null | tr -d ' ')"
    [ -n "$b" ] || b=0
    echo "$b"
}

start_fp() {
    remaining="$1"
    ( cd "$FPDIR" && "$FPPY" run.py \
        --websocket-uri "$WS" \
        --ps-username "$FP_USER" \
        --bot-mode challenge_user \
        --user-to-challenge "$SEAT_USER" \
        --pokemon-format "$FORMAT" \
        --search-time-ms "$SEARCH_TIME_MS" \
        --search-parallelism "$SEARCH_PARALLELISM" \
        --run-count "$remaining" ) >> "$FP_LOG" 2>&1 &
    FP_PID=$!
    log "foul-play started pid $FP_PID, run-count $remaining"
}

write_runner_json() {
    void_flag="$1"
    completed="$(fp_completed)"
    cat > "$RUNNER_JSON" <<EOF
{
  "tag": "$TAG",
  "arm": "$ARM",
  "prereg": "$PREREG",
  "battles_requested": $BATTLES,
  "relaunches": $RELAUNCHES,
  "crash_forfeits": $RELAUNCHES,
  "max_relaunches": $MAX_RELAUNCHES,
  "fp_completed_battles": $completed,
  "crash_points_fp_completed": [$CRASH_POINTS],
  "crash_points_utc": [$CRASH_TIMES],
  "void_too_many_crashes": $void_flag,
  "liveness_rule": "foul-play log byte/battle progress; directory existence never consulted",
  "read_rule": "n_eff = seat_finished - crash_forfeits; our_wins reduced by the same count (2026-08-23, verbatim in the R4 pre-reg)"
}
EOF
    log "wrote $RUNNER_JSON (relaunches $RELAUNCHES, fp completed $completed)"
}

# ---- the seat: OUR side, started first and staggered (torch lazy-init
# ---- SIGSEGV landmine). CH4 R1: fp_vs_sh arms seat SimpleHeuristics via
# ---- foulplay_vs_sh.py (BI-2a — the same implementation that produced
# ---- every banked hub number, so H1/H2 stay commensurable); every other
# ---- kind seats a checkpoint via ch3_fp_h2h.py. ------------------------
if [ "$ARM_KIND" = "fp_vs_sh" ]; then
    "$PY" scripts/foulplay_vs_sh.py --opponent "$FP_USER" --battles "$BATTLES" \
        --username "$SEAT_USER" --tag "$TAG" --out-dir "$OUT" > "$SEAT_LOG" 2>&1 &
else
    "$PY" scripts/ch3_fp_h2h.py --prereg "$PREREG" --arm "$ARM" \
        --battles "$BATTLES" --tag "$TAG" > "$SEAT_LOG" 2>&1 &
fi
SEAT_PID=$!
log "seat pid $SEAT_PID ($ARM, $BATTLES battles, tag $TAG); staggering ${START_STAGGER}s"
sleep "$START_STAGGER"

if ! kill -0 "$SEAT_PID" 2>/dev/null; then
    log "SEAT DIED DURING STARTUP -- see $SEAT_LOG (torch lazy-init SIGSEGV?)"
    RELAUNCHES=0
    CRASH_POINTS=""
    CRASH_TIMES=""
    write_runner_json false
    exit 1
fi

RELAUNCHES=0
CRASH_POINTS=""
CRASH_TIMES=""
LAST_BYTES=0
STALLED=0

start_fp "$BATTLES"

while kill -0 "$SEAT_PID" 2>/dev/null; do
    sleep "$POLL_SECS"
    NOW_BYTES="$(log_bytes)"
    if [ "${NOW_BYTES:-0}" != "$LAST_BYTES" ]; then
        LAST_BYTES="${NOW_BYTES:-0}"
        STALLED=0
    else
        STALLED=$((STALLED + 1))
    fi

    FP_DEAD=0
    if ! kill -0 "$FP_PID" 2>/dev/null; then
        FP_DEAD=1
        log "foul-play pid $FP_PID is gone"
    elif [ "$STALLED" -ge "$STALL_POLLS" ]; then
        FP_DEAD=1
        log "foul-play log stalled for $((STALLED * POLL_SECS))s -- killing pid $FP_PID"
        kill "$FP_PID" 2>/dev/null
        sleep 2
        kill -9 "$FP_PID" 2>/dev/null
    fi
    [ "$FP_DEAD" -eq 0 ] && continue

    # The seat is still alive, so the run is not finished: this is a crash
    # (or a hang), and it forfeited the in-flight battle to us.
    if ! kill -0 "$SEAT_PID" 2>/dev/null; then
        log "seat finished; foul-play exit is the normal end of the run"
        break
    fi
    COMPLETED="$(fp_completed)"
    RELAUNCHES=$((RELAUNCHES + 1))
    if [ -n "$CRASH_POINTS" ]; then
        CRASH_POINTS="$CRASH_POINTS, $COMPLETED"
        CRASH_TIMES="$CRASH_TIMES, \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    else
        CRASH_POINTS="$COMPLETED"
        CRASH_TIMES="\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    fi
    log "CRASH $RELAUNCHES/$MAX_RELAUNCHES at fp-completed $COMPLETED (that battle forfeits TO US and is EXCLUDED)"

    if [ "$RELAUNCHES" -ge "$MAX_RELAUNCHES" ]; then
        log "TOO_MANY_CRASHES: $RELAUNCHES >= $MAX_RELAUNCHES -- the arm is VOID"
        date -u +%Y-%m-%dT%H:%M:%SZ > "$VOID_MARKER"
        echo "relaunches=$RELAUNCHES max=$MAX_RELAUNCHES arm=$ARM" >> "$VOID_MARKER"
        kill "$SEAT_PID" 2>/dev/null
        sleep 2
        kill -9 "$SEAT_PID" 2>/dev/null
        write_runner_json true
        exit 2
    fi

    REMAINING=$((BATTLES - COMPLETED - RELAUNCHES))
    if [ "$REMAINING" -lt 1 ]; then
        log "no battles remain ($REMAINING) -- not relaunching; waiting on the seat"
        break
    fi
    sleep "$POLL_SECS"
    start_fp "$REMAINING"
    LAST_BYTES="$(log_bytes)"
    STALLED=0
done

wait "$SEAT_PID"
SEAT_RC=$?
kill "$FP_PID" 2>/dev/null
write_runner_json false
log "seat exited rc=$SEAT_RC; relaunches=$RELAUNCHES"
log "G2 OWED: cross-check the seat tally against foul-play's own W/L on n_eff EXACTLY before believing the number."
exit "$SEAT_RC"
