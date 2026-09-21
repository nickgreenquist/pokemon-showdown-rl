#!/bin/bash
# R6 prep plan items 3 and 4, chained behind the wavg_r5 read so no two FP-timed
# blocks and no CPU-heavy rollout job ever overlap an FP arm:
#   WAIT   logs/wavg_r5/queue.log prints QUEUE DONE
#   GAP    scripts/action_gap.py (CLEANUP L9 FIXED) -- the prize, by rollout; skips if its json exists
#   EXIT   configs/eval/exit_gate_r5.yaml: smoke -> XGR (control) -> XTG9 -> readout
# Detached, resume-safe, rate-readable (CLAUDE.md rule 4).
#
#   nohup bash scripts/exit_gate_queue.sh > logs/exit_gate_r5/queue.nohup 2>&1 &
#
# RELAUNCH AFTER A DEATH (folded from HANDOFF 2026-09-21): an FP arm that dies mid-run
# poisons its username pair for hours (scripts/ch3_r4_fp_runner.sh's incident record), so
# BEFORE relaunching give that arm a fresh, prefix-free `seat_username` / `fp_username` in
# configs/eval/exit_gate_r5.yaml (this queue's inventory check names a collision), keep
# logs/exit_gate_r5/GO in place, and run the same nohup line with `>>`. Phases whose JSON
# exists are skipped; the readout is only valid if XGR and XTG9 both finished in ONE
# session with no relaunch on a poisoned pair -- say so in the readout if they did not.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t exit_gate_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PREREG=configs/eval/exit_gate_r5.yaml
OUT=results/exit_gate_r5
LOG=logs/exit_gate_r5
mkdir -p "$LOG" "$OUT" results/outcome_variance
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

log "WAIT: holding until logs/wavg_r5/queue.log prints QUEUE DONE"
until grep -q "QUEUE DONE" logs/wavg_r5/queue.log 2>/dev/null; do sleep 120; done
sleep 60
# GAP is the §27 rollout instrument: no FP seat, but it opens ONE live battle per
# position on the local server and needs the box awake; caffeinate follows it.
lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1 || { log "REFUSING: no server on :8000"; exit 1; }
pgrep -f "bin/python -m rl.train" > /dev/null 2>&1 && { log "REFUSING: rl.train alive"; exit 1; }
pgrep -f "ch3_fp_h2h.py" > /dev/null 2>&1 && { log "REFUSING: another FP seat is alive"; exit 1; }
grep -q "FIXED 2026-09-19 (docs/CLEANUP.md L9)" scripts/action_gap.py || { log "REFUSING: action_gap.py is not the fixed version"; exit 1; }
log "guards ok (sha $(git rev-parse --short HEAD); dirty=$(git status --porcelain | wc -l | tr -d ' '))"

# ---------------------------------------------------------------- GAP
# Skip only a json the FIXED script wrote (it carries top1_is_played_frac). The
# pre-L9 runs left a json and two rows files here; a bare existence check
# skipped the fixed run on 2026-09-19 20:38Z, and the rows file would have been
# RESUMED from invalid rows. Those artifacts now live in invalid_pre_L9/.
if [ -f results/outcome_variance/action_gap.json ] && grep -q top1_is_played_frac results/outcome_variance/action_gap.json; then
  log "GAP SKIP (a fixed-version action_gap.json exists)"
else
  log "GAP: scripts/action_gap.py --battles 150 --rollouts 24 (resume-safe on its rows file)"
  "$PY" scripts/action_gap.py --battles 150 --rollouts 24 >> "$LOG/action_gap.log" 2>&1
  if [ -f results/outcome_variance/action_gap.json ]; then
    log "GAP DONE: $("$PY" -c "
import json; d=json.load(open('results/outcome_variance/action_gap.json'))
print('positions', d['positions'], 'ceiling', round(d['ceiling_win_rate'],4), 'frac_top1_worse', round(d['frac_top1_worse'],3), 'top1_is_played', d.get('top1_is_played_frac'))")"
  else
    log "GAP NO JSON -- see $LOG/action_gap.log"
  fi
fi
sleep 30

# ---------------------------------------------------------------- HOLD
# The EXIT block is ~26 h of wall clock and a killed FP arm poisons its
# username pair for hours, so it never starts on its own: it needs the GO
# sentinel, which the maintainer touches when the box will stay up.
#   touch logs/exit_gate_r5/GO && nohup bash scripts/exit_gate_queue.sh > logs/exit_gate_r5/queue.nohup 2>&1 &
if [ ! -f "$LOG/GO" ]; then
  log "EXIT block HELD: touch $LOG/GO and re-run this queue when the box will stay up ~26 h (GAP re-runs resume-safe if it was cut)"
  exit 0
fi

# ---------------------------------------------------------------- EXIT
fparm() {
  local arm="$1" tag="$2" extra="${3:-}"
  case "$extra" in *SMOKE_BATTLES=*) tag="smoke_$tag";; esac
  if [ -f "$OUT/$tag.json" ]; then log "$arm SKIP (json exists)"; return; fi
  log "$arm launching"
  env PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" STALL_POLLS=120 \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 $extra \
    bash scripts/ch3_r4_fp_runner.sh >> "$LOG/$tag.driver.log" 2>&1
  if [ -f "$OUT/$tag.json" ]; then
    log "$arm DONE: $("$PY" -c "
import json; d = json.load(open('$OUT/$tag.json'))
def g(k, nd=4):
    v = d.get(k)
    return round(v, nd) if isinstance(v, (int, float)) else v
print('win', g('our_win_rate'), 'n', d.get('battles_finished'), 'ties', d.get('ties'), 'ms', g('search/ms_mean', 1),
      'KL', g('tree/kl_pi_prior'), 'pi_top1', g('tree/pi_top1', 3), 'moved', g('tree/argmax_moved', 3), 'overrode', g('search/overrode', 3))")"
  else
    log "$arm NO JSON -- see $LOG/$tag.driver.log"
  fi
  sleep 30
}
if [ ! -f "$OUT/smoke_xsm.json" ]; then
  log "SMOKE: the 900-iteration gumbel tree through the FP seat, throwaway pair"
  fparm XSM xsm "SMOKE_BATTLES=2"
  [ -f "$OUT/smoke_xsm.json" ] || { log "SMOKE FAILED -- not starting phase R"; exit 1; }
fi
log "PHASE R: control first (XGR, greedy committee), then XTG9 (gumbel, iters 900), n=3200 each"
fparm XGR xgr
fparm XTG9 xtg9
"$PY" - <<'PYEOF3' | tee "$OUT/READOUT.txt"
import json, math
a = json.load(open("results/exit_gate_r5/xgr.json")); b = json.load(open("results/exit_gate_r5/xtg9.json"))
pa, na = a["our_win_rate"], a["battles_finished"]; pb, nb = b["our_win_rate"], b["battles_finished"]
d = pb - pa; se = math.sqrt(pa*(1-pa)/na + pb*(1-pb)/nb)
print(f"XGR  (greedy committee, control)  {pa:.4f} n={na} ties={a.get('ties')}")
print(f"XTG9 (gumbel tree, iters 900)     {pb:.4f} n={nb} ties={b.get('ties')}  ms/decision {b.get('search/ms_mean')}  KL {b.get('tree/kl_pi_prior')}  pi_top1 {b.get('tree/pi_top1')}  argmax_moved {b.get('tree/argmax_moved')}  overrode {b.get('search/overrode')}")
print(f"delta XTG9-XGR                    {d:+.4f}  se_diff {se:.4f}  z {d/se:+.2f}")
if d >= 0.025 and d >= 2*se: v = "CLEARS -> the tree at 900 is a policy-improvement operator here; 4.9 gets R7's first trio (pre-reg next)"
else: v = "DOES NOT CLEAR -> no measurable expert at the strongest affordable budget; 4.9 closed on this object for R7 (a measured bound, rule 6)"
print("verdict:", v)
print("disclosures: FP@20 equivalence weakly powered; point estimate flatters us; binomial se governs (one arm per cell); never differenced against a banked number")
PYEOF3
log "QUEUE DONE"
