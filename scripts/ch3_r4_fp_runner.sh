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
# CH5 B-5.4c / BI-3: a hung SEAT stops FP writing too (FP is waiting on our
# move), so the stall detector fires and kills the HEALTHY process. That is
# the S1 churn shape with a different root cause, and it burns the whole
# relaunch budget at zero progress while LOOKING exactly like slow progress
# (the CLAUDE.md landmine, verbatim). N relaunches that produce zero new
# `Winner:` lines abort the arm as an OPS FAILURE, not a data verdict.
NO_PROGRESS_RELAUNCHES="${NO_PROGRESS_RELAUNCHES:-3}"
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
# BOTH sentinels must be cleared at arm start, not just the crash one. The
# NO_PROGRESS marker was left behind (2026-08-28) and a CLEAN re-run of the
# same tag inherited it: rs81 finished 3000/3000 with rc=0, relaunches 0 and
# G2 exact, and the wave still logged "OPS FAILURE ... NOT graded" while
# ch5_r1_grade.py would have REFUSED the arm on the stale file. A failure
# marker that outlives the failure discards good data and looks like a real
# abort while doing it.
NO_PROGRESS_MARKER="$OUT/$TAG.NO_PROGRESS"

rm -f "$VOID_MARKER" "$NO_PROGRESS_MARKER"
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

# 2026-08-31, THE ORPHANED-ROOM DEADLOCK (docs/landmines.md): "the watchdog
# blames the wrong process". A wedged SEAT starves foul-play of anything to
# log, so the FP-log stall detector above fires and charges the RELAUNCH -- and
# therefore a CRASH FORFEIT -- to a foul-play that was doing nothing wrong.
# Both R4S66 attempts died that way.
#
# The obvious fix, summing the SEAT log's bytes into log_bytes(), was
# CONSIDERED AND REJECTED: ch3_fp_h2h.py prints at start and at end and
# NOTHING per battle, so the seat log does not grow during a healthy run --
# summing changes no decision and would only give a growing FP log a way to
# hide a dead seat. The seat's real liveness signal is CPU TIME, which is the
# instrument CLAUDE.md already mandates for the stall signature (process
# ALIVE, zero CPU, `pgrep` never catches it; confirm in 15 s with two
# samples). So: keep the FP-log trigger, and ATTRIBUTE at the moment of the
# kill.
#
# Attribution is RECORDED, NOT ACTED ON. Whether a relaunch that killed a
# LIVE foul-play forfeited a real in-flight battle is an accounting question
# against a FROZEN pre-reg ("n_eff = seat_finished - crash_forfeits"), and
# that is the maintainer's to answer -- so `crash_forfeits` keeps its exact
# meaning (= relaunches) and the evidence lands beside it in the arm JSON.

# CPU-seconds for a pid, or empty if it is gone. macOS `ps -o time=` prints
# MM:SS.ss with minutes UNBOUNDED (108:34.43 is real), so parse from the right.
cpu_secs() {
    ps -o time= -p "$1" 2>/dev/null | tr -d ' ' | awk -F: '
        NF==0 { exit }
        { s = $NF; if (NF >= 2) s += $(NF-1) * 60; if (NF >= 3) s += $(NF-2) * 3600;
          printf "%.2f\n", s }'
}

# 1 if the pid burned no CPU across the probe window -- the stall signature.
seat_frozen() {
    a="$(cpu_secs "$1")"
    [ -n "$a" ] || return 1
    sleep "${WEDGE_PROBE_SECS:-15}"
    b="$(cpu_secs "$1")"
    [ -n "$b" ] || return 1
    [ "$a" = "$b" ]
}

# 2026-08-25 (S1 incident): `( ... ) &` makes $! the SUBSHELL's pid, so
# every kill orphaned a live foul-play python that kept holding the
# websocket AND the username. The relaunch then hit
# "|nametaken|<user>|Someone is already using the name" and wrote nothing,
# so the stall detector killed it and orphaned another — 15 relaunches, 14
# orphans, zero progress. `exec` replaces the subshell with python, so
# FP_PID is the real process; kill_fp() sweeps by username as belt-and-
# braces and waits for the server to release the name before relaunching.
kill_fp() {
    # 2026-08-26, MEASURED: foul-play spawns multiprocessing SEARCH WORKERS
    # whose command lines read `... -c from multiprocessing.spawn import
    # spawn_main ...` and therefore do NOT match the --ps-username sweep
    # below. Killing the parent alone ORPHANS them. They survive, keep
    # server-side battle state alive, and a relaunched seat/fp pair then
    # DEADLOCKS AT 0% CPU on a battle neither side owns — the S1 shape with
    # a new root cause, and it looks exactly like slow progress. Kill the
    # CHILDREN FIRST, while $FP_PID is still their parent and `pkill -P` can
    # still see them; once the parent dies they reparent to init and -P
    # cannot find them.
    pkill -9 -P "$FP_PID" 2>/dev/null
    kill "$FP_PID" 2>/dev/null
    sleep 2
    kill -9 "$FP_PID" 2>/dev/null
    pkill -9 -f "run.py .*--ps-username $FP_USER( |\$)" 2>/dev/null
    # Belt, for workers already reparented by an earlier bad kill. Arms are
    # SERIAL (k=1), so there is never a second foul-play to hit by mistake.
    pkill -9 -f "foul-play/bin/python -c from multiprocessing" 2>/dev/null
    sleep "${NAME_RELEASE_SECS:-15}"
}

start_fp() {
    remaining="$1"
    ( cd "$FPDIR" && exec "$FPPY" run.py \
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
  "fp_found_dead": $FP_FOUND_DEAD,
  "fp_killed_while_alive": $FP_KILLED_ALIVE,
  "seat_frozen_at_kill": $SEAT_FROZEN_AT_KILL,
  "attribution_note": "crash_forfeits keeps its pre-reg meaning (= relaunches). fp_found_dead is an unambiguous FP death; fp_killed_while_alive is a log-stall kill; seat_frozen_at_kill is the subset of those where OUR seat burned zero CPU too (the orphaned-room signature) and is the count a grader should question before believing a forfeit.",
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
    FP_FOUND_DEAD=0
    FP_KILLED_ALIVE=0
    SEAT_FROZEN_AT_KILL=0
    write_runner_json false
    exit 1
fi

RELAUNCHES=0
CRASH_POINTS=""
CRASH_TIMES=""
LAST_BYTES=0
STALLED=0
NO_PROGRESS=0
LAST_CRASH_COMPLETED=-1
# Attribution counters (see cpu_secs/seat_frozen above). FOUND_DEAD is an
# unambiguous foul-play death; KILLED_ALIVE is us killing a live process on a
# log stall; SEAT_FROZEN_AT_KILL is the subset of those where OUR seat was
# burning no CPU either, i.e. the orphaned-room signature.
FP_FOUND_DEAD=0
FP_KILLED_ALIVE=0
SEAT_FROZEN_AT_KILL=0

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
        FP_FOUND_DEAD=$((FP_FOUND_DEAD + 1))
        log "foul-play pid $FP_PID is gone"
        # 2026-08-31: this branch used to set FP_DEAD and fall straight
        # through to the relaunch WITHOUT calling kill_fp, so foul-play's
        # multiprocessing SEARCH WORKERS were never reaped here -- the exact
        # orphaned-children failure the 2026-08-26 note above documents, left
        # open on the one path where the parent dies by itself. kill_fp is
        # safe on a dead parent (`pkill -P` is a no-op) and still sweeps by
        # username and by the multiprocessing pattern, and it holds the
        # username-release wait the relaunch needs.
        kill_fp
    elif [ "$STALLED" -ge "$STALL_POLLS" ]; then
        FP_DEAD=1
        FP_KILLED_ALIVE=$((FP_KILLED_ALIVE + 1))
        if seat_frozen "$SEAT_PID"; then
            SEAT_FROZEN_AT_KILL=$((SEAT_FROZEN_AT_KILL + 1))
            log "ATTRIBUTION: the SEAT burned ZERO CPU across a ${WEDGE_PROBE_SECS:-15}s probe while foul-play's log was stalled -- the ORPHANED-ROOM signature (docs/landmines.md). Relaunching FP is unlikely to help and this relaunch is NOT evidence that foul-play crashed."
        else
            log "ATTRIBUTION: the seat is burning CPU; foul-play is the stalled side."
        fi
        log "foul-play log stalled for $((STALLED * POLL_SECS))s -- killing pid $FP_PID"
        kill_fp
    fi
    # A relaunch that never logged in (username still held) is an OPS
    # failure, not a battle crash: detect it and abort rather than burn
    # the relaunch budget orphaning processes.
    if tail -40 "$FP_LOG" 2>/dev/null | grep -q "nametaken"; then
        log "USERNAME DEADLOCK: '$FP_USER' still registered after a kill; aborting arm (ops failure, NOT a data verdict)"
        pkill -9 -P "$FP_PID" 2>/dev/null
        pkill -9 -f "run.py .*--ps-username $FP_USER( |\$)" 2>/dev/null
        pkill -9 -f "foul-play/bin/python -c from multiprocessing" 2>/dev/null
        date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/$TAG.USERNAME_DEADLOCK"
        kill "$SEAT_PID" 2>/dev/null
        sleep 2
        kill -9 "$SEAT_PID" 2>/dev/null
        write_runner_json false
        exit 3
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

    # NO_PROGRESS abort (designer B §5.4 / BI-3). `set -u` is on, hence the
    # ${LAST_CRASH_COMPLETED:--1} guard. Mirrors the nametaken abort below,
    # including the sentinel-file convention; exit 4 is its own code so the
    # wave and the grader can tell an ops failure from a VOID.
    if [ "$COMPLETED" -eq "${LAST_CRASH_COMPLETED:--1}" ]; then
        NO_PROGRESS=$((NO_PROGRESS + 1))
    else
        NO_PROGRESS=1
    fi
    LAST_CRASH_COMPLETED="$COMPLETED"
    if [ "$NO_PROGRESS" -ge "$NO_PROGRESS_RELAUNCHES" ]; then
        log "NO_PROGRESS: $NO_PROGRESS relaunches with zero new Winner: lines at fp-completed $COMPLETED -- aborting arm as an OPS FAILURE (not a data verdict; the SEAT is the suspect, not FP)"
        pkill -9 -P "$FP_PID" 2>/dev/null
        pkill -9 -f "run.py .*--ps-username $FP_USER( |\$)" 2>/dev/null
        pkill -9 -f "foul-play/bin/python -c from multiprocessing" 2>/dev/null
        date -u +%Y-%m-%dT%H:%M:%SZ > "$NO_PROGRESS_MARKER"
        kill "$SEAT_PID" 2>/dev/null
        sleep 2
        kill -9 "$SEAT_PID" 2>/dev/null
        write_runner_json false
        exit 4
    fi

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
