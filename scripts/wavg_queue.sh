#!/bin/bash
# IDEAS 2.12 -- the weight-averaging read (configs/eval/wavg_r5.yaml). Hacking
# run, detached and resume-safe; each arm skips if its JSON exists; control first.
#
#   nohup bash scripts/wavg_queue.sh > logs/wavg_r5/queue.nohup 2>&1 &
#
# Rate check (CLAUDE.md rule 4): FP@20 arms run ~1.2-1.6 s/battle; a 3000-battle
# arm is ~60-80 min. Read the driver log's battle count against the clock.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t wavg_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/wavg_r5.yaml
OUT=results/wavg_r5
LOG=logs/wavg_r5
mkdir -p "$LOG" "$OUT"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no server on :8000"; exit 1; }
pgrep -f "bin/python -m rl.train" > /dev/null 2>&1 && { log "REFUSING: rl.train alive"; exit 1; }
pgrep -f "ch3_fp_h2h.py" > /dev/null 2>&1 && { log "REFUSING: another FP seat is alive"; exit 1; }
git status --porcelain | grep -q . && { log "REFUSING: dirty tree (rule 3)"; exit 1; }
"$PY" - <<'PYEOF2' || { log "USERNAME PREFIX CHECK FAILED"; exit 2; }
import glob, re, sys
names = set()
for f in glob.glob("configs/eval/*.yaml"):
    for m in re.finditer(r"(?:seat_username|fp_username|seat|fp|bot):\s*([a-z0-9]+)\b", open(f).read()):
        names.add(m.group(1))
bad = [(a, b) for a in sorted(names) for b in sorted(names) if a != b and b.startswith(a)]
if bad:
    print("PREFIX COLLISIONS:", bad[:10]); sys.exit(1)
print(f"{len(names)} usernames, prefix-free")
PYEOF2
log "guards ok (sha $(git rev-parse --short HEAD))"

fparm() {
  local arm="$1" tag="$2" extra="${3:-}"
  case "$extra" in *SMOKE_BATTLES=*) tag="smoke_$tag";; esac
  if [ -f "$OUT/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching"
  env PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=60 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 $extra \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$OUT/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/$tag.json'))
print('win', d.get('our_win_rate'), 'n', d.get('battles_finished'), 'ties', d.get('ties'))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log"
  fi
  sleep 30
}

if [ ! -f "$OUT/smoke_wsm.json" ]; then
  log "SMOKE: the averaged checkpoints through the FP seat path, throwaway pair"
  fparm WSM wsm "SMOKE_BATTLES=2"
  [ -f "$OUT/smoke_wsm.json" ] || { log "SMOKE FAILED -- not starting phase R"; exit 1; }
fi
log "PHASE R: control first (E3WA, the finals), then E3AF (the averages), n=3000 each"
fparm E3WA e3wa
fparm E3AF e3af
"$PY" - <<'PYEOF3' | tee "$OUT/READOUT.txt"
import json, math
a = json.load(open("results/wavg_r5/e3wa.json")); b = json.load(open("results/wavg_r5/e3af.json"))
pa, na = a["our_win_rate"], a["battles_finished"]; pb, nb = b["our_win_rate"], b["battles_finished"]
d = pb - pa; se = math.sqrt(pa*(1-pa)/na + pb*(1-pb)/nb)
print(f"E3WA (finals, control)  {pa:.4f} n={na} ties={a.get('ties')}")
print(f"E3AF (avg_last5)        {pb:.4f} n={nb} ties={b.get('ties')}")
print(f"delta E3AF-E3WA         {d:+.4f}  se_diff {se:.4f}  z {d/se:+.2f}")
if d >= 0.025 and d >= 2*se: v = "CREDIT -> the R6 object rule takes avg_last5 members"
elif d <= -0.025 and -d >= 2*se: v = "CLOSED -> a measured cost; the finals stay the members"
else: v = "UNRESOLVED -> the row stays open; nothing changes"
print("verdict:", v)
print("disclosures: FP@20 equivalence weakly powered; point estimate flatters us; binomial se governs (one committee per arm); never differenced against the banked 0.5987")
PYEOF3
log "QUEUE DONE"
