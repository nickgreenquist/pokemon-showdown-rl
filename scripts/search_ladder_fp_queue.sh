#!/usr/bin/env bash
# Budget ladder, off-FOUL-PLAY legs. Waits for the peak delta, fills the pre-reg,
# runs STAGE 1 (BLM) ALONE, then applies the pre-decided branch before funding
# STAGE 2. Detached, resume-safe, rate-readable. Frozen-copy re-exec.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t search_ladder_fp); cat "$0" > "$FROZEN"; QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
PREREG=configs/eval/search_budget_ladder_offfp.yaml
OUT=results/search_budget_ladder_offfp
LOG=logs/search_ladder_fp.log; mkdir -p logs "$OUT"
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

run_arm() {  # $1 arm, $2 tag, $3 stall polls
  [ -f "$OUT/$2.json" ] && { say "$1 SKIP (json exists)"; return 0; }
  say "$1 starting (n=1000)"
  PREREG="$PREREG" ARM="$1" TAG="$2" OUT="$OUT" STALL_POLLS="$3" \
    MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 bash scripts/ch3_r4_fp_runner.sh >> "logs/$2.driver.log" 2>&1
  say "$1 finished rc=$?"
}

say "waiting for the peak arms (s3g10 + p15 + p20 on s112)"
while :; do
  n=0; for j in s3g10_s112 p15_s112 p20_s112; do [ -f "results/search_s3_100m/$j.final.json" ] && n=$((n+1)); done
  [ "$n" -ge 3 ] && break; sleep 300
done
D=$("$PY" -c "
import json
c={0.10:'s3g10_s112',0.15:'p15_s112',0.20:'p20_s112'}
print(max(c, key=lambda d: json.load(open(f'results/search_s3_100m/{c[d]}.final.json'))['eval/win_rate']))")
say "peak delta = $D"
"$PY" - "$D" <<'PYEOF'
import sys, pathlib
d = float(sys.argv[1]); p = pathlib.Path("configs/eval/search_budget_ladder_offfp.yaml")
s = p.read_text()
old = "margin_delta: null          # [FILL BEFORE LAUNCH] the peak from S3 P15/P20"
assert s.count(old) == 1
s = s.replace(old, f"margin_delta: {d}          # [FILLED at launch] the peak measured on dose M (S3 s112)")
for arm in ("BLM", "BLL", "BLX"):
    i = s.index(f"  {arm}: {{kind: search_seat")
    j = s.index("}", i)
    s = s[:j] + f", margin_delta: {d}" + s[j:]
p.write_text(s)
PYEOF
git add "$PREREG" && git commit -q -m "Budget ladder off-FP: FILL margin_delta = $D, before the legs run

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Rz5TMHg1uVyb6emrgq7rXn" && say "delta filled and committed"

say "STAGE 1: BLM alone (the transfer probe)"
run_arm BLM blm 60
R=$("$PY" -c "
import json; d=json.load(open('$OUT/blm.json'))
f=json.load(open('$OUT/blm.runner.json')).get('crash_forfeits',0)
n=d['battles_finished']-f; print(f\"{(d['our_wins']-f)/n:.5f} {n}\")" 2>/dev/null || echo "NA 0")
RATE=$(echo "$R" | cut -d' ' -f1); NEFF=$(echo "$R" | cut -d' ' -f2)
say "BLM = $RATE on n_eff=$NEFF  (banked greedy 0.50167 n=3000; UNGATED search@M 0.39600 n=1000)"
BR=$("$PY" -c "
r=float('$RATE')
print('TRANSFERS' if r>=0.47 else ('PARTIAL' if r>=0.42 else 'SH-FACING'))" 2>/dev/null || echo "NA")
say "PRE-DECIDED BRANCH: $BR"
case "$BR" in
  TRANSFERS) say "stage 2 RUNS in full (BLL then BLX)"; run_arm BLL bll 60; run_arm BLX blx 90 ;;
  PARTIAL)   say "stage 2 runs dose L ONLY; XL is not funded on a partial transfer"; run_arm BLL bll 60 ;;
  SH-FACING) say "STAGE 2 DOES NOT RUN. The gate is SH-facing (CH3 R2 repeats); the live question is the OPPONENT MODEL, not compute. 13.4 h NOT spent." ;;
  *)         say "branch could not be evaluated — BLM json missing or malformed; stage 2 HELD" ;;
esac
say "FP LEGS DONE"
