#!/usr/bin/env bash
# BUDGET LADDER queue (configs/eval/search_budget_ladder.yaml). Waits for S3's
# P15/P20 to bracket the peak, FILLS margin_delta in the pre-reg with the best
# measured delta, commits that fill, then launches R-L and R-XL. Detached,
# resume-safe, rate-readable. Frozen-copy re-exec (never edit a running script).
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t search_ladder_queue); cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
LOG=logs/search_ladder.log; mkdir -p logs results/search_budget_ladder
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

say "waiting for the peak arms (s3g10 + p15 + p20 on s112)"
while :; do
  n=0
  for j in s3g10_s112 p15_s112 p20_s112; do [ -f "results/search_s3_100m/$j.final.json" ] && n=$((n+1)); done
  [ "$n" -ge 3 ] && break
  sleep 300
done
BEST=$("$PY" - <<'PYEOF'
import json
cand = {0.10: "s3g10_s112", 0.15: "p15_s112", 0.20: "p20_s112"}
best, rate = None, -1.0
for d, j in sorted(cand.items()):
    r = json.load(open(f"results/search_s3_100m/{j}.final.json"))["eval/win_rate"]
    print(f"# delta {d}: {r:.5f}")
    if r > rate: best, rate = d, r
print(best)
PYEOF
)
D=$(echo "$BEST" | tail -1)
say "peak delta = $D"; echo "$BEST" | grep '^#' | tee -a "$LOG"
"$PY" - "$D" <<'PYEOF'
import sys, pathlib
d = float(sys.argv[1]); p = pathlib.Path("configs/eval/search_budget_ladder.yaml")
s = p.read_text()
old = "margin_delta: null          # [FILL BEFORE LAUNCH] the peak from S3 P15/P20"
new = (f"margin_delta: {d}          # [FILLED at launch] the peak measured on dose M by\n"
       f"                           # S3's S3G10/P15/P20 arms on s112; held FIXED across rungs.")
assert s.count(old) == 1, "fill site missing"
p.write_text(s.replace(old, new))
PYEOF
for a in RL RXL; do
  "$PY" - "$a" "$D" <<'PYEOF'
import sys, pathlib, yaml
arm, d = sys.argv[1], float(sys.argv[2]); p = pathlib.Path("configs/eval/search_budget_ladder.yaml")
s = p.read_text().splitlines()
for i, l in enumerate(s):
    if l.strip().startswith(f"{arm}:"):
        assert "margin_delta" not in l, "already filled"
        s[i] = l.rstrip()[:-1] + f", margin_delta: {d}}}"
pathlib.Path(p).write_text("\n".join(s) + "\n")
PYEOF
done
git add configs/eval/search_budget_ladder.yaml
git commit -q -m "Budget ladder: FILL margin_delta = $D (the peak measured on dose M), before the rungs run

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Rz5TMHg1uVyb6emrgq7rXn" && say "delta filled and committed"
git status --porcelain | grep -q . && { say "DIRTY TREE after the fill — refusing to launch (rule 3)"; exit 1; }

for j in rl_s112 rxl_s112; do
  [ -f "results/search_budget_ladder/$j.final.json" ] && { say "$j SKIP (final exists)"; continue; }
  nohup "$PY" scripts/ch3_eval.py --prereg configs/eval/search_budget_ladder.yaml --job "$j" >> "logs/search_s3/$j.log" 2>&1 &
  say "$j launched pid $!"
  sleep 60
done
say "LADDER LAUNCHED — rate-read with: ls results/search_budget_ladder/*.chunk*.json"
