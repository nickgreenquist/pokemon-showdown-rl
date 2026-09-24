#!/bin/bash
# R7 SMOKES, orchestrated -- the fleet pre-reg's R0 gates (2) and (1) (scripts/derive_r7_fleet.py's header):
#
#   bash -c 'nohup bash scripts/r7_smokes.sh lr <base> > logs/r7_smokes/lr.nohup 2>&1 &'   (from bash: zsh's BG_NICE niced it)
#       the nine 2M LR smokes, ONE LR AT A TIME as a triple under one watchdog (the searched arm, the control and the
#       beta-0 comparator at the same lr, under the same contention); their histories and the donor's; the seven vs-SH
#       evals (the donor's final + each searched/control smoke's final, n 3000, sequential -- usernames derive from
#       each checkpoint's seed); then derive_r7_fleet.py --read-lr, whose verdict JSON the fleet stage requires.
#   bash -c 'nohup bash scripts/r7_smokes.sh shakedown > logs/r7_smokes/shakedown.nohup 2>&1 &'
#       the two warm-start shakedown smokes together under one watchdog; the SEARCHED one is killed once its first
#       checkpoint.pt exists (the only file a resume loads; the async loop writes it every SAVE_LATEST_EVERY_UPDATES
#       updates) -- its process group, TERM then KILL, the watchdog's own shape -- and must be RESUMED by the watchdog
#       (a warm-started lane's resume re-installs the donor's theta0: new code); then scripts/r7_smoke_check.py on
#       both (verdict JSONs in results/r7_smokes/).
#   DRY=1 bash scripts/r7_smokes.sh <stage> [base]     prints the plan, launches nothing.
#
# The configs are the ones scripts/derive_r7_fleet.py wrote into configs/ (--stage lr-smokes / --stage fleet), run
# from a CLEAN tree (monster_fleet.sh refuses a dirty one). Resumable: a lane whose DONE line is in the watchdog log
# is skipped, an eval whose JSON exists is skipped; a run dir that exists without DONE is refused, never clobbered.
# Refuses beside a Foul Play arm (its budget is wall-clock). Re-execs from a FROZEN copy (never edit a bash script an
# instance is executing).
set -u
if [ "${SMOKES_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t r7_smokes)
  cat "$0" > "$FROZEN"
  SMOKES_FROZEN=1 REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)" exec bash "$FROZEN" "$@"
fi
cd "$REPO_DIR" || exit 1
STAGE="${1:-}"; BASE="${2:-}"
PYB=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python     # analysis: derive, checker, histories
PYE=/opt/anaconda3/envs/pkmn-engine-port/bin/python        # the lanes' and the evals' interpreter
WD=runs/train_watchdog.log
OUT=results/r7_smokes; LOGD=logs/r7_smokes; mkdir -p "$OUT" "$LOGD" results/r7_lr
LOG="$LOGD/smokes.log"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
die() { log "STOP: $*"; exit 1; }
wait_for() {  # <desc> <timeout s> <cmd...>: poll every 30 s until cmd succeeds
  local desc="$1" t="$2"; shift 2
  local t0; t0=$(date +%s)
  until "$@"; do
    sleep 30
    if [ $(( $(date +%s) - t0 )) -ge "$t" ]; then log "TIMEOUT waiting for $desc (${t}s)"; return 1; fi
  done
}
lane_pid() { pgrep -f "bin/python -m rl.train.*(--run-name $1\$|--resume runs/$1\$)" 2>/dev/null | head -1; }
cfg_int() { "$PYB" -c "import yaml,sys; c=yaml.safe_load(open(sys.argv[1])); print(int(eval('c' + sys.argv[2])))" "$1" "$2"; }
is_done() { grep -q "$1 DONE at step" "$WD" 2>/dev/null; }
all_done() { local d; for d in "$@"; do is_done "$d" || return 1; done; }

launch() {  # <cfg>...: every lane with WATCHDOG=0, then ONE watchdog over the lanes that came up. Sets LAUNCHED.
  # A lane that fails stops the launching, but whatever DID come up still gets its watchdog (never left unwatched).
  local upf cfg seed total failed=0; upf="$(mktemp -t r7_smokes_up)"; LAUNCHED=()
  for cfg in "$@"; do
    seed="$(cfg_int "$cfg" "['seed']")"; total="$(cfg_int "$cfg" "['total_steps']")"
    log "launching $cfg ($total steps, seed $seed)"
    if ! ALLOW_ANNEAL_OVER_HORIZON=1 WATCHDOG=0 FLEET_WIDTH=$# UP_FILE="$upf" PY="$PYE" \
         bash scripts/monster_fleet.sh "$cfg" "$total" "$seed" >> "$LOGD/launcher.log" 2>&1; then
      log "LAUNCHER FAILED for $cfg -- $LOGD/launcher.log:"; tail -6 "$LOGD/launcher.log" | tee -a "$LOG"; failed=1; break
    fi
  done
  while read -r d; do [ -n "$d" ] && LAUNCHED+=("$d"); done < "$upf"
  if [ "${#LAUNCHED[@]}" -gt 0 ]; then
    PY="$PYE" nohup bash scripts/train_watchdog.sh "${LAUNCHED[@]}" > /dev/null 2>&1 &
    local wdpid=$!
    nohup caffeinate -i -s -w "$wdpid" > /dev/null 2>&1 &
    log "ONE watchdog pid $wdpid over ${LAUNCHED[*]}"
  fi
  [ "$failed" = 0 ] && [ "${#LAUNCHED[@]}" -eq "$#" ] || { log "only ${#LAUNCHED[@]}/$# lanes came up"; return 1; }
}
wait_done() {  # <timeout s> <dir>...: until every DONE line; a RETIRED lane stops the stage. The watchdog owns liveness
  # (CPU-delta, resumes); this timeout is a backstop scaled to the steps (the T-op lane's rate is unmeasured).
  local limit="$1"; shift
  local t0 d; t0=$(date +%s)
  until all_done "$@"; do
    for d in "$@"; do
      if grep -q "ALERT $d .*RETIRING" "$WD" 2>/dev/null; then die "LANE RETIRED by the watchdog: $(grep "ALERT $d" "$WD" | tail -1)"; fi
    done
    sleep 30
    [ $(( $(date +%s) - t0 )) -ge "$limit" ] && die "TIMEOUT waiting for DONE on $* (${limit}s)"
  done
  for d in "$@"; do log "$(grep "$d DONE at step" "$WD" | tail -1)"; done
}
dir_of() { echo "runs/$(basename "$1" .yaml)_s$(cfg_int "$1" "['seed']")"; }
limit_for() { local t; t="$(cfg_int "$1" "['total_steps']")"; echo $(( t / 150 > 7200 ? t / 150 : 7200 )); }  # >= 150 steps/s
fresh_or_done() {  # <dir>: 0 = launch it, 1 = already DONE (skip); refuses a dir that exists without DONE
  if is_done "$1"; then return 1; fi
  [ -e "$1" ] && die "$1 exists without a DONE line -- check it by hand; never clobbered"
  return 0
}

if [ "${DRY:-0}" != "1" ]; then
  pgrep -f "foul-play.*/bin/python run.py" > /dev/null && die "a Foul Play arm is alive (never a training lane beside an FP arm)"
  # zsh's BG_NICE (on by default) runs `cmd &` at nice +5 and every lane and eval would inherit it: refuse loudly here
  # rather than lane by lane (the two-core launcher's own QoS check) or silently (the vs-SH evals). Launch from bash.
  [ "$(ps -o nice= -p $$ | tr -d ' ')" = "0" ] || die "this runner is niced ($(ps -o nice= -p $$ | tr -d ' ')) -- zsh's BG_NICE? launch it from bash: bash -c 'nohup bash scripts/r7_smokes.sh ... &'"
fi
log "=== R7 SMOKES: stage '$STAGE' base '${BASE:-n/a}' (DRY=${DRY:-0}); tree $(git rev-parse --short HEAD) ==="

case "$STAGE" in
lr)
  [ -n "$BASE" ] || die "usage: $0 lr <base>"
  LRS=$("$PYB" -c "import importlib.util as u; s=u.spec_from_file_location('d','scripts/derive_r7_fleet.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(' '.join(f'{x:g}' for x in m.LR_CANDIDATES))")
  for lr in $LRS; do
    cfgs=(); dirs=()
    for arm in searched control beta0; do
      c="configs/r7_lr_smoke_${arm}_${lr}.yaml"
      [ -f "$c" ] || die "missing $c -- run: $PYB scripts/derive_r7_fleet.py --base $BASE --stage lr-smokes (and commit)"
      cfgs+=("$c"); dirs+=("$(dir_of "$c")")
    done
    if [ "${DRY:-0}" = "1" ]; then log "DRY: lr $lr -> ${dirs[*]} (one triple, one watchdog)"; continue; fi
    need=()
    for i in 0 1 2; do fresh_or_done "${dirs[$i]}" && need+=("${cfgs[$i]}"); done
    if [ "${#need[@]}" -gt 0 ]; then launch "${need[@]}" || die "lr $lr: launch failed"; fi
    wait_done "$(limit_for "${cfgs[0]}")" "${dirs[@]}"
  done
  [ "${DRY:-0}" = "1" ] && { log "DRY: then histories, the vs-SH evals (--stage lr-evals) and --read-lr"; exit 0; }
  for lr in $LRS; do
    for arm in searched control beta0; do
      d="$(dir_of "configs/r7_lr_smoke_${arm}_${lr}.yaml")"
      "$PYB" -c "import sys; sys.path.insert(0,'scripts'); from merge_history import history_path; print(history_path(sys.argv[1]))" "$d" | tee -a "$LOG"
    done
  done
  # The LR rule's entropy reference is the donor f1's own history (the R6 readout extracts it; this is idempotent).
  DONOR=$("$PYB" -c "import importlib.util as u,sys; s=u.spec_from_file_location('d','scripts/derive_r7_fleet.py'); m=u.module_from_spec(s); s.loader.exec_module(m); t=m.donor_trio(sys.argv[1]); print('runs/' + m.DONOR_DIR[t].format(m.DONOR_SEEDS[t][0]))" "$BASE")
  "$PYB" -c "import sys; sys.path.insert(0,'scripts'); from merge_history import history_path; print(history_path(sys.argv[1]))" "$DONOR" | tee -a "$LOG"
  pgrep -f "node pokemon-showdown" > /dev/null || die "no Showdown server for the vs-SH evals"
  "$PYB" scripts/derive_r7_fleet.py --base "$BASE" --stage lr-evals > "$LOGD/lr_evals.txt" || die "lr-evals failed"
  grep -v '^#' "$LOGD/lr_evals.txt" | while read -r line; do
    out="${line##*--out }"
    if [ -f "$out" ]; then log "eval SKIP ($out exists)"; continue; fi
    log "eval: $line"
    bash -c "$line" >> "$LOGD/lr_evals.log" 2>&1 < /dev/null || log "EVAL FAILED: $line (see $LOGD/lr_evals.log)"
    [ -f "$out" ] && log "  -> $("$PYB" -c "import json,sys; print(json.load(open(sys.argv[1]))['eval/win_rate'])" "$out")"
  done
  "$PYB" scripts/derive_r7_fleet.py --base "$BASE" --read-lr 2>&1 | tee -a "$LOG"
  log "LR STAGE DONE -- the verdict: results/r7_lr/read_lr.json"
  ;;
shakedown)
  cs=configs/r7_fleet_smoke_searched.yaml; cc=configs/r7_fleet_smoke_control.yaml
  [ -f "$cs" ] && [ -f "$cc" ] || die "missing $cs / $cc -- run derive_r7_fleet.py --stage fleet (and commit)"
  ds="$(dir_of "$cs")"; dc="$(dir_of "$cc")"
  if [ "${DRY:-0}" = "1" ]; then log "DRY: $ds (killed once checkpoint.pt exists, then resumed) + $dc, one watchdog; then r7_smoke_check.py on both"; exit 0; fi
  need=(); fresh_or_done "$ds" && need+=("$cs"); fresh_or_done "$dc" && need+=("$cc")
  if [ "${#need[@]}" -gt 0 ]; then launch "${need[@]}" || die "shakedown: launch failed"; fi
  if ! grep -q "RESUMED $ds ->" "$WD" 2>/dev/null && ! is_done "$ds"; then
    has_latest() { [ -f "$ds/checkpoint.pt" ]; }
    wait_for "the first checkpoint.pt in $ds" "$(limit_for "$cs")" has_latest || die "no checkpoint.pt in $ds"
    sleep 20   # never kill mid-write: the save is a single torch.save, done well inside 20 s
    base="$(basename "$ds")"; pid="$(lane_pid "$base")"
    [ -n "$pid" ] || die "RESUME TEST: no lane pid for $base after its checkpoint.pt -- see $ds.nohup.log"
    pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
    log "RESUME TEST: killing $base (pid $pid, pgid $pgid) at checkpoint.pt step $("$PYE" -c "import torch,sys; print(torch.load(sys.argv[1], map_location='cpu', weights_only=False)['step'])" "$ds/checkpoint.pt" 2>/dev/null)"
    kill -TERM -"$pgid" 2>/dev/null; sleep 10; kill -KILL -"$pgid" 2>/dev/null
    resumed() { grep -q "RESUMED $ds ->" "$WD"; }
    wait_for "the watchdog's RESUMED line for $ds" 1200 resumed || die "the watchdog never resumed $ds"
    log "$(grep "RESUMED $ds ->" "$WD" | tail -1)"
  fi
  wait_done "$(limit_for "$cs")" "$ds" "$dc"
  sleep 20
  v=""
  for pair in "searched|$ds|--expect-resume" "control|$dc|"; do
    IFS='|' read -r arm d flag <<<"$pair"
    "$PYB" scripts/r7_smoke_check.py "$d" --arm "$arm" $flag --json-out "$OUT/shakedown_$arm.json" 2>&1 | tee -a "$LOG"
    v+="$arm=$(grep -o '"verdict": "[A-Z]*"' "$OUT/shakedown_$arm.json" 2>/dev/null | head -1 | cut -d'"' -f4) "
  done
  log "SHAKEDOWN DONE: $v(the fleet launches only if both PASS)"
  ;;
*)
  die "usage: $0 lr <base> | shakedown"
  ;;
esac
