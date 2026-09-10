#!/usr/bin/env bash
# DESIGN-B SEAM SMOKE (configs/engine_a1_priveval_smoke.yaml): one lane, seed 66,
# k=8, killed at the 12M crossing rung, rung eval n=12,000. NOT a pre-reg; nothing
# it produces is comparable to a banked number. Its reads: (i) loss/priv_eval_value
# falls and priv_eval/explained_variance rises in history.csv (the head reads a live
# 408-block); (ii) INERTNESS end-to-end — the actor and critic of the rung
# checkpoint must be BITWISE identical to runs/engine_a1b_s66's rung checkpoint
# (same seed, same config otherwise, same engine build): the head touches
# nothing the policy sees, so the two lanes must have collected identical data
# and taken identical updates. Any difference is a leak. Waits for the A-1
# re-run lanes to stop (box width). Detached, resume-safe, rate-readable.
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t engine_pe_smoke); cat "$0" > "$FROZEN"; QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pkmn-engine-port/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
S=66; RUN=engine_pe_s$S; CONFIG=configs/engine_a1_priveval_smoke.yaml; OUT=results/engine_a1
LOG=logs/engine_pe_smoke.log; mkdir -p logs "$OUT"
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
rung() { ls "runs/$RUN"/ckpt_0120*.pt 2>/dev/null | head -1; }
lane_pid() { pgrep -f "bin/python -m rl.train.*$RUN" | head -1; }

# Re-gated 2026-09-10 21:45Z: the A-1 re-run lanes are DONE (A1-PASS on the fixed
# build), and the box now carries seven eval jobs — the three margin-gate arms are
# the night's read and a training lane must not contend with them. Wait for THEM.
say "waiting for the margin-gate arms to finish (results/search_s3_100m/s3g*_s112.final.json)"
while :; do
  n=0
  for j in s3g02_s112 s3g05_s112 s3g10_s112; do [ -f "results/search_s3_100m/$j.final.json" ] && n=$((n+1)); done
  [ "$n" -ge 3 ] && break
  sleep 300
done
say "margin arms done"
sleep 120
git status --porcelain | grep -q . && { say "DIRTY TREE — refusing (rule 3)"; exit 1; }
curl -s -o /dev/null --max-time 3 http://localhost:8000/ || { say "server down — refusing"; exit 1; }
say "git HEAD: $(git rev-parse HEAD)"
if [ -z "$(rung)" ]; then
  if [ -d "runs/$RUN" ]; then say "RESUME $RUN"; nohup "$PY" -m rl.train --resume "runs/$RUN" > "runs/$RUN.nohup.log" 2>&1 &
  else say "START $RUN"; nohup "$PY" -m rl.train --config "$CONFIG" --seed "$S" --run-name "$RUN" > "runs/$RUN.nohup.log" 2>&1 & fi
  while [ -z "$(rung)" ]; do
    pid=$(lane_pid); [ -z "$pid" ] && { say "NO PROCESS — re-run to resume"; exit 1; }
    c0=$(ps -p "$pid" -o time=); sleep 15; c1=$(ps -p "$pid" -o time=)
    [ "$c0" = "$c1" ] && say "ALIVE AT ZERO CPU over 15 s (pid $pid) — stall shape"
    sleep 600
  done
  say "rung reached — holding 120 s for the 48th in-loop eval"; sleep 120
  pid=$(lane_pid); [ -n "$pid" ] && kill "$pid"; sleep 30
fi
[ -f "$OUT/pe_rung12m_s$S.json" ] || "$PY" scripts/eval_checkpoint.py "$(rung)" --episodes 12000 --opponent heuristics --out "$OUT/pe_rung12m_s$S.json" >> "$LOG" 2>&1
say "rung eval: $("$PY" -c "import json; d=json.load(open('$OUT/pe_rung12m_s$S.json')); print(d['eval/win_rate'], d['episodes'])")"
"$PY" - <<PYEOF 2>&1 | tee -a "$LOG"
import glob, torch, csv
pe = sorted(glob.glob("runs/$RUN/ckpt_0120*.pt"))[0]
ref = sorted(glob.glob("runs/engine_a1b_s$S/ckpt_0120*.pt"))
print("pe ckpt:", pe, "| ref:", ref[:1])
a = torch.load(pe, map_location="cpu", weights_only=False)
print("pe step", a["step"], "| agent keys", sorted(a["agent"].keys()))
if ref:
    b = torch.load(ref[0], map_location="cpu", weights_only=False)
    print("ref step", b["step"])
    for part in ("actor", "critic", "aux_head"):
        sa, sb = a["agent"][part], b["agent"][part]
        same = sa.keys() == sb.keys() and all(torch.equal(sa[k], sb[k]) for k in sa)
        maxd = max((float((sa[k].float() - sb[k].float()).abs().max()) for k in sa if k in sb), default=float("nan"))
        print(f"INERTNESS {part}: bitwise_identical={same} max_abs_diff={maxd:.3e}")
rows = list(csv.DictReader(open("runs/$RUN/history.csv")))
keys = [k for k in rows[0] if k.startswith("loss/priv_eval") or k.startswith("priv_eval/")]
for k in keys:
    vals = [float(r[k]) for r in rows if r.get(k) not in (None, "", "nan")]
    print(f"{k}: first {vals[0]:.4f}  at 1/4 {vals[len(vals)//4]:.4f}  last {vals[-1]:.4f}  (n={len(vals)})")
PYEOF
say "PE SMOKE DONE"
